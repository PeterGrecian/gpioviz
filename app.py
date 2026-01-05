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

# Import component system
from components import ComponentRegistry
from components.producers import DHT22Component, DHT11Component

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

# Component system
component_registry = ComponentRegistry(definitions_file='components/definitions.json')
# Register available component classes
component_registry.register_class('dht22', DHT22Component)
component_registry.register_class('dht11', DHT11Component)

# Component reading state
component_threads = {}  # pin -> thread
component_running = {}  # pin -> bool
component_data = {}     # pin -> latest data

# HAT mode clock display using left 3 columns for tens, right 3 columns for ones
# Creates digit patterns in 4x3 grids to display seconds

# HAT layout left 3 columns (C1, C2, C3):
# Row 0: [11, 12, 19]  GPIO: [17, 18, 10]
# Row 1: [ 8, 10, 18]  GPIO: [14, 15, 24]
# Row 2: [16, 15, 27]  GPIO: [23, 22, --]  (27 is reserved ID_SD)
# Row 3: [ 3,  5,  7]  GPIO: [ 2,  3,  4]

# HAT layout right 3 columns (C5, C6, C7):
# Row 0: [23, 24, 26]  GPIO: [11,  8,  7]
# Row 1: [29, 31, 36]  GPIO: [ 5,  6, 16]
# Row 2: [32, 38, 35]  GPIO: [12, 20, 19]
# Row 3: [40, 33, 37]  GPIO: [21, 13, 26]

# Digit patterns for ONES digit (right 3 columns) - using GPIO numbers
# Grid layout:  Left(L) Mid(M) Right(R)
#   Row 0 (T):   11     8      7
#   Row 1 (U):    5     6     16
#   Row 2 (L):   12    20     19
#   Row 3 (B):   21    13     26

ONES_PATTERNS_GPIO = {
    0: [11, 8, 7,  5, 16,  12, 19,  21, 13, 26],        # All except middle row
    1: [8, 6, 20, 13],                                   # Middle column
    2: [11, 8, 7,  16,  20,  12, 21,  13, 26],          # Top, UR, middle, LL, bottom
    3: [11, 8, 7,  6, 16,  20,  19, 26,  13],           # Top, right, middle, bottom-mid
    4: [11,  5,  12, 20, 19,  6, 16, 26],               # TL, left-upper, middle, right
    5: [11, 8, 7,  5,  20,  19, 26,  13],               # Top, left-upper, middle-center, BR, bottom-mid
    6: [11, 8, 7,  5,  12, 20, 19,  21, 13, 26],        # Top, left-upper, middle, bottom (6 shape)
    7: [11, 8, 7,  16,  19, 26],                        # Top, right side
    8: [11, 8, 7,  5, 6, 16,  12, 20, 19,  21, 13, 26], # All 12 segments
    9: [11, 8, 7,  5, 6, 16,  20,  19, 26, 13]          # Top, upper-sides, middle-center, BR, bottom-mid
}

# Digit patterns for TENS digit (left 3 columns) - using GPIO numbers
# Grid layout:  Left(L) Mid(M) Right(R)
#   Row 0 (T):   17    18     10
#   Row 1 (U):   14    15     24
#   Row 2 (L):   23    22     --  (skip reserved pin 27)
#   Row 3 (B):    2     3      4

TENS_PATTERNS_GPIO = {
    0: [17, 18, 10,  14, 24,  23, 2,  3, 4],            # All except middle row
    1: [18, 15, 22, 3],                                  # Middle column
    2: [17, 18, 10,  24,  22,  23, 2,  3, 4],           # Top, UR, middle, LL, bottom
    3: [17, 18, 10,  15, 24,  22,  4,  3],              # Top, right, middle, bottom-mid
    4: [17,  14,  23, 22,  15, 24, 4],                  # TL, left-upper, middle, right
    5: [17, 18, 10,  14,  22,  4,  3],                  # Top, left-upper, middle-center, BR, bottom-mid
    6: [17, 18, 10,  14,  23, 22,  2, 3, 4],            # Top, left-upper, middle, bottom (6 shape)
    7: [17, 18, 10,  24,  4],                           # Top, right side
    8: [17, 18, 10,  14, 15, 24,  23, 22,  2, 3, 4],    # All segments (skip reserved pin 27)
    9: [17, 18, 10,  14, 15, 24,  22,  4, 3]            # Top, upper-sides, middle-center, BR, bottom-mid
}

# Mapping from GPIO number to pin number for the right 3 columns (ones)
ONES_GPIO_TO_PIN = {
    11: 23, 8: 24, 7: 26,    # Row 0
    5: 29, 6: 31, 16: 36,    # Row 1
    12: 32, 20: 38, 19: 35,  # Row 2
    21: 40, 13: 33, 26: 37   # Row 3
}

