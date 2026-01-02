// GPIO Pin numbers that can be controlled
const GPIO_PINS = [3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40];

let currentPin = null;
let pinStates = {};
let flashIntervals = {};
let flashToolActive = false;
let configToolActive = false;
let peripheralToolActive = false;
let clockToolActive = false;
let currentLayout = 'hat';
let originalHTML = null;
const FLASH_SPEED = 500; // Fixed flash speed in ms
let testSequenceRunning = false;
let testSequenceAbort = false;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('pin-container');
    originalHTML = container.innerHTML; // Save original layout

    // Set default layout to Hat mode BEFORE initializing listeners
    setLayout('hat');

    loadPinStates();
    loadVersionInfo();

    // Poll at 500ms to show real-time GPIO state
    // For outputs: shows the commanded state (what we wrote)
    // For inputs: shows actual GPIO voltage reading
    setInterval(updatePinStates, 500);
});

async function loadVersionInfo() {
    try {
        const response = await fetch('/api/version');
        const data = await response.json();
        if (data.commit_hash) {
            document.getElementById('commit-hash').textContent = data.commit_hash;
        }
    } catch (error) {
        console.error('Error loading version info:', error);
    }

    // Detect mobile/desktop based on viewport width
    const deviceType = window.innerWidth <= 768 ? 'mobile' : 'desktop';
    document.getElementById('device-type').textContent = deviceType;

    // Update on resize
    window.addEventListener('resize', () => {
        const newDeviceType = window.innerWidth <= 768 ? 'mobile' : 'desktop';
        document.getElementById('device-type').textContent = newDeviceType;
    });
}

