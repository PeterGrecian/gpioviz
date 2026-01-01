# Raspberry Pi GPIO Visualizer

A Python Flask web application for visualizing, configuring, and controlling all 40 GPIO pins on a Raspberry Pi Zero. Features real-time control with visual flashing effects.

## Features

- Visual representation of all 40 pins on the Raspberry Pi Zero header
- Configure pins as INPUT or OUTPUT
- Control output pins (HIGH/LOW)
- Flash pins at configurable speeds (100ms - 2000ms)
- Real-time state updates
- Clean, responsive web interface
- Color-coded pins (GPIO, Power, Ground, Reserved)

## Requirements

- Raspberry Pi Zero (or any Raspberry Pi with 40-pin header)
- Python 3.7+
- Root/sudo access for GPIO control

## Installation

1. Clone or navigate to this directory:
```bash
cd gpioviz
```

2. Create a virtual environment:
```bash
python3 -m venv venv
```

3. Activate the virtual environment:
```bash
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

**Alternative (system-wide installation):**
```bash
sudo apt-get install -y python3-flask python3-rpi.gpio
```

## Running the Application

1. Start the server (requires sudo for GPIO access):

**If using virtual environment:**
```bash
sudo venv/bin/python3 app.py
```

**If using system packages:**
```bash
sudo python3 app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

Or from another device on the same network:
```
http://<raspberry-pi-ip>:5000
```

## Usage

### Pin Control

1. **Select a Pin**: Click on any green GPIO pin in the visual display
2. **Set Mode**: Choose between INPUT or OUTPUT mode
3. **Output Mode**:
   - Click HIGH/LOW buttons to set the pin state
   - Click "Start Flash" to make the pin flash
   - Adjust the speed slider (100ms - 2000ms)
   - Click "Stop Flash" to stop flashing
4. **Input Mode**:
   - View the current pin state (HIGH/LOW)
   - Click "Refresh" to update the reading

### Visual Indicators

- **Gray Circle**: Pin is LOW (off)
- **Green Circle**: Pin is HIGH (on)
- **Flashing Green**: Pin is in flash mode
- **Red Circle**: Power pins (3.3V, 5V)
- **Dark Circle**: Ground pins
- **Light Gray Circle**: Reserved pins (ID_SD, ID_SC)

### Reset All

Click the "Reset All Pins" button to:
- Stop all flashing
- Set all GPIO pins to OUTPUT mode
- Set all pins to LOW state

## Pin Layout

The application displays the exact physical layout of the 40-pin header:

- **GPIO Pins (Green)**: Configurable and controllable
- **Power Pins (Red)**: 3.3V (pins 1, 17) and 5V (pins 2, 4)
- **Ground Pins (Black)**: Pins 6, 9, 14, 20, 25, 30, 34, 39
- **Reserved Pins (Gray)**: ID_SD (27), ID_SC (28)

## API Endpoints

### GET /api/pins
Get all pin states and GPIO mapping

### POST /api/pin/<pin>/set
Set pin state (HIGH/LOW)
```json
{"state": 1}
```

### POST /api/pin/<pin>/mode
Set pin mode (IN/OUT)
```json
{"mode": "OUT"}
```

### POST /api/pin/<pin>/flash
Toggle pin flashing
```json
{"enabled": true, "speed": 500}
```

### GET /api/pin/<pin>/read
Read current pin state

### POST /api/reset
Reset all pins to default state

## Safety Notes

- Be careful when controlling GPIO pins connected to external circuits
- Always verify your wiring before enabling outputs
- The application runs with sudo privileges - use responsibly
- Power and ground pins cannot be controlled (display only)

## Troubleshooting

**Permission Denied Error**:
- Make sure to run with sudo: `sudo python3 app.py`

**GPIO Warnings**:
- The app disables GPIO warnings by default
- Pins may already be in use by other processes

**Can't Access from Other Devices**:
- Check your Raspberry Pi's IP address: `hostname -I`
- Ensure port 5000 is not blocked by firewall
- The app binds to 0.0.0.0 to accept external connections

## Development

Project structure:
```
gpioviz/
├── app.py                 # Flask backend with GPIO control
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Main HTML interface
├── static/
│   ├── css/
│   │   └── style.css     # Styling
│   └── js/
│       └── app.js        # Frontend JavaScript
└── README.md
```

## License

MIT License - Feel free to modify and use as needed.
