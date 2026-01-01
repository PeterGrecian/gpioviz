from flask import Flask, render_template, jsonify, request
import RPi.GPIO as GPIO
import threading
import time

app = Flask(__name__)

# GPIO setup
GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

# Pin state storage
pin_states = {}
flashing_pins = {}
flash_threads = {}

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
        GPIO.setup(pin, GPIO.OUT if mode == 'OUT' else GPIO.IN)
        if mode == 'OUT':
            GPIO.output(pin, GPIO.LOW)
    except Exception as e:
        print(f"Warning: Could not setup pin {pin}: {e}")

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
    return jsonify({
        'pins': pin_states,
        'gpio_map': GPIO_PINS
    })

@app.route('/api/pin/<int:pin>/set', methods=['POST'])
def set_pin(pin):
    """Set pin state"""
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

    return jsonify({'success': True, 'pin': pin, 'state': state})

@app.route('/api/pin/<int:pin>/mode', methods=['POST'])
def set_pin_mode(pin):
    """Set pin mode (IN/OUT)"""
    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    data = request.json
    mode = data.get('mode', 'OUT')

    # Stop flashing if active
    if pin_states[pin]['flashing']:
        flashing_pins[pin] = False
        if pin in flash_threads:
            flash_threads[pin].join()
        pin_states[pin]['flashing'] = False

    if mode == 'IN':
        GPIO.setup(pin, GPIO.IN)
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
    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    data = request.json
    flash_enabled = data.get('enabled', False)
    speed = data.get('speed', 500)

    pin_states[pin]['flash_speed'] = speed

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

def cleanup():
    """Cleanup GPIO on exit"""
    for pin in flashing_pins.keys():
        flashing_pins[pin] = False
    GPIO.cleanup()

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        cleanup()
