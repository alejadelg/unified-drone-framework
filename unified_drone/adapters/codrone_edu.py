"""Adapter for the Robolink CoDrone EDU.

Wraps the CoDrone library (``import CoDrone``) behind the unified DroneAdapter
interface. The library is imported lazily inside connect() so the framework loads
even when the CoDrone package is not installed.

API translation reference:
    connect()      -> CoDrone().pair() / .pair(port)
    disconnect()   -> .close()
    takeoff()      -> .takeoff()
    land()         -> .land()
    emergency_stop -> .emergency_stop()
    move()         -> .go(direction_str, power, duration)
    turn()         -> .turn_right(deg) / .turn_left(abs(deg))
    hover()        -> .hover(seconds)
    set_led()      -> .set_drone_LED(r, g, b, brightness)
    get_battery()  -> .get_battery()
    get_height()   -> .get_height() / 100.0   (cm -> meters)
"""

import logging
from typing import Any, Optional

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)

_DIRECTION_MAP = {
    Direction.FORWARD: "forward",
    Direction.BACKWARD: "backward",
    Direction.LEFT: "left",
    Direction.RIGHT: "right",
    Direction.UP: "up",
    Direction.DOWN: "down",
}


@register_drone("codrone_edu")
class CoDroneEduAdapter(DroneAdapter):
    """Adapter translating unified commands into CoDrone EDU API calls."""

    def __init__(self, name: str = "codrone_edu", port: Optional[str] = None) -> None:
        super().__init__(name=name)
        self._port = port
        self._drone: Any = None

    def connect(self, **kwargs: Any) -> None:
        port = kwargs.get("port", self._port)
        try:
            from CoDrone import CoDrone  # type: ignore[import-untyped]

            self._drone = CoDrone()
            if port:
                self._drone.pair(port)
            else:
                self._drone.pair()
            self._status = DroneStatus.CONNECTED
            logger.info("CoDrone EDU connected (port=%s)", port or "auto")
        except Exception as e:
            raise DroneConnectionError(f"CoDrone EDU pair failed: {e}") from e

    def disconnect(self) -> None:
        if self._drone:
            self._drone.close()
        self._status = DroneStatus.DISCONNECTED
        self._drone = None
        logger.info("CoDrone EDU disconnected")

    def takeoff(self) -> None:
        self._ensure_connected()
        self._drone.takeoff()
        self._status = DroneStatus.FLYING
        logger.info("CoDrone EDU takeoff")

    def land(self) -> None:
        self._ensure_connected()
        self._drone.land()
        self._status = DroneStatus.CONNECTED
        logger.info("CoDrone EDU landed")

    def emergency_stop(self) -> None:
        if self._drone:
            self._drone.emergency_stop()
        self._status = DroneStatus.CONNECTED
        logger.warning("CoDrone EDU emergency stop")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        dir_str = _DIRECTION_MAP.get(direction)
        if dir_str is None:
            raise DroneCommandError(f"Unsupported direction for CoDrone EDU: {direction}")
        power = int(min(max(speed, 0), 100))
        duration = max(distance, 0.1)
        self._drone.go(dir_str, power, duration)
        logger.info("CoDrone EDU move %s (power=%d, duration=%.1f)", dir_str, power, duration)

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        if degrees >= 0:
            self._drone.turn_right(int(degrees))
        else:
            self._drone.turn_left(int(abs(degrees)))
        logger.info("CoDrone EDU turn %.1f degrees", degrees)

    def hover(self, duration: float = 1.0) -> None:
        self._ensure_connected()
        self._drone.hover(int(duration))
        logger.info("CoDrone EDU hover %.1fs", duration)

    def set_led(self, color: LEDColor) -> None:
        self._ensure_connected()
        self._drone.set_drone_LED(color.red, color.green, color.blue, color.brightness)
        logger.info("CoDrone EDU LED set to (%d,%d,%d)", color.red, color.green, color.blue)

    def get_battery(self) -> int:
        self._ensure_connected()
        return self._drone.get_battery()

    def get_height(self) -> float:
        self._ensure_connected()
        # CoDrone EDU returns height in cm; convert to meters for the unified API
        try:
            return float(self._drone.get_height()) / 100.0
        except Exception as e:
            logger.warning("CoDrone EDU get_height failed: %s", e)
            return -1.0

    def _ensure_connected(self) -> None:
        if self._drone is None or self._status == DroneStatus.DISCONNECTED:
            raise DroneConnectionError("CoDrone EDU is not connected")
