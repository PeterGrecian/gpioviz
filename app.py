from flask import Flask, render_template, jsonify, request
import RPi.GPIO as GPIO
import threading
import time
import sys
import subprocess
from datetime import datetime
import yaml
import os
import argparse

# Check if running as root
def is_root():
    """Check if the process is running as root"""
    return os.geteuid() == 0

# Determine if we need sudo prefix for commands
SUDO_PREFIX = [] if is_root() else ['sudo']

app = Flask(__name__)
app.logger.disabled = True  # Disable Flask's request logging

# GPIO setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Pin state storage
pin_states = {}
flashing_pins = {}
flash_threads = {}

# Clock state
clock_running = False
clock_thread = None

# Clock digit patterns - using a subset of pins to display digits 0-9
# Each digit uses a pattern of pins to create a recognizable shape
# Using simplified 7-segment style mapping
DIGIT_PATTERNS = {
    0: [11, 12, 19, 21, 23, 24, 26],  # Pattern for 0
    1: [12, 19],                       # Pattern for 1
    2: [11, 12, 8, 23, 24],           # Pattern for 2
    3: [11, 12, 8, 21, 26],           # Pattern for 3
    4: [19, 8, 12, 21],               # Pattern for 4
    5: [11, 23, 8, 21, 26],           # Pattern for 5
    6: [11, 23, 24, 26, 21, 8],       # Pattern for 6
    7: [11, 12, 19],                  # Pattern for 7
    8: [11, 12, 19, 21, 23, 24, 26, 8], # Pattern for 8
    9: [11, 12, 19, 21, 8, 26]        # Pattern for 9
}

# Pin positions for each digit in HH:MM display
# Digit 1 (Hour tens), Digit 2 (Hour ones), Digit 3 (Minute tens), Digit 4 (Minute ones)
DIGIT_POSITIONS = {
    0: {  # Hour tens - using leftmost pins
        'offset_pins': [3, 5, 7, 11, 13, 15, 16, 8]
    },
    1: {  # Hour ones - using left-center pins
        'offset_pins': [10, 12, 18, 22, 29, 31, 32, 36]
    },
    2: {  # Minute tens - using right-center pins
        'offset_pins': [19, 21, 23, 24, 26, 35, 38, 40]
    },
    3: {  # Minute ones - using rightmost pins
        'offset_pins': [33, 37, 15, 22, 32, 35, 38, 40]
    }
}

def display_digit_on_pins(digit, position):
    """Light up pins to display a digit at a specific position"""
    pattern = DIGIT_PATTERNS.get(digit, [])
    pin_map = DIGIT_POSITIONS.get(position, {}).get('offset_pins', [])

    # Use first N pins from the position's pin map, where N is the pattern length
    active_pins = []
    for i, segment_active in enumerate(range(len(pattern))):
        if i < len(pin_map) and segment_active < len(pattern):
            # Map pattern index to actual pin
            if segment_active < len(pin_map):
                active_pins.append(pin_map[i])

    return active_pins

def clock_display_thread():
    """Thread function to display clock on GPIO LEDs"""
    global clock_running, pin_changes

    while clock_running:
        # Get current time
        now = datetime.now()
        hour = now.hour
        minute = now.minute

        # Extract digits
        h_tens = hour // 10
        h_ones = hour % 10
        m_tens = minute // 10
        m_ones = minute % 10

        # Turn off all GPIO pins first
        all_clock_pins = []
        for pos_data in DIGIT_POSITIONS.values():
            all_clock_pins.extend(pos_data['offset_pins'])

        for pin in GPIO_PINS.keys():
            if pin in all_clock_pins:
                ensure_pin_setup(pin, 'OUT')
                GPIO.output(pin, GPIO.LOW)
                pin_states[pin]['state'] = 0

        # Light up pins for each digit using a simple binary representation
        # This is simpler and more reliable than complex patterns
        digits = [h_tens, h_ones, m_tens, m_ones]

        for digit_pos, digit_value in enumerate(digits):
            pin_list = DIGIT_POSITIONS.get(digit_pos, {}).get('offset_pins', [])
            # Use binary representation: each digit uses 4 LEDs to show binary value
            for bit_pos in range(4):
                if bit_pos < len(pin_list):
                    pin = pin_list[bit_pos]
                    if pin in GPIO_PINS:
                        # Check if this bit is set in the digit value
                        bit_value = (digit_value >> bit_pos) & 1
                        ensure_pin_setup(pin, 'OUT')
                        GPIO.output(pin, GPIO.HIGH if bit_value else GPIO.LOW)
                        pin_states[pin]['state'] = bit_value
                        if bit_value:
                            pin_changes += 1

        # Update every second
        time.sleep(1)

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

