"""
DHT11 Temperature and Humidity Sensor Component
"""

import logging
from typing import Dict, Optional

try:
    import Adafruit_DHT
    DHT11_AVAILABLE = True
except ImportError:
    DHT11_AVAILABLE = False

from ..base import ProducerComponent

logger = logging.getLogger(__name__)


class DHT11Component(ProducerComponent):
    """
    DHT11 temperature and humidity sensor

    Provides:
    - temperature (°C)
    - humidity (%)
    """

    SENSOR_TYPE = Adafruit_DHT.DHT11 if DHT11_AVAILABLE else None

    def __init__(self, name: str, gpio_pins: dict, config: Optional[dict] = None):
        super().__init__(name, gpio_pins, config)

        if not DHT11_AVAILABLE:
            raise ImportError("Adafruit_DHT library not available")

        self.data_pin = gpio_pins.get('data')
        if not self.data_pin:
            raise ValueError("DHT11 requires 'data' pin in gpio_pins")

        # Configuration
        self.polling_interval = self.config.get('polling', 2)  # seconds
        self.retries = self.config.get('retries', 3)

        # Output schema
        self.outputs = {
            'temperature': {
                'type': 'float',
                'unit': '°C',
                'range': [0, 50]
            },
            'humidity': {
                'type': 'float',
                'unit': '%',
                'range': [20, 80]
            }
        }

        print(f"DHT11 INIT: name='{name}', data_pin={self.data_pin} (type: {type(self.data_pin)}), retries={self.retries}, polling={self.polling_interval}")
        logger.info(f"DHT11 '{name}' initialized on GPIO {self.data_pin}")

    def read(self) -> Dict[str, Optional[float]]:
        """
        Read temperature and humidity from sensor

        Returns:
            dict with 'temperature' and 'humidity' keys
            Values are None if read failed
        """
        try:
            import time
            start_time = time.time()
            print(f"DHT11 '{self.name}': Attempting read on BCM GPIO {self.data_pin}...")

            # Manual retry loop to count attempts
            humidity, temperature = None, None
            for attempt in range(1, self.retries + 1):
                humidity, temperature = Adafruit_DHT.read(
                    self.SENSOR_TYPE,
                    self.data_pin
                )
                if humidity is not None and temperature is not None:
                    break
                if attempt < self.retries:
                    time.sleep(2)  # Wait before retry

            elapsed = time.time() - start_time

            if humidity is not None and temperature is not None:
                print(f"DHT11 '{self.name}': ✓ SUCCESS - {temperature:.1f}°C, {humidity:.1f}% (attempt {attempt}/{self.retries}, took {elapsed:.1f}s)")
                logger.debug(f"DHT11 '{self.name}': {temperature:.1f}°C, {humidity:.1f}%")
                return {
                    'temperature': round(temperature, 1),
                    'humidity': round(humidity, 1)
                }
            else:
                print(f"DHT11 '{self.name}': ✗ FAILED - all {self.retries} attempts exhausted (took {elapsed:.1f}s)")
                logger.warning(f"DHT11 '{self.name}': Failed to read sensor")
                return {
                    'temperature': None,
                    'humidity': None
                }

        except Exception as e:
            print(f"DHT11 '{self.name}': ✗ EXCEPTION - {e}")
            logger.error(f"DHT11 '{self.name}': Error reading sensor: {e}")
            return {
                'temperature': None,
                'humidity': None
            }

    def test(self) -> bool:
        """
        Test if sensor is responding

        Returns:
            True if sensor reads successfully, False otherwise
        """
        logger.info(f"Testing DHT11 '{self.name}'...")

        data = self.read()

        if data['temperature'] is not None and data['humidity'] is not None:
            # Validate readings are within reasonable range
            temp_valid = 0 <= data['temperature'] <= 50
            humidity_valid = 20 <= data['humidity'] <= 80

            if temp_valid and humidity_valid:
                logger.info(f"DHT11 '{self.name}': Test PASSED")
                self.tested = True
                return True
            else:
                logger.warning(f"DHT11 '{self.name}': Test FAILED - readings out of range")
                return False
        else:
            logger.warning(f"DHT11 '{self.name}': Test FAILED - no response")
            return False
