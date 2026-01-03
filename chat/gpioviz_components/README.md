# gpioviz Component System

This directory contains design documents and examples for adding a component abstraction layer to gpioviz.

## Purpose

Enable gpioviz to:
1. Configure hardware components (sensors, displays, motors) through a visual UI
2. Test components before generating code
3. Export validated hardware configurations as YAML
4. Serve as a hardware prototyping tool for Raspberry Pi projects

## Files in This Package

- **ARCHITECTURE.md** - Overall system design, component types, file structure
- **IMPLEMENTATION.md** - Step-by-step guide for adding features to gpioviz
- **component_definitions.json** - Example component metadata (DHT22, ST7789, steppers, etc.)
- **example_dht22_component.py** - Reference implementation of a producer component

## Quick Start for Claude CLI

1. Read `ARCHITECTURE.md` to understand the system design
2. Read `IMPLEMENTATION.md` for step-by-step implementation guidance
3. Start with Phase 1 (MVP): DHT22 component only
4. Test with real hardware before expanding

## Key Concepts

### Component Types

**Producers** generate data:
- DHT22 → temperature, humidity
- Button → pressed/released state
- BME280 → temp, humidity, pressure

**Consumers** accept commands:
- ST7789 Display → render text/images
- SG90 Servo → move to angle
- LED → on/off, brightness

### Tool Mode Workflow

1. Click component tool (sticky cursor)
2. Click GPIO pin to assign
3. Component auto-configures (SPI pins, etc.)
4. Info panel shows pinout diagram
5. Test component with live controls
6. Export YAML configuration

### YAML Export

Generated configs can be used by:
- Custom Python scripts
- Claude CLI for app development
- Other automation tools

Example:
```yaml
hardware:
  temp_sensor:
    type: DHT22
    gpio: 4
    tested: true
    outputs: [temperature, humidity]
```

## Integration with Existing gpioviz

**No breaking changes** - component system is additive:

- Existing pin control (HIGH/LOW/Flash) remains unchanged
- Component mode is opt-in via tool selector
- Can use both modes simultaneously (some pins as components, others as raw GPIO)

## Implementation Priority

**Phase 1 (MVP):**
1. Component definitions JSON
2. Base component classes
3. DHT22 implementation
4. Tool selector UI
5. Test endpoint

**Phase 2 (Expand):**
6. More component types (Button, LED, ST7789)
7. Info panel with pinouts
8. YAML export

**Phase 3 (Polish):**
9. Config import
10. Documentation links
11. Auto-detection for I2C/SPI

## Testing

With real hardware:
1. Connect DHT22 to GPIO 4
2. Start gpioviz
3. Click DHT22 tool
4. Click GPIO 4 pin
5. Click "Test Component"
6. Verify temperature reading appears
7. Export YAML

## Example Use Case: Bus Clock

The bus_clock project demonstrates the value of this system:

**Before gpioviz components:**
- Manual wiring of 4 steppers + 2 switches = 18 GPIO pins
- Easy to wire wrong
- No validation before coding
- Hard to document configuration

**With gpioviz components:**
1. Assign 4× 28BYJ-48 steppers via UI
2. Assign 2× button switches
3. Test each component individually
4. Export validated YAML
5. Use YAML as source of truth for bus_clock.py

## Related Projects

- **bus_clock** - Standalone K2 bus arrival display (uses 4 steppers)
- **gpioviz** - Main visualization tool (add components to this)

## Questions?

When implementing, refer to:
- ARCHITECTURE.md for "what and why"
- IMPLEMENTATION.md for "how to build it"
- component_definitions.json for component specs
- example_dht22_component.py for code patterns

## Success Criteria

Component system is working when:

1. ✅ Can assign DHT22 to GPIO via UI tool
2. ✅ Can test and see live temperature
3. ✅ Info panel shows DHT22 pinout
4. ✅ Can export YAML configuration
5. ✅ YAML includes tested hardware
6. ✅ Existing flash mode still works
7. ✅ Can import YAML to restore config

## License

Same as gpioviz (add component system under same license)
