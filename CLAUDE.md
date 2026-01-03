# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Raspberry Pi GPIO Visualizer - A Python Flask web application for visualizing, configuring, and controlling all 40 GPIO pins on Raspberry Pi. Features real-time control, peripheral configuration, sensor components, and visual effects.

## Essential Commands

### Running the Application

Must run with sudo for GPIO access:

```bash
# Using virtual environment (recommended)
sudo venv/bin/python3 app.py

# Using system packages
sudo python3 app.py

# With configuration file
sudo venv/bin/python3 app.py --load-config configs/myconfig.yaml

# Custom port
sudo venv/bin/python3 app.py --port 8080
```

### Development Setup

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Alternative: system-wide installation
sudo apt-get install -y python3-flask python3-rpi.gpio
```

### Environment Management

```bash
# Activate virtual environment
source venv/bin/activate

# Or use the provided script
source sourceme.bash
```

## Architecture

### Core Components

**app.py** (840 lines) - Main Flask application and GPIO controller
- GPIO pin state management and control
- Threading for flashing pins and clock display
- Component registry integration
- REST API endpoints for all operations
- Runtime peripheral configuration (I2C, SPI, UART, PWM)
- Configuration save/load (YAML)

**Component System** (`components/` directory)
- **base.py**: Abstract base classes `ProducerComponent` (sensors/inputs) and `ConsumerComponent` (displays/outputs)
- **registry.py**: `ComponentRegistry` class manages component definitions, instances, and lifecycle
- **producers/**: Sensor components (e.g., `dht22.py`)
- **consumers/**: Output components (e.g., displays, motors)
- **definitions.json**: Component metadata with pinouts, requirements, and documentation links

**Frontend** (templates/index.html, static/js/app.js, static/css/style.css)
- Interactive GPIO pin visualization with two layout modes (HAT 4×8 grid, Header 2×20)
- Tool-based interaction system (Toggle, Config, Flash, Peripheral, Clock, DHT22)
- Menu bar with dropdown menus (File, Tools, Apps)
- Dynamic info panel showing context-sensitive help
- Real-time pin state polling (500ms interval)

### Key Architectural Patterns

**Pin State Management**
- All GPIO pins tracked in `pin_states` dict with mode, state, flashing status, flash_speed, peripheral_mode, and available_modes
- Lazy pin initialization via `ensure_pin_setup()` - only configured on first use
- Threaded operations for flashing and clock display to avoid blocking

**Component System**
- Producer/Consumer pattern: ProducerComponents read data (sensors), ConsumerComponents accept commands (displays, motors)
- Registry pattern: ComponentRegistry manages component lifecycle, class registration, and pin assignments
- Component threads run continuously for producer components, updating `component_data` dict with latest readings

**Tool Mode System**
- JavaScript frontend implements sticky tool cursors
- Each tool modifies pin click behavior (e.g., Flash tool toggles flashing on click)
- Dynamic info panel updates based on active tool
- Tools: Toggle Output, I/O Config, Flash, Peripheral, Clock, DHT22

**Clock Display Implementation**
- Uses HAT layout left 3 columns for tens digit, right 3 columns for ones digit
- `TENS_PATTERNS_GPIO` and `ONES_PATTERNS_GPIO` dicts map digits to GPIO numbers
- Clock thread updates every second, turns off all clock pins then lights pattern for current seconds value (0-59)

**Peripheral Configuration**
- Runtime toggling via `dtparam` commands and kernel module loading
- Each pin tracks available peripheral modes (I2C, SPI, UART, PWM, GPIO)
- `/api/pin/<pin>/peripheral` endpoint cycles through available modes
- Uses sudo prefix when not running as root

### GPIO Pin Mapping

26 controllable GPIO pins out of 40 total (others are power/ground/reserved):
- Physical pins 3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40
- Pin mapping defined in `GPIO_PINS` dict (physical pin -> BCM GPIO number + label)
- Alternative functions in `PIN_ALT_FUNCTIONS` dict (I2C, SPI, UART, PWM)

### Layout Modes

**HAT Mode**: 4 rows × 8 columns matching physical screw terminal HAT layout
- Defined in `hat-layout.json`
- Designed for 52pi EP-0129 GPIO Screw Terminal HAT

**Header Mode**: 2 columns × 20 pins showing traditional GPIO header arrangement
- Defined in `pins.json`

### Important GPIO Safety Constraints

From docs/README.md:
- **Never connect 5V signals** - all GPIO pins are 3.3V logic
- **Always use 1kΩ-10kΩ resistors** between pins to prevent damage from accidental shorts (>16mA can damage pins/SoC)
- **Pins 3 & 5 (I2C)**: Have permanent 1.8kΩ pull-up resistors, always pulled HIGH by default
- **Pins 27 & 28 (ID_SD, ID_SC)**: Reserved for HAT EEPROM during boot, not recommended for GPIO use

## API Endpoints

All API endpoints return JSON and are implemented in app.py:

- `GET /api/pins` - Get all pin states and GPIO mapping
- `POST /api/pin/<pin>/set` - Set pin state (HIGH/LOW)
- `POST /api/pin/<pin>/mode` - Set pin mode (IN/OUT)
- `POST /api/pin/<pin>/flash` - Toggle pin flashing with speed
- `GET /api/pin/<pin>/read` - Read current pin state
- `POST /api/pin/<pin>/peripheral` - Cycle through peripheral modes
- `POST /api/reset` - Reset all pins to LOW output
- `POST /api/clock/toggle` - Toggle clock display on/off
- `POST /api/component/assign` - Assign component to pin
- `GET /api/component/<pin>/data` - Get component data
- `POST /api/component/<pin>/remove` - Remove component from pin
- `POST /api/config/save` - Save configuration to YAML
- `POST /api/config/load` - Load configuration from YAML
- `GET /api/config/list` - List available configurations
- `GET /api/version` - Get git commit hash

## Configuration Files

**pins.json** - Header mode layout (2×20 pin arrangement)

**hat-layout.json** - HAT mode layout (4×8 grid arrangement)

**components/definitions.json** - Component metadata including pinouts, datasheets, tutorials, requirements, and outputs/inputs

**configs/** directory - Saved pin configurations in YAML format

## Adding New Components

1. Create component class in `components/producers/` or `components/consumers/`
2. Inherit from `ProducerComponent` or `ConsumerComponent`
3. Implement required methods: `read()` or `write()`, `test()`, `cleanup()`
4. Register class in app.py: `component_registry.register_class('type_name', ComponentClass)`
5. Add metadata to `components/definitions.json` with pinout, requirements, outputs/inputs
6. Frontend integration in static/js/app.js for UI controls

Example: DHT22 is implemented in `components/producers/dht22.py` and registered in app.py:812

## Threading Model

**Flash threads**: One daemon thread per flashing pin, controlled via `flashing_pins` dict
**Clock thread**: Single daemon thread updating clock display every second
**Component threads**: One daemon thread per producer component, reading data every 2 seconds
**Status line updater**: Updates terminal status line with running stats (uptime, requests, pin changes, active pins, flashing pins)

All threads are daemon threads and clean up on app shutdown via `cleanup()` function.

## Terminal Status Line

app.py displays a live status line on stderr showing:
- Spinner animation
- Uptime (HH:MM:SS)
- Request count (user actions, excludes polling)
- Pin changes count
- Active pins count
- Flashing pins count

Initial message: "✓ Server ready - waiting for client connection..."
Updated on first `/api/pins` poll from frontend.

## Hardware Integration

Designed for Raspberry Pi with 40-pin GPIO header (Pi Zero, Zero 2, 3, 4, 5).

Optimized for 52pi EP-0129 GPIO Screw Terminal HAT with LED indicators:
- 3.3V pins: Pink LEDs
- 5V pins: Red LEDs
- ID_SD/ID_SC pins: Turquoise/dim LEDs
- GPIO pins: Green when HIGH, dark when LOW

See docs/README.md and docs/PERIPHERALS.md for detailed hardware documentation.
