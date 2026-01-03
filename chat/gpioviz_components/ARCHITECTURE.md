# gpioviz Component System Architecture

## Overview

This document describes the component abstraction layer being added to gpioviz to support configuring and testing hardware components (sensors, displays, motors, etc.) through a visual interface.

## Goals

1. **Visual Component Assignment**: Use tool/cursor mode to assign components to GPIO pins
2. **Hardware Validation**: Test components before generating configuration
3. **Config Export**: Generate YAML files for use with other tools (Claude CLI, custom apps)
4. **Plugin Architecture**: Support both producer (sensors) and consumer (displays, motors) components
5. **Documentation Integration**: Show pinouts, datasheets, and wiring diagrams in UI

## Core Concepts

### Component Types

**Producer Components** - Generate data
- DHT22 (temperature, humidity)
- BME280 (temp, humidity, pressure)
- DS18B20 (temperature)
- Button (digital input)

**Consumer Components** - Accept data/commands
- ST7789 Display (text, graphics)
- SG90 Servo (angle)
- 28BYJ-48 Stepper (angle)
- LED (on/off)
- Buzzer (tone)

### Tool Mode Workflow

1. User clicks component tool (e.g., "DHT22")
2. Tool becomes sticky - cursor shows component type
3. User clicks available GPIO pin
4. Component is assigned with auto-configuration where possible
5. Info panel shows:
   - Physical pinout diagram
   - Wiring requirements
   - Documentation links
   - Test controls
6. User tests component
7. Save configuration to YAML

## File Structure

```
gpioviz/
├── components/
│   ├── __init__.py
│   ├── base.py                 # Base component classes
│   ├── definitions.json        # Component metadata
│   ├── producers/
│   │   ├── __init__.py
│   │   ├── dht22.py
│   │   ├── bme280.py
│   │   └── button.py
│   └── consumers/
│       ├── __init__.py
│       ├── st7789.py
│       ├── sg90.py
│       ├── stepper28byj48.py
│       └── led.py
├── config/
│   ├── __init__.py
│   ├── exporter.py            # YAML generation
│   └── validator.py           # Config validation
└── static/
    ├── js/
    │   ├── components.js      # Component tool UI
    │   └── info-panel.js      # Info panel controller
    └── css/
        └── components.css     # Component styling
```

## Component Definition Format

Each component has metadata in `components/definitions.json`:

```json
{
  "dht22": {
    "name": "DHT22 Temperature & Humidity Sensor",
    "type": "producer",
    "manufacturer": "Aosong",
    "datasheet": "https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf",
    "tutorials": ["https://learn.adafruit.com/dht"],
    "pinout": {
      "type": "inline",
      "pins": [
        {"num": 1, "name": "VCC", "type": "power", "voltage": "3.3-5V"},
        {"num": 2, "name": "DATA", "type": "gpio", "gpio": "any"},
        {"num": 3, "name": "NC", "type": "unused"},
        {"num": 4, "name": "GND", "type": "ground"}
      ]
    },
    "requirements": {
      "gpio_pins": 1,
      "pin_type": "flexible",
      "power": "3.3V or 5V"
    },
    "outputs": {
      "temperature": {"type": "float", "unit": "°C", "range": [-40, 80]},
      "humidity": {"type": "float", "unit": "%", "range": [0, 100]}
    },
    "libraries": [
      {"name": "Adafruit_DHT", "install": "pip install Adafruit_DHT --break-system-packages"}
    ]
  }
}
```

## Base Component Classes

### Producer Base Class

```python
class ProducerComponent:
    """Base class for components that generate data"""
    
    def __init__(self, name: str, gpio_pins: dict):
        self.name = name
        self.gpio_pins = gpio_pins
        self.outputs = {}  # Defined by subclass
    
    def read(self) -> dict:
        """Read current values from sensor"""
        raise NotImplementedError
    
    def test(self) -> bool:
        """Test if component is working"""
        raise NotImplementedError
    
    def get_metadata(self) -> dict:
        """Return component metadata"""
        raise NotImplementedError
```

### Consumer Base Class

