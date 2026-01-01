# Hardware Documentation

This folder contains documentation for the hardware used with the GPIO Visualizer.

## Screw Terminal HAT

The GPIO visualizer is designed to work with a screw terminal HAT that has:
- 4 rows × 8 columns of terminals and LEDs
- 40-pin GPIO header layout
- Product: 52pi EP-0129 GPIO Screw Terminal HAT
- Documentation: https://wiki.52pi.com/index.php/GPIO_Screw_Terminal_Hat_SKU:_EP-0129
- LED indicators showing pin states:
  - 3.3V pins: Pink LEDs
  - 5V pins: Red LEDs
  - ID_SD/ID_SC pins: Turquoise/dim LEDs
  - GPIO pins: Green when HIGH, dark when LOW

## Layout Modes

- **Hat Mode**: 4 rows × 8 columns arranged to match the physical HAT layout (default)
- **Header Mode**: 2 columns × 20 pins showing the traditional GPIO header arrangement

## GPIO Safety Information

### Configurable Pins
Almost every pin that is not power (3.3V, 5V) or Ground can be configured as GPIO. Of the 40 pins, 26-28 are standard GPIOs (BCM 0-27 on newer models).

### Dual Functions
Many pins have secondary functions (I2C, SPI, UART) that are only active if enabled in software. When disabled, they behave as standard GPIOs.

### Important Exceptions and Cautions

**ID_SD and ID_SC (Pins 27 & 28, turquoise LEDs on HAT):**
- Reserved for HAT EEPROM communication during boot
- Can be used as GPIO (BCM 0 and 1) by disabling EEPROM check in /boot/config.txt
- **Not recommended** to avoid hardware identification conflicts

**Permanent Pull-up Resistors:**
- Physical pins 3 and 5 (BCM 2 and 3) have physical 1.8kΩ pull-up resistors
- Used for I2C communication
- Can be used as GPIO but will always be pulled HIGH by default

**Voltage Limit:**
- All GPIO pins operate at **3.3V logic**
- **Never connect 5V signals** - this will damage your Raspberry Pi

### Critical: Why You Need Resistors

**The Problem:**
If two Output pins are accidentally configured with opposing states (one HIGH at 3.3V, one LOW at 0V):
- Creates a "dead short" between 3.3V and Ground
- Can draw excessive current (>16mA per pin or 50mA total)
- **May permanently damage pins, GPIO banks, or the entire SoC**

**The Solution:**
**Always use 1kΩ to 10kΩ resistors** between pins to limit current to safe levels without interfering with logic signals.

## Files in this Directory

- `hat-diagram.jpg` - Photo of the 52pi HAT pinout diagram
- `README.md` - This file
