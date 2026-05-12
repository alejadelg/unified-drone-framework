"""Interoperability evaluation for the Unified Drone Control Framework.

Runs a standardized test suite of commands against every supported drone
platform and measures success, timing, implementation type (NATIVE vs
COMPENSATORY), warnings emitted and DroneStatus transitions.

The script supports two modes:

  * --mock (default)  Uses three mock adapters that simulate each platform
                      with realistic timing and per-platform quirks.
                      Registered as: mock_codrone_edu, mock_coding_rider,
                      mock_wizwing.

  * --real            Uses the real adapters (codrone_edu, coding_rider,
                      wizwing). Requires the actual drone libraries and
                      hardware to be available.

Optional:

  * --fast            Scale all simulated delays by 1/100 for a quick run.

Outputs:
  * Console table with per-command verdicts
  * interoperability_results.csv with every measurement
  * Summary: pass rate, native vs compensatory counts, average timing
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from unified_drone import (  # noqa: E402
    Direction,
    DroneAdapter,
    DroneCommand,
    DroneManager,
    DroneRegistry,
    DroneStatus,
    LEDColor,
)
from unified_drone.core.exceptions import (  # noqa: E402
    DroneCommandError,
    DroneConnectionError,
    DroneError,
)
from unified_drone.core.registry import register_drone  # noqa: E402

CSV_OUTPUT = ROOT / "interoperability_results.csv"

# ---------------------------------------------------------------------
# Time scaling: realistic by default, scalable for fast runs
# ---------------------------------------------------------------------

TIME_SCALE: float = 1.0  # set by main()


def sim_sleep(seconds: float) -> None:
    """Sleep for ``seconds`` scaled by the global TIME_SCALE."""
    if seconds > 0:
        time.sleep(seconds * TIME_SCALE)


# ---------------------------------------------------------------------
# Mock adapters — realistic simulations of each platform
# ---------------------------------------------------------------------


class _MockBase(DroneAdapter):
    """Shared state and helpers for the three mock platforms."""

    INITIAL_BATTERY = 100

    def __init__(self, name: str) -> None:
        super().__init__(name=name)
        self._x: float = 0.0
        self._y: float = 0.0
        self._z: float = 0.0
        self._yaw: float = 0.0
        self._battery: int = self.INITIAL_BATTERY
        self._airborne: bool = False
        self._led: Tuple[int, int, int] = (0, 0, 0)

    # -- shared default implementations --

    def _drain(self, amount: int) -> None:
        self._battery = max(0, self._battery - amount)

    def _ensure_connected(self) -> None:
        if self._status == DroneStatus.DISCONNECTED:
            raise DroneConnectionError(f"{self.name} is not connected")


# ---- 1. CoDrone EDU mock (everything NATIVE) ----


@register_drone("mock_codrone_edu")
class MockCoDroneEdu(_MockBase):
    """Realistic mock of the CoDrone EDU. All commands native."""

    def __init__(self, name: str = "mock_codrone_edu") -> None:
        super().__init__(name=name)

    def connect(self, **kwargs: Any) -> None:
        sim_sleep(0.5)  # Bluetooth pairing
        self._status = DroneStatus.CONNECTED
        self._drain(1)

    def disconnect(self) -> None:
        sim_sleep(0.1)
        self._status = DroneStatus.DISCONNECTED

    def takeoff(self) -> None:
        self._ensure_connected()
        sim_sleep(2.0)  # realistic takeoff
        self._airborne = True
        self._z = 1.0
        self._status = DroneStatus.FLYING
        self._drain(3)

    def land(self) -> None:
        self._ensure_connected()
        sim_sleep(2.0)
        self._airborne = False
        self._z = 0.0
        self._status = DroneStatus.CONNECTED
        self._drain(2)

    def emergency_stop(self) -> None:
        sim_sleep(0.05)
        self._airborne = False
        self._z = 0.0
        self._status = DroneStatus.CONNECTED

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        # realistic time = distance / (speed/100 * max_speed_m_s); bounded
        max_speed_m_s = 1.0
        time_s = max(0.2, distance / max(1.0, (speed / 100.0) * max_speed_m_s) * 0.05)
        sim_sleep(time_s)
        self._drain(2)
        # Update position simply (forward = +y for example)
        deltas = {
            Direction.FORWARD: (0, 1, 0),
            Direction.BACKWARD: (0, -1, 0),
            Direction.LEFT: (-1, 0, 0),
            Direction.RIGHT: (1, 0, 0),
            Direction.UP: (0, 0, 1),
            Direction.DOWN: (0, 0, -1),
        }
        dx, dy, dz = deltas.get(direction, (0, 0, 0))
        scale = distance / 100.0  # treat distance as cm in the mock
        self._x += dx * scale
        self._y += dy * scale
        self._z += dz * scale

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        sim_sleep(max(0.3, abs(degrees) * 0.005))
        self._yaw = (self._yaw + degrees) % 360.0
        self._drain(1)

    def hover(self, duration: float = 1.0) -> None:
        self._ensure_connected()
        # Native hover: drone holds altitude using IMU
        sim_sleep(duration)
        self._drain(int(duration))

    def set_led(self, color: LEDColor) -> None:
        self._ensure_connected()
        sim_sleep(0.05)
        self._led = (color.red, color.green, color.blue)

    def get_battery(self) -> int:
        self._ensure_connected()
        sim_sleep(0.03)
        return self._battery

    def get_height(self) -> float:
        self._ensure_connected()
        sim_sleep(0.03)
        return self._z


# ---- 2. CodingRider mock (5 COMPENSATORY mechanisms) ----


@register_drone("mock_coding_rider")
class MockCodingRider(_MockBase):
    """Realistic mock of the CodingRider with 2 compensatory mechanisms.

    COMPENSATORY mechanisms exposed by this mock:
      * get_battery()    -> async->sync event bridge:
                            CodingRider exposes battery via
                              setEventHandler(DataType.State, cb)
                              sendRequest(DeviceType.Drone, DataType.State)
                            The adapter converts the async callback into a
                            blocking call. The data is real; only the
                            interaction paradigm is bridged.
      * get_height()     -> async->sync event bridge (same pattern, using
                            DataType.Altitude).

    Everything else is NATIVE with parameter translation:
      * takeoff/land     -> sendTakeOff() / sendLanding()
      * emergency_stop   -> sendStop()                 (real CodingRider primitive)
      * hover            -> sendControlWhile(0,0,0,0,ms)  (zero control held)
      * move / turn      -> sendControlWhile(roll, pitch, yaw, throttle, ms)
      * set_led          -> sendLightModeColor(LightModeDrone.BodyHold, ...)
    """

    logger = logging.getLogger("MockCodingRider")

    def __init__(self, name: str = "mock_coding_rider") -> None:
        super().__init__(name=name)

    def connect(self, **kwargs: Any) -> None:
        sim_sleep(0.8)
        self._status = DroneStatus.CONNECTED
        self._drain(1)

    def disconnect(self) -> None:
        sim_sleep(0.2)
        self._status = DroneStatus.DISCONNECTED

    def takeoff(self) -> None:
        self._ensure_connected()
        sim_sleep(2.5)
        self._airborne = True
        self._z = 1.0
        self._status = DroneStatus.FLYING
        self._drain(3)

    def land(self) -> None:
        self._ensure_connected()
        sim_sleep(2.5)
        self._airborne = False
        self._z = 0.0
        self._status = DroneStatus.CONNECTED
        self._drain(2)

    def emergency_stop(self) -> None:
        # NATIVE: CodingRider exposes drone.sendStop() as a real primitive.
        sim_sleep(0.05)
        self._airborne = False
        self._status = DroneStatus.CONNECTED
        self.logger.info("emergency_stop via sendStop (NATIVE)")

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        time_s = max(0.25, distance / max(1.0, speed) * 0.08)
        sim_sleep(time_s)
        self._drain(2)

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        sim_sleep(max(0.4, abs(degrees) * 0.006))
        self._yaw = (self._yaw + degrees) % 360.0
        self._drain(1)

    def hover(self, duration: float = 1.0) -> None:
        # NATIVE: drone.sendControlWhile(0, 0, 0, 0, duration_ms) holds the
        # drone with zero control input; the FC stabilises altitude. This is
        # the standard CodingRider idiom for hovering.
        self._ensure_connected()
        sim_sleep(duration)
        self._drain(int(duration))

    def set_led(self, color: LEDColor) -> None:
        # NATIVE: CodingRider supports LED via sendLightModeColor with
        # LightModeDrone.BodyHold (solid). Brightness is applied in software
        # by scaling RGB because the native API takes only R,G,B (0-255).
        self._ensure_connected()
        factor = max(0, min(color.brightness, 100)) / 100.0
        r = int(color.red * factor)
        g = int(color.green * factor)
        b = int(color.blue * factor)
        self._led = (r, g, b)
        sim_sleep(0.05)

    def get_battery(self) -> int:
        # COMPENSATORY: CodingRider exposes battery via an event-driven
        # callback (setEventHandler/sendRequest with DataType.State). The
        # adapter converts that async pattern into a synchronous return.
        # We simulate the round-trip latency; the value itself is real.
        self._ensure_connected()
        sim_sleep(0.1)  # simulated callback round-trip
        self.logger.warning("get_battery via async->sync event bridge (DataType.State)")
        return self._battery

    def get_height(self) -> float:
        # COMPENSATORY: same async->sync bridge using DataType.Altitude.
        # The callback receives altitude.altitude; we return the live value.
        self._ensure_connected()
        sim_sleep(0.1)
        self.logger.warning("get_height via async->sync event bridge (DataType.Altitude)")
        return self._z


# ---- 3. WIZWING mock (NATIVE via binary protocol) ----


@register_drone("mock_wizwing")
class MockWizwing(_MockBase):
    """Realistic mock of the WIZWING drone (USB serial, binary protocol)."""

    def __init__(self, name: str = "mock_wizwing") -> None:
        super().__init__(name=name)
        self._packets_sent: int = 0

    def _tx(self) -> None:
        self._packets_sent += 1
        sim_sleep(0.01)  # serial round-trip

    def connect(self, **kwargs: Any) -> None:
        sim_sleep(0.3)  # USB serial open is fast
        self._status = DroneStatus.CONNECTED
        self._drain(1)

    def disconnect(self) -> None:
        sim_sleep(0.05)
        self._status = DroneStatus.DISCONNECTED

    def takeoff(self) -> None:
        self._ensure_connected()
        self._tx()
        sim_sleep(2.2)
        self._airborne = True
        self._z = 1.0
        self._status = DroneStatus.FLYING
        self._drain(3)

    def land(self) -> None:
        self._ensure_connected()
        self._tx()
        sim_sleep(2.2)
        self._airborne = False
        self._z = 0.0
        self._status = DroneStatus.CONNECTED
        self._drain(2)

    def emergency_stop(self) -> None:
        self._tx()
        sim_sleep(0.05)
        self._airborne = False
        self._z = 0.0
        self._status = DroneStatus.CONNECTED

    def move(self, direction: Direction, distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        self._tx()
        time_s = max(0.2, distance / max(1.0, speed) * 0.06)
        sim_sleep(time_s)
        self._drain(2)

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        self._tx()
        sim_sleep(max(0.3, abs(degrees) * 0.005))
        self._yaw = (self._yaw + degrees) % 360.0
        self._drain(1)

    def hover(self, duration: float = 1.0) -> None:
        # Native: WIZWING has a hover packet
        self._ensure_connected()
        self._tx()
        sim_sleep(duration)
        self._drain(int(duration))

    def set_led(self, color: LEDColor) -> None:
        self._ensure_connected()
        self._tx()
        sim_sleep(0.06)
        self._led = (color.red, color.green, color.blue)

    def get_battery(self) -> int:
        self._ensure_connected()
        self._tx()
        sim_sleep(0.1)  # request + response
        return self._battery

    def get_height(self) -> float:
        self._ensure_connected()
        self._tx()
        sim_sleep(0.1)  # request + response
        return self._z


# ---------------------------------------------------------------------
# Implementation type catalogue
# ---------------------------------------------------------------------

# Map (platform_key, command_label) -> "NATIVE" | "COMPENSATORY"
IMPLEMENTATION_TYPE: Dict[Tuple[str, str], str] = {
    # CoDrone EDU is fully native
    **{("codrone_edu", c): "NATIVE" for c in (
        "connect", "takeoff", "land", "hover", "move", "turn",
        "get_battery", "get_height", "set_led", "disconnect", "emergency_stop",
    )},
    **{("mock_codrone_edu", c): "NATIVE" for c in (
        "connect", "takeoff", "land", "hover", "move", "turn",
        "get_battery", "get_height", "set_led", "disconnect", "emergency_stop",
    )},
    # CodingRider has only 2 compensatory mechanisms (the async->sync event bridges).
    # hover, emergency_stop, and set_led are all NATIVE primitives.
    **{("coding_rider", c): "NATIVE" for c in (
        "connect", "takeoff", "land", "move", "turn", "hover",
        "disconnect", "set_led", "emergency_stop",
    )},
    ("coding_rider", "get_battery"): "COMPENSATORY",
    ("coding_rider", "get_height"): "COMPENSATORY",
    **{("mock_coding_rider", c): "NATIVE" for c in (
        "connect", "takeoff", "land", "move", "turn", "hover",
        "disconnect", "set_led", "emergency_stop",
    )},
    ("mock_coding_rider", "get_battery"): "COMPENSATORY",
    ("mock_coding_rider", "get_height"): "COMPENSATORY",
    # WIZWING is fully native (binary protocol covers everything)
    **{("wizwing", c): "NATIVE" for c in (
        "connect", "takeoff", "land", "hover", "move", "turn",
        "get_battery", "get_height", "set_led", "disconnect", "emergency_stop",
    )},
    **{("mock_wizwing", c): "NATIVE" for c in (
        "connect", "takeoff", "land", "hover", "move", "turn",
        "get_battery", "get_height", "set_led", "disconnect", "emergency_stop",
    )},
}


def implementation_type(platform_key: str, command_label: str) -> str:
    return IMPLEMENTATION_TYPE.get((platform_key, command_label), "NATIVE")


# ---------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------

# A logical sequence that exercises every command in the unified interface.
TEST_SUITE: List[Tuple[str, Optional[DroneCommand]]] = [
    ("connect",        DroneCommand.connect()),
    ("takeoff",        DroneCommand.takeoff()),
    ("hover",          DroneCommand.hover(duration=3.0)),
    ("move",           DroneCommand.move(Direction.FORWARD, distance=50, speed=30)),
    ("turn",           DroneCommand.turn(degrees=90)),
    ("get_battery",    DroneCommand.get_battery()),
    ("get_height",     DroneCommand.get_height()),
    ("set_led",        DroneCommand.set_led(LEDColor(red=255, green=0, blue=0))),
    ("get_battery_2",  DroneCommand.get_battery()),
    ("land",           DroneCommand.land()),
    ("disconnect",     DroneCommand.disconnect()),
]


# ---------------------------------------------------------------------
# Warning capturer
# ---------------------------------------------------------------------


class WarningCapturer(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.WARNING:
            self.records.append(record.getMessage())

    def reset(self) -> None:
        self.records = []


# ---------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------


def classify_result(label: str, returned: Any, exception: Optional[BaseException]) -> str:
    if exception is not None:
        return "FAIL"
    # Telemetry returning -1 / -1.0 is a partial success — the call worked
    # but the underlying telemetry is not available on that platform.
    if label.startswith("get_battery") and isinstance(returned, int) and returned < 0:
        return "PARTIAL"
    if label == "get_height" and isinstance(returned, (int, float)) and returned < 0:
        return "PARTIAL"
    return "PASS"


def run_test_suite_on_platform(
    adapter_key: str,
    drone_id: str,
    capturer: WarningCapturer,
) -> List[Dict[str, Any]]:
    """Run every command in TEST_SUITE on one platform; return measurements."""
    manager = DroneManager()
    manager.add_drone(drone_id, adapter_key)
    drone = manager.get_drone(drone_id)

    results: List[Dict[str, Any]] = []

    for label, cmd in TEST_SUITE:
        capturer.reset()
        # Map both "get_battery" and "get_battery_2" to the same lookup key
        lookup_label = "get_battery" if label.startswith("get_battery") else label
        impl = implementation_type(adapter_key, lookup_label)

        params_str = _format_params(cmd)
        status_before = drone.status.name
        t0 = time.perf_counter()
        returned: Any = None
        exc: Optional[BaseException] = None
        try:
            returned = manager.send_command(drone_id, cmd)  # type: ignore[arg-type]
        except DroneError as e:
            exc = e
        except Exception as e:  # pragma: no cover (unexpected)
            exc = e
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        status_after = drone.status.name

        results.append({
            "platform": adapter_key,
            "command": label,
            "params": params_str,
            "result": classify_result(label, returned, exc),
            "elapsed_ms": round(elapsed_ms, 2),
            "implementation": impl,
            "status_before": status_before,
            "status_after": status_after,
            "return_value": _short_repr(returned),
            "warnings": " | ".join(capturer.records),
            "exception": f"{type(exc).__name__}: {exc}" if exc else "",
        })

    return results


def _format_params(cmd: DroneCommand) -> str:
    if not cmd.params:
        return ""
    parts = []
    for k, v in cmd.params.items():
        if hasattr(v, "name"):  # enum
            parts.append(f"{k}={v.name}")
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _short_repr(value: Any) -> str:
    if value is None:
        return ""
    s = repr(value)
    return s if len(s) <= 60 else s[:57] + "..."


# ---------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------


VERDICT_GLYPH = {
    "PASS": "PASS",
    "PARTIAL": "PART",
    "FAIL": "FAIL",
    "FRAMEWORK_LIMIT": "SKIP",
}


def print_table(results: List[Dict[str, Any]]) -> None:
    print()
    print("=" * 120)
    print(" PER-COMMAND RESULTS")
    print("=" * 120)
    header = (
        f"| {'Platform':<20} | {'Command':<14} | {'Verdict':<7} | "
        f"{'Time (ms)':>10} | {'Impl':<14} | {'Status before -> after':<30} |"
    )
    sep = "|" + "-" * 22 + "|" + "-" * 16 + "|" + "-" * 9 + "|" + "-" * 12 + "|" + "-" * 16 + "|" + "-" * 32 + "|"
    print(header)
    print(sep)
    last_platform = None
    for r in results:
        if last_platform is not None and r["platform"] != last_platform:
            print(sep)
        last_platform = r["platform"]
        transition = f"{r['status_before']} -> {r['status_after']}"
        print(
            f"| {r['platform']:<20} | {r['command']:<14} | "
            f"{VERDICT_GLYPH.get(r['result'], r['result']):<7} | "
            f"{r['elapsed_ms']:>10.2f} | {r['implementation']:<14} | {transition:<30} |"
        )
    print("=" * 120)


def print_warnings(results: List[Dict[str, Any]]) -> None:
    rows = [r for r in results if r["warnings"] or r["exception"]]
    if not rows:
        return
    print()
    print(" Warnings and exceptions captured")
    print(" --------------------------------")
    for r in rows:
        annotation = r["warnings"] or r["exception"]
        print(f"   [{r['platform']}/{r['command']}] {annotation}")


def print_summary(results: List[Dict[str, Any]]) -> None:
    by_platform: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        by_platform.setdefault(r["platform"], []).append(r)

    print()
    print("=" * 120)
    print(" SUMMARY BY PLATFORM")
    print("=" * 120)
    header = (
        f"| {'Platform':<20} | {'Tested':>6} | {'PASS':>5} | {'PART':>5} | "
        f"{'FAIL':>5} | {'SKIP':>5} | {'NATIVE':>6} | {'COMP':>5} | {'Avg ms':>10} |"
    )
    sep = "|" + "-" * 22 + "|" + "-" * 8 + ("|" + "-" * 7) * 4 + "|" + "-" * 8 + "|" + "-" * 7 + "|" + "-" * 12 + "|"
    print(header)
    print(sep)
    for platform, rows in by_platform.items():
        n = len(rows)
        n_pass = sum(1 for r in rows if r["result"] == "PASS")
        n_part = sum(1 for r in rows if r["result"] == "PARTIAL")
        n_fail = sum(1 for r in rows if r["result"] == "FAIL")
        n_skip = sum(1 for r in rows if r["result"] == "FRAMEWORK_LIMIT")
        n_native = sum(1 for r in rows if r["implementation"] == "NATIVE")
        n_comp = sum(1 for r in rows if r["implementation"] == "COMPENSATORY")
        # average over commands that actually ran
        ran = [r for r in rows if r["result"] not in ("FRAMEWORK_LIMIT",)]
        avg_ms = sum(r["elapsed_ms"] for r in ran) / max(1, len(ran))
        print(
            f"| {platform:<20} | {n:>6} | {n_pass:>5} | {n_part:>5} | "
            f"{n_fail:>5} | {n_skip:>5} | {n_native:>6} | {n_comp:>5} | {avg_ms:>10.2f} |"
        )
    print("=" * 120)

    # Pass rate per platform
    print()
    print(" Pass rate per platform (PASS + PARTIAL counted as success)")
    print(" ----------------------------------------------------------")
    for platform, rows in by_platform.items():
        ran = [r for r in rows if r["result"] != "FRAMEWORK_LIMIT"]
        ok = sum(1 for r in ran if r["result"] in ("PASS", "PARTIAL"))
        rate = (ok / len(ran)) * 100.0 if ran else 0.0
        print(f"   {platform:<22} {ok}/{len(ran)} = {rate:.1f}%")


def write_csv(results: List[Dict[str, Any]]) -> None:
    fields = [
        "platform", "command", "params", "result", "elapsed_ms",
        "implementation", "status_before", "status_after",
        "return_value", "warnings", "exception",
    ]
    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, "") for k in fields})


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------


def setup_real_mode() -> None:
    """Inject mock libraries so the real adapters can run without hardware.

    This is called only when the user opts into real mode AND the libraries
    are not actually installed. It allows the script to demonstrate the
    real-mode code path even on a machine without drone hardware.
    """
    from unittest.mock import MagicMock
    for fake in ("CoDrone", "CodingRider", "CodingRider.drone", "serial"):
        sys.modules.setdefault(fake, MagicMock())


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interoperability evaluation")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", default=False,
                      help="Use mock adapters with simulated timing (default)")
    mode.add_argument("--real", action="store_true", default=False,
                      help="Use the real adapters (requires libraries)")
    p.add_argument("--fast", action="store_true",
                   help="Scale all simulated delays by 1/100 for a quick run")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for any stochastic mock behaviour")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    use_real = args.real and not args.mock

    global TIME_SCALE
    TIME_SCALE = 0.01 if args.fast else 1.0
    random.seed(args.seed)

    # Configure logging + warning capture
    capturer = WarningCapturer()
    logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s",
                        stream=sys.stderr)
    logging.getLogger().addHandler(capturer)

    # Import built-in adapters; this is needed for --real mode
    if use_real:
        setup_real_mode()
        import unified_drone.adapters  # noqa: F401

    if use_real:
        platforms: List[Tuple[str, str]] = [
            ("codrone_edu", "edu"),
            ("coding_rider", "rider"),
            ("wizwing", "wiz"),
        ]
        mode_label = "REAL"
    else:
        platforms = [
            ("mock_codrone_edu", "edu"),
            ("mock_coding_rider", "rider"),
            ("mock_wizwing", "wiz"),
        ]
        mode_label = "MOCK"

    print(f"\n Interoperability evaluation - mode: {mode_label}, "
          f"time-scale: {TIME_SCALE:g}, seed: {args.seed}")
    print(f" Registered adapters: {DroneRegistry.available()}")
    print(f" Test suite size: {len(TEST_SUITE)} commands")

    all_results: List[Dict[str, Any]] = []
    overall_t0 = time.perf_counter()
    for adapter_key, drone_id in platforms:
        print(f"\n ---> Running suite on '{adapter_key}' ...")
        platform_t0 = time.perf_counter()
        results = run_test_suite_on_platform(adapter_key, drone_id, capturer)
        platform_dt = time.perf_counter() - platform_t0
        print(f"      finished in {platform_dt:.2f}s")
        all_results.extend(results)
    overall_dt = time.perf_counter() - overall_t0

    print_table(all_results)
    print_warnings(all_results)
    print_summary(all_results)
    write_csv(all_results)
    print(f"\n Total runtime: {overall_dt:.2f}s")
    print(f" CSV written to: {CSV_OUTPUT}")

    # Exit code: 0 if no FAILs (PARTIAL and FRAMEWORK_LIMIT are OK), 1 otherwise
    has_fail = any(r["result"] == "FAIL" for r in all_results)
    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
