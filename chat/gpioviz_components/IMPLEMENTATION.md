# Implementation Guide for Component System

## For Claude CLI: How to Implement This

This guide helps Claude CLI understand how to add the component system to the existing gpioviz codebase.

## Step 1: Add Component Definitions

Create `components/definitions.json` with component metadata:

**Priority components to implement first:**
1. DHT22 (simple, single GPIO pin)
2. Button (validates input mode)
3. LED (validates output mode)
4. ST7789 (complex, multi-pin with SPI)
5. 28BYJ-48 Stepper (multi-pin, for bus clock)

**File location:** `gpioviz/components/definitions.json`

## Step 2: Create Base Component Classes

**File:** `gpioviz/components/base.py`

Key features:
- Abstract base classes for Producer and Consumer
- GPIO setup/cleanup methods
- Test framework hooks
- Metadata accessors

Reference the ARCHITECTURE.md for class structure.

## Step 3: Implement DHT22 Component

**File:** `gpioviz/components/producers/dht22.py`

This is the proof-of-concept. Should:
- Inherit from ProducerComponent
- Use Adafruit_DHT library
- Implement read() method returning {temperature, humidity}
- Implement test() method that verifies sensor responds
- Handle errors gracefully (sensor not connected, checksum fail)

**Example usage:**
```python
sensor = DHT22Component(name="Living Room", gpio_pins={"data": 4})
data = sensor.read()
# Returns: {"temperature": 22.1, "humidity": 45.2}
```

## Step 4: Update Flask Backend

**File:** `gpioviz/app.py`

Add new routes:

```python
@app.route('/api/component/assign', methods=['POST'])
def assign_component():
    """Assign a component to GPIO pin(s)"""
    # Parse request: component type, pins, config
    # Validate pin availability
    # Create component instance
    # Store in active components dict
    # Return success/failure

@app.route('/api/component/<int:pin>/test', methods=['GET'])
def test_component(pin):
    """Test component assigned to pin"""
    # Look up component
    # Call component.test()
    # Return test results (success + data)

@app.route('/api/config/export', methods=['GET'])
def export_config():
    """Export current config as YAML"""
    # Build YAML from active components
    # Include hardware verification status
    # Return YAML string
```

## Step 5: Add UI Components

### Tool Selector

**File:** `gpioviz/static/js/components.js`

```javascript
class ComponentToolSelector {
    constructor() {
        this.currentTool = 'select';
        this.setupEventListeners();
    }
    
    selectTool(toolName) {
        this.currentTool = toolName;
        document.body.style.cursor = this.getCursorForTool(toolName);
        this.updateStatusBar();
    }
    
    handlePinClick(pinNumber) {
        if (this.currentTool === 'select') {
            // Existing pin selection behavior
        } else {
            // Assign component to pin
            this.assignComponent(this.currentTool, pinNumber);
        }
    }
    
    async assignComponent(componentType, pinNumber) {
        // Check if pin available
        // Call /api/component/assign
        // Update pin visual
        // Show info panel with component details
    }
}
```

### Info Panel Enhancement

**File:** `gpioviz/static/js/info-panel.js`

Extend existing info panel (currently shows warnings) to display:
- Component pinout diagrams
- Test controls
- Documentation links
- Live sensor readings

```javascript
class ComponentInfoPanel {
    showPinout(componentType) {
        // Fetch component definition
        // Render SVG pinout diagram
        // Show wiring instructions
    }
    
    showTestControls(componentType, pinNumber) {
        // Add "Test Component" button
        // Show live readings (if producer)
        // Show control sliders (if consumer)
    }
    
    async testComponent(pinNumber) {
        const result = await fetch(`/api/component/${pinNumber}/test`);
        // Display test results
        // Show success/error state
    }
}
```

## Step 6: Update HTML Template

**File:** `gpioviz/templates/index.html`

Add above the existing GPIO grid:

```html
<!-- Tool Selector -->
<div id="tool-selector" class="toolbar">
    <button class="tool active" data-tool="select">👆 Select</button>
    <button class="tool" data-tool="dht22">🌡️ DHT22</button>
    <button class="tool" data-tool="button">🔘 Button</button>
    <button class="tool" data-tool="led">💡 LED</button>
    <!-- More tools... -->
</div>

<!-- Status Bar -->
<div id="status-bar">
    <span id="current-tool">Tool: Select</span>
    <span id="mode">Mode: Navigate</span>
</div>

<!-- Enhanced Info Panel (extend existing) -->
<div id="info-panel">
    <div id="pinout-display"></div>
    <div id="test-controls"></div>
    <div id="documentation-links"></div>
</div>
```

## Step 7: Add CSS Styling

