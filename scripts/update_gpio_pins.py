#!/usr/bin/env python3
"""
Script to add radio buttons to all GPIO pins in the HTML template.

This script was used to automatically update the template HTML to include
Output/Input mode radio buttons for each GPIO pin. It updates the pin
structure to include inline mode controls.

Usage:
    python3 scripts/update_gpio_pins.py

Note: This was used during development to bulk-update all GPIO pin elements.
Kept for reference in case similar bulk updates are needed in the future.
"""

import re

# Read the HTML file
with open('/home/peter/gpioviz/templates/index.html', 'r') as f:
    html = f.read()

# GPIO pins to update
gpio_pins = [3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40]

# Pattern to match GPIO pin divs
for pin in gpio_pins:
    # Pattern: <div class="pin gpio" data-pin="X">...<div class="pin-indicator"></div>...</div>
    old_pattern = f'(<div class="pin gpio" data-pin="{pin}">\\s*<span class="pin-number">{pin}</span>\\s*<span class="pin-label">GPIO[^<]*</span>)\\s*(<div class="pin-indicator"></div>)'

    new_content = f'''\\1
                        <div class="pin-mode">
                            <label><input type="radio" name="mode-{pin}" value="OUT" checked onchange="setMode({pin}, 'OUT')">O</label>
                            <label><input type="radio" name="mode-{pin}" value="IN" onchange="setMode({pin}, 'IN')">I</label>
                        </div>
                        \\2'''

    html = re.sub(old_pattern, new_content, html)

# Write back
with open('/home/peter/gpioviz/templates/index.html', 'w') as f:
    f.write(html)

print("Updated all GPIO pins with mode radio buttons")
