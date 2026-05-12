"""Mission task implemented WITHOUT the framework, using native libraries.

Executes the same canonical 11-step mission as ``version_a_framework.py``
and ``eval_interoperability.py``, but using the three vendor SDKs
directly. Every logical step must be expanded into per-vendor branches
because the SDKs disagree on names, parameter units, and interaction
paradigms.

What this version exposes that the framework normally hides:

  * 3 different connection patterns
        - CoDrone EDU:  Drone().pair(portname=...)
        - CodingRider:  Drone().open(port)
        - WIZWING:      serial.Serial(...) + b'connect\\r'

  * 3 different command surfaces
        - CoDrone EDU:  drone.takeoff() / drone.move_distance(x,y,z,v) / ...
        - CodingRider:  drone.sendTakeOff() /
                        drone.sendControlWhile(roll,pitch,yaw,throttle,ms) /
                        drone.sendLightModeColor(...) / ...
        - WIZWING:      ASCII text ('takeoff\\r', 'forward 250 1000\\r', ...)

  * Manual async->sync bridge for CodingRider telemetry
        (setEventHandler + sendRequest + sleep)

  * Manual hover compensation for WIZWING (no native hover)

  * LED capability gap on WIZWING (only 'funled' preset; no RGB)
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

from codrone_edu.drone import Drone as CoDroneEDU              # type: ignore[import-not-found]
from CodingRider.drone import Drone as CodingRiderDrone        # type: ignore[import-not-found]
import serial                                                   # type: ignore[import-not-found]

logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s")


# ====================================================================
# Per-platform setup (3 different connection patterns)
# ====================================================================

def setup_codrone():
    drone = CoDroneEDU()
    try:
        drone.pair(portname="COM4")
    except Exception as e:
        print(f"[CoDrone EDU] pair failed: {e}")
        return None
    return drone


def setup_coding_rider():
    drone = CodingRiderDrone()
    try:
        drone.open("COM3")
    except Exception as e:
        print(f"[CodingRider] open failed: {e}")
        return None
    return drone


def setup_wizwing():
    try:
        ser = serial.Serial(
            port="COM3", baudrate=9600,
            parity="N", stopbits=1, bytesize=8, timeout=8,
        )
        ser.write(b"connect\r")
    except Exception as e:
        print(f"[WIZWING] serial open failed: {e}")
        return None
    return ser


# ====================================================================
# Per-step broadcast helpers — one per command of the standard mission
# ====================================================================

def takeoff_all(codrone, rider, wiz):
    if codrone is not None:
        codrone.takeoff()
    if rider is not None:
        rider.sendTakeOff()
    if wiz is not None:
        wiz.write(b"takeoff\r")


def hover_all(codrone, rider, wiz, seconds: float):
    if codrone is not None:
        codrone.hover(int(seconds))
    if rider is not None:
        rider.sendControlWhile(0, 0, 0, 0, int(seconds * 1000))
    if wiz is not None:
        time.sleep(seconds)  # COMPENSATORY: no native hover


def move_forward_all(codrone, rider, wiz, distance: float, speed: float):
    if codrone is not None:
        velocity_m_s = max(0.1, (speed / 100.0) * 2.0)
        codrone.move_distance(distance, 0, 0, velocity_m_s)
    if rider is not None:
        duration_ms = int(distance / max(0.01, speed / 100.0) * 1000)
        rider.sendControlWhile(0, int(speed), 0, 0, duration_ms)
    if wiz is not None:
        strength = max(20, min(500, int(speed * 5)))
        duration_ms = int(distance / max(0.01, speed / 100.0) * 1000)
        wiz.write(f"forward {strength} {duration_ms}\r".encode("ascii"))


def turn_cw_all(codrone, rider, wiz, degrees: float):
    if codrone is not None:
        codrone.turn(power=-50, seconds=abs(degrees) / 90.0)
    if rider is not None:
        rider.sendControlWhile(0, 0, -50, 0, int(abs(degrees) / 90.0 * 1000))
    if wiz is not None:
        wiz.write(f"cw 200 {int(abs(degrees) / 90.0 * 1000)}\r".encode("ascii"))


def get_battery_all(codrone, rider, wiz):
    batteries = {}
    if codrone is not None:
        batteries["codrone"] = codrone.get_battery()
    if rider is not None:
        # CodingRider: ASYNC pattern — register handler + send request + wait
        from CodingRider.protocol import DataType, DeviceType  # type: ignore[import-not-found]
        result = {"battery": -1}
        def on_state(state):
            try:
                result["battery"] = int(state.battery)
            except Exception:
                pass
        rider.setEventHandler(DataType.State, on_state)
        rider.sendRequest(DeviceType.Drone, DataType.State)
        time.sleep(0.3)
        batteries["rider"] = result["battery"]
    if wiz is not None:
        wiz.write(b"battery?\r")
        line = wiz.readline()
        try:
            batteries["wizwing"] = int(line.decode("ascii").strip())
        except Exception:
            batteries["wizwing"] = -1
    return batteries


def get_height_all(codrone, rider, wiz):
    heights = {}
    if codrone is not None:
        try:
            heights["codrone"] = float(codrone.get_height()) / 100.0  # cm -> m
        except Exception:
            heights["codrone"] = -1.0
    if rider is not None:
        from CodingRider.protocol import DataType, DeviceType  # type: ignore[import-not-found]
        result = {"altitude": -1.0}
        def on_altitude(alt):
            try:
                result["altitude"] = float(alt.altitude)
            except Exception:
                pass
        rider.setEventHandler(DataType.Altitude, on_altitude)
        rider.sendRequest(DeviceType.Drone, DataType.Altitude)
        time.sleep(0.3)
        heights["rider"] = result["altitude"]
    if wiz is not None:
        wiz.write(b"height?\r")
        line = wiz.readline()
        try:
            heights["wizwing"] = float(line.decode("ascii").strip())
        except Exception:
            heights["wizwing"] = -1.0
    return heights


def set_led_all(codrone, rider, wiz, r: int, g: int, b: int):
    if codrone is not None:
        codrone.set_drone_LED(r, g, b, 255)
    if rider is not None:
        from CodingRider.protocol import LightModeDrone  # type: ignore[import-not-found]
        rider.sendLightModeColor(LightModeDrone.BodyHold, 255, r, g, b)
    if wiz is not None:
        # WIZWING: only 'funled' preset cycle available; RGB ignored
        print(f"[WIZWING] LED limited to 'funled' preset cycle; "
              f"requested RGB=({r},{g},{b}) ignored")
        wiz.write(b"funled\r")


def land_all(codrone, rider, wiz):
    if codrone is not None:
        codrone.land()
    if rider is not None:
        rider.sendControlWhile(0, 0, 0, 0, 500)
        rider.sendLanding()
    if wiz is not None:
        wiz.write(b"land\r")


def disconnect_all(codrone, rider, wiz):
    if codrone is not None:
        try:
            codrone.close()
        except Exception as e:
            print(f"[CoDrone EDU] close error: {e}")
    if rider is not None:
        try:
            rider.close()
        except Exception as e:
            print(f"[CodingRider] close error: {e}")
    if wiz is not None:
        try:
            wiz.write(b"off\r")
            wiz.close()
        except Exception as e:
            print(f"[WIZWING] close error: {e}")


# ====================================================================
# Mission entry point — executes the same 11-step STANDARD_MISSION as
# version_a_framework.py, but with explicit per-vendor branching at
# every step.
# ====================================================================

def run_mission() -> None:
    # Step 1 (connect): per-platform setup
    codrone = setup_codrone()
    rider = setup_coding_rider()
    wiz = setup_wizwing()

    # Step 2 (takeoff)
    takeoff_all(codrone, rider, wiz)

    # Step 3 (hover 3s)
    hover_all(codrone, rider, wiz, seconds=3.0)

    # Step 4 (move FORWARD distance=50 speed=30)
    move_forward_all(codrone, rider, wiz, distance=50, speed=30)

    # Step 5 (turn 90 deg CW)
    turn_cw_all(codrone, rider, wiz, degrees=90)

    # Step 6 (get_battery — first read)
    batteries_1 = get_battery_all(codrone, rider, wiz)
    print(f"Batteries (initial): {batteries_1}")

    # Step 7 (get_height)
    heights = get_height_all(codrone, rider, wiz)
    print(f"Heights: {heights}")

    # Step 8 (set_led red)
    set_led_all(codrone, rider, wiz, r=255, g=0, b=0)

    # Step 9 (get_battery — second read, drain check)
    batteries_2 = get_battery_all(codrone, rider, wiz)
    print(f"Batteries (after activity): {batteries_2}")

    # Step 10 (land)
    land_all(codrone, rider, wiz)

    # Step 11 (disconnect)
    disconnect_all(codrone, rider, wiz)


if __name__ == "__main__":
    run_mission()
    print("Mission complete (Version B: native)")
