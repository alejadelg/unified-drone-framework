"""Mission task implemented WITHOUT the framework, using native libraries.

Task (identical to Version A):
    Connect 3 drones (CoDrone EDU, CodingRider, WIZWING),
    take off all three, fly a square pattern (forward 1 m, turn 90 deg, x4),
    hover 2 s, query battery on all, set LED to green on all,
    land all, disconnect all.

This version exposes everything that the framework normally hides:
  * 3 different connection patterns
        - CoDrone EDU:  Drone().pair(portname=...)
        - CodingRider:  Drone().open(port)
        - WIZWING:      serial.Serial(...) + b'connect\\r'
  * 3 different command surfaces
        - CoDrone EDU:  drone.takeoff() / drone.land() / drone.move_distance(...)
        - CodingRider:  drone.sendTakeOff() / drone.sendLanding() /
                        drone.sendControlWhile(roll,pitch,yaw,throttle,ms)
        - WIZWING:      ASCII text commands ('takeoff\\r', 'forward 250 1000\\r', ...)
  * Manual async->sync bridge for CodingRider telemetry
        (setEventHandler + sendRequest + threading.Event)
  * Manual hover compensation for WIZWING (no native hover command)
  * LED capability gap on WIZWING (only 'funled' preset cycle, no RGB)
  * Independent error handling per platform
"""

from __future__ import annotations

import logging
import sys
import time
from unittest.mock import MagicMock

# --- Make the script runnable without real hardware ---
sys.modules["codrone_edu"] = MagicMock()
sys.modules["codrone_edu.drone"] = MagicMock()
sys.modules["CodingRider"] = MagicMock()
sys.modules["CodingRider.drone"] = MagicMock()
sys.modules["CodingRider.protocol"] = MagicMock()
sys.modules["serial"] = MagicMock()

from codrone_edu.drone import Drone as CoDroneEDU  # type: ignore[import-not-found]
from CodingRider.drone import Drone as CodingRiderDrone  # type: ignore[import-not-found]
import serial                                          # type: ignore[import-not-found]

logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s")


# ====================================================================
# Per-platform setup (3 different patterns, 3 different error flavors)
# ====================================================================

def setup_codrone():
    drone = CoDroneEDU()  # codrone_edu.drone.Drone
    try:
        drone.pair(portname="COM4")
    except Exception as e:
        print(f"[CoDrone EDU] pair failed: {e}")
        return None
    return drone


def setup_coding_rider():
    drone = CodingRiderDrone()  # CodingRider.drone.Drone
    try:
        drone.open("COM3")
    except Exception as e:
        print(f"[CodingRider] open failed: {e}")
        return None
    return drone


def setup_wizwing():
    # WIZWING uses a text-based ASCII protocol over serial @ 9600 baud
    try:
        ser = serial.Serial(
            port="COM3",
            baudrate=9600,
            parity="N",
            stopbits=1,
            bytesize=8,
            timeout=8,
        )
        ser.write(b"connect\r")  # initial pairing
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
        codrone_obj.takeoff()                  # CoDrone EDU
    if rider_obj is not None:
        rider_obj.sendTakeOff()                # CodingRider
    if wiz_obj is not None:
        wiz_obj.write(b"takeoff\r")            # WIZWING (ASCII text)


def land_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        codrone_obj.land()
    if rider_obj is not None:
        rider_obj.sendControlWhile(0, 0, 0, 0, 500)  # stop motion first
        rider_obj.sendLanding()
    if wiz_obj is not None:
        wiz_obj.write(b"land\r")


def move_forward_1m(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        # CoDrone EDU: move_distance(x, y, z, velocity_m_s)
        codrone_obj.move_distance(1.0, 0, 0, 1.0)
    if rider_obj is not None:
        # CodingRider: sendControlWhile(roll, pitch, yaw, throttle, ms)
        rider_obj.sendControlWhile(0, 50, 0, 0, 1000)
    if wiz_obj is not None:
        # WIZWING: ASCII text "forward <strength> <ms>\r"
        wiz_obj.write(b"forward 250 1000\r")


def turn_90_cw(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        # CoDrone EDU: turn(power, seconds); negative power = right (CW)
        codrone_obj.turn(power=-50, seconds=1.0)
    if rider_obj is not None:
        # CodingRider: yaw negative = CW
        rider_obj.sendControlWhile(0, 0, -50, 0, 1000)
    if wiz_obj is not None:
        wiz_obj.write(b"cw 200 1000\r")


def hover_all(codrone_obj, rider_obj, wiz_obj, seconds: float):
    if codrone_obj is not None:
        # CoDrone EDU: native hover(seconds)
        codrone_obj.hover(int(seconds))
    if rider_obj is not None:
        # CodingRider: sendControlWhile(0,0,0,0,ms) with zero control = hover
        rider_obj.sendControlWhile(0, 0, 0, 0, int(seconds * 1000))
    if wiz_obj is not None:
        # WIZWING has no native hover; emulate with time.sleep
        time.sleep(seconds)


def get_battery_all(codrone_obj, rider_obj, wiz_obj):
    batteries = {}
    if codrone_obj is not None:
        # CoDrone EDU: synchronous get_battery() -> int percent
        batteries["codrone"] = codrone_obj.get_battery()
    if rider_obj is not None:
        # CodingRider: ASYNC pattern — register handler + send request + wait
        from CodingRider.protocol import DataType, DeviceType  # type: ignore[import-not-found]
        result = {"battery": -1}
        def on_state(state):
            result["battery"] = int(state.battery)
        rider_obj.setEventHandler(DataType.State, on_state)
        rider_obj.sendRequest(DeviceType.Drone, DataType.State)
        time.sleep(0.3)
        batteries["rider"] = result["battery"]
    if wiz_obj is not None:
        # WIZWING: write 'battery?\r' and read ASCII response line
        wiz_obj.write(b"battery?\r")
        line = wiz_obj.readline()
        try:
            batteries["wizwing"] = int(line.decode("ascii").strip())
        except Exception:
            batteries["wizwing"] = -1
    return batteries


def set_led_green_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        # CoDrone EDU: set_drone_LED(r, g, b, brightness 0-255)
        codrone_obj.set_drone_LED(0, 255, 0, 255)
    if rider_obj is not None:
        # CodingRider: sendLightModeColor(mode, interval, r, g, b)
        from CodingRider.protocol import LightModeDrone  # type: ignore[import-not-found]
        rider_obj.sendLightModeColor(LightModeDrone.BodyHold, 255, 0, 255, 0)
    if wiz_obj is not None:
        # WIZWING: only 'funled' (preset cycle); RGB ignored
        print("[WIZWING] LED limited to 'funled' preset cycle; green-specific not possible")
        wiz_obj.write(b"funled\r")


def disconnect_all(codrone_obj, rider_obj, wiz_obj):
    if codrone_obj is not None:
        try:
            codrone_obj.close()                    # CoDrone EDU
        except Exception as e:
            print(f"[CoDrone EDU] close error: {e}")
    if rider_obj is not None:
        try:
            rider_obj.close()                      # CodingRider (also close())
        except Exception as e:
            print(f"[CodingRider] close error: {e}")
    if wiz_obj is not None:
        try:
            wiz_obj.write(b"off\r")                # stop motors
            wiz_obj.close()                        # serial close
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