**File:** `gpioviz/static/css/components.css`

```css
.toolbar {
    display: flex;
    gap: 8px;
    padding: 10px;
    background: #f5f5f5;
    border-bottom: 1px solid #ddd;
}

.tool {
    padding: 8px 16px;
    border: 1px solid #ccc;
    background: white;
    cursor: pointer;
}

.tool.active {
    background: #4CAF50;
    color: white;
}

#status-bar {
    padding: 5px 10px;
    background: #eee;
    font-size: 14px;
    display: flex;
    gap: 20px;
}

/* Pin states when component assigned */
.pin.has-component {
    border: 2px solid #2196F3;
}

.pin.has-component.producer {
    background: #E3F2FD;
}

.pin.has-component.consumer {
    background: #FFF3E0;
}
```

## Step 8: Implement YAML Export

**File:** `gpioviz/config/exporter.py`

```python
import yaml
from datetime import datetime

class ConfigExporter:
    def __init__(self, components):
        self.components = components
    
    def to_yaml(self):
        config = {
            'hardware': {
                'timestamp': datetime.now().isoformat(),
                'verified': True,
                'components': {}
            }
        }
        
        for name, component in self.components.items():
            config['hardware']['components'][name] = {
                'type': component.__class__.__name__,
                'pins': component.gpio_pins,
                'tested': component.tested,
            }
            
            # Add outputs for producers
            if hasattr(component, 'outputs'):
                config['hardware']['components'][name]['outputs'] = \
                    list(component.outputs.keys())
        
        return yaml.dump(config, default_flow_style=False)
```

## Testing Strategy

### Unit Tests

**File:** `gpioviz/tests/test_components.py`

```python
import unittest
from components.producers.dht22 import DHT22Component

class TestDHT22(unittest.TestCase):
    def test_initialization(self):
        sensor = DHT22Component("test", {"data": 4})
        self.assertEqual(sensor.gpio_pins["data"], 4)
    
    def test_read_mock(self):
        # Mock GPIO for testing without hardware
        sensor = DHT22Component("test", {"data": 4})
        # Test read() with mocked data
```

### Integration Tests

Test with actual hardware:
1. Connect DHT22 to GPIO 4
2. Load gpioviz
3. Click DHT22 tool
4. Click GPIO 4
5. Verify sensor reads successfully
6. Export YAML
7. Verify YAML structure

## Migration from Current Code

The existing gpioviz code has:
- Flask app in `app.py`
- Pin control endpoints
- Flash functionality
- Visual pin grid

**Integration points:**

1. **Pin state tracking**: Extend existing pin state dict to include component info
2. **Flash mode**: Keep existing flash logic, add component test as alternative
3. **Info panel**: Enhance existing warnings panel
4. **Pin visual**: Add component indicator to existing pin circles

**No breaking changes needed** - component system is additive.

## Rollout Plan

### Phase 1 (MVP)
- Component definitions.json
- Base component classes
- DHT22 implementation
- Basic tool selector UI
- Test endpoint

### Phase 2 (Polish)
- Info panel with pinouts
- More component types
- YAML export
- Documentation links

### Phase 3 (Advanced)
- Config import
- Pipeline builder
- Auto-detection
- Component library

## Questions for Implementation

When implementing, consider:

1. **State persistence**: Should component assignments survive page reload?
   - **Suggestion**: Store in server-side session or simple JSON file

2. **Concurrent access**: Multiple components on same GPIO?
   - **Suggestion**: Prevent with validation - one component per GPIO

3. **Component cleanup**: What happens when unassigning?
   - **Suggestion**: Call component.cleanup(), reset GPIO to safe state

4. **Error handling**: Sensor not responding during test?
   - **Suggestion**: Show clear error in info panel, don't crash

5. **Component versioning**: Track library versions?
   - **Suggestion**: Include in YAML export for reproducibility

## Success Criteria

Implementation is complete when:

1. ✅ Can assign DHT22 to GPIO pin via UI
2. ✅ Can test DHT22 and see live temperature reading
3. ✅ Info panel shows DHT22 pinout diagram
4. ✅ Can export config to YAML
5. ✅ YAML includes tested hardware configuration
6. ✅ Existing flash functionality still works
7. ✅ All tests pass

## Getting Started

**Recommended order:**

1. Read ARCHITECTURE.md
2. Create component definitions JSON (start with DHT22 only)
3. Implement base.py classes
4. Implement DHT22 producer
5. Add backend endpoints
6. Add tool selector UI
7. Test with real hardware
8. Iterate and expand

**First PR should include:**
- Component infrastructure
- DHT22 working end-to-end
- Basic documentation
- Tests

Then subsequent PRs can add more components incrementally.