# Mapping from GPIO number to pin number for the left 3 columns (tens)
TENS_GPIO_TO_PIN = {
    17: 11, 18: 12, 10: 19,  # Row 0
    14: 8, 15: 10, 24: 18,   # Row 1
    23: 16, 22: 15,          # Row 2 (skip 27 reserved)
    2: 3, 3: 5, 4: 7         # Row 3
}

def get_all_clock_pins():
    """Get all pins used by the clock display"""
    return list(ONES_GPIO_TO_PIN.values()) + list(TENS_GPIO_TO_PIN.values())

def clock_display_thread():
    """Thread function to display seconds as two digits on GPIO LEDs"""
    global clock_running, pin_changes

    while clock_running:
        # Get current seconds (0-59)
        now = datetime.now()
        seconds = now.second

        # Extract tens and ones digits
        tens_digit = seconds // 10
        ones_digit = seconds % 10

        # Turn off all clock pins first (skip pins with components)
        all_clock_pins = get_all_clock_pins()
        for pin in all_clock_pins:
            if pin in GPIO_PINS and not pin_states[pin].get('component', False):
                ensure_pin_setup(pin, 'OUT')
                GPIO.output(pin, GPIO.LOW)
                pin_states[pin]['state'] = 0

        # Display tens digit on left 3 columns (skip pins with components)
        tens_gpio_pattern = TENS_PATTERNS_GPIO.get(tens_digit, [])
        for gpio_num in tens_gpio_pattern:
            pin = TENS_GPIO_TO_PIN.get(gpio_num)
            if pin and pin in GPIO_PINS and not pin_states[pin].get('component', False):
                ensure_pin_setup(pin, 'OUT')
                GPIO.output(pin, GPIO.HIGH)
                pin_states[pin]['state'] = 1

        # Display ones digit on right 3 columns (skip pins with components)
        ones_gpio_pattern = ONES_PATTERNS_GPIO.get(ones_digit, [])
        for gpio_num in ones_gpio_pattern:
            pin = ONES_GPIO_TO_PIN.get(gpio_num)
            if pin and pin in GPIO_PINS and not pin_states[pin].get('component', False):
                ensure_pin_setup(pin, 'OUT')
                GPIO.output(pin, GPIO.HIGH)
                pin_states[pin]['state'] = 1

        # Update every second
        time.sleep(1)

def component_read_thread(pin):
    """Thread function to periodically read component data"""
    global component_running, component_data

    print(f"[THREAD] Component thread started for pin {pin}")

    # Initial delay to let sensor stabilize after GPIO setup
    # Critical for sensors like DHT22 that need time after pin state changes
    print(f"[THREAD] Waiting 2 seconds for sensor stabilization...")
    time.sleep(2)

    print(f"[THREAD] Starting read loop for pin {pin}")
    read_count = 0
    while component_running.get(pin, False):
        component = component_registry.get_component(pin)
        if component:
            try:
                read_count += 1
                print(f"[THREAD] Read #{read_count} for pin {pin}")

                # Read data from component
                data = component.read()

                # Store data with timestamp
                component_data[pin] = {
                    'data': data,
                    'last_updated': datetime.now().strftime('%H:%M:%S'),
                    'component_type': component.__class__.__name__
                }

                print(f"[THREAD] Stored data: {data}")
            except Exception as e:
                print(f"[THREAD] ERROR reading component on pin {pin}: {e}")
                import traceback
                traceback.print_exc()

        # Update interval (could be configurable per component)
        time.sleep(2)

    print(f"[THREAD] Component thread stopped for pin {pin}")

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

