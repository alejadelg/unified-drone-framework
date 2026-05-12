"""Adapter for the hypothetical SimDrone educational platform.

SimDrone is a Wi-Fi connected educational drone whose Python interface
exposes a text-based UDP socket protocol. It has several quirks that
require translation by the adapter:

  * Speed is specified in metres per second (0.0 - 10.0 m/s),
    not as a percentage (0 - 100).
  * Distances are specified in millimetres, not metres.
  * There is no combined RGB-LED command; the colour must be split into
    three independent single-channel commands.
  * The drone must be ARMED before takeoff and DISARMED after disconnect.

All of these differences are absorbed by this adapter, so user code keeps
using the unified DroneCommand API without change.

The adapter supports a ``simulated`` mode (default) that does not open a
real socket; it merely tracks internal state. That makes the class usable
for automated extensibility evaluation without requiring real hardware.
"""

from __future__ import annotations

import logging
import socket
import time
from typing import Any, Optional, Tuple

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)


# --- SimDrone protocol command verbs (text protocol) ---
_CMD_ARM = "arm"
_CMD_DISARM = "disarm"
_CMD_TAKEOFF = "takeoff"
_CMD_LAND = "land"
_CMD_EMERGENCY = "emergency"
_CMD_HOVER = "hover"
_CMD_GO = "go"
_CMD_ROTATE = "rotate"
_CMD_LED_R = "led_red"
_CMD_LED_G = "led_green"
_CMD_LED_B = "led_blue"


# --- Direction unit-vectors used to update internal position ---
_DIRECTION_VECTOR = {
    Direction.FORWARD: (0.0, 1.0, 0.0),
    Direction.BACKWARD: (0.0, -1.0, 0.0),
    Direction.LEFT: (-1.0, 0.0, 0.0),
    Direction.RIGHT: (1.0, 0.0, 0.0),
    Direction.UP: (0.0, 0.0, 1.0),
    Direction.DOWN: (0.0, 0.0, -1.0),
}


