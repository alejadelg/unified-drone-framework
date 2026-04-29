"""Enumerations for the unified drone control framework."""

from enum import Enum, auto


class FlightAction(Enum):
    """All actions supported by the unified drone interface."""

    CONNECT = auto()
    DISCONNECT = auto()
    TAKEOFF = auto()
    LAND = auto()
    EMERGENCY_STOP = auto()
    MOVE = auto()
    TURN = auto()
    HOVER = auto()
    SET_LED = auto()
    GET_BATTERY = auto()
    GET_STATUS = auto()


class Direction(Enum):
    """Movement directions normalized across all drone platforms."""

    FORWARD = auto()
    BACKWARD = auto()
    LEFT = auto()
    RIGHT = auto()
    UP = auto()
    DOWN = auto()


class DroneStatus(Enum):
    """Lifecycle states of a drone."""

    DISCONNECTED = auto()
    CONNECTED = auto()
    ARMED = auto()
    FLYING = auto()
    LANDING = auto()
    ERROR = auto()
