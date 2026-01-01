// GPIO Pin numbers that can be controlled
const GPIO_PINS = [3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40];

let currentPin = null;
let pinStates = {};
let flashIntervals = {};
let flashToolActive = false;
let configToolActive = false;
let globalFlashSpeed = 500;
let currentLayout = 'hat';
let originalHTML = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('pin-container');
    originalHTML = container.innerHTML; // Save original layout

    initializeEventListeners();
    loadPinStates();

    // Set default layout to Hat mode
    setLayout('hat');

    // Poll at 500ms to show real-time GPIO state
    // For outputs: shows the commanded state (what we wrote)
    // For inputs: shows actual GPIO voltage reading
    setInterval(updatePinStates, 500);
});

function initializeEventListeners() {
    // Reset all button
    document.getElementById('reset-all').addEventListener('click', resetAll);

    // Config tool button
    document.getElementById('config-tool').addEventListener('click', toggleConfigTool);

    // Flash tool button
    document.getElementById('flash-tool').addEventListener('click', toggleFlashTool);

    // Global flash speed slider
    const globalSlider = document.getElementById('global-flash-speed');
    globalSlider.addEventListener('input', (e) => {
        globalFlashSpeed = parseInt(e.target.value);
        document.getElementById('global-speed-display').textContent = globalFlashSpeed + 'ms';
    });

    // Add click listeners to GPIO pin indicators
    GPIO_PINS.forEach(pin => {
        const pinElement = document.querySelector(`.pin[data-pin="${pin}"]`);
        const indicator = pinElement?.querySelector('.pin-indicator');

        if (indicator) {
            indicator.addEventListener('click', (e) => {
                e.stopPropagation();
                if (flashToolActive) {
                    activateFlashOnPin(pin);
                } else if (configToolActive) {
                    togglePinMode(pin);
                } else {
                    togglePinState(pin);
                }
            });
        }
    });
}

async function loadPinStates() {
    try {
        const response = await fetch('/api/pins');
        const data = await response.json();
        pinStates = data.pins;
        updateUI();
    } catch (error) {
        console.error('Error loading pin states:', error);
    }
}

async function updatePinStates() {
    try {
        const response = await fetch('/api/pins');
        const data = await response.json();
        pinStates = data.pins;
        updateUI();
    } catch (error) {
        console.error('Error updating pin states:', error);
    }
}

function updateUI() {
    GPIO_PINS.forEach(pin => {
        const pinElement = document.querySelector(`.pin[data-pin="${pin}"]`);
        const indicator = pinElement.querySelector('.pin-indicator');
        const modeIndicator = pinElement.querySelector('.pin-mode-indicator');

        if (pinStates[pin]) {
            const state = pinStates[pin];

            // Update indicator shape based on mode
            if (state.mode === 'IN') {
                indicator.classList.add('input-mode');
            } else {
                indicator.classList.remove('input-mode');
            }

            // Update indicator state - show actual GPIO state
            // When flashing, the state value will toggle, so we just reflect it
            if (state.state === 1) {
                indicator.classList.add('active');
            } else {
                indicator.classList.remove('active');
            }

            // Update mode indicator
            if (modeIndicator) {
                if (state.mode === 'IN') {
                    modeIndicator.classList.remove('output-mode');
                    modeIndicator.classList.add('input-mode');
                } else {
                    modeIndicator.classList.remove('input-mode');
                    modeIndicator.classList.add('output-mode');
                }
            }
        }
    });
}

function selectPin(pin) {
    currentPin = pin;
    showControlPanel(pin);
}

