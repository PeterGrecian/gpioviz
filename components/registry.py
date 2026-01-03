"""
Component registry for managing hardware components
"""

import json
import os
import logging
from typing import Dict, Optional, Type, Any
from .base import ProducerComponent, ConsumerComponent

logger = logging.getLogger(__name__)


class ComponentRegistry:
    """
    Registry for managing component definitions and instances
    """

    def __init__(self, definitions_file: Optional[str] = None):
        self.definitions = {}
        self.instances = {}  # pin -> component instance
        self.component_classes = {}  # type -> class

        # Load definitions from JSON
        if definitions_file and os.path.exists(definitions_file):
            self.load_definitions(definitions_file)

    def load_definitions(self, filepath: str):
        """Load component definitions from JSON file"""
        try:
            with open(filepath, 'r') as f:
                self.definitions = json.load(f)
            logger.info(f"Loaded {len(self.definitions)} component definitions")
        except Exception as e:
            logger.error(f"Failed to load component definitions: {e}")
            self.definitions = {}

    def register_class(self, component_type: str, component_class: Type):
        """
        Register a component class

        Args:
            component_type: Component type identifier (e.g., 'dht22')
            component_class: Component class (must inherit from ProducerComponent or ConsumerComponent)
        """
        self.component_classes[component_type] = component_class
        logger.debug(f"Registered component class: {component_type}")

    def create_component(self, component_type: str, name: str, gpio_pins: dict,
                        config: Optional[dict] = None) -> Optional[Any]:
        """
        Create a component instance

        Args:
            component_type: Type of component (e.g., 'dht22')
            name: Component instance name
            gpio_pins: GPIO pin mapping
            config: Optional configuration dict

        Returns:
            Component instance or None if creation failed
        """
        if component_type not in self.component_classes:
            logger.error(f"Unknown component type: {component_type}")
            return None

        try:
            component_class = self.component_classes[component_type]
            instance = component_class(name, gpio_pins, config)
            return instance
        except Exception as e:
            logger.error(f"Failed to create {component_type} component: {e}")
            return None

    def assign_component(self, pin: int, component: Any):
        """
        Assign a component instance to a pin

        Args:
            pin: GPIO pin number
            component: Component instance
        """
        # Clean up existing component on this pin
        if pin in self.instances:
            self.remove_component(pin)

        self.instances[pin] = component
        logger.info(f"Assigned {component.name} to pin {pin}")

    def get_component(self, pin: int) -> Optional[Any]:
        """
        Get component assigned to a pin

        Args:
            pin: GPIO pin number

        Returns:
            Component instance or None
        """
        return self.instances.get(pin)

    def remove_component(self, pin: int):
        """
        Remove component from a pin

        Args:
            pin: GPIO pin number
        """
        if pin in self.instances:
            component = self.instances[pin]
            component.cleanup()
            del self.instances[pin]
            logger.info(f"Removed component from pin {pin}")

    def get_all_components(self) -> Dict[int, Any]:
        """
        Get all component instances

        Returns:
            dict mapping pin -> component
        """
        return self.instances.copy()

    def get_definition(self, component_type: str) -> Optional[dict]:
        """
        Get component definition from JSON

        Args:
            component_type: Component type identifier

        Returns:
            Component definition dict or None
        """
        return self.definitions.get(component_type)

    def cleanup_all(self):
        """Clean up all component instances"""
        for pin in list(self.instances.keys()):
            self.remove_component(pin)
