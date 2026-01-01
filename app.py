from flask import Flask, render_template, jsonify, request
import RPi.GPIO as GPIO
import threading
import time
import sys
import subprocess
from datetime import datetime

app = Flask(__name__)
app.logger.disabled = True  # Disable Flask's request logging

# GPIO setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Pin state storage
pin_states = {}
flashing_pins = {}
flash_threads = {}

# Stats tracking
start_time = datetime.now()
request_count = 0
pin_changes = 0
spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
spinner_idx = 0
app_ready = False

# Raspberry Pi Zero 40-pin header
# Pins 1-40, some are power/ground, some are GPIO
GPIO_PINS = {
    3: 'GPIO2 (SDA)',
    5: 'GPIO3 (SCL)',
    7: 'GPIO4',
    8: 'GPIO14 (TXD)',
    10: 'GPIO15 (RXD)',
    11: 'GPIO17',
    12: 'GPIO18',
    13: 'GPIO27',
    15: 'GPIO22',
    16: 'GPIO23',
    18: 'GPIO24',
    19: 'GPIO10 (MOSI)',
    21: 'GPIO9 (MISO)',
    22: 'GPIO25',
    23: 'GPIO11 (SCLK)',
    24: 'GPIO8 (CE0)',
    26: 'GPIO7 (CE1)',
    29: 'GPIO5',
    31: 'GPIO6',
    32: 'GPIO12',
    33: 'GPIO13',
    35: 'GPIO19',
    36: 'GPIO16',
    37: 'GPIO26',
    38: 'GPIO20',
    40: 'GPIO21'
}

# Initialize pin states (setup pins lazily on first use)
for pin in GPIO_PINS.keys():
    pin_states[pin] = {'mode': 'OUT', 'state': 0, 'flashing': False, 'flash_speed': 500}

def ensure_pin_setup(pin, mode='OUT'):
    """Ensure a pin is properly set up before use"""
    try:
        if mode == 'OUT':
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
        else:
            GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    except Exception as e:
        print(f"Warning: Could not setup pin {pin}: {e}")