function showControlPanel(pin) {
    const controlPanel = document.getElementById('control-panel');
    const state = pinStates[pin] || { mode: 'OUT', state: 0, flashing: false, flash_speed: 500 };

    controlPanel.innerHTML = `
        <h2>Pin ${pin} Control</h2>
        <div class="control-form">
            <div class="form-group">
                <label for="pin-mode">Mode:</label>
                <select id="pin-mode" onchange="setMode(${pin}, this.value)">
                    <option value="OUT" ${state.mode === 'OUT' ? 'selected' : ''}>Output</option>
                    <option value="IN" ${state.mode === 'IN' ? 'selected' : ''}>Input</option>
                </select>
            </div>

            <div id="output-controls" style="display: ${state.mode === 'OUT' ? 'block' : 'none'}">
                <div class="form-group">
                    <label>Output State:</label>
                    <div class="control-buttons">
                        <button class="btn btn-success" onclick="setPin(${pin}, 1)">HIGH</button>
                        <button class="btn btn-danger" onclick="setPin(${pin}, 0)">LOW</button>
                    </div>
                </div>

                <div class="form-group">
                    <label>Flash Control:</label>
                    <div class="control-buttons">
                        <button class="btn ${state.flashing ? 'btn-danger' : 'btn-primary'}"
                                onclick="toggleFlash(${pin})">
                            ${state.flashing ? 'Stop Flash' : 'Start Flash'}
                        </button>
                    </div>
                </div>

                <div class="flash-controls">
                    <label>Speed:</label>
                    <input type="range" id="flash-speed" min="100" max="2000" step="100"
                           value="${state.flash_speed}"
                           oninput="updateFlashSpeed(${pin}, this.value)">
                    <span class="speed-value" id="speed-value">${state.flash_speed}ms</span>
                </div>
            </div>

            <div id="input-controls" style="display: ${state.mode === 'IN' ? 'block' : 'none'}">
                <div class="form-group">
                    <label>Current State:</label>
                    <p style="font-size: 18px; font-weight: bold; color: ${state.state ? '#2ecc71' : '#e74c3c'}">
                        ${state.state ? 'HIGH' : 'LOW'}
                    </p>
                    <button class="btn btn-primary" onclick="readPin(${pin})">Refresh</button>
                </div>
            </div>
        </div>
    `;
}

function toggleConfigTool() {
    configToolActive = !configToolActive;
    const button = document.getElementById('config-tool');

    // Deactivate flash tool if active
    if (configToolActive && flashToolActive) {
        toggleFlashTool();
    }

    if (configToolActive) {
        button.classList.add('active');
        document.body.classList.add('config-tool-active');
    } else {
        button.classList.remove('active');
        document.body.classList.remove('config-tool-active');
    }
}

function toggleFlashTool() {
    flashToolActive = !flashToolActive;
    const button = document.getElementById('flash-tool');

    // Deactivate config tool if active
    if (flashToolActive && configToolActive) {
        toggleConfigTool();
    }

    if (flashToolActive) {
        button.classList.add('active');
        document.body.classList.add('flash-tool-active');
    } else {
        button.classList.remove('active');
        document.body.classList.remove('flash-tool-active');
    }
}

async function togglePinMode(pin) {
    const state = pinStates[pin];
    if (!state) return;

    // Toggle between IN and OUT
    const newMode = state.mode === 'OUT' ? 'IN' : 'OUT';
    await setMode(pin, newMode);
}

async function activateFlashOnPin(pin) {
    const state = pinStates[pin];
    if (!state) return;

    // Set to output mode if not already
    if (state.mode !== 'OUT') {
        await setMode(pin, 'OUT');
    }

    // Toggle flashing with global flash speed
    await toggleFlash(pin, !state.flashing);
}

async function togglePinState(pin) {
    const state = pinStates[pin];
    if (!state) return;

    // Only toggle if in OUTPUT mode and not flashing
    if (state.mode === 'OUT' && !state.flashing) {
        const newState = state.state === 1 ? 0 : 1;
        await setPin(pin, newState);
    }
}

async function setMode(pin, mode) {
    try {
        const response = await fetch(`/api/pin/${pin}/mode`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ mode })
        });

        const data = await response.json();
        if (data.success) {
            await loadPinStates();
        }
    } catch (error) {
        console.error('Error setting pin mode:', error);
    }
}

async function setPin(pin, state) {
    try {
        const response = await fetch(`/api/pin/${pin}/set`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ state })
        });

        const data = await response.json();
        if (data.success) {
            await loadPinStates();
        }
    } catch (error) {
        console.error('Error setting pin:', error);
    }
}

async function toggleFlash(pin, enabled = null) {
    const state = pinStates[pin];
    if (enabled === null) {
        enabled = !state.flashing;
    }
    const speed = globalFlashSpeed;

    try {
        const response = await fetch(`/api/pin/${pin}/flash`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ enabled, speed })
        });

        const data = await response.json();
        if (data.success) {
            await loadPinStates();
            if (currentPin === pin) {
                showControlPanel(pin);
            }
        }
    } catch (error) {
        console.error('Error toggling flash:', error);
    }
}

async function updateFlashSpeed(pin, speed) {
    document.getElementById('speed-value').textContent = speed + 'ms';

    const state = pinStates[pin];
    if (state.flashing) {
        try {
            await fetch(`/api/pin/${pin}/flash`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ enabled: true, speed: parseInt(speed) })
            });
        } catch (error) {
            console.error('Error updating flash speed:', error);
        }
    } else {
        // Just update the stored speed for next flash
        pinStates[pin].flash_speed = parseInt(speed);
    }
}

