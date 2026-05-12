"""Data models for the unified drone control framework.

All models are frozen (immutable) dataclasses, making them safe to log, queue, and replay.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from .enums import Direction, FlightAction


@dataclass(frozen=True)
class Position:
    """Represents a 3D position with yaw rotation."""

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    yaw: float = 0.0


@dataclass(frozen=True)
class LEDColor:
    """RGB color with brightness for drone LED control."""

    red: int = 0
    green: int = 0
    blue: int = 0
    brightness: int = 100


@dataclass(frozen=True)
class DroneCommand:
    """Generic command object that encapsulates a drone action and its parameters.

    Use the factory classmethods (e.g., DroneCommand.takeoff()) for convenience.
    """

    action: FlightAction
    params: Dict[str, Any] = field(default_factory=dict)

    # --- Factory classmethods ---

    @classmethod
    def connect(cls, **kwargs: Any) -> DroneCommand:
        return cls(action=FlightAction.CONNECT, params=kwargs)

    @classmethod
    def disconnect(cls) -> DroneCommand:
        return cls(action=FlightAction.DISCONNECT)

    @classmethod
    def takeoff(cls) -> DroneCommand:
        return cls(action=FlightAction.TAKEOFF)

    @classmethod
    def land(cls) -> DroneCommand:
        return cls(action=FlightAction.LAND)

    @classmethod
    def emergency_stop(cls) -> DroneCommand:
        return cls(action=FlightAction.EMERGENCY_STOP)

    @classmethod
    def move(
        cls,
        direction: Direction,
        distance: float = 1.0,
        speed: float = 50.0,
    ) -> DroneCommand:
        return cls(
            action=FlightAction.MOVE,
            params={"direction": direction, "distance": distance, "speed": speed},
        )

    @classmethod
    def turn(cls, degrees: float) -> DroneCommand:
        return cls(action=FlightAction.TURN, params={"degrees": degrees})

    @classmethod
    def hover(cls, duration: float = 1.0) -> DroneCommand:
        return cls(action=FlightAction.HOVER, params={"duration": duration})

    @classmethod
    def set_led(cls, color: LEDColor) -> DroneCommand:
        return cls(action=FlightAction.SET_LED, params={"color": color})

    @classmethod
    def get_battery(cls) -> DroneCommand:
        return cls(action=FlightAction.GET_BATTERY)

    @classmethod
    def get_height(cls) -> DroneCommand:
        return cls(action=FlightAction.GET_HEIGHT)

    @classmethod
    def get_status(cls) -> DroneCommand:
        return cls(action=FlightAction.GET_STATUS)
