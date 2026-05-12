"""Adapter for the CodingRider educational drone.

Wraps the CodingRider.drone module behind the unified DroneAdapter interface.
The library is imported lazily inside connect().

API translation reference (verified against the official CodingRider book):

    connect()       -> Drone().open(port)
    disconnect()    -> drone.close()
    takeoff()       -> drone.sendTakeOff()
    land()          -> drone.sendControlWhile(0, 0, 0, 0, 500)   (stop motion)
                       drone.sendLanding()
    emergency_stop  -> drone.sendStop()                          NATIVE primitive
    move()          -> drone.sendControlWhile(roll, pitch, yaw, throttle, ms)
                       direction is mapped to one of the 4 axes; duration is
                       derived from (distance, speed).
    turn()          -> drone.sendControlWhile(0, 0, yaw, 0, ms)
                       framework convention (positive = clockwise) is the
                       opposite of CodingRider's (positive = CCW); we negate.
    hover()         -> drone.sendControlWhile(0, 0, 0, 0, duration_ms)
                       zero control held for the requested duration; the FC
                       stabilises altitude.
    set_led()       -> drone.sendLightModeColor(LightModeDrone.BodyHold,
                                                 interval, R, G, B)
                       Brightness from LEDColor is applied in software by
                       scaling R, G, B (CodingRider has no brightness param).

    get_battery()   -> ASYNC->SYNC BRIDGE (COMPENSATORY)
                       drone.setEventHandler(DataType.State, cb)
                       drone.sendRequest(DeviceType.Drone, DataType.State)
                       The adapter blocks on threading.Event() until the
                       callback receives state.battery.

    get_height()    -> ASYNC->SYNC BRIDGE (COMPENSATORY)
                       Same pattern using DataType.Altitude; the callback
                       receives altitude.altitude.
"""

import logging
import threading
from typing import Any, Tuple

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)


# Direction -> (roll, pitch, yaw, throttle) sign for sendControlWhile.
# Magnitude is filled in from the speed argument at call time.
_AXIS_VECTOR = {
    Direction.FORWARD:  (0,  1, 0, 0),   # pitch+
    Direction.BACKWARD: (0, -1, 0, 0),   # pitch-
    Direction.LEFT:     (-1, 0, 0, 0),   # roll-
    Direction.RIGHT:    (1,  0, 0, 0),   # roll+
    Direction.UP:       (0,  0, 0, 1),   # throttle+
    Direction.DOWN:     (0,  0, 0, -1),  # throttle-
}

# Heuristic: at speed=100 (% of max input), the drone moves at ~1 m/s.
_MAX_SPEED_M_S = 1.0


