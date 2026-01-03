"""
DHT22 Temperature and Humidity Sensor Component
Example implementation showing the component pattern
"""

import Adafruit_DHT
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProducerComponent:
    """Base class for components that generate data"""
    
    def __init__(self, name: str, gpio_pins: dict):
        self.name = name
        self.gpio_pins = gpio_pins
        self.outputs = {}
        self.tested = False
    
    def read(self) -> dict:
        """Read current values from sensor"""
        raise NotImplementedError
    
    def test(self) -> bool:
        """Test if component is working"""
        raise NotImplementedError
    
    def get_metadata(self) -> dict:
        """Return component metadata"""
        raise NotImplementedError
    
    def cleanup(self):
        """Clean up GPIO resources"""
        pass


class DHT22Component(ProducerComponent):
    """
    DHT22 temperature and humidity sensor
    
    Provides:
    - temperature (°C)
    - humidity (%)
    """
    
    SENSOR_TYPE = Adafruit_DHT.DHT22
    
    def __init__(self, name: str, gpio_pins: dict, config: Optional[dict] = None):
        super().__init__(name, gpio_pins)
        
        self.data_pin = gpio_pins.get('data')
        if not self.data_pin:
            raise ValueError("DHT22 requires 'data' pin in gpio_pins")
        
        # Configuration
        config = config or {}
        self.polling_interval = config.get('polling', 2)  # seconds
        self.retries = config.get('retries', 3)
        
        # Output schema
        self.outputs = {
            'temperature': {
                'type': 'float',
                'unit': '°C',
                'range': [-40, 80]
            },
            'humidity': {
                'type': 'float',
                'unit': '%',
                'range': [0, 100]
            }
        }
        
        logger.info(f"DHT22 '{name}' initialized on GPIO {self.data_pin}")
    
    def read(self) -> Dict[str, Optional[float]]:
        """
        Read temperature and humidity from sensor
        
        Returns:
            dict with 'temperature' and 'humidity' keys
            Values are None if read failed
        """
        try:
            humidity, temperature = Adafruit_DHT.read_retry(
                self.SENSOR_TYPE,
                self.data_pin,
                retries=self.retries
            )
            
            if humidity is not None and temperature is not None:
                logger.debug(f"DHT22 '{self.name}': {temperature:.1f}°C, {humidity:.1f}%")
                return {
                    'temperature': round(temperature, 1),
                    'humidity': round(humidity, 1)
                }
            else:
                logger.warning(f"DHT22 '{self.name}': Failed to read sensor")
                return {
                    'temperature': None,
                    'humidity': None
                }
        
        except Exception as e:
            logger.error(f"DHT22 '{self.name}': Error reading sensor: {e}")
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
        logger.info(f"Testing DHT22 '{self.name}'...")
        
        data = self.read()
        
        if data['temperature'] is not None and data['humidity'] is not None:
            # Validate readings are within reasonable range
            temp_valid = -40 <= data['temperature'] <= 80
            humidity_valid = 0 <= data['humidity'] <= 100
            
            if temp_valid and humidity_valid:
                logger.info(f"DHT22 '{self.name}': Test PASSED")
                self.tested = True
                return True
            else:
                logger.warning(f"DHT22 '{self.name}': Test FAILED - readings out of range")
                return False
        else:
            logger.warning(f"DHT22 '{self.name}': Test FAILED - no response")
            return False
    
    def get_metadata(self) -> dict:
        """Get component metadata"""
        return {
            'name': self.name,
            'type': 'DHT22',
            'category': 'producer',
            'gpio_pins': self.gpio_pins,
            'outputs': self.outputs,
            'tested': self.tested,
            'config': {
                'polling_interval': self.polling_interval,
                'retries': self.retries
            }
        }


# Example usage
if __name__ == '__main__':
    import time
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create sensor instance
    sensor = DHT22Component(
        name="Living Room",
        gpio_pins={'data': 4},
        config={'polling': 2}
    )
    
    # Test sensor
    if sensor.test():
        print("✓ Sensor working")
        
        # Read continuously
        try:
            while True:
                data = sensor.read()
                if data['temperature'] is not None:
                    print(f"Temperature: {data['temperature']}°C")
                    print(f"Humidity: {data['humidity']}%")
                else:
                    print("Failed to read sensor")
                
                time.sleep(sensor.polling_interval)
        
        except KeyboardInterrupt:
            print("\nStopped")
    else:
        print("✗ Sensor test failed")
