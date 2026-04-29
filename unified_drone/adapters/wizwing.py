"""Adapter for the WIZWING drone controlled via pyserial.

Sends raw byte command packets over a serial port. The protocol uses a simple
packet format: [HEADER][CMD][LEN][PAYLOAD...][CHECKSUM][FOOTER].

The pyserial library is imported lazily inside connect().

API translation reference:
    connect()      -> serial.Serial(port, baudrate)
    disconnect()   -> serial.close()
    takeoff()      -> packet(CMD=0x01)
    land()         -> packet(CMD=0x02)
    emergency_stop -> packet(CMD=0x03)
    move()         -> packet(CMD=0x04, payload=[dir, dist_cm, speed])
    turn()         -> packet(CMD=0x05, payload=[sign, degrees])
    hover()        -> packet(CMD=0x06, payload=[duration_ms])
    set_led()      -> packet(CMD=0x07, payload=[r, g, b, brightness])
    get_battery()  -> packet(CMD=0x08) + read response
"""

import logging
import struct
from typing import Any, Optional

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)


class _WizwingCmd:
    """WIZWING serial protocol command identifiers."""

    HEADER = 0xAA
    TAKEOFF = 0x01
    LAND = 0x02
    EMERGENCY = 0x03
    MOVE = 0x04
    TURN = 0x05
    HOVER = 0x06
    LED = 0x07
    BATTERY_REQ = 0x08
    FOOTER = 0x55


_DIR_BYTE = {
    Direction.FORWARD: 0x01,
    Direction.BACKWARD: 0x02,
    Direction.LEFT: 0x03,
    Direction.RIGHT: 0x04,
    Direction.UP: 0x05,
    Direction.DOWN: 0x06,
}


def _checksum(payload: bytes) -> int:
    """Calculate a simple additive checksum (mod 256)."""
    return sum(payload) & 0xFF


def _build_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    """Build a WIZWING serial packet.

    Format: [HEADER][CMD][LEN][PAYLOAD...][CHECKSUM][FOOTER]
    Checksum covers CMD + LEN + PAYLOAD.
    """
    length = len(payload)
    body = bytes([cmd_id, length]) + payload
    chk = _checksum(body)
    return bytes([_WizwingCmd.HEADER]) + body + bytes([chk, _WizwingCmd.FOOTER])


@register_drone("wizwing")
class WizwingAdapter(DroneAdapter):
    """Adapter translating unified commands into WIZWING serial byte packets."""

    def __init__(
        self,
        name: str = "wizwing",
        port: str = "COM3",
        baudrate: int = 115200,
    ) -> None:
        super().__init__(name=name)
        self._port = port
        self._baudrate = baudrate
        self._serial: Any = None

    def connect(self, **kwargs: Any) -> None:
        port = kwargs.get("port", self._port)
        baudrate = kwargs.get("baudrate", self._baudrate)
        try:
            import serial  # type: ignore[import-untyped]

            self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=2)
            self._status = DroneStatus.CONNECTED
            logger.info("WIZWING connected on %s @ %d", port, baudrate)
        except Exception as e:
            raise DroneConnectionError(f"WIZWING serial open failed: {e}") from e

    def disconnect(self) -> None:
        if self._serial and self._serial.is_open:
            self._serial.close()
        self._status = DroneStatus.DISCONNECTED
        self._serial = None
        logger.info("WIZWING disconnected")

    def takeoff(self) -> None:
        self._send_packet(_build_packet(_WizwingCmd.TAKEOFF))
        self._status = DroneStatus.FLYING
        logger.info("WIZWING takeoff")

    def land(self) -> None:
        self._send_packet(_build_packet(_WizwingCmd.LAND))
        self._status = DroneStatus.CONNECTED
        logger.info("WIZWING landed")

    def emergency_stop(self) -> None:
        self._send_packet(_build_packet(_WizwingCmd.EMERGENCY))
        self._status = DroneStatus.CONNECTED
        logger.warning("WIZWING emergency stop")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        dir_byte = _DIR_BYTE.get(direction)
        if dir_byte is None:
            raise DroneCommandError(f"Unsupported direction for WIZWING: {direction}")
        dist_cm = int(distance * 100)
        payload = struct.pack(">BHB", dir_byte, dist_cm, int(speed))
        self._send_packet(_build_packet(_WizwingCmd.MOVE, payload))
        logger.info("WIZWING move dir=0x%02X dist=%dcm speed=%d", dir_byte, dist_cm, int(speed))

    def turn(self, degrees: float) -> None:
        sign = 0x00 if degrees >= 0 else 0x01
        payload = struct.pack(">BH", sign, int(abs(degrees)))
        self._send_packet(_build_packet(_WizwingCmd.TURN, payload))
        logger.info("WIZWING turn %.1f degrees", degrees)

    def hover(self, duration: float = 1.0) -> None:
        payload = struct.pack(">H", int(duration * 1000))
        self._send_packet(_build_packet(_WizwingCmd.HOVER, payload))
        logger.info("WIZWING hover %.1fs", duration)

    def set_led(self, color: LEDColor) -> None:
        payload = bytes([color.red, color.green, color.blue, color.brightness])
        self._send_packet(_build_packet(_WizwingCmd.LED, payload))
        logger.info("WIZWING LED set to (%d,%d,%d)", color.red, color.green, color.blue)

    def get_battery(self) -> int:
        self._send_packet(_build_packet(_WizwingCmd.BATTERY_REQ))
        response = self._read_response(expected_cmd=_WizwingCmd.BATTERY_REQ)
        if response and len(response) >= 1:
            return response[0]
        return -1

    # --- Internal helpers ---

    def _send_packet(self, packet: bytes) -> None:
        self._ensure_connected()
        logger.debug("WIZWING TX: %s", packet.hex())
        self._serial.write(packet)

    def _read_response(self, expected_cmd: int) -> Optional[bytes]:
        """Read and parse a response packet from the WIZWING drone."""
        self._ensure_connected()
        header = self._serial.read(3)  # [HEADER, CMD, LEN]
        if len(header) < 3 or header[0] != _WizwingCmd.HEADER:
            return None
        cmd, length = header[1], header[2]
        payload = self._serial.read(length)
        self._serial.read(2)  # [CHECKSUM, FOOTER]
        if cmd != expected_cmd:
            logger.warning("WIZWING unexpected response cmd: 0x%02X", cmd)
            return None
        return payload

    def _ensure_connected(self) -> None:
        if self._serial is None or not self._serial.is_open:
            raise DroneConnectionError("WIZWING serial port not open")
