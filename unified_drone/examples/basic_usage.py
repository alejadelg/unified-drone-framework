"""Demonstrates unified control across all 3 drone platforms.

This example shows how the same high-level logic (takeoff, move, land) works
identically across CoDrone EDU, CodingRider, and WIZWING drones. The framework
handles all API translation behind the scenes.

Note: Running this requires the actual drone hardware and libraries installed.
The code below illustrates the framework API and command flow.
"""

import logging
import sys

# Add parent directory to path so we can import unified_drone
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from unified_drone import (
    Direction,
    DroneCommand,
    DroneManager,
    DroneRegistry,
    LEDColor,
)

# Importing adapters triggers auto-registration
import unified_drone.adapters  # noqa: F401

logging.basicConfig(level=logging.INFO, format="%(name)s | %(levelname)s | %(message)s")


def main() -> None:
    # ---------------------------------------------------------------
    # 1. Show all registered adapters
    # ---------------------------------------------------------------
    print("Available adapters:", DroneRegistry.available())
    # => ['codrone_edu', 'coding_rider', 'wizwing']

    # ---------------------------------------------------------------
    # 2. Create a DroneManager and add drones of different types
    # ---------------------------------------------------------------
    manager = DroneManager()

    manager.add_drone("edu_1", "codrone_edu", port="COM4")
    manager.add_drone("rider_1", "coding_rider")
    manager.add_drone("wiz_1", "wizwing", port="COM5", baudrate=115200)

    print("Managed drones:", manager.drone_ids)

    # ---------------------------------------------------------------
    # 3. Connect all drones with a single broadcast
    # ---------------------------------------------------------------
    manager.broadcast_command(DroneCommand.connect())

    # ---------------------------------------------------------------
    # 4. Unified takeoff — same command, three different libraries
    # ---------------------------------------------------------------
    manager.broadcast_command(DroneCommand.takeoff())

    # ---------------------------------------------------------------
    # 5. Individual commands to specific drones
    # ---------------------------------------------------------------
    manager.send_command(
        "edu_1", DroneCommand.move(Direction.FORWARD, distance=1.5, speed=60)
    )
    manager.send_command("rider_1", DroneCommand.turn(degrees=90))
    manager.send_command(
        "wiz_1", DroneCommand.set_led(LEDColor(red=255, green=0, blue=0))
    )

    # ---------------------------------------------------------------
    # 6. Check battery on all drones
    # ---------------------------------------------------------------
    batteries = manager.broadcast_command(DroneCommand.get_battery())
    for drone_id, level in batteries.items():
        print(f"  {drone_id}: battery = {level}%")

    # ---------------------------------------------------------------
    # 7. Execute a command sequence on one drone
    # ---------------------------------------------------------------
    flight_plan = [
        DroneCommand.move(Direction.FORWARD, distance=2.0, speed=50),
        DroneCommand.turn(degrees=-45),
        DroneCommand.hover(duration=1.0),
        DroneCommand.move(Direction.LEFT, distance=1.0, speed=40),
    ]
    manager.send_sequence("edu_1", flight_plan)

    # ---------------------------------------------------------------
    # 8. Land and disconnect all drones
    # ---------------------------------------------------------------
    manager.broadcast_command(DroneCommand.land())
    manager.broadcast_command(DroneCommand.disconnect())

    print("Final status:", manager.status_report())


if __name__ == "__main__":
    main()