function initializeEventListeners() {
    // Reset all button
    document.getElementById('reset-all').addEventListener('click', resetAll);

    // Config tool button
    document.getElementById('config-tool').addEventListener('click', toggleConfigTool);

    // Flash tool button
    document.getElementById('flash-tool').addEventListener('click', toggleFlashTool);

    // Peripheral tool button
    document.getElementById('peripheral-tool').addEventListener('click', togglePeripheralTool);

    // Clock tool button
    document.getElementById('clock-tool').addEventListener('click', toggleClock);

    // Test sequence button
    document.getElementById('test-sequence').addEventListener('click', toggleTestSequence);

    // All input button
    document.getElementById('all-input').addEventListener('click', setAllInput);

    // Save/Load config buttons
    document.getElementById('save-config').addEventListener('click', saveConfiguration);
    document.getElementById('load-config').addEventListener('click', loadConfiguration);

    // Layout toggle buttons
    document.getElementById('btn-hat-mode').addEventListener('click', () => setLayout('hat'));
    document.getElementById('btn-header-mode').addEventListener('click', () => setLayout('header'));

    // Add click listeners to GPIO pins
    // Use querySelectorAll to handle all pins (including clones in Hat mode)
    GPIO_PINS.forEach(pin => {
        const pinElements = document.querySelectorAll(`.pin[data-pin="${pin}"]`);

        pinElements.forEach(pinElement => {
            const indicator = pinElement.querySelector('.pin-indicator');

            // Click handler for the whole pin cell
            pinElement.addEventListener('click', (e) => {
                // Only handle if click is on cell but not on indicator (unless mode tool active)
                if (e.target !== indicator || peripheralToolActive || flashToolActive || configToolActive) {
                    e.stopPropagation();
                    if (peripheralToolActive) {
                        togglePeripheralMode(pin);
                    } else if (flashToolActive) {
                        activateFlashOnPin(pin);
                    } else if (configToolActive) {
                        togglePinMode(pin);
                    }
                }
            });

            // Click handler for the indicator
            if (indicator) {
                indicator.addEventListener('click', (e) => {
                    e.stopPropagation();
                    if (peripheralToolActive) {
                        togglePeripheralMode(pin);
                    } else if (flashToolActive) {
                        activateFlashOnPin(pin);
                    } else if (configToolActive) {
                        togglePinMode(pin);
                    } else {
                        togglePinState(pin);
                    }
                });
            }
        });
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
        // Update all instances of this pin (handles clones in Hat mode)
        const pinElements = document.querySelectorAll(`.pin[data-pin="${pin}"]`);

        pinElements.forEach(pinElement => {
            const indicator = pinElement.querySelector('.pin-indicator');
            const modeIndicator = pinElement.querySelector('.pin-mode-indicator');
            const label = pinElement.querySelector('.pin-label');

            if (pinStates[pin]) {
                const state = pinStates[pin];

                // Update label with peripheral mode in Hat mode
                if (currentLayout === 'hat') {
                    const availableModes = state.available_modes || ['GPIO'];
                    const currentMode = state.peripheral_mode || 'GPIO';

                    if (peripheralToolActive && availableModes.length > 1) {
                        // Show current mode and next mode preview
                        const currentIndex = availableModes.indexOf(currentMode);
                        const nextIndex = (currentIndex + 1) % availableModes.length;
                        const nextMode = availableModes[nextIndex];
                        label.innerHTML = `${currentMode}<br><span class="next-mode">→${nextMode}</span>`;
                    } else if (currentMode !== 'GPIO') {
                        label.innerHTML = currentMode;
                    }
                }

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

    // Deactivate other tools if active
    if (configToolActive && flashToolActive) {
        toggleFlashTool();
    }
    if (configToolActive && peripheralToolActive) {
        togglePeripheralTool();
    }
    if (configToolActive && clockToolActive) {
        toggleClock();
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

    // Deactivate other tools if active
    if (flashToolActive && configToolActive) {
        toggleConfigTool();
    }
    if (flashToolActive && peripheralToolActive) {
        togglePeripheralTool();
    }
    if (flashToolActive && clockToolActive) {
        toggleClock();
    }

    if (flashToolActive) {
        button.classList.add('active');
        document.body.classList.add('flash-tool-active');
    } else {
        button.classList.remove('active');
        document.body.classList.remove('flash-tool-active');
    }
}

function togglePeripheralTool() {
    peripheralToolActive = !peripheralToolActive;
    const button = document.getElementById('peripheral-tool');

    // Deactivate other tools if active
    if (peripheralToolActive && flashToolActive) {
        toggleFlashTool();
    }
    if (peripheralToolActive && configToolActive) {
        toggleConfigTool();
    }
    if (peripheralToolActive && clockToolActive) {
        toggleClock();
    }

    if (peripheralToolActive) {
        button.classList.add('active');
        document.body.classList.add('peripheral-tool-active');
    } else {
        button.classList.remove('active');
        document.body.classList.remove('peripheral-tool-active');
    }

    // Update UI to show/hide next mode previews
    updateUI();
}

async function toggleClock() {
    const button = document.getElementById('clock-tool');

    // Deactivate other tools if active
    if (!clockToolActive && flashToolActive) {
        toggleFlashTool();
    }
    if (!clockToolActive && configToolActive) {
        toggleConfigTool();
    }
    if (!clockToolActive && peripheralToolActive) {
        togglePeripheralTool();
    }

    try {
        const response = await fetch('/api/clock/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();
        if (data.success) {
            clockToolActive = data.clock_running;

            if (clockToolActive) {
                button.classList.add('active');
                button.textContent = '🕐 Stop Clock';
            } else {
                button.classList.remove('active');
                button.textContent = '🕐 Clock';
            }

            await loadPinStates();
        }
    } catch (error) {
        console.error('Error toggling clock:', error);
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

async function togglePeripheralMode(pin) {
    try {
        const response = await fetch(`/api/pin/${pin}/peripheral`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();
        if (data.success) {
            await loadPinStates();
        }
    } catch (error) {
        console.error('Error toggling peripheral mode:', error);
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
    const speed = FLASH_SPEED;

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
    const hatBtn = document.getElementById('btn-hat-mode');
    const headerBtn = document.getElementById('btn-header-mode');

    // Update button states
    hatBtn.classList.remove('active');
    headerBtn.classList.remove('active');
    if (layout === 'hat') {
        hatBtn.classList.add('active');
    } else {
        headerBtn.classList.add('active');
    }

    if (layout === 'hat') {
        container.classList.remove('layout-header');
        container.classList.add('layout-hat');

        // Clear existing layout
        container.innerHTML = '';

        // Parse original HTML to extract pin data
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = originalHTML;

        // HAT layout: 4 rows × 8 columns (verified with physical HAT)
        // All rows VERIFIED CORRECT against physical LED positions
        const hatLayout = [
            // Row 1: 3V3(17), IO17(11), IO18(12), MOSI(19), MISO(21), SCLK(23), CE0(24), CE1(26)
            [17, 11, 12, 19, 21, 23, 24, 26],
            // Row 2: 3V3(1), TXD(8), RXD(10), IO24(18), IO25(22), IO5(29), IO6(31), IO16(36)
            [1, 8, 10, 18, 22, 29, 31, 36],
            // Row 3: 5V(2), IO23(16), IO22(15), IDSD(27), IDSC(28), IO12(32), IO20(38), IO19(35)
            [2, 16, 15, 27, 28, 32, 38, 35],
            // Row 4: 5V(4), SDA(3), SCL(5), IO4(7), IO27(13), IO21(40), IO13(33), IO26(37)
            [4, 3, 5, 7, 13, 40, 33, 37]
        ];

        for (let row = 0; row < hatLayout.length; row++) {
            const rowDiv = document.createElement('div');
            rowDiv.className = 'pin-row-hat';

            for (let col = 0; col < hatLayout[row].length; col++) {
                const pinNum = hatLayout[row][col];
                if (pinNum !== null && pinNum !== undefined) {
                    const originalPin = tempDiv.querySelector(`.pin[data-pin="${pinNum}"]`);
                    if (originalPin) {
                        rowDiv.appendChild(originalPin.cloneNode(true));
                    }
                }
            }
            container.appendChild(rowDiv);
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

async function toggleTestSequence() {
    if (testSequenceRunning) {
        // Stop the test sequence
        testSequenceAbort = true;
        return;
    }

    testSequenceRunning = true;
    testSequenceAbort = false;
    const button = document.getElementById('test-sequence');
    button.textContent = '⏹ Stop Test';
    button.classList.add('active');

    // Save original pin modes
    const originalModes = {};
    GPIO_PINS.forEach(pin => {
        if (pinStates[pin]) {
            originalModes[pin] = pinStates[pin].mode;
        }
    });

    // Get pin order based on current layout
    let pinOrder = [];
    if (currentLayout === 'hat') {
        // Hat mode: row by row, left to right
        const hatLayout = [
            [17, 11, 12, 19, 21, 23, 24, 26],
            [1, 8, 10, 18, 22, 29, 31, 36],
            [2, 16, 15, 27, 28, 32, 38, 35],
            [4, 3, 5, 7, 13, 40, 33, 37]
        ];
        for (let row of hatLayout) {
            for (let pin of row) {
                if (GPIO_PINS.includes(pin)) {
                    pinOrder.push(pin);
                }
            }
        }
    } else {
        // Header mode: odd pins then even pins, top to bottom
        pinOrder = GPIO_PINS.slice().sort((a, b) => a - b);
    }

    // Flash each pin in sequence
    for (let pin of pinOrder) {
        if (testSequenceAbort) break;

        // Set to output mode and flash briefly
        await setMode(pin, 'OUT');
        await setPin(pin, 1);
        await new Promise(resolve => setTimeout(resolve, 200));
        await setPin(pin, 0);
        await new Promise(resolve => setTimeout(resolve, 50));
    }

    // Restore original pin modes
    if (!testSequenceAbort) {
        for (let pin of GPIO_PINS) {
            if (originalModes[pin] && originalModes[pin] !== pinStates[pin].mode) {
                await setMode(pin, originalModes[pin]);
            }
        }
    }

    // Reset state
    testSequenceRunning = false;
    testSequenceAbort = false;
    button.textContent = '▶ Test Sequence';
    button.classList.remove('active');
}

async function setAllInput() {
    if (confirm('Set all GPIO pins to INPUT mode?')) {
        for (let pin of GPIO_PINS) {
            await setMode(pin, 'IN');
        }
        await loadPinStates();
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
            }
        } catch (error) {
            console.error('Error resetting pins:', error);
        }
    }
}

async function saveConfiguration() {
    const filename = prompt('Enter configuration filename:', 'config.yaml');
    if (!filename) return;

    // Ensure .yaml extension
    const finalFilename = filename.endsWith('.yaml') || filename.endsWith('.yml') ? filename : filename + '.yaml';

    try {
        const response = await fetch('/api/config/save', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: finalFilename })
        });

        const data = await response.json();
        if (data.success) {
            alert(`Configuration saved to ${data.filepath}`);
        } else {
            alert(`Error saving configuration: ${data.error}`);
        }
    } catch (error) {
        console.error('Error saving configuration:', error);
        alert('Error saving configuration');
    }
}

async function loadConfiguration() {
    try {
        // Get list of available configurations
        const listResponse = await fetch('/api/config/list');
        const listData = await listResponse.json();

        if (listData.configs.length === 0) {
            alert('No saved configurations found');
            return;
        }

        const configList = listData.configs.join('\n');
        const filename = prompt(`Available configurations:\n${configList}\n\nEnter filename to load:`, listData.configs[0] || 'config.yaml');
        if (!filename) return;

        const response = await fetch('/api/config/load', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: filename })
        });

        const data = await response.json();
        if (data.success) {
            await loadPinStates();
            alert(`Configuration loaded from ${filename}`);
        } else {
            alert(`Error loading configuration: ${data.error}`);
        }
    } catch (error) {
        console.error('Error loading configuration:', error);
        alert('Error loading configuration');
    }
}
