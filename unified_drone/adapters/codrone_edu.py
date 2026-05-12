"""Adapter for the Robolink CoDrone EDU.

Verified against the official ``codrone_edu`` Python library documentation
(version 2.8). The library is imported lazily inside ``connect()``.

API translation reference:

    connect()       -> Drone().pair() / .pair(portname='COM3')
    disconnect()    -> drone.close()
    takeoff()       -> drone.takeoff()        (auto-hovers 1s at ~80 cm)
    land()          -> drone.land()
    emergency_stop  -> drone.emergency_stop()
    move()          -> drone.move_distance(x, y, z, velocity)
                       (x=forward+/back-, y=left+/right-, z=up+/down-,
                       velocity in m/s, max ~2.0)
    turn()          -> drone.turn(power, seconds)
                       (power -100..100; negative=right, positive=left;
                       framework convention +degrees = clockwise so we negate)
    hover()         -> drone.hover(duration)        (integer seconds)
    set_led()       -> drone.set_drone_LED(r, g, b, brightness)
                       (all 0-255; framework's 0-100 brightness is scaled)
    get_battery()   -> drone.get_battery()          (int percentage)
    get_height()    -> drone.get_height()           (height in cm -> meters)
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)


# Direction enum -> (x, y, z) axis vector for move_distance.
#   +x = forward, +y = left, +z = up   (per the CoDrone EDU coordinate frame)
_AXIS_VECTOR = {
    Direction.FORWARD:  (1, 0, 0),
    Direction.BACKWARD: (-1, 0, 0),
    Direction.LEFT:     (0, 1, 0),
    Direction.RIGHT:    (0, -1, 0),
    Direction.UP:       (0, 0, 1),
    Direction.DOWN:     (0, 0, -1),
}

# CoDrone EDU max horizontal velocity (per move_backward docs: max 2.0 m/s).
_MAX_VELOCITY_M_S = 2.0


@register_drone("codrone_edu")
class CoDroneEduAdapter(DroneAdapter):
    """Adapter wrapping the ``codrone_edu`` Python SDK (Robolink)."""

    def __init__(self, name: str = "codrone_edu", port: Optional[str] = None) -> None:
        super().__init__(name=name)
        self._port = port
        self._drone: Any = None

    # --- Lifecycle ---

    def connect(self, **kwargs: Any) -> None:
        port = kwargs.get("port", self._port)
        try:
            from codrone_edu.drone import Drone  # type: ignore[import-untyped]

            self._drone = Drone()
            if port:
                self._drone.pair(portname=port)
            else:
                self._drone.pair()
            self._status = DroneStatus.CONNECTED
            logger.info("CoDrone EDU paired (port=%s)", port or "auto")
        except Exception as e:
            raise DroneConnectionError(f"CoDrone EDU pair failed: {e}") from e

    def disconnect(self) -> None:
        if self._drone is not None:
            try:
                self._drone.close()
            except Exception as e:
                logger.warning("CoDrone EDU close failed: %s", e)
        self._status = DroneStatus.DISCONNECTED
        self._drone = None
        logger.info("CoDrone EDU disconnected")

    # --- Flight primitives (NATIVE) ---

    def takeoff(self) -> None:
        self._ensure_connected()
        self._drone.takeoff()
        self._status = DroneStatus.FLYING
        logger.info("CoDrone EDU takeoff (~80 cm, auto-hover 1s)")

    def land(self) -> None:
        self._ensure_connected()
        # Per docs: include hover() or sleep() before land() to prevent skipping.
        self._drone.hover(1)
        self._drone.land()
        self._status = DroneStatus.CONNECTED
        logger.info("CoDrone EDU land")

    def emergency_stop(self) -> None:
        if self._drone is not None:
            try:
                self._drone.emergency_stop()
            except Exception as e:
                logger.warning("CoDrone EDU emergency_stop failed: %s", e)
        self._status = DroneStatus.CONNECTED
        logger.warning("CoDrone EDU emergency stop")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        """Move the drone via ``move_distance(x, y, z, velocity)``.

        x = forward(+)/back(-), y = left(+)/right(-), z = up(+)/down(-),
        velocity = metres per second (max ~2.0).
        """
        self._ensure_connected()
        vec = _AXIS_VECTOR.get(direction)
        if vec is None:
            raise DroneCommandError(f"Unsupported direction for CoDrone EDU: {direction}")

        # Map framework speed (0-100%) to m/s, clamped to the SDK maximum.
        speed_clamped = max(0.0, min(100.0, speed))
        velocity_m_s = max(0.1, (speed_clamped / 100.0) * _MAX_VELOCITY_M_S)

        x = vec[0] * distance
        y = vec[1] * distance
        z = vec[2] * distance
        self._drone.move_distance(x, y, z, velocity_m_s)
        logger.info(
            "CoDrone EDU move_distance(x=%.2f, y=%.2f, z=%.2f, v=%.2f m/s) [%s]",
            x, y, z, velocity_m_s, direction.name,
        )

    def turn(self, degrees: float) -> None:
        """Rotate via ``turn(power, seconds)``.

        SDK convention: negative power = right (clockwise), positive = left.
        Framework convention: +degrees = clockwise.
        So a +90 framework turn maps to power=-50 with the appropriate duration.
        Heuristic: 50% power rotates at ~90 deg/sec.
        """
        self._ensure_connected()
        power = -50 if degrees > 0 else 50
        seconds = abs(degrees) / 90.0
        self._drone.turn(power=power, seconds=seconds)
        logger.info(
            "CoDrone EDU turn(power=%d, seconds=%.2f) for %.1f deg",
            power, seconds, degrees,
        )

    def hover(self, duration: float = 1.0) -> None:
        self._ensure_connected()
        self._drone.hover(int(duration))
        logger.info("CoDrone EDU hover %ds", int(duration))

    def set_led(self, color: LEDColor) -> None:
        """Set drone LED via ``set_drone_LED(r, g, b, brightness)``.

        Per docs, all four channels are 0-255. The unified ``LEDColor.brightness``
        uses a 0-100 scale, so we scale it to 0-255 here.
        """
        self._ensure_connected()
        b = max(0, min(100, color.brightness))
        brightness_sdk = int(b / 100.0 * 255)
        self._drone.set_drone_LED(
            int(color.red), int(color.green), int(color.blue), brightness_sdk
        )
        logger.info(
            "CoDrone EDU LED set_drone_LED(%d, %d, %d, %d) [framework brightness=%d%%]",
            color.red, color.green, color.blue, brightness_sdk, b,
        )

    # --- Telemetry (NATIVE) ---

    def get_battery(self) -> int:
        self._ensure_connected()
        try:
            return int(self._drone.get_battery())
        except Exception as e:
            logger.warning("CoDrone EDU get_battery failed: %s", e)
            return -1

    def get_height(self) -> float:
        """Return current altitude in metres (SDK returns centimetres)."""
        self._ensure_connected()
        try:
            cm = float(self._drone.get_height())
            return cm / 100.0
        except Exception as e:
            logger.warning("CoDrone EDU get_height failed: %s", e)
            return -1.0

    # --- Internal helpers ---

    def _ensure_connected(self) -> None:
        if self._drone is None or self._status == DroneStatus.DISCONNECTED:
            raise DroneConnectionError("CoDrone EDU is not connected")