# BOARD (physical pin) to BCM GPIO number mapping
# Some libraries like Adafruit_DHT only use BCM numbering
BOARD_TO_BCM = {
    3: 2, 5: 3, 7: 4, 8: 14, 10: 15, 11: 17, 12: 18, 13: 27,
    15: 22, 16: 23, 18: 24, 19: 10, 21: 9, 22: 25, 23: 11, 24: 8,
    26: 7, 29: 5, 31: 6, 32: 12, 33: 13, 35: 19, 36: 16, 37: 26,
    38: 20, 40: 21
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
        'available_modes': alt_funcs,
        'component': False  # Track if pin has a component assigned
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
    # Exclude /api/pins (polling), /api/component/*/data (component polling), and static files
    # Component polling can interfere with timing-sensitive sensors like DHT22
    if request.path == '/' or (request.path.startswith('/api/')
                                and request.path != '/api/pins'
                                and request.path != '/api/version'
                                and '/component/' not in request.path):
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
    # Skip pins with components (they manage their own state)
    for pin in GPIO_PINS.keys():
        if pin_states[pin]['mode'] == 'IN' and not pin_states[pin].get('component', False):
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
        # Skip pins with components assigned
        if pin_states[pin].get('component', False):
            continue

        # Stop flashing
        if pin_states[pin]['flashing']:
            flashing_pins[pin] = False
            if pin in flash_threads:
                flash_threads[pin].join()

        ensure_pin_setup(pin, 'OUT')
        GPIO.output(pin, GPIO.LOW)
        # Preserve important fields when resetting
        pin_states[pin]['mode'] = 'OUT'
        pin_states[pin]['state'] = 0
        pin_states[pin]['flashing'] = False

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
        all_clock_pins = get_all_clock_pins()

        for pin in all_clock_pins:
            if pin in GPIO_PINS:
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
        all_clock_pins = get_all_clock_pins()

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

@app.route('/api/component/assign', methods=['POST'])
def assign_component():
    """Assign a component to a pin"""
    global pin_changes

    data = request.json
    pin = data.get('pin')
    component_type = data.get('component_type')
    name = data.get('name', f'{component_type}_{pin}')
    gpio_pins = data.get('gpio_pins', {'data': pin})
    config = data.get('config', {})

    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    # Stop any existing component on this pin
    if pin in component_running:
        component_running[pin] = False
        if pin in component_threads:
            component_threads[pin].join()
            del component_threads[pin]

    # Stop any flashing on this pin
    if pin_states[pin].get('flashing', False):
        flashing_pins[pin] = False
        if pin in flash_threads:
            flash_threads[pin].join()
        pin_states[pin]['flashing'] = False

    # Clean up GPIO only if NOT a DHT sensor component
    # DHT sensors use Adafruit_DHT which does its own low-level GPIO access
    # and doesn't need (or want) RPi.GPIO to touch the pin
    if component_type not in ['dht22', 'dht11']:
        try:
            GPIO.cleanup(pin)
            # Re-establish GPIO mode after cleanup
            GPIO.setmode(GPIO.BOARD)
        except:
            pass  # Ignore if pin wasn't set up

    # Convert BOARD pin numbers to BCM for components that require BCM numbering
    # (e.g., Adafruit_DHT library only uses BCM)
    if component_type in ['dht22', 'dht11']:
        # Convert data pin from BOARD to BCM
        if 'data' in gpio_pins:
            board_pin = gpio_pins['data']
            bcm_pin = BOARD_TO_BCM.get(board_pin, board_pin)
            gpio_pins['data'] = bcm_pin
            print(f"{component_type.upper()}: Converting BOARD pin {board_pin} → BCM GPIO {bcm_pin}")

    # Create and assign component
    component = component_registry.create_component(component_type, name, gpio_pins, config)

    if not component:
        return jsonify({'success': False, 'error': f'Failed to create {component_type} component'}), 500

    component_registry.assign_component(pin, component)

    # Update pin state
    pin_states[pin]['mode'] = component_type.upper()
    pin_states[pin]['component'] = True
    pin_changes += 1

    # Start reading thread for producer components
    if hasattr(component, 'read'):
        component_running[pin] = True
        thread = threading.Thread(target=component_read_thread, args=(pin,))
        thread.daemon = True
        component_threads[pin] = thread
        thread.start()

    return jsonify({
        'success': True,
        'pin': pin,
        'component_type': component_type,
        'name': name
    })

@app.route('/api/component/<int:pin>/data', methods=['GET'])
def get_component_data(pin):
    """Get current component data for a pin"""
    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    component = component_registry.get_component(pin)

    if not component:
        return jsonify({'success': False, 'error': 'No component assigned to this pin'}), 404

    data = component_data.get(pin, {})

    return jsonify({
        'success': True,
        'pin': pin,
        'running': component_running.get(pin, False),
        'component_type': component.__class__.__name__,
        'data': data
    })

@app.route('/api/component/<int:pin>/remove', methods=['POST'])
def remove_component(pin):
    """Remove component from a pin"""
    global pin_changes

    if pin not in GPIO_PINS:
        return jsonify({'error': 'Invalid pin'}), 400

    # Stop reading thread if running
    if pin in component_running:
        component_running[pin] = False
        if pin in component_threads:
            component_threads[pin].join()
            del component_threads[pin]

    # Remove component from registry
    component_registry.remove_component(pin)

    # Reset pin to normal input mode
    pin_states[pin]['mode'] = 'IN'
    pin_states[pin]['component'] = False
    pin_changes += 1

    # Clean up component data
    if pin in component_data:
        del component_data[pin]

    return jsonify({'success': True, 'pin': pin, 'running': False})

def save_configuration(filename='config.yaml'):
    """Save current pin configuration to YAML file"""
    config = {
        'pins': {},
        'components': {}
    }

    for pin, state in pin_states.items():
        config['pins'][pin] = {
            'mode': state['mode'],
            'state': state['state'],
            'peripheral_mode': state.get('peripheral_mode', 'GPIO'),
            'flash_speed': state.get('flash_speed', 500)
        }

    # Save component assignments
    for pin, component in component_registry.instances.items():
        component_type = component.__class__.__name__.lower().replace('component', '')
        # For DHT22, save the BOARD pin number, not BCM
        gpio_pins = {'data': pin}  # Use BOARD pin number
        config['components'][pin] = {
            'type': component_type,
            'name': component.name,
            'gpio_pins': gpio_pins,
            'config': component.config if hasattr(component, 'config') else {}
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
    global pin_changes
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

    # Apply pin configuration
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

    # Restore component assignments
    if 'components' in config:
        for pin, comp_info in config['components'].items():
            pin = int(pin)
            if pin not in GPIO_PINS:
                continue

            component_type = comp_info.get('type')
            name = comp_info.get('name', f"{component_type}_{pin}")
            gpio_pins = comp_info.get('gpio_pins', {'data': pin})
            comp_config = comp_info.get('config', {})

            # Convert data pin from BOARD to BCM for DHT sensors
            if component_type in ['dht22', 'dht11']:
                if 'data' in gpio_pins:
                    board_pin = gpio_pins['data']
                    bcm_pin = BOARD_TO_BCM.get(board_pin, board_pin)
                    gpio_pins['data'] = bcm_pin
                    print(f"{component_type.upper()}: Converting BOARD pin {board_pin} → BCM GPIO {bcm_pin}")

            # Create and assign component
            component = component_registry.create_component(component_type, name, gpio_pins, comp_config)

            if component:
                component_registry.assign_component(pin, component)
                pin_states[pin]['mode'] = component_type.upper()
                pin_states[pin]['component'] = True
                pin_changes += 1

                # Start reading thread for producer components
                if hasattr(component, 'read'):
                    component_running[pin] = True
                    thread = threading.Thread(target=component_read_thread, args=(pin,))
                    thread.daemon = True
                    component_threads[pin] = thread
                    thread.start()
                    print(f"Started component thread for {component_type} on pin {pin}")

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

    # Stop all component reading threads
    for pin in list(component_running.keys()):
        component_running[pin] = False
    for thread in component_threads.values():
        thread.join()

    # Cleanup all components
    component_registry.cleanup_all()

    # Stop all flashing
    for pin in flashing_pins.keys():
        flashing_pins[pin] = False

    GPIO.cleanup()

def detect_hat():
    """
    Detect if a HAT is connected by checking for HAT EEPROM
    Returns tuple: (detected: bool, hat_info: str)
    """
    try:
        # Check for HAT device tree overlay
        import os
        hat_paths = [
            '/proc/device-tree/hat/product',
            '/proc/device-tree/hat/vendor',
            '/sys/firmware/devicetree/base/hat/product',
            '/sys/firmware/devicetree/base/hat/vendor'
        ]

        hat_info = {}
        for path in hat_paths:
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        content = f.read().strip('\x00').strip()
                        key = path.split('/')[-1]
                        if content:
                            hat_info[key] = content
                except:
                    pass

        if hat_info:
            info_str = ', '.join([f"{k}: {v}" for k, v in hat_info.items()])
            return True, info_str

        # Fallback: check if ID EEPROM is accessible
        # Note: This requires dtparam=i2c_vc=on in /boot/config.txt
        eeprom_path = '/sys/class/i2c-adapter/i2c-0/0-0050/eeprom'
        if os.path.exists(eeprom_path):
            return True, "ID EEPROM detected at 0x50"

        return False, "No HAT detected"
    except Exception as e:
        return False, f"Detection error: {str(e)}"

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
        # Detect HAT
        hat_detected, hat_info = detect_hat()

        # Get git commit hash
        try:
            commit_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        except Exception:
            commit_hash = 'unknown'

        print("\n" + "="*70)
        print("  Raspberry Pi GPIO Visualizer")
        print(f"  http://0.0.0.0:{args.port}")
        if hat_detected:
            print(f"  HAT: ✓ {hat_info}")
        else:
            print(f"  HAT: ✗ {hat_info}")
        print(f"  Git commit: {commit_hash}")
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
