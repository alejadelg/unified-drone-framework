"""Custom exception hierarchy for the drone framework."""


class DroneError(Exception):
    """Base exception for all drone framework errors."""


class DroneConnectionError(DroneError):
    """Raised when connection or disconnection fails."""


class DroneCommandError(DroneError):
    """Raised when a command cannot be executed."""


class DroneTimeoutError(DroneError):
    """Raised when an operation times out."""


class AdapterNotFoundError(DroneError):
    """Raised when no adapter is registered for a given key."""
