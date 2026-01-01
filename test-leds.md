# LED Testing Guide for HAT Layout

## Goal
Map which physical GPIO pin controls which LED position on the HAT

## Row 1 Status: ✓ CORRECT
All LEDs in row 1 respond correctly to their GPIO pins.

## Testing Method

1. Use the Flash tool or Config tool to activate one pin at a time
2. Note which LED lights up on the physical HAT
3. Compare to the expected position in the web interface

## Current Mapping (from hat-layout.json)

### Row 1 (VERIFIED CORRECT)
- Col 1: 3V3 (no LED)
- Col 2: Pin 11 (GPIO17)
- Col 3: Pin 12 (GPIO18)
- Col 4: Pin 19 (GPIO10/MOSI)
- Col 5: Pin 21 (GPIO9/MISO)
- Col 6: Pin 23 (GPIO11/SCLK)
- Col 7: Pin 24 (GPIO8/CE0)
- Col 8: Pin 26 (GPIO7/CE1)

### Row 2 (NEEDS VERIFICATION)
Expected in code vs HAT:
- Col 1: 5V (no LED)
- Col 2: Pin 16 (GPIO23) - does this LED light up?
- Col 3: Pin 10 (GPIO15/RXD) - does this LED light up?
- Col 4: Pin 18 (GPIO24) - does this LED light up?
- Col 5: Pin 22 (GPIO25) - does this LED light up?
- Col 6: Pin 32 (GPIO12) - does this LED light up?
- Col 7: Pin 38 (GPIO20) - does this LED light up?
- Col 8: Pin 35 (GPIO19) - does this LED light up?

### Row 3 (NEEDS VERIFICATION)
### Row 4 (NEEDS VERIFICATION)

## Quick Test Procedure

1. Click Flash tool (⚡)
2. Click on a GPIO pin in the web interface
3. Watch which LED flashes on the physical HAT
4. Note if it's in the expected position or different position
5. Report back which pins are mismatched

## What to Report

For any mismatch:
- "When I flash Pin X (GPIOY), the LED that lights up is at Row R, Column C"
- This tells us the actual physical wiring of the HAT

