"""Demonstrates how to add a 4th drone platform (DJI Tello).

Adding a new drone to the framework requires:
  1. Create one new file with a class that extends DroneAdapter
  2. Decorate it with @register_drone("key")
  3. Import the module so registration runs

Zero existing files are modified. This is the Open/Closed Principle in action.
"""

import logging
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from unified_drone import (
    Direction,
    DroneAdapter,
    DroneCommand,
    DroneManager,
    DroneRegistry,
    register_drone,
)
from unified_drone.core.enums import DroneStatus
from unified_drone.core.exceptions import DroneConnectionError
from unified_drone.core.models import LEDColor

# Import built-in adapters
import unified_drone.adapters  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")


# ===================================================================
# STEP 1: Define a new adapter — this would normally be a new file
#          e.g., unified_drone/adapters/tello.py
# ===================================================================


@register_drone("tello")
class TelloAdapter(DroneAdapter):
    """Hypothetical adapter for the DJI Tello EDU drone.

    Uses the djitellopy library. Shows the minimal work needed to
    integrate a new drone platform into the framework.
    """

    def __init__(self, name: str = "tello") -> None:
        super().__init__(name=name)
        self._tello = None

    def connect(self, **kwargs) -> None:
        try:
            from djitellopy import Tello  # type: ignore[import-untyped]

            self._tello = Tello()
            self._tello.connect()
            self._status = DroneStatus.CONNECTED
        except Exception as e:
            raise DroneConnectionError(f"Tello connect failed: {e}") from e

    def disconnect(self) -> None:
        if self._tello:
            self._tello.end()
        self._status = DroneStatus.DISCONNECTED

    def takeoff(self) -> None:
        self._tello.takeoff()
        self._status = DroneStatus.FLYING

    def land(self) -> None:
        self._tello.land()
        self._status = DroneStatus.CONNECTED

    def emergency_stop(self) -> None:
        self._tello.emergency()
        self._status = DroneStatus.CONNECTED

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        dist_cm = int(distance * 100)
        mapping = {
            Direction.FORWARD: self._tello.move_forward,
            Direction.BACKWARD: self._tello.move_back,
            Direction.LEFT: self._tello.move_left,
            Direction.RIGHT: self._tello.move_right,
            Direction.UP: self._tello.move_up,
            Direction.DOWN: self._tello.move_down,
        }
        fn = mapping.get(direction)
        if fn:
            fn(dist_cm)

    def turn(self, degrees: float) -> None:
        if degrees >= 0:
            self._tello.rotate_clockwise(int(degrees))
        else:
            self._tello.rotate_counter_clockwise(int(abs(degrees)))

    def hover(self, duration: float = 1.0) -> None:
        import time

        time.sleep(duration)

    def set_led(self, color: LEDColor) -> None:
        logging.info("Tello LED not supported via djitellopy")

    def get_battery(self) -> int:
        return self._tello.get_battery()


# ===================================================================
# STEP 2: Use it — the framework now recognizes "tello" automatically
# ===================================================================


def main() -> None:
    # The Tello adapter is now registered alongside the built-in ones
    print("Available adapters:", DroneRegistry.available())
    # => ['codrone_edu', 'coding_rider', 'wizwing', 'tello']

    manager = DroneManager()

    # Add a Tello drone using the same API as any other drone
    manager.add_drone("my_tello", "tello")

    # Same unified commands work on the new drone
    manager.send_command("my_tello", DroneCommand.connect())
    manager.send_command("my_tello", DroneCommand.takeoff())
    manager.send_command(
        "my_tello", DroneCommand.move(Direction.FORWARD, distance=1.0, speed=50)
    )
    manager.send_command("my_tello", DroneCommand.turn(degrees=180))
    manager.send_command(
        "my_tello", DroneCommand.move(Direction.FORWARD, distance=1.0, speed=50)
    )
    manager.send_command("my_tello", DroneCommand.land())
    manager.send_command("my_tello", DroneCommand.disconnect())

    print("Status:", manager.status_report())


if __name__ == "__main__":
    main()
