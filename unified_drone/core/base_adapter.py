"""Abstract base class defining the unified drone interface.

Every drone adapter must subclass DroneAdapter and implement all abstract methods.
The concrete execute() method handles command dispatch — adapters never override it.
"""

from abc import ABC, abstractmethod
from typing import Any

from .enums import Direction, DroneStatus, FlightAction
from .exceptions import DroneCommandError
from .models import DroneCommand, LEDColor


class DroneAdapter(ABC):
    """Target interface of the Adapter pattern.

    Subclasses translate this unified API into library-specific calls.
    """

    def __init__(self, name: str = "drone") -> None:
        self._name = name
        self._status = DroneStatus.DISCONNECTED

    @property
    def name(self) -> str:
        return self._name

    @property
    def status(self) -> DroneStatus:
        return self._status

    # --- Abstract methods: every adapter MUST implement these ---

    @abstractmethod
    def connect(self, **kwargs: Any) -> None:
        """Establish connection to the physical drone."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the drone."""

    @abstractmethod
    def takeoff(self) -> None:
        """Command the drone to take off."""

    @abstractmethod
    def land(self) -> None:
        """Command the drone to land."""

    @abstractmethod
    def emergency_stop(self) -> None:
        """Immediately stop all motors."""

    @abstractmethod
    def move(self, direction: Direction, distance: float, speed: float) -> None:
        """Move the drone in the given direction."""

    @abstractmethod
    def turn(self, degrees: float) -> None:
        """Rotate the drone. Positive = clockwise, negative = counter-clockwise."""

    @abstractmethod
    def hover(self, duration: float) -> None:
        """Hold position for the given duration in seconds."""

    @abstractmethod
    def set_led(self, color: LEDColor) -> None:
        """Set the drone's LED color."""

    @abstractmethod
    def get_battery(self) -> int:
        """Return battery level as a percentage (0-100), or -1 if unavailable."""

    # --- Concrete command dispatch ---

    def execute(self, command: DroneCommand) -> Any:
        """Dispatch a DroneCommand to the appropriate abstract method.

        This is the single entry point for the Command pattern.
        Subclasses should NOT override this method.
        """
        dispatch = {
            FlightAction.CONNECT: lambda: self.connect(**command.params),
            FlightAction.DISCONNECT: lambda: self.disconnect(),
            FlightAction.TAKEOFF: lambda: self.takeoff(),
            FlightAction.LAND: lambda: self.land(),
            FlightAction.EMERGENCY_STOP: lambda: self.emergency_stop(),
            FlightAction.MOVE: lambda: self.move(**command.params),
            FlightAction.TURN: lambda: self.turn(**command.params),
            FlightAction.HOVER: lambda: self.hover(**command.params),
            FlightAction.SET_LED: lambda: self.set_led(**command.params),
            FlightAction.GET_BATTERY: lambda: self.get_battery(),
            FlightAction.GET_STATUS: lambda: self.status,
        }
        handler = dispatch.get(command.action)
        if handler is None:
            raise DroneCommandError(f"Unknown action: {command.action}")
        return handler()
