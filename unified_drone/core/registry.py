"""Adapter registry enabling the Open/Closed Principle.

New drone adapters register themselves via @register_drone("key") — no existing
code needs modification. DroneManager uses DroneRegistry.create() to instantiate
adapters by key, never referencing concrete classes directly.
"""

import logging
from typing import Any, Dict, List, Type

from .base_adapter import DroneAdapter
from .exceptions import AdapterNotFoundError

logger = logging.getLogger(__name__)


class DroneRegistry:
    """Central registry mapping string keys to DroneAdapter subclasses."""

    _adapters: Dict[str, Type[DroneAdapter]] = {}

    @classmethod
    def register(cls, key: str, adapter_class: Type[DroneAdapter]) -> None:
        """Register an adapter class under the given key."""
        if key in cls._adapters:
            logger.warning("Overwriting adapter for key '%s'", key)
        cls._adapters[key] = adapter_class
        logger.info("Registered adapter '%s' -> %s", key, adapter_class.__name__)

    @classmethod
    def get(cls, key: str) -> Type[DroneAdapter]:
        """Look up an adapter class by key. Raises AdapterNotFoundError if missing."""
        if key not in cls._adapters:
            raise AdapterNotFoundError(
                f"No adapter registered for '{key}'. "
                f"Available: {list(cls._adapters.keys())}"
            )
        return cls._adapters[key]

    @classmethod
    def create(cls, key: str, **kwargs: Any) -> DroneAdapter:
        """Factory method: instantiate a registered adapter by key."""
        adapter_class = cls.get(key)
        return adapter_class(**kwargs)

    @classmethod
    def available(cls) -> List[str]:
        """Return all registered adapter keys."""
        return list(cls._adapters.keys())


def register_drone(key: str):
    """Class decorator for auto-registration.

    Usage::

        @register_drone("my_drone")
        class MyDroneAdapter(DroneAdapter):
            ...
    """

    def decorator(cls: Type[DroneAdapter]) -> Type[DroneAdapter]:
        DroneRegistry.register(key, cls)
        return cls

    return decorator