```python
class ConsumerComponent:
    """Base class for components that accept commands/data"""
    
    def __init__(self, name: str, gpio_pins: dict):
        self.name = name
        self.gpio_pins = gpio_pins
        self.inputs = {}  # Defined by subclass
    
    def write(self, data: dict):
        """Write data to component"""
        raise NotImplementedError
    
    def test(self) -> bool:
        """Test if component is working"""
        raise NotImplementedError
    
    def get_metadata(self) -> dict:
        """Return component metadata"""
        raise NotImplementedError
```

## UI Changes

### Tool Selector

Add toolbar above GPIO grid:

```html
<div id="tool-selector">
  <button class="tool" data-tool="select">👆 Select</button>
  <button class="tool" data-tool="dht22">🌡️ DHT22</button>
  <button class="tool" data-tool="st7789">🖥️ ST7789</button>
  <button class="tool" data-tool="sg90">⚙️ SG90</button>
  <button class="tool" data-tool="stepper">🔄 Stepper</button>
  <button class="tool" data-tool="button">🔘 Button</button>
  <button class="tool" data-tool="led">💡 LED</button>
  <div class="tool-dropdown">
    <button>▼ More</button>
    <!-- Additional components -->
  </div>
</div>
```

### Status Line

```html
<div id="status-bar">
  <span id="current-tool">Tool: Select</span>
  <span id="mode">Mode: Navigate</span>
  <span id="config-status">Unsaved changes</span>
</div>
```

### Info Panel Enhancement

Expand existing info panel to show:
- Component pinout diagrams (SVG/Canvas)
- Wiring instructions with color coding
- Documentation links
- Live test controls
- Warning messages

## API Endpoints

### New Endpoints

```
POST /api/component/assign
- Assign component to pin(s)
- Body: {type: "dht22", pins: {data: 4}, config: {...}}

GET /api/component/<pin>/test
- Test component on pin
- Returns: {success: true, data: {...}}

POST /api/component/<pin>/configure
- Update component configuration
- Body: {polling: 2, ...}

DELETE /api/component/<pin>
- Remove component assignment

GET /api/config/export
- Export current configuration as YAML
- Returns: YAML string

POST /api/config/import
- Import YAML configuration
- Body: {yaml: "..."}
```

## YAML Export Format

Generated configuration for use with external tools:

```yaml
hardware:
  timestamp: "2026-01-03T10:30:00Z"
  verified: true
  
  components:
    temp_sensor:
      type: DHT22
      gpio: 4
      polling: 2s
      tested: true
      outputs:
        - temperature
        - humidity
    
    main_display:
      type: ST7789
      interface: SPI0
      pins:
        dc: 24
        rst: 25
        cs: 8
      tested: true
      inputs:
        - text
        - image

pipelines:
  temp_display:
    trigger: interval(2s)
    flow:
      - component: temp_sensor
        action: read
      - transform: "f'{temperature:.1f}°C'"
      - component: main_display
        action: render_text
```

## Migration Path

### Phase 1: Component Infrastructure
- Add component definitions JSON
- Create base component classes
- Implement DHT22 as proof of concept

### Phase 2: UI Enhancement
- Add tool selector
- Implement tool mode cursor
- Enhance info panel with pinout display

### Phase 3: Testing Framework
- Component testing logic
- Live sensor readings in UI
- Validation feedback

### Phase 4: Config Export
- YAML generation
- Config import/restore
- Integration with existing flash demo

## Backward Compatibility

Existing gpioviz functionality remains unchanged:
- Current pin control (HIGH/LOW/Flash) works as before
- No breaking changes to existing API
- Component mode is opt-in via tool selector

## Future Enhancements

1. **Component Library**: User-contributed component definitions
2. **Visual Wiring**: Generate Fritzing-style diagrams
3. **Auto-detection**: Scan I2C/SPI buses for connected devices
4. **Data Logging**: Record sensor data over time
5. **App Templates**: Pre-built configurations for common projects

## Example Use Cases

### Temperature Monitor
1. Click DHT22 tool
2. Click GPIO 4 to assign
3. Test sensor (see live readings)
4. Export YAML
5. Use with custom Python script or Claude CLI

### Display Test
1. Click ST7789 tool
2. Auto-assigns SPI pins, prompt for DC/RST
3. Test with pattern display
4. Save config
5. Build app using validated hardware setup

### Bus Clock
1. Assign 4x 28BYJ-48 steppers
2. Assign 2x buttons (mode switches)
3. Test each component
4. Export config
5. Generate bus_clock.py using Claude CLI
