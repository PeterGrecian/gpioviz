import re

with open('/home/peter/gpioviz/templates/index.html', 'r') as f:
    html = f.read()

# Replace the pin-mode divs with pin-mode-indicator
gpio_pins = [3, 5, 7, 8, 10, 11, 12, 13, 15, 16, 18, 19, 21, 22, 23, 24, 26, 29, 31, 32, 33, 35, 36, 37, 38, 40]

for pin in gpio_pins:
    # Find and replace the radio button section
    old_pattern = f'''<div class="pin-mode">
                            <label><input type="radio" name="mode-{pin}" value="OUT" checked onchange="setMode({pin}, 'OUT')">O</label>
                            <label><input type="radio" name="mode-{pin}" value="IN" onchange="setMode({pin}, 'IN')">I</label>
                        </div>'''
    
    new_pattern = f'<div class="pin-mode-indicator output-mode"></div>'
    
    html = html.replace(old_pattern, new_pattern)

with open('/home/peter/gpioviz/templates/index.html', 'w') as f:
    f.write(html)

print("Updated all GPIO pins to use mode indicators")
