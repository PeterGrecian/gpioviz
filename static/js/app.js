// GPIO Pin numbers that can be controlled
const GPIO_PINS = [3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40];

let currentPin = null;
let pinStates = {};
let flashIntervals = {};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initializeEventListeners();
    loadPinStates();
    setInterval(updatePinStates, 1000);
});

function initializeEventListeners() {
    // Reset all button
    document.getElementById('reset-all').addEventListener('click', resetAll);

    // Add click listeners to GPIO pins
    GPIO_PINS.forEach(pin => {
        const pinElement = document.querySelector(`.pin[data-pin="${pin}"]`);
        if (pinElement) {
            pinElement.addEventListener('click', () => selectPin(pin));
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

        if (pinStates[pin]) {
            const state = pinStates[pin];

            // Update indicator
            if (state.flashing) {
                indicator.classList.add('flashing');
                indicator.classList.remove('active');
            } else if (state.state === 1) {
                indicator.classList.add('active');
                indicator.classList.remove('flashing');
            } else {
                indicator.classList.remove('active', 'flashing');
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
            showControlPanel(pin);
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

async function toggleFlash(pin) {
    const state = pinStates[pin];
    const enabled = !state.flashing;
    const speed = state.flash_speed || 500;

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
            showControlPanel(pin);
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
                    <p>All pins have been reset. Click a GPIO pin above to configure it.</p>
                `;
            }
        } catch (error) {
            console.error('Error resetting pins:', error);
        }
    }
}
