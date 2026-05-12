"""Mission task implemented using ONLY the unified drone framework.

Executes the canonical ``STANDARD_MISSION`` (11 commands, defined in
``unified_drone/scenarios.py``) against three drones of different vendors
simultaneously via ``DroneManager.broadcast_command``.

The same mission is used by the other two evaluations:
  * ``eval_interoperability.py`` runs it per platform to measure
    per-command verdict and timing.
  * ``eval_extensibility.py`` runs it via broadcast against four drones
    (the three originals + SimDrone).

Design observations made visible by this version:
  * The control logic is a single 2-line loop over the mission.
  * Vendor names appear ONLY as configuration (the registry keys passed
    to ``add_drone``) — never in the mission code.
  * Switching to a different drone fleet only changes ``add_drone`` calls.
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock

# --- Make the script runnable without real hardware ---
for _mod in (
    "codrone_edu", "codrone_edu.drone",
    "CodingRider", "CodingRider.drone", "CodingRider.protocol",
    "serial",
):
    sys.modules[_mod] = MagicMock()

from unified_drone import DroneManager, FlightAction
import unified_drone.adapters  # noqa: F401  (registers built-in adapters)
from unified_drone.scenarios import STANDARD_MISSION

logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s")


def run_mission() -> None:
    manager = DroneManager()

    # Register the fleet (vendor names appear ONLY here, as configuration)
    manager.add_drone("edu",   "codrone_edu", port="COM4")
    manager.add_drone("rider", "coding_rider")
    manager.add_drone("wiz",   "wizwing", port="COM3", baudrate=9600)

    # Execute the entire canonical mission via broadcast.
    # Print intermediate telemetry returned by GET_BATTERY commands.
    for cmd in STANDARD_MISSION:
        results = manager.broadcast_command(cmd)
        if cmd.action == FlightAction.GET_BATTERY:
            print(f"Batteries: {results}")


if __name__ == "__main__":
    run_mission()
    print("Mission complete (Version A: framework)")
