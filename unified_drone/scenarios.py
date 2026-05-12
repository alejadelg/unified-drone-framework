"""Canonical scenarios used across all three empirical evaluations.

The ``STANDARD_MISSION`` defined here is the single reference scenario
used by every experiment in the thesis (extensibility, effort, and
interoperability). It contains 11 commands in logical flight order and
exercises every method of the unified ``DroneAdapter`` interface at least
once (with one battery query repeated to verify discharge).

Importing this module guarantees that the three evaluations agree on:
  * the exact command vocabulary,
  * the parameter values (distance, speed, duration, colour),
  * the ordering of operations,
  * the labels used for reporting purposes.

Any future change to the mission propagates automatically to all three
experiments by editing only this file.
"""

from __future__ import annotations

from typing import List, Tuple

from .core.enums import Direction
from .core.models import DroneCommand, LEDColor


# ---------------------------------------------------------------------
# Standard Mission (canonical 11-step scenario)
# ---------------------------------------------------------------------

STANDARD_MISSION: List[DroneCommand] = [
    DroneCommand.connect(),
    DroneCommand.takeoff(),
    DroneCommand.hover(duration=3.0),
    DroneCommand.move(Direction.FORWARD, distance=50, speed=30),
    DroneCommand.turn(degrees=90),
    DroneCommand.get_battery(),
    DroneCommand.get_height(),
    DroneCommand.set_led(LEDColor(red=255, green=0, blue=0)),
    DroneCommand.get_battery(),  # second query to verify discharge
    DroneCommand.land(),
    DroneCommand.disconnect(),
]


# Same mission with per-step labels for reporting purposes.
# ``get_battery`` is exercised twice; the second occurrence is tagged
# ``get_battery_2`` so per-command reports can distinguish them.
STANDARD_MISSION_LABELED: List[Tuple[str, DroneCommand]] = [
    ("connect",       STANDARD_MISSION[0]),
    ("takeoff",       STANDARD_MISSION[1]),
    ("hover",         STANDARD_MISSION[2]),
    ("move",          STANDARD_MISSION[3]),
    ("turn",          STANDARD_MISSION[4]),
    ("get_battery",   STANDARD_MISSION[5]),
    ("get_height",    STANDARD_MISSION[6]),
    ("set_led",       STANDARD_MISSION[7]),
    ("get_battery_2", STANDARD_MISSION[8]),
    ("land",          STANDARD_MISSION[9]),
    ("disconnect",    STANDARD_MISSION[10]),
]

__all__ = ["STANDARD_MISSION", "STANDARD_MISSION_LABELED"]
