"""Adapter for the CodingRider educational drone.

Wraps the CodingRider.drone module behind the unified DroneAdapter interface.
The library is imported lazily inside connect().

API translation reference:
    connect()      -> drone.connect()
    disconnect()   -> drone.disconnect()
    takeoff()      -> drone.takeoff()
    land()         -> drone.landing()          (note: "landing", not "land")
    move()         -> drone.go(dir_code, distance, speed)
    turn()         -> drone.turn(degrees)
"""

import logging
import time
from typing import Any, Optional

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)

_DIRECTION_MAP = {
    Direction.FORWARD: 0,
    Direction.BACKWARD: 1,
    Direction.LEFT: 2,
    Direction.RIGHT: 3,
    Direction.UP: 4,
    Direction.DOWN: 5,
}


@register_drone("coding_rider")
class CodingRiderAdapter(DroneAdapter):
    """Adapter translating unified commands into CodingRider API calls."""

    def __init__(self, name: str = "coding_rider") -> None:
        super().__init__(name=name)
        self._drone: Any = None

    def connect(self, **kwargs: Any) -> None:
        try:
            from CodingRider import drone as cr_drone  # type: ignore[import-untyped]

            self._drone = cr_drone
            self._drone.connect()
            self._status = DroneStatus.CONNECTED
            logger.info("CodingRider connected")
        except Exception as e:
            raise DroneConnectionError(f"CodingRider connect failed: {e}") from e

    def disconnect(self) -> None:
        if self._drone:
            self._drone.disconnect()
        self._status = DroneStatus.DISCONNECTED
        self._drone = None
        logger.info("CodingRider disconnected")

    def takeoff(self) -> None:
        self._ensure_connected()
        self._drone.takeoff()
        self._status = DroneStatus.FLYING
        logger.info("CodingRider takeoff")

    def land(self) -> None:
        self._ensure_connected()
        self._drone.landing()
        self._status = DroneStatus.CONNECTED
        logger.info("CodingRider landed")

    def emergency_stop(self) -> None:
        if self._drone:
            try:
                self._drone.landing()
            except Exception:
                pass
        self._status = DroneStatus.CONNECTED
        logger.warning("CodingRider emergency stop (forced landing)")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        dir_code = _DIRECTION_MAP.get(direction)
        if dir_code is None:
            raise DroneCommandError(f"Unsupported direction for CodingRider: {direction}")
        self._drone.go(dir_code, int(distance), int(speed))
        logger.info("CodingRider move dir_code=%d dist=%d speed=%d", dir_code, int(distance), int(speed))

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        self._drone.turn(int(degrees))
        logger.info("CodingRider turn %.1f degrees", degrees)

    def hover(self, duration: float = 1.0) -> None:
        self._ensure_connected()
        time.sleep(duration)
        logger.info("CodingRider hover %.1fs (simulated)", duration)

    def set_led(self, color: LEDColor) -> None:
        logger.warning("CodingRider LED control not fully supported")

    def get_battery(self) -> int:
        self._ensure_connected()
        if hasattr(self._drone, "get_battery"):
            return self._drone.get_battery()
        logger.warning("CodingRider battery query not available")
        return -1

    def _ensure_connected(self) -> None:
        if self._drone is None or self._status == DroneStatus.DISCONNECTED:
            raise DroneConnectionError("CodingRider is not connected")
