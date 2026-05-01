"""Mission task implemented WITHOUT the framework, using native libraries.

Task (identical to Version A):
    Connect 3 drones (CoDrone EDU, CodingRider, WIZWING),
    take off all three, fly a square pattern (forward 1 m, turn 90 deg, x4),
    hover 2 s, query battery on all, set LED to green on all,
    land all, disconnect all.

This version exposes everything that the framework normally hides:
  * 3 different connection patterns (pair / connect / Serial())
  * 3 different naming conventions (.land vs .landing vs raw 0x02 byte)
  * 3 different parameter conventions
        - CoDrone:     go(direction_str, power, duration_s)
        - CodingRider: go(direction_code, distance_cm, speed)
        - WIZWING:     raw byte packet with struct.pack
  * Manual hover compensation for CodingRider (no native primitive)
  * LED skip for CodingRider (limited support)
  * Manual request/response decoding for the WIZWING battery query
  * Independent error handling per platform
"""

from __future__ import annotations

import logging
import struct
import sys
import time
from unittest.mock import MagicMock

# --- Make the script runnable without real hardware ---
sys.modules["CoDrone"] = MagicMock()
sys.modules["CodingRider"] = MagicMock()
sys.modules["CodingRider.drone"] = MagicMock()
sys.modules["serial"] = MagicMock()

from CoDrone import CoDrone               # type: ignore[import-not-found]
from CodingRider import drone as cr_drone  # type: ignore[import-not-found]
import serial                              # type: ignore[import-not-found]

logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s")


# ====================================================================
# WIZWING serial protocol (we have to hand-code it here because there
# is no Python library for the WIZWING — only raw bytes over a serial
# port).
# ====================================================================

WIZ_HEADER = 0xAA
WIZ_FOOTER = 0x55
WIZ_TAKEOFF = 0x01
WIZ_LAND = 0x02
WIZ_MOVE = 0x04
WIZ_TURN = 0x05
WIZ_HOVER = 0x06
WIZ_LED = 0x07
WIZ_BATTERY_REQ = 0x08
WIZ_DIR_FORWARD = 0x01


def wiz_build_packet(cmd_id: int, payload: bytes = b"") -> bytes:
    length = len(payload)
    body = bytes([cmd_id, length]) + payload
    chk = sum(body) & 0xFF
    return bytes([WIZ_HEADER]) + body + bytes([chk, WIZ_FOOTER])


# ====================================================================
# Per-platform setup (3 different patterns, 3 different error flavors)
# ====================================================================

def setup_codrone():
    drone = CoDrone()
    try:
        drone.pair("COM4")
    except Exception as e:
        print(f"[CoDrone] pair failed: {e}")
        return None
    return drone


def setup_coding_rider():
    try:
        cr_drone.connect()
    except Exception as e:
        print(f"[CodingRider] connect failed: {e}")
        return None
    return cr_drone


def setup_wizwing():
    try:
        ser = serial.Serial(port="COM3", baudrate=115200, timeout=2)
    except Exception as e:
        print(f"[WIZWING] serial open failed: {e}")
        return None
    return ser


# ====================================================================
# Per-operation broadcast: every logical action expands into 3 lines
# of vendor-specific code. Note the divergent method names and units.
# ====================================================================

def takeoff_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        codrone_obj.takeoff()
    if rider_obj is not None:
        rider_obj.takeoff()
    if wiz_obj is not None:
        wiz_obj.write(wiz_build_packet(WIZ_TAKEOFF))


def land_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        codrone_obj.land()
    if rider_obj is not None:
        rider_obj.landing()  # different method name!
    if wiz_obj is not None:
        wiz_obj.write(wiz_build_packet(WIZ_LAND))


