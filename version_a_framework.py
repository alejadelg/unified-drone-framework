"""Mission task implemented using ONLY the unified drone framework.

Task:
    Connect 3 drones (CoDrone EDU, CodingRider, WIZWING),
    take off all three, fly a square pattern (forward 1 m, turn 90 deg, x4),
    hover 2 s, query battery on all, set LED to green on all,
    land all, disconnect all.

Design observations:
  * One API for every drone — DroneCommand + DroneManager.
  * Same vocabulary for every operation regardless of vendor.
  * The control logic is 100% reusable across platforms; switching to
    a different drone fleet only changes the add_drone() arguments.
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock

# --- Make the script runnable without real hardware ---
for _mod in ("CoDrone", "CodingRider", "CodingRider.drone", "serial"):
    sys.modules[_mod] = MagicMock()

from unified_drone import (
    Direction,
    DroneCommand,
    DroneManager,
    LEDColor,
)
import unified_drone.adapters  # noqa: F401  (registers built-in adapters)

logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s")


def run_mission() -> None:
    manager = DroneManager()

    # Register the fleet (vendor names appear ONLY here — as configuration)
    manager.add_drone("edu", "codrone_edu", port="COM4")
    manager.add_drone("rider", "coding_rider")
    manager.add_drone("wiz", "wizwing", port="COM3", baudrate=115200)

    # Connect and take off — one command, three drones
    manager.broadcast_command(DroneCommand.connect())
    manager.broadcast_command(DroneCommand.takeoff())

    # Square pattern (forward 1 m, turn 90 deg, x4)
    for _ in range(4):
        manager.broadcast_command(
            DroneCommand.move(Direction.FORWARD, distance=1.0, speed=50)
        )
        manager.broadcast_command(DroneCommand.turn(degrees=90))

    # Hover, battery, LED — all uniform
    manager.broadcast_command(DroneCommand.hover(duration=2.0))
    batteries = manager.broadcast_command(DroneCommand.get_battery())
    print(f"Batteries: {batteries}")
    manager.broadcast_command(
        DroneCommand.set_led(LEDColor(red=0, green=255, blue=0, brightness=100))
    )

    # Land and disconnect
    manager.broadcast_command(DroneCommand.land())
    manager.broadcast_command(DroneCommand.disconnect())


if __name__ == "__main__":
    run_mission()
    print("Mission complete (Version A: framework)")