# Pin alternative functions mapping
PIN_ALT_FUNCTIONS = {
    3: ['I2C1 SDA', 'GPIO'],
    5: ['I2C1 SCL', 'GPIO'],
    7: ['GPCLK0', 'GPIO'],
    8: ['UART TX', 'GPIO'],
    10: ['UART RX', 'GPIO'],
    12: ['PWM0', 'PCM CLK', 'GPIO'],
    19: ['SPI0 MOSI', 'GPIO'],
    21: ['SPI0 MISO', 'GPIO'],
    23: ['SPI0 SCLK', 'GPIO'],
    24: ['SPI0 CE0', 'GPIO'],
    26: ['SPI0 CE1', 'GPIO'],
    32: ['PWM0', 'GPIO'],
    33: ['PWM1', 'GPIO'],
    35: ['PWM1', 'SPI1 MISO', 'GPIO'],
    38: ['SPI1 MISO', 'PCM DIN', 'GPIO'],
    40: ['SPI1 SCLK', 'PCM DOUT', 'GPIO'],
}

# Initialize pin states (setup pins lazily on first use)
for pin in GPIO_PINS.keys():
    alt_funcs = PIN_ALT_FUNCTIONS.get(pin, ['GPIO'])
    pin_states[pin] = {
        'mode': 'OUT',
        'state': 0,
        'flashing': False,
        'flash_speed': 500,
        'peripheral_mode': 'GPIO',  # Current peripheral function
        'available_modes': alt_funcs
    }

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

@app.route('/api/pin/<int:pin>/peripheral', methods=['POST'])
def toggle_peripheral(pin):
    """Toggle pin peripheral mode"""
    global pin_changes

    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    available_modes = pin_states[pin].get('available_modes', ['GPIO'])
    current_mode = pin_states[pin].get('peripheral_mode', 'GPIO')

    # Find current index and move to next mode
    try:
        current_index = available_modes.index(current_mode)
        next_index = (current_index + 1) % len(available_modes)
        new_mode = available_modes[next_index]
    except ValueError:
        new_mode = available_modes[0]

    # Attempt to enable/disable peripheral at runtime using dtparam
    # Use sudo if not running as root
    try:
        if new_mode == 'GPIO':
            # Disable all peripherals for this pin (return to GPIO mode)
            # Note: This is simplified - actual implementation would need to know
            # which specific peripheral to disable
            pass
        elif 'I2C' in new_mode:
            # Enable I2C at runtime
            subprocess.run(SUDO_PREFIX + ['dtparam', 'i2c_arm=on'], check=True, capture_output=True)
            subprocess.run(SUDO_PREFIX + ['modprobe', 'i2c-dev'], check=False, capture_output=True)
            subprocess.run(SUDO_PREFIX + ['modprobe', 'i2c-bcm2835'], check=False, capture_output=True)
            print(f"Enabled I2C for pin {pin}")
        elif 'SPI' in new_mode:
            # Enable SPI at runtime
            subprocess.run(SUDO_PREFIX + ['dtparam', 'spi=on'], check=True, capture_output=True)
            print(f"Enabled SPI for pin {pin}")
        elif 'UART' in new_mode:
            # UART enabling is more complex, may require reboot
            pass
        # PWM and PCM can be controlled via software without dtparam
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.decode().strip() if e.stderr else str(e)
        print(f"Warning: Could not enable {new_mode} for pin {pin}: {stderr_msg}")
        # Continue anyway - show the mode even if activation failed
    except Exception as e:
        print(f"Warning: Could not enable {new_mode} for pin {pin}: {e}")
        # Continue anyway - show the mode even if activation failed

    pin_states[pin]['peripheral_mode'] = new_mode
    pin_changes += 1

    return jsonify({
        'success': True,
        'pin': pin,
        'peripheral_mode': new_mode,
        'available_modes': available_modes
    })

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

@app.route('/api/config/save', methods=['POST'])
def api_save_config():
    """API endpoint to save configuration"""
    data = request.json or {}
    filename = data.get('filename', 'config.yaml')

    try:
        filepath = save_configuration(filename)
        return jsonify({'success': True, 'filepath': filepath})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/load', methods=['POST'])
def api_load_config():
    """API endpoint to load configuration"""
    data = request.json or {}
    filename = data.get('filename', 'config.yaml')

    try:
        success = load_configuration(filename)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/config/list', methods=['GET'])
def api_list_configs():
    """API endpoint to list available configurations"""
    config_dir = 'configs'
    if not os.path.exists(config_dir):
        return jsonify({'configs': []})

    configs = [f for f in os.listdir(config_dir) if f.endswith('.yaml') or f.endswith('.yml')]
    return jsonify({'configs': configs})

