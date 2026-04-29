"""Unified Drone Control Framework.

A reusable, extensible framework that abstracts differences between educational
drone control libraries behind a single unified interface.

Typical usage::

    from unified_drone import DroneManager, DroneCommand, Direction
    import unified_drone.adapters  # triggers adapter registration

    manager = DroneManager()
    manager.add_drone("my_drone", "codrone_edu")
    manager.send_command("my_drone", DroneCommand.connect())
    manager.send_command("my_drone", DroneCommand.takeoff())
    manager.send_command("my_drone", DroneCommand.move(Direction.FORWARD, distance=2.0))
    manager.send_command("my_drone", DroneCommand.land())
"""

from .core.base_adapter import DroneAdapter
from .core.enums import Direction, DroneStatus, FlightAction
from .core.exceptions import (
    AdapterNotFoundError,
    DroneCommandError,
    DroneConnectionError,
    DroneError,
    DroneTimeoutError,
)
from .core.manager import DroneManager
from .core.models import DroneCommand, LEDColor, Position
from .core.registry import DroneRegistry, register_drone

__all__ = [
    "DroneAdapter",
    "DroneCommand",
    "DroneManager",
    "DroneRegistry",
    "Direction",
    "DroneStatus",
    "FlightAction",
    "LEDColor",
    "Position",
    "register_drone",
    "DroneError",
    "DroneConnectionError",
    "DroneCommandError",
    "DroneTimeoutError",
    "AdapterNotFoundError",
]
