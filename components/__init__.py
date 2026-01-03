"""
Component system for gpioviz
Provides abstraction layer for hardware components
"""

from .base import ProducerComponent, ConsumerComponent
from .registry import ComponentRegistry

__all__ = ['ProducerComponent', 'ConsumerComponent', 'ComponentRegistry']