def update_status_line():
    """Update terminal status line with running stats"""
    global spinner_idx, request_count

    if not app_ready:
        # Show "Ready" message until first client connects
        sys.stderr.write("\r\033[K✓ Server ready - waiting for client connection...")
        sys.stderr.flush()
        return

    uptime = datetime.now() - start_time
    hours = int(uptime.total_seconds() // 3600)
    minutes = int((uptime.total_seconds() % 3600) // 60)
    seconds = int(uptime.total_seconds() % 60)

    flashing_count = sum(1 for p in pin_states.values() if p.get('flashing', False))
    active_count = sum(1 for p in pin_states.values() if p.get('state', 0) == 1 and p.get('mode', 'OUT') == 'OUT')

    spinner = spinner_chars[spinner_idx]
    spinner_idx = (spinner_idx + 1) % len(spinner_chars)

    # Clear the line and write status
    status = f"\r\033[K{spinner} Uptime: {hours:02d}:{minutes:02d}:{seconds:02d} | Requests: {request_count} | Pin changes: {pin_changes} | Active: {active_count} | Flashing: {flashing_count}"
    sys.stderr.write(status)
    sys.stderr.flush()

@app.before_request
def track_request():
    """Track each request (user actions only, not polling)"""
    global request_count
    # Only count user actions: page loads, pin changes, mode changes, etc.
    # Exclude /api/pins (polling) and static files
    if request.path == '/' or (request.path.startswith('/api/') and request.path != '/api/pins' and request.path != '/api/version'):
        request_count += 1
        update_status_line()

def flash_pin(pin, speed_ms):
    """Flash a pin at specified speed"""
    ensure_pin_setup(pin, 'OUT')
    while flashing_pins.get(pin, False):
        GPIO.output(pin, GPIO.HIGH)
        pin_states[pin]['state'] = 1
        time.sleep(speed_ms / 1000.0)
        GPIO.output(pin, GPIO.LOW)
        pin_states[pin]['state'] = 0
        time.sleep(speed_ms / 1000.0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/pins', methods=['GET'])
def get_pins():
    """Get all pin states"""
    global app_ready

    # Mark app as ready on first poll
    if not app_ready:
        app_ready = True
        update_status_line()

    # Read actual state of all INPUT pins
    for pin in GPIO_PINS.keys():
        if pin_states[pin]['mode'] == 'IN':
            pin_states[pin]['state'] = GPIO.input(pin)

    return jsonify({
        'pins': pin_states,
        'gpio_map': GPIO_PINS
    })

@app.route('/api/pin/<int:pin>/set', methods=['POST'])
def set_pin(pin):
    """Set pin state"""
    global pin_changes

    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    data = request.json
    state = data.get('state', 0)

    # Stop flashing if active
    if pin_states[pin]['flashing']:
        flashing_pins[pin] = False
        if pin in flash_threads:
            flash_threads[pin].join()
        pin_states[pin]['flashing'] = False

    ensure_pin_setup(pin, 'OUT')
    GPIO.output(pin, GPIO.HIGH if state else GPIO.LOW)
    pin_states[pin]['state'] = state
    pin_changes += 1

    return jsonify({'success': True, 'pin': pin, 'state': state})

@app.route('/api/pin/<int:pin>/mode', methods=['POST'])
def set_pin_mode(pin):
    """Set pin mode (IN/OUT)"""
    global pin_changes

    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    data = request.json
    mode = data.get('mode', 'OUT')
    pin_changes += 1

    # Stop flashing if active
    if pin_states[pin]['flashing']:
        flashing_pins[pin] = False
        if pin in flash_threads:
            flash_threads[pin].join()
        pin_states[pin]['flashing'] = False

    if mode == 'IN':
        # Set up input with pull-down resistor so it reads LOW by default
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        pin_states[pin]['state'] = GPIO.input(pin)
    else:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)
        pin_states[pin]['state'] = 0

    pin_states[pin]['mode'] = mode

    return jsonify({'success': True, 'pin': pin, 'mode': mode})

@app.route('/api/pin/<int:pin>/flash', methods=['POST'])
def toggle_flash(pin):
    """Toggle pin flashing"""
    global pin_changes

    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    data = request.json
    flash_enabled = data.get('enabled', False)
    speed = data.get('speed', 500)

    pin_states[pin]['flash_speed'] = speed
    pin_changes += 1

    if flash_enabled:
        # Start flashing
        if not pin_states[pin]['flashing']:
            ensure_pin_setup(pin, 'OUT')
            pin_states[pin]['flashing'] = True
            flashing_pins[pin] = True
            thread = threading.Thread(target=flash_pin, args=(pin, speed))
            thread.daemon = True
            flash_threads[pin] = thread
            thread.start()
    else:
        # Stop flashing
        if pin_states[pin]['flashing']:
            flashing_pins[pin] = False
            if pin in flash_threads:
                flash_threads[pin].join()
            pin_states[pin]['flashing'] = False
            ensure_pin_setup(pin, 'OUT')
            GPIO.output(pin, GPIO.LOW)
            pin_states[pin]['state'] = 0

    return jsonify({'success': True, 'pin': pin, 'flashing': pin_states[pin]['flashing']})

@app.route('/api/pin/<int:pin>/read', methods=['GET'])
def read_pin(pin):
    """Read pin state (for input mode)"""
    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    if pin_states[pin]['mode'] == 'IN':
        state = GPIO.input(pin)
        pin_states[pin]['state'] = state
        return jsonify({'success': True, 'pin': pin, 'state': state})

    return jsonify({'success': True, 'pin': pin, 'state': pin_states[pin]['state']})

@app.route('/api/reset', methods=['POST'])
def reset_all():
    """Reset all pins to LOW output"""
    for pin in GPIO_PINS.keys():
        # Stop flashing
        if pin_states[pin]['flashing']:
            flashing_pins[pin] = False
            if pin in flash_threads:
                flash_threads[pin].join()

        ensure_pin_setup(pin, 'OUT')
        GPIO.output(pin, GPIO.LOW)
        pin_states[pin] = {'mode': 'OUT', 'state': 0, 'flashing': False, 'flash_speed': 500}

    return jsonify({'success': True})

@app.route('/api/version', methods=['GET'])
def get_version():
    """Get git version information"""
    try:
        commit_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        return jsonify({'commit_hash': commit_hash})
    except Exception as e:
        return jsonify({'commit_hash': 'unknown'})

def cleanup():
    """Cleanup GPIO on exit"""
    for pin in flashing_pins.keys():
        flashing_pins[pin] = False
    GPIO.cleanup()

if __name__ == '__main__':
    import logging

    # Disable werkzeug logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    try:
        print("\n" + "="*70)
        print("  Raspberry Pi GPIO Visualizer")
        print("  http://0.0.0.0:5000")
        print("="*70 + "\n")
        sys.stderr.write("\n")  # Add newline before status starts
        sys.stderr.flush()
        update_status_line()  # Show "ready" message
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        cleanup()
