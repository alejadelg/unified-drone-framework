"""Adapter for the WIZWING drone (text-based ASCII serial protocol).

Verified against the official WIZWING / R4-A controller documentation. The
WIZWING is controlled by a simple text shell over a serial port at 9600 baud.
Every command is an ASCII string terminated by carriage return (``\\r``), and
telemetry queries return ASCII lines that the host reads with
``ser.readline()``.

API translation reference:

    connect()       -> serial.Serial(port=..., baudrate=9600,
                                     parity='N', stopbits=1,
                                     bytesize=8, timeout=8)
                       drone.write(b'connect\\r')
    disconnect()    -> drone.write(b'off\\r') then serial.close()
    takeoff()       -> 'takeoff\\r'
    land()          -> 'land\\r'
    emergency_stop  -> 'emergency\\r'
    move()          -> '<verb> <strength> <duration_ms>\\r'
                       where verb is one of {forward, back, left, right,
                       up, down} and strength is 20-500.
    turn()          -> 'cw <strength> <ms>\\r' or 'ccw <strength> <ms>\\r'
                       (framework convention: +degrees = clockwise)
    set_led()       -> COMPENSATORY: WIZWING only exposes ``funled`` (a
                       toggle that cycles preset colours). Arbitrary RGB
                       cannot be specified. The adapter sends 'funled\\r'
                       and warns that the requested colour was ignored.
    hover()         -> COMPENSATORY: WIZWING has no native hover command.
                       The drone naturally stabilises when no movement
                       command is sent, so the adapter blocks via
                       ``time.sleep(duration)`` to emulate hover.
    get_battery()   -> 'battery?\\r' then read response line; parses the
                       first integer found.
    get_height()    -> 'height?\\r' then read response line; parses the
                       first float found.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)


# Framework Direction -> WIZWING text verb
_DIRECTION_VERB = {
    Direction.FORWARD: "forward",
    Direction.BACKWARD: "back",
    Direction.LEFT: "left",
    Direction.RIGHT: "right",
    Direction.UP: "up",
    Direction.DOWN: "down",
}

# Heuristic: at max joystick strength (500), the drone moves ~1 m/s.
_MAX_SPEED_M_S = 1.0


@register_drone("wizwing")
class WizwingAdapter(DroneAdapter):
    """Adapter wrapping the WIZWING ASCII text protocol over pyserial."""

    DEFAULT_BAUDRATE = 9600

    def __init__(
        self,
        name: str = "wizwing",
        port: str = "COM3",
        baudrate: int = DEFAULT_BAUDRATE,
    ) -> None:
        super().__init__(name=name)
        self._port = port
        self._baudrate = baudrate
        self._serial: Any = None

    # --- Lifecycle ---

    def connect(self, **kwargs: Any) -> None:
        port = kwargs.get("port", self._port)
        baudrate = kwargs.get("baudrate", self._baudrate)
        try:
            import serial  # type: ignore[import-untyped]

            self._serial = serial.Serial(
                port=port,
                baudrate=baudrate,
                parity="N",
                stopbits=1,
                bytesize=8,
                timeout=8,
            )
            # Pairing command per the WIZWING sample (cable-attached auto-pair)
            self._send("connect")
            self._status = DroneStatus.CONNECTED
            logger.info("WIZWING connected on %s @ %d baud", port, baudrate)
        except Exception as e:
            raise DroneConnectionError(f"WIZWING serial open failed: {e}") from e

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                if self._serial.is_open:
                    self._send("off")  # stop motors, best effort
                    self._serial.close()
            except Exception as e:
                logger.warning("WIZWING close failed: %s", e)
        self._status = DroneStatus.DISCONNECTED
        self._serial = None
        logger.info("WIZWING disconnected")

    # --- Flight primitives (NATIVE) ---

    def takeoff(self) -> None:
        self._send("takeoff")
        self._status = DroneStatus.FLYING
        logger.info("WIZWING takeoff")

    def land(self) -> None:
        self._send("land")
        self._status = DroneStatus.CONNECTED
        logger.info("WIZWING land")

    def emergency_stop(self) -> None:
        try:
            self._send("emergency")
        except Exception as e:
            logger.warning("WIZWING emergency send failed: %s", e)
        self._status = DroneStatus.CONNECTED
        logger.warning("WIZWING emergency stop")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        verb = _DIRECTION_VERB.get(direction)
        if verb is None:
            raise DroneCommandError(f"Unsupported direction for WIZWING: {direction}")

        # Translate units:
        #   framework speed (0-100%) -> WIZWING joystick strength (20-500)
        #   framework distance (m) + speed -> WIZWING duration (ms)
        speed_clamped = max(0.0, min(100.0, speed))
        strength = max(20, min(500, int(speed_clamped * 5)))
        if speed_clamped == 0:
            duration_ms = 0
        else:
            duration_ms = int(
                distance / (speed_clamped / 100.0 * _MAX_SPEED_M_S) * 1000
            )

        self._send(f"{verb} {strength} {duration_ms}")
        logger.info(
            "WIZWING move %s strength=%d duration=%dms (distance=%.2fm, speed=%.0f%%)",
            verb, strength, duration_ms, distance, speed_clamped,
        )

    def turn(self, degrees: float) -> None:
        # Framework: +degrees = clockwise; WIZWING: 'cw' / 'ccw' commands.
        verb = "cw" if degrees > 0 else "ccw"
        # Assume strength=200 rotates at ~90 deg/sec; tune as needed.
        strength = 200
        duration_ms = int(abs(degrees) / 90.0 * 1000)
        self._send(f"{verb} {strength} {duration_ms}")
        logger.info(
            "WIZWING turn %s strength=%d duration=%dms (degrees=%.1f)",
            verb, strength, duration_ms, degrees,
        )

    # --- Compensatory mechanisms ---

    def hover(self, duration: float = 1.0) -> None:
        """COMPENSATORY: WIZWING has no native hover command.

        The drone naturally maintains position when no movement command is
        active (its flight controller stabilises altitude). We emulate the
        hover semantics by blocking the caller for the requested duration
        without sending any motion command.
        """
        self._ensure_connected()
        logger.warning(
            "WIZWING hover emulated via time.sleep (no native hover command)"
        )
        time.sleep(duration)

    def set_led(self, color: LEDColor) -> None:
        """COMPENSATORY: WIZWING only exposes 'funled' (a preset 4-colour cycle).

        Arbitrary RGB cannot be specified. The adapter sends the 'funled'
        command and warns that the requested colour was ignored. Calling
        ``set_led`` again toggles the LED on / off.
        """
        self._ensure_connected()
        logger.warning(
            "WIZWING set_led: only 'funled' (preset 4-colour cycle) available; "
            "requested RGB=(%d,%d,%d) ignored",
            color.red, color.green, color.blue,
        )
        self._send("funled")

    # --- Telemetry (NATIVE) ---

    def get_battery(self) -> int:
        """Request battery level via 'battery?' and parse the ASCII response."""
        self._send("battery?")
        response = self._read_response()
        return self._parse_int(response, fallback=-1)

    def get_height(self) -> float:
        """Request barometer-derived height via 'height?' and parse response."""
        self._send("height?")
        response = self._read_response()
        return self._parse_float(response, fallback=-1.0)

    # --- Internal helpers ---

    def _send(self, command: str) -> None:
        """Send an ASCII text command terminated by carriage return."""
        self._ensure_connected()
        payload = (command + "\r").encode("ascii")
        logger.debug("WIZWING TX: %r", payload)
        self._serial.write(payload)

    def _read_response(self) -> Optional[str]:
        """Read one line from the serial port; return decoded string or None."""
        if self._serial is None or not self._serial.is_open:
            return None
        try:
            if self._serial.readable():
                line = self._serial.readline()
                if line:
                    return line.decode("ascii", errors="replace").rstrip()
        except Exception as e:
            logger.warning("WIZWING readline failed: %s", e)
        return None

    def _ensure_connected(self) -> None:
        if self._serial is None or not getattr(self._serial, "is_open", False):
            raise DroneConnectionError("WIZWING serial port is not open")

    @staticmethod
    def _parse_int(s: Optional[str], fallback: int = -1) -> int:
        """Extract the first integer from a response string."""
        if not s:
            return fallback
        match = re.search(r"-?\d+", s)
        return int(match.group()) if match else fallback

    @staticmethod
    def _parse_float(s: Optional[str], fallback: float = -1.0) -> float:
        """Extract the first floating-point number from a response string."""
        if not s:
            return fallback
        match = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(match.group()) if match else fallback