@register_drone("coding_rider")
class CodingRiderAdapter(DroneAdapter):
    """Adapter translating unified commands into CodingRider API calls."""

    def __init__(self, name: str = "coding_rider") -> None:
        super().__init__(name=name)
        self._drone: Any = None

    # --- Lifecycle ---

    def connect(self, **kwargs: Any) -> None:
        port = kwargs.get("port", "COM3")
        try:
            from CodingRider.drone import Drone  # type: ignore[import-untyped]

            self._drone = Drone()
            self._drone.open(port)
            self._status = DroneStatus.CONNECTED
            logger.info("CodingRider connected on %s", port)
        except Exception as e:
            raise DroneConnectionError(f"CodingRider connect failed: {e}") from e

    def disconnect(self) -> None:
        if self._drone:
            try:
                self._drone.close()
            except Exception as e:
                logger.warning("CodingRider close failed: %s", e)
        self._status = DroneStatus.DISCONNECTED
        self._drone = None
        logger.info("CodingRider disconnected")

    # --- Flight primitives (NATIVE) ---

    def takeoff(self) -> None:
        self._ensure_connected()
        self._drone.sendTakeOff()
        self._status = DroneStatus.FLYING
        logger.info("CodingRider sendTakeOff")

    def land(self) -> None:
        self._ensure_connected()
        # The book example always stops motion before landing
        self._drone.sendControlWhile(0, 0, 0, 0, 500)
        self._drone.sendLanding()
        self._status = DroneStatus.CONNECTED
        logger.info("CodingRider sendLanding")

    def emergency_stop(self) -> None:
        """NATIVE: CodingRider exposes drone.sendStop() for emergency halt."""
        if self._drone:
            try:
                self._drone.sendStop()
            except Exception as e:
                logger.warning("CodingRider sendStop failed: %s", e)
        self._status = DroneStatus.CONNECTED
        logger.warning("CodingRider emergency stop via sendStop")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        sign = _AXIS_VECTOR.get(direction)
        if sign is None:
            raise DroneCommandError(f"Unsupported direction for CodingRider: {direction}")

        # Map (distance, speed) -> (control magnitude, duration_ms).
        # speed (0-100) is sent directly as the control input.
        # duration = distance / (speed/100 * max_speed)
        speed_input = int(max(0.0, min(100.0, speed)))
        if speed_input == 0:
            duration_ms = 0
        else:
            duration_ms = int(distance / (speed_input / 100.0 * _MAX_SPEED_M_S) * 1000)

        roll, pitch, yaw, throttle = (s * speed_input for s in sign)
        self._drone.sendControlWhile(roll, pitch, yaw, throttle, duration_ms)
        logger.info(
            "CodingRider sendControlWhile(roll=%d, pitch=%d, yaw=%d, throttle=%d, ms=%d)",
            roll, pitch, yaw, throttle, duration_ms,
        )

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        # Framework convention: +degrees = clockwise.
        # CodingRider convention: +yaw = counter-clockwise (left turn).
        # Negate so a +90 deg framework turn becomes -50 yaw input (CW).
        yaw_input = -50 if degrees > 0 else 50
        duration_ms = int(abs(degrees) / 90.0 * 1000)  # ~1 second per 90 deg
        self._drone.sendControlWhile(0, 0, yaw_input, 0, duration_ms)
        logger.info("CodingRider turn %.1f deg via sendControlWhile (ms=%d)", degrees, duration_ms)

    def hover(self, duration: float = 1.0) -> None:
        """NATIVE: sendControlWhile with zero control inputs holds the drone in place.

        This is the standard CodingRider idiom for 'do not move for N ms' — the
        flight controller's stabilisation maintains altitude automatically.
        """
        self._ensure_connected()
        duration_ms = int(duration * 1000)
        self._drone.sendControlWhile(0, 0, 0, 0, duration_ms)
        logger.info("CodingRider hover via sendControlWhile(0,0,0,0,%dms)", duration_ms)

    def set_led(self, color: LEDColor) -> None:
        """NATIVE: drone.sendLightModeColor(LightModeDrone.BodyHold, interval, R, G, B).

        Brightness from the unified LEDColor is applied in software (R/G/B are
        scaled by brightness/100) because the underlying API takes only RGB.
        """
        self._ensure_connected()
        try:
            from CodingRider.protocol import LightModeDrone  # type: ignore[import-untyped]
        except Exception as e:
            logger.warning("CodingRider LightModeDrone import failed: %s", e)
            return

        factor = max(0, min(color.brightness, 100)) / 100.0
        r = int(color.red * factor)
        g = int(color.green * factor)
        b = int(color.blue * factor)
        # interval=255 = solid (no blink) for BodyHold mode
        self._drone.sendLightModeColor(LightModeDrone.BodyHold, 255, r, g, b)
        logger.info("CodingRider LED set via sendLightModeColor: RGB=(%d,%d,%d)", r, g, b)

    # --- Telemetry (COMPENSATORY: async->sync event bridge) ---

    def get_battery(self) -> int:
        """Bridge CodingRider's async event-driven State telemetry to a sync return.

        CodingRider does NOT expose a synchronous drone.get_battery(). Battery
        telemetry arrives via an event callback. The adapter:
          1. Registers a callback for DataType.State.
          2. Sends sendRequest(DeviceType.Drone, DataType.State).
          3. Blocks on threading.Event() until the callback fires.
          4. Returns state.battery (or -1 on timeout).
        """
        self._ensure_connected()
        try:
            from CodingRider.protocol import DataType, DeviceType  # type: ignore[import-untyped]
        except Exception as e:
            logger.warning("CodingRider protocol import failed: %s", e)
            return -1

        result = {"battery": -1}
        received = threading.Event()

        def _on_state(state: Any) -> None:
            try:
                result["battery"] = int(state.battery)
            except Exception:
                pass
            received.set()

        self._drone.setEventHandler(DataType.State, _on_state)
        self._drone.sendRequest(DeviceType.Drone, DataType.State)
        logger.warning("CodingRider get_battery via async->sync event bridge")

        if received.wait(timeout=1.0):
            return result["battery"]
        logger.warning("CodingRider get_battery: timeout waiting for State event")
        return -1

    def get_height(self) -> float:
        """Bridge CodingRider's async event-driven Altitude telemetry to a sync return.

        Same pattern as get_battery but using DataType.Altitude; the callback
        receives an altitude object with .altitude as the metres value.
        """
        self._ensure_connected()
        try:
            from CodingRider.protocol import DataType, DeviceType  # type: ignore[import-untyped]
        except Exception as e:
            logger.warning("CodingRider protocol import failed: %s", e)
            return -1.0

        result = {"altitude": -1.0}
        received = threading.Event()

        def _on_altitude(altitude: Any) -> None:
            try:
                result["altitude"] = float(altitude.altitude)
            except Exception:
                pass
            received.set()

        self._drone.setEventHandler(DataType.Altitude, _on_altitude)
        self._drone.sendRequest(DeviceType.Drone, DataType.Altitude)
        logger.warning("CodingRider get_height via async->sync event bridge")

        if received.wait(timeout=1.0):
            return result["altitude"]
        logger.warning("CodingRider get_height: timeout waiting for Altitude event")
        return -1.0

    # --- Internal helpers ---

    def _ensure_connected(self) -> None:
        if self._drone is None or self._status == DroneStatus.DISCONNECTED:
            raise DroneConnectionError("CodingRider is not connected")