def move_forward_1m(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        # CoDrone: go(direction_str, power 0-100, duration_seconds)
        codrone_obj.go("forward", 50, 1)
    if rider_obj is not None:
        # CodingRider: go(direction_code, distance_cm, speed)
        rider_obj.go(0, 100, 50)
    if wiz_obj is not None:
        # WIZWING: raw packet (direction, dist_cm uint16 BE, speed)
        payload = struct.pack(">BHB", WIZ_DIR_FORWARD, 100, 50)
        wiz_obj.write(wiz_build_packet(WIZ_MOVE, payload))


def turn_90_cw(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        codrone_obj.turn_right(90)
    if rider_obj is not None:
        rider_obj.turn(90)
    if wiz_obj is not None:
        payload = struct.pack(">BH", 0x00, 90)
        wiz_obj.write(wiz_build_packet(WIZ_TURN, payload))


def hover_all(codrone_obj, rider_obj, wiz_obj, seconds: float):
    if codrone_obj is not None:
        codrone_obj.hover(int(seconds))
    if rider_obj is not None:
        # No native hover on CodingRider — emulate with sleep
        time.sleep(seconds)
    if wiz_obj is not None:
        payload = struct.pack(">H", int(seconds * 1000))
        wiz_obj.write(wiz_build_packet(WIZ_HOVER, payload))


def get_battery_all(codrone_obj, rider_obj, wiz_obj):
    batteries = {}
    if codrone_obj is not None:
        batteries["codrone"] = codrone_obj.get_battery()
    if rider_obj is not None:
        # CodingRider may not implement get_battery on every firmware
        if hasattr(rider_obj, "get_battery"):
            batteries["rider"] = rider_obj.get_battery()
        else:
            batteries["rider"] = -1
    if wiz_obj is not None:
        # WIZWING uses request/response over serial — we have to parse the packet
        wiz_obj.write(wiz_build_packet(WIZ_BATTERY_REQ))
        header = wiz_obj.read(3)
        if isinstance(header, (bytes, bytearray)) and len(header) >= 3 and header[0] == WIZ_HEADER:
            payload = wiz_obj.read(header[2])
            wiz_obj.read(2)  # checksum + footer
            batteries["wizwing"] = payload[0] if payload else -1
        else:
            batteries["wizwing"] = -1
    return batteries


def set_led_green_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        codrone_obj.set_drone_LED(0, 255, 0, 100)
    if rider_obj is not None:
        # CodingRider LED is unreliable; we skip with a warning
        print("[CodingRider] LED control not supported; skipping")
    if wiz_obj is not None:
        payload = bytes([0, 255, 0, 100])
        wiz_obj.write(wiz_build_packet(WIZ_LED, payload))


def disconnect_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        try:
            codrone_obj.close()  # CoDrone uses close()
        except Exception as e:
            print(f"[CoDrone] close error: {e}")
    if rider_obj is not None:
        try:
            rider_obj.disconnect()  # CodingRider uses disconnect()
        except Exception as e:
            print(f"[CodingRider] disconnect error: {e}")
    if wiz_obj is not None:
        try:
            wiz_obj.close()  # serial.Serial uses close()
        except Exception as e:
            print(f"[WIZWING] close error: {e}")


# ====================================================================
# Mission entry point
# ====================================================================

def run_mission() -> None:
    codrone_obj = setup_codrone()
    rider_obj = setup_coding_rider()
    wiz_obj = setup_wizwing()

    takeoff_all(codrone_obj, rider_obj, wiz_obj)

    for _ in range(4):
        move_forward_1m(codrone_obj, rider_obj, wiz_obj)
        turn_90_cw(codrone_obj, rider_obj, wiz_obj)

    hover_all(codrone_obj, rider_obj, wiz_obj, 2.0)
    batteries = get_battery_all(codrone_obj, rider_obj, wiz_obj)
    print(f"Batteries: {batteries}")
    set_led_green_all(codrone_obj, rider_obj, wiz_obj)

    land_all(codrone_obj, rider_obj, wiz_obj)
    disconnect_all(codrone_obj, rider_obj, wiz_obj)


if __name__ == "__main__":
    run_mission()
    print("Mission complete (Version B: native)")