@register_drone("simdrone")
class MockDroneAdapter(DroneAdapter):
    """Adapter that connects the unified interface to the SimDrone protocol.

    Key responsibilities:
      * unit translation (m -> mm, percentage -> m/s);
      * compensation for missing primitives (combined LED command);
      * internal state tracking (position, yaw, battery, command counter);
      * graceful simulated mode for testing without a real device.
    """

    DEFAULT_HOST = "192.168.10.1"
    DEFAULT_PORT = 8889
    SPEED_MAX_MPS = 10.0  # SimDrone hardware limit

    def __init__(
        self,
        name: str = "simdrone",
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        simulated: bool = True,
    ) -> None:
        super().__init__(name=name)
        self._host = host
        self._port = port
        self._simulated = simulated
        self._socket: Optional[socket.socket] = None

        # --- Internal state ---
        self._x: float = 0.0
        self._y: float = 0.0
        self._z: float = 0.0
        self._yaw: float = 0.0
        self._battery: int = 100
        self._airborne: bool = False
        self._led_state: Tuple[int, int, int] = (0, 0, 0)
        self._command_count: int = 0

    # --- Public state inspectors (used by tests) ---

    @property
    def position(self) -> Tuple[float, float, float]:
        return (self._x, self._y, self._z)

    @property
    def yaw_degrees(self) -> float:
        return self._yaw

    @property
    def is_airborne(self) -> bool:
        return self._airborne

    @property
    def commands_sent(self) -> int:
        return self._command_count

    # --- Lifecycle ---

    def connect(self, **kwargs: Any) -> None:
        host = kwargs.get("host", self._host)
        port = kwargs.get("port", self._port)
        try:
            if not self._simulated:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self._socket.settimeout(2.0)
                self._socket.connect((host, port))
            self._send(_CMD_ARM)
            self._status = DroneStatus.CONNECTED
            logger.info("SimDrone connected to %s:%d (sim=%s)", host, port, self._simulated)
        except Exception as e:
            raise DroneConnectionError(f"SimDrone connect failed: {e}") from e

    def disconnect(self) -> None:
        try:
            self._send(_CMD_DISARM)
        except Exception:
            pass  # best effort on disconnect
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._status = DroneStatus.DISCONNECTED
        logger.info("SimDrone disconnected")

    # --- Flight ---

    def takeoff(self) -> None:
        self._ensure_connected()
        self._send(_CMD_TAKEOFF)
        self._airborne = True
        self._z = 1.0  # default takeoff altitude
        self._consume_battery(2)
        self._status = DroneStatus.FLYING
        logger.info("SimDrone takeoff -> z=%.1fm", self._z)

    def land(self) -> None:
        self._ensure_connected()
        self._send(_CMD_LAND)
        self._airborne = False
        self._z = 0.0
        self._consume_battery(2)
        self._status = DroneStatus.CONNECTED
        logger.info("SimDrone landed")

    def emergency_stop(self) -> None:
        self._send(_CMD_EMERGENCY)
        self._airborne = False
        self._status = DroneStatus.CONNECTED
        logger.warning("SimDrone emergency stop")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        vector = _DIRECTION_VECTOR.get(direction)
        if vector is None:
            raise DroneCommandError(f"Unsupported direction for SimDrone: {direction}")

        # --- Unit translation: framework -> SimDrone ---
        distance_mm = int(distance * 1000)                          # m  -> mm
        speed_mps = (max(0.0, min(speed, 100.0)) / 100.0) * self.SPEED_MAX_MPS  # % -> m/s

        cmd = (
            f"{_CMD_GO} {distance_mm} {speed_mps:.2f} "
            f"{vector[0]:.1f} {vector[1]:.1f} {vector[2]:.1f}"
        )
        self._send(cmd)

        # Update tracked position
        self._x += vector[0] * distance
        self._y += vector[1] * distance
        self._z += vector[2] * distance
        self._consume_battery(1)

        logger.info(
            "SimDrone move %s dist=%dmm speed=%.2fm/s -> pos=(%.2f, %.2f, %.2f)",
            direction.name, distance_mm, speed_mps, self._x, self._y, self._z,
        )

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        self._send(f"{_CMD_ROTATE} {int(degrees)}")
        self._yaw = (self._yaw + degrees) % 360.0
        self._consume_battery(1)
        logger.info("SimDrone turn %.1fdeg -> yaw=%.1f", degrees, self._yaw)

    def hover(self, duration: float = 1.0) -> None:
        self._ensure_connected()
        self._send(f"{_CMD_HOVER} {duration:.2f}")
        if not self._simulated:
            time.sleep(duration)
        self._consume_battery(1)
        logger.info("SimDrone hover %.1fs", duration)

    # --- LED (compensatory mechanism: 1 logical -> 3 protocol commands) ---

    def set_led(self, color: LEDColor) -> None:
        """SimDrone has no combined RGB LED command.

        We split the unified set_led() call into three single-channel
        commands and apply the brightness factor in software. This is
        invisible to the user; the unified API stays clean.
        """
        self._ensure_connected()
        b = max(0, min(color.brightness, 100)) / 100.0
        r = int(color.red * b)
        g = int(color.green * b)
        bl = int(color.blue * b)
        self._send(f"{_CMD_LED_R} {r}")
        self._send(f"{_CMD_LED_G} {g}")
        self._send(f"{_CMD_LED_B} {bl}")
        self._led_state = (r, g, bl)
        logger.info("SimDrone LED set via 3 channels -> RGB=(%d,%d,%d)", r, g, bl)

    # --- Telemetry ---

    def get_battery(self) -> int:
        self._ensure_connected()
        return self._battery

    def get_height(self) -> float:
        # SimDrone exposes height via the same protocol channel as position;
        # we already track it natively in self._z (metres).
        self._ensure_connected()
        return self._z

    # --- Internal helpers ---

    def _send(self, cmd: str) -> None:
        """Send a command string. In simulated mode this is a no-op."""
        self._command_count += 1
        if self._simulated:
            logger.debug("SimDrone (sim) TX [#%d]: %s", self._command_count, cmd)
            return
        if self._socket is None:
            raise DroneConnectionError("SimDrone socket is not open")
        self._socket.sendall(cmd.encode("utf-8"))

    def _ensure_connected(self) -> None:
        if self._status == DroneStatus.DISCONNECTED:
            raise DroneConnectionError("SimDrone is not connected")

    def _consume_battery(self, amount: int) -> None:
        self._battery = max(0, self._battery - amount)
