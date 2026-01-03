"""
Base classes for hardware components
"""

from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ProducerComponent:
    """
    Base class for components that generate data (sensors, inputs)

    Examples: DHT22, BME280, Button, DS18B20
    """

    def __init__(self, name: str, gpio_pins: dict, config: Optional[dict] = None):
        self.name = name
        self.gpio_pins = gpio_pins
        self.config = config or {}
        self.outputs = {}  # Output schema defined by subclass
        self.tested = False
        logger.info(f"Initialized {self.__class__.__name__} '{name}'")

    def read(self) -> Dict[str, Any]:
        """
        Read current values from sensor/input

        Returns:
            dict with output values (keys defined in self.outputs)
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement read()")

    def test(self) -> bool:
        """
        Test if component is working correctly

        Returns:
            True if component responds correctly, False otherwise
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement test()")

    def get_metadata(self) -> dict:
        """
        Return component metadata

        Returns:
            dict with component information
        """
        return {
            'name': self.name,
            'type': self.__class__.__name__,
            'category': 'producer',
            'gpio_pins': self.gpio_pins,
            'outputs': self.outputs,
            'tested': self.tested,
            'config': self.config
        }

    def cleanup(self):
        """Clean up GPIO resources"""
        pass


class ConsumerComponent:
    """
    Base class for components that accept commands/data (displays, motors, outputs)

    Examples: ST7789 display, SG90 servo, LED, Buzzer
    """

    def __init__(self, name: str, gpio_pins: dict, config: Optional[dict] = None):
        self.name = name
        self.gpio_pins = gpio_pins
        self.config = config or {}
        self.inputs = {}  # Input schema defined by subclass
        self.tested = False
        logger.info(f"Initialized {self.__class__.__name__} '{name}'")

    def write(self, data: dict):
        """
        Write data/commands to component

        Args:
            data: dict with input values (keys defined in self.inputs)
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement write()")

    def test(self) -> bool:
        """
        Test if component is working correctly

        Returns:
            True if component responds correctly, False otherwise
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement test()")

    def get_metadata(self) -> dict:
        """
        Return component metadata

        Returns:
            dict with component information
        """
        return {
            'name': self.name,
            'type': self.__class__.__name__,
            'category': 'consumer',
            'gpio_pins': self.gpio_pins,
            'inputs': self.inputs,
            'tested': self.tested,
            'config': self.config
        }

    def cleanup(self):
        """Clean up GPIO resources"""
        pass