@app.route('/api/clock/toggle', methods=['POST'])
def toggle_clock():
    """Toggle clock display on/off"""
    global clock_running, clock_thread, pin_changes

    if clock_running:
        # Stop the clock
        clock_running = False
        if clock_thread:
            clock_thread.join()
            clock_thread = None

        # Turn off all clock pins
        all_clock_pins = []
        for pos_data in DIGIT_POSITIONS.values():
            all_clock_pins.extend(pos_data['offset_pins'])

        for pin in GPIO_PINS.keys():
            if pin in all_clock_pins:
                # Stop any flashing first
                if pin_states[pin].get('flashing', False):
                    flashing_pins[pin] = False
                    if pin in flash_threads:
                        flash_threads[pin].join()
                    pin_states[pin]['flashing'] = False

                ensure_pin_setup(pin, 'OUT')
                GPIO.output(pin, GPIO.LOW)
                pin_states[pin]['state'] = 0

        return jsonify({'success': True, 'clock_running': False})
    else:
        # Start the clock
        # First stop any flashing on pins we'll use
        all_clock_pins = []
        for pos_data in DIGIT_POSITIONS.values():
            all_clock_pins.extend(pos_data['offset_pins'])

        for pin in all_clock_pins:
            if pin in GPIO_PINS and pin_states[pin].get('flashing', False):
                flashing_pins[pin] = False
                if pin in flash_threads:
                    flash_threads[pin].join()
                pin_states[pin]['flashing'] = False

        clock_running = True
        clock_thread = threading.Thread(target=clock_display_thread)
        clock_thread.daemon = True
        clock_thread.start()
        pin_changes += 1

        return jsonify({'success': True, 'clock_running': True})

def save_configuration(filename='config.yaml'):
    """Save current pin configuration to YAML file"""
    config = {
        'pins': {}
    }

    for pin, state in pin_states.items():
        config['pins'][pin] = {
            'mode': state['mode'],
            'state': state['state'],
            'peripheral_mode': state.get('peripheral_mode', 'GPIO'),
            'flash_speed': state.get('flash_speed', 500)
        }

    config_dir = 'configs'
    os.makedirs(config_dir, exist_ok=True)
    filepath = os.path.join(config_dir, filename)

    with open(filepath, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    print(f"Configuration saved to {filepath}")
    return filepath

def load_configuration(filename='config.yaml'):
    """Load pin configuration from YAML file"""
    config_dir = 'configs'
    filepath = os.path.join(config_dir, filename)

    if not os.path.exists(filepath):
        print(f"Configuration file not found: {filepath}")
        return False

    with open(filepath, 'r') as f:
        config = yaml.safe_load(f)

    if 'pins' not in config:
        print("Invalid configuration file format")
        return False

    # Apply configuration
    for pin, settings in config['pins'].items():
        pin = int(pin)
        if pin in GPIO_PINS:
            # Set mode
            mode = settings.get('mode', 'OUT')
            if mode == 'OUT':
                ensure_pin_setup(pin, 'OUT')
                GPIO.output(pin, GPIO.HIGH if settings.get('state', 0) else GPIO.LOW)
            else:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            # Update state
            pin_states[pin]['mode'] = mode
            pin_states[pin]['state'] = settings.get('state', 0)
            pin_states[pin]['peripheral_mode'] = settings.get('peripheral_mode', 'GPIO')
            pin_states[pin]['flash_speed'] = settings.get('flash_speed', 500)

    print(f"Configuration loaded from {filepath}")
    return True

def cleanup():
    """Cleanup GPIO on exit"""
    global clock_running

    # Stop clock if running
    if clock_running:
        clock_running = False
        if clock_thread:
            clock_thread.join()

    # Stop all flashing
    for pin in flashing_pins.keys():
        flashing_pins[pin] = False

    GPIO.cleanup()

if __name__ == '__main__':
    import logging

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Raspberry Pi GPIO Visualizer')
    parser.add_argument('--load-config', type=str, help='Load configuration from YAML file on startup')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the web server on (default: 5000)')
    args = parser.parse_args()

    # Disable werkzeug logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    # Load configuration if specified
    if args.load_config:
        print(f"Loading configuration: {args.load_config}")
        load_configuration(args.load_config)

    try:
        print("\n" + "="*70)
        print("  Raspberry Pi GPIO Visualizer")
        print(f"  http://0.0.0.0:{args.port}")
        if args.load_config:
            print(f"  Loaded config: {args.load_config}")
        print("="*70 + "\n")
        sys.stderr.write("\n")  # Add newline before status starts
        sys.stderr.flush()
        update_status_line()  # Show "ready" message
        app.run(host='0.0.0.0', port=args.port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        cleanup()
