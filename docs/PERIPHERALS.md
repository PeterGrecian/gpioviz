# Enabling Peripheral Functions on Raspberry Pi

GPIO pins can be configured to use their alternative functions (I2C, SPI, UART, PWM, etc.) instead of standard GPIO mode. This is done through Device Tree configuration.

## Configuration Methods

### Method 1: Using raspi-config (Recommended for beginners)
```bash
sudo raspi-config
```
Navigate to: **Interface Options** → Enable/disable specific peripherals (I2C, SPI, etc.)

### Method 2: Manual Configuration via /boot/firmware/config.txt

Edit the configuration file:
```bash
sudo nano /boot/firmware/config.txt
```
(On older systems, use `/boot/config.txt`)

## Peripheral Activation Commands

Add these lines to `/boot/firmware/config.txt` to enable peripherals:

### I2C (Pins 3, 5 - GPIO2/GPIO3)
```
dtparam=i2c_arm=on
# Optional: Set baudrate (default is 100kHz)
dtparam=i2c_arm_baudrate=400000
```

### SPI0 (Pins 19, 21, 23, 24, 26 - GPIO10/9/11/8/7)
```
dtparam=spi=on
```

### SPI1 (Pins 38, 40 - GPIO20/21 for MISO/SCLK)
```
# Enable SPI1 with 3 chip selects
dtoverlay=spi1-3cs
```

### UART0 (Pins 8, 10 - GPIO14/GPIO15)
```
enable_uart=1
```

### PWM (Pins 12, 32, 33, 35 - GPIO18/12/13/19)
PWM is available through software control or hardware PWM channels.
Hardware PWM doesn't require special Device Tree configuration.

### I2S/PCM Audio (Pins 12, 35, 38, 40)
```
dtparam=i2s=on
```

## Pin Functions from pins.json

| Physical Pin | BCM GPIO | Alternative Function |
|--------------|----------|---------------------|
| 3 | 2 | I2C1 SDA |
| 5 | 3 | I2C1 SCL |
| 8 | 14 | UART0 TX |
| 10 | 15 | UART0 RX |
| 12 | 18 | PWM0 / PCM_CLK |
| 19 | 10 | SPI0 MOSI |
| 21 | 9 | SPI0 MISO |
| 23 | 11 | SPI0 SCLK |
| 24 | 8 | SPI0 CE0 |
| 26 | 7 | SPI0 CE1 |
| 27 | 0 | I2C0 SDA (ID EEPROM) |
| 28 | 1 | I2C0 SCL (ID EEPROM) |
| 32 | 12 | PWM0 |
| 33 | 13 | PWM1 |
| 35 | 19 | PWM1 / SPI1 MISO |
| 38 | 20 | SPI1 MISO / PCM_DIN |
| 40 | 21 | SPI1 SCLK / PCM_DOUT |

## After Configuration

After editing `/boot/firmware/config.txt`, reboot for changes to take effect:
```bash
sudo reboot
```

## Checking Active Interfaces

### Check loaded Device Tree overlays:
```bash
dtoverlay -l
```

### Check I2C devices:
```bash
i2cdetect -y 1
```

### Check SPI devices:
```bash
ls /dev/spi*
```

### Check UART:
```bash
ls /dev/serial*
```

## Important Notes

⚠️ **WARNING**: Enabling peripheral functions on a pin **disables GPIO control** for that pin. The pin can no longer be controlled via RPi.GPIO or similar GPIO libraries while the peripheral is active.

⚠️ **CRITICAL**: Before enabling peripherals, ensure no conflicting GPIO control is running. Disable the gpioviz application if testing peripheral functions.

⚠️ **Pull-up Resistors**: Pins 3 & 5 (GPIO2/3) have permanent 1.8kΩ pull-up resistors for I2C. These cannot be disabled.

## Sources

- [Raspberry Pi config.txt Documentation](https://www.raspberrypi.com/documentation/computers/config_txt.html)
- [Raspberry Pi Firmware Overlays README](https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README)
- [SparkFun: Raspberry Pi SPI and I2C Tutorial](https://learn.sparkfun.com/tutorials/raspberry-pi-spi-and-i2c-tutorial/all)
- [SPI at Raspberry Pi GPIO Pinout](https://pinout.xyz/pinout/spi)