async function readPin(pin) {
    try {
        const response = await fetch(`/api/pin/${pin}/read`);
        const data = await response.json();

        if (data.success) {
            await loadPinStates();
            showControlPanel(pin);
        }
    } catch (error) {
        console.error('Error reading pin:', error);
    }
}

function setLayout(layout) {
    currentLayout = layout;
    const container = document.getElementById('pin-container');
    const buttons = document.querySelectorAll('.layout-toggle button');

    buttons.forEach(btn => btn.classList.remove('active'));
    if (event && event.target) {
        event.target.classList.add('active');
    } else {
        // If no event (initial load), activate the correct button
        const targetBtn = layout === 'hat' ? buttons[0] : buttons[1];
        if (targetBtn) targetBtn.classList.add('active');
    }

    if (layout === 'hat') {
        container.classList.remove('layout-header');
        container.classList.add('layout-hat');

        // Clear existing layout
        container.innerHTML = '';

        // Parse original HTML to extract pin data
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = originalHTML;

        // HAT layout matches physical screw terminal arrangement
        // 4 columns with specific pin assignments from the HAT diagram
        // Mapping: GPIO2=SDA(pin3), GPIO3=SCL(pin5), GPIO4(pin7), GPIO14=TXD(pin8), GPIO15=RXD(pin10)
        // GPIO17(pin11), GPIO18(pin12), GPIO27(pin13), GPIO22(pin15), GPIO23(pin16), GPIO24(pin18)
        // GPIO10=MOSI(pin19), GPIO9=MISO(pin21), GPIO25(pin22), GPIO11=SCLK(pin23), GPIO8=CE0(pin24)
        // GPIO7=CE1(pin26), GPIO5(pin29), GPIO6(pin31), GPIO12(pin32), GPIO13(pin33), GPIO19(pin35)
        // GPIO16(pin36), GPIO26(pin37), GPIO20(pin38), GPIO21(pin40)
        const hatLayout = [
            // Column 1: +5V(2), SDA/GPIO2(3), -, GPIO4(7), GPIO27(13), GPIO21(40), GPIO13(33), GPIO26(37), GND(39)
            [2, 3, null, 7, 13, 40, 33, 37, 39],
            // Column 2: +5V(4), GPIO23(16), GPIO22(15), ID_SD(27), ID_SC(28), GPIO12(32), GPIO20(38), GPIO19(35), GND(34)
            [4, 16, 15, 27, 28, 32, 38, 35, 34],
            // Column 3: +3V3(1), TXD/GPIO14(8), RXD/GPIO15(10), GPIO24(18), GPIO25(22), GPIO5(29), GPIO6(31), GPIO16(36), GND(30)
            [1, 8, 10, 18, 22, 29, 31, 36, 30],
            // Column 4: +3V3(17), GPIO17(11), GPIO18(12), MOSI/GPIO10(19), MISO/GPIO9(21), SCLK/GPIO11(23), CE0/GPIO8(24), CE1/GPIO7(26), GND(25)
            [17, 11, 12, 19, 21, 23, 24, 26, 25]
        ];

        for (let col = 0; col < 4; col++) {
            const column = document.createElement('div');
            column.className = 'pin-column';

            for (let row = 0; row < hatLayout[col].length; row++) {
                const pinNum = hatLayout[col][row];
                if (pinNum !== null) {
                    const originalPin = tempDiv.querySelector(`.pin[data-pin="${pinNum}"]`);
                    if (originalPin) {
                        column.appendChild(originalPin.cloneNode(true));
                    }
                }
            }
            container.appendChild(column);
        }

        // Reattach event listeners
        initializeEventListeners();
    } else {
        // Restore header mode (2×20)
        container.classList.remove('layout-hat');
        container.classList.add('layout-header');
        container.innerHTML = originalHTML;

        // Reattach event listeners
        initializeEventListeners();
    }
}

async function resetAll() {
    if (confirm('Reset all pins to LOW output?')) {
        try {
            const response = await fetch('/api/reset', {
                method: 'POST'
            });

            const data = await response.json();
            if (data.success) {
                await loadPinStates();

                const controlPanel = document.getElementById('control-panel');
                controlPanel.innerHTML = `
                    <h2>Pin Control</h2>
                    <p>All pins have been reset. Click a GPIO pin to configure it.</p>
                `;
            }
        } catch (error) {
            console.error('Error resetting pins:', error);
        }
    }
}
