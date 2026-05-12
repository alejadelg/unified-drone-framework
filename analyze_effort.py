"""Development effort comparison: framework (Version A) vs native (Version B).

Reads ``version_a_framework.py`` and ``version_b_native.py``, parses each with
the AST module, and computes a set of quantitative metrics that empirically
demonstrate the cost of NOT using the framework.

Usage:
    python analyze_effort.py

Outputs:
    * Console comparison table (Markdown-style)
    * effort_comparison.csv
    * Qualitative summary printed to stdout

# ===================================================================
# QUALITATIVE COMPARISON  (kept here as comments for the report)
# ===================================================================
#
# Learning curve
# --------------
#   Version A (framework):
#     The developer learns ONE API: DroneManager + DroneCommand.
#     Once the unified vocabulary is understood, every drone is a
#     drop-in replacement. Onboarding is platform-agnostic.
#
#   Version B (native):
#     The developer must learn THREE distinct libraries: the CoDrone
#     EDU SDK, the CodingRider drone module, and the WIZWING binary
#     serial protocol. Each has its own conventions, units, and quirks.
#
# Terminology consistency
# -----------------------
#   Version A: "takeoff" everywhere, "land" everywhere, "move" everywhere.
#   Version B: "takeoff" + "takeoff" + write(packet([0xAA, 0x01, ...]))
#              "land"    + "landing" + write(packet([0xAA, 0x02, ...]))
#              "go(forward,...)" + "go(0,...)" + struct.pack(">BHB",...)
#
# Code readability
# ----------------
#   Version A reads like a flight plan:
#       takeoff -> square pattern -> hover -> land
#   A non-expert can predict what the code does at a glance.
#
#   Version B reads like a polyglot driver. Every logical action is
#   buried under per-vendor branching and byte-level manipulation,
#   forcing readers to mentally diff the three implementations.
#
# Maintainability
# ---------------
#   Version A: When CoDrone EDU releases a new SDK, only the adapter
#   module changes. Application code stays untouched.
#
#   Version B: Updates ripple through every helper function that
#   touches that vendor — easy to miss a call-site, easy to introduce
#   regressions, hard to test in isolation.
#
# ===================================================================
"""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parent
VERSION_A = ROOT / "version_a_framework.py"
VERSION_B = ROOT / "version_b_native.py"
CSV_OUTPUT = ROOT / "effort_comparison.csv"


# ---------------------------------------------------------------------
# Tokens that mark a line as platform-specific (used to compute the
# reusability percentage).
# ---------------------------------------------------------------------

NATIVE_TOKEN_RE = re.compile(
    r"\b("
    # ---- vendor SDK module / class names ----
    r"codrone_edu|CoDroneEDU|"
    r"CodingRider|CodingRiderDrone|cr_drone|"
    r"serial\.Serial|"
    r"DataType|DeviceType|LightModeDrone|"
    # ---- vendor-specific method patterns ----
    r"sendTakeOff|sendLanding|sendStop|sendControlWhile|"
    r"sendLightModeColor|sendRequest|setEventHandler|"
    r"set_drone_LED|move_distance|turn_right|turn_left|landing|"
    # ---- WIZWING protocol-specific ----
    r"funled|"
    r"build_packet|wiz_build_packet|struct\.pack|struct\.unpack|"
    r"WIZ_[A-Z_]+|wiz_[a-z_]+|"
    # ---- helper functions specific to Version B ----
    r"setup_codrone|setup_coding_rider|setup_wizwing|"
    r"takeoff_all|land_all|hover_all|move_forward_all|"
    r"turn_cw_all|get_battery_all|get_height_all|"
    r"set_led_all|disconnect_all|"
    # ---- vendor object variable names ----
    r"codrone_obj|rider_obj|wiz_obj|"
    r"codrone|rider|wiz|"
    # ---- method call patterns ----
    r"\.pair\(|\.sendTakeOff\(|\.sendLanding\(|\.sendStop\("
    r")\b",
)
HEX_LITERAL_RE = re.compile(r"\b0x[0-9A-Fa-f]+\b")
# Bytes-string literals with carriage-return terminator are WIZWING-specific
WIZWING_BYTE_RE = re.compile(r"b['\"][^'\"]*\\r['\"]")

# Receivers that should NOT count as drone object variables
STDLIB_RECEIVERS: Set[str] = {
    "time", "struct", "sys", "logging", "print", "bytes",
    "int", "float", "str", "list", "dict", "set", "tuple",
    "len", "range", "MagicMock", "isinstance",
}

# Method/function names that should NOT count as "API calls" because
# they are basic Python built-ins.
BUILTIN_METHOD_NAMES: Set[str] = {
    "encode", "decode", "format", "join", "append", "extend",
}


# ---------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------


def load_source(path: Path) -> Tuple[str, ast.Module]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(path))
    return src, tree


# ---------------------------------------------------------------------
# Metric collectors
# ---------------------------------------------------------------------


def count_loc(src: str) -> int:
    """Count lines of code excluding blanks, comments, and import statements.

    A docstring (the very first triple-quoted string of the module) is also
    excluded because we treat it as documentation, not code. Other strings
    are kept intact.
    """
    lines = src.splitlines()
    total = 0
    in_docstring = False
    docstring_quote: str = ""
    seen_code = False  # to detect the module-level docstring

    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue

        # Track triple-quoted module/function docstrings
        if not in_docstring and (stripped.startswith('"""') or stripped.startswith("'''")):
            quote = stripped[:3]
            # one-line docstring
            if stripped.endswith(quote) and len(stripped) > 3:
                if not seen_code:
                    continue  # skip module docstring
            else:
                in_docstring = True
                docstring_quote = quote
            continue
        if in_docstring:
            if docstring_quote in stripped:
                in_docstring = False
            continue

        # Skip pure import lines for "lines of LOGIC code"
        if re.match(r"^\s*(import|from)\s+\S+", stripped):
            continue

        seen_code = True
        total += 1

    return total


def count_imports(tree: ast.Module) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))


def collect_method_calls(tree: ast.Module) -> List[Tuple[str, str]]:
    """Collect (receiver, method) pairs for every method-style call.

    A method call is `expr.method(...)`. The receiver is the name of the
    leftmost identifier in `expr`.
    """
    pairs: List[Tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = _leftmost_name(node.func.value)
            method = node.func.attr
            if method in BUILTIN_METHOD_NAMES:
                continue
            pairs.append((receiver, method))
    return pairs


def _leftmost_name(node: ast.AST) -> str:
    """Walk an attribute chain down to its leftmost ast.Name and return its id."""
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    return "<expr>"


def distinct_api_calls(pairs: List[Tuple[str, str]]) -> Set[str]:
    """Set of unique method names invoked across the file."""
    return {m for _, m in pairs}


def distinct_drone_variables(pairs: List[Tuple[str, str]]) -> Set[str]:
    """Receivers that look like drone-handle variables (excludes stdlib)."""
    seen: Set[str] = set()
    for receiver, _ in pairs:
        if receiver in STDLIB_RECEIVERS:
            continue
        if receiver == "<expr>":
            continue
        # Filter out class names that are not drone instances
        # (DroneCommand and LEDColor are classes, not drone variables)
        if receiver in {"DroneCommand", "LEDColor", "Direction"}:
            continue
        seen.add(receiver)
    return seen


def count_if_blocks(tree: ast.Module) -> int:
    """Number of If-statements outside of `if __name__ == '__main__'` guards."""
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Skip the standard module guard
            if _is_main_guard(node):
                continue
            count += 1
    return count


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    if isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__":
        return True
    return False


def count_try_except(tree: ast.Module) -> int:
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Try))


def reusable_percentage(src: str) -> float:
    """% of code lines that contain NO platform-specific tokens."""
    lines = src.splitlines()
    code_lines: List[str] = []
    in_docstring = False
    quote = ""
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if not in_docstring and (s.startswith('"""') or s.startswith("'''")):
            q = s[:3]
            if s.endswith(q) and len(s) > 3:
                continue
            in_docstring = True
            quote = q
            continue
        if in_docstring:
            if quote in s:
                in_docstring = False
            continue
        if re.match(r"^\s*(import|from)\s+\S+", s):
            continue
        code_lines.append(s)

    if not code_lines:
        return 0.0
    platform_specific = sum(
        1 for ln in code_lines
        if NATIVE_TOKEN_RE.search(ln)
        or HEX_LITERAL_RE.search(ln)
        or WIZWING_BYTE_RE.search(ln)
    )
    return (1.0 - platform_specific / len(code_lines)) * 100.0


# ---------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------


def analyze(path: Path) -> Dict[str, object]:
    src, tree = load_source(path)
    pairs = collect_method_calls(tree)
    return {
        "path": path.name,
        "loc": count_loc(src),
        "imports": count_imports(tree),
        "distinct_api_calls": len(distinct_api_calls(pairs)),
        "api_call_names": sorted(distinct_api_calls(pairs)),
        "drone_variables": len(distinct_drone_variables(pairs)),
        "drone_variable_names": sorted(distinct_drone_variables(pairs)),
        "if_blocks": count_if_blocks(tree),
        "try_except": count_try_except(tree),
        "reusable_pct": reusable_percentage(src),
    }


def reduction_pct(a: float, b: float) -> str:
    """How much smaller A is compared to B, as a percentage."""
    if b == 0:
        return "n/a"
    if a > b:
        return f"+{((a - b) / b) * 100:.0f}%"
    return f"{((b - a) / b) * 100:.0f}%"


# ---------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------


def print_table(a: Dict[str, object], b: Dict[str, object]) -> None:
    # Build comparison rows
    rows = [
        ("Lines of code (logic only)", a["loc"], b["loc"]),
        ("Import statements", a["imports"], b["imports"]),
        ("Distinct API method names", a["distinct_api_calls"], b["distinct_api_calls"]),
        ("Drone-object variables", a["drone_variables"], b["drone_variables"]),
        ("If/elif decision blocks", a["if_blocks"], b["if_blocks"]),
        ("Try/except blocks", a["try_except"], b["try_except"]),
    ]

    print()
    print("=" * 85)
    print(" DEVELOPMENT EFFORT COMPARISON  (Framework vs Native)")
    print("=" * 85)
    header = f"| {'Metric':<32} | {'Version A (Framework)':>22} | {'Version B (Native)':>20} | {'Reduction':>10} |"
    sep = "|" + "-" * 34 + "|" + "-" * 24 + "|" + "-" * 22 + "|" + "-" * 12 + "|"
    print(header)
    print(sep)
    for label, va, vb in rows:
        red = reduction_pct(float(va), float(vb))
        print(f"| {label:<32} | {str(va):>22} | {str(vb):>20} | {red:>10} |")

    # Reusability is a percentage, shown separately
    print(sep)
    print(
        f"| {'Reusable code (%)':<32} | "
        f"{a['reusable_pct']:>21.1f}% | "
        f"{b['reusable_pct']:>19.1f}% | "
        f"{a['reusable_pct'] - b['reusable_pct']:>+9.1f}pp |"
    )
    print("=" * 85)


def print_details(a: Dict[str, object], b: Dict[str, object]) -> None:
    print()
    print(" Distinct API method names")
    print("---------------------------")
    print(f" Version A ({a['distinct_api_calls']:>2}): {', '.join(a['api_call_names'])}")
    print(f" Version B ({b['distinct_api_calls']:>2}): {', '.join(b['api_call_names'])}")
    print()
    print(" Drone-object variables")
    print("-----------------------")
    print(f" Version A ({a['drone_variables']:>2}): {', '.join(a['drone_variable_names']) or '(none)'}")
    print(f" Version B ({b['drone_variables']:>2}): {', '.join(b['drone_variable_names']) or '(none)'}")


def print_qualitative_summary() -> None:
    print()
    print("=" * 85)
    print(" QUALITATIVE SUMMARY")
    print("=" * 85)
    blocks = [
        ("Learning curve",
         "1 unified API to learn",
         "3 separate libraries + 1 binary protocol"),
        ("Terminology",
         "takeoff/land/move are the same words for every drone",
         "takeoff vs takeoff vs write(0xAA 0x01 ...); land vs landing vs 0x02"),
        ("Readability",
         "Reads like a flight plan; intent is obvious",
         "Reads like a polyglot driver; intent buried in vendor branching"),
        ("Maintainability",
         "SDK update => one adapter changes; app code untouched",
         "SDK update => every helper that touches that vendor must change"),
    ]
    for title, ver_a, ver_b in blocks:
        print(f" {title}")
        print(f"     Version A: {ver_a}")
        print(f"     Version B: {ver_b}")
        print()


def write_csv(a: Dict[str, object], b: Dict[str, object]) -> None:
    rows = [
        ("metric", "version_a_framework", "version_b_native", "reduction"),
        ("lines_of_code", a["loc"], b["loc"], reduction_pct(float(a["loc"]), float(b["loc"]))),
        ("import_statements", a["imports"], b["imports"], reduction_pct(float(a["imports"]), float(b["imports"]))),
        ("distinct_api_calls", a["distinct_api_calls"], b["distinct_api_calls"],
         reduction_pct(float(a["distinct_api_calls"]), float(b["distinct_api_calls"]))),
        ("drone_object_variables", a["drone_variables"], b["drone_variables"],
         reduction_pct(float(a["drone_variables"]), float(b["drone_variables"]))),
        ("if_blocks", a["if_blocks"], b["if_blocks"], reduction_pct(float(a["if_blocks"]), float(b["if_blocks"]))),
        ("try_except_blocks", a["try_except"], b["try_except"],
         reduction_pct(float(a["try_except"]), float(b["try_except"]))),
        ("reusable_code_pct", f"{a['reusable_pct']:.1f}", f"{b['reusable_pct']:.1f}",
         f"{a['reusable_pct'] - b['reusable_pct']:+.1f}pp"),
    ]
    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------


def main() -> int:
    if not VERSION_A.is_file():
        print(f"ERROR: missing {VERSION_A}")
        return 2
    if not VERSION_B.is_file():
        print(f"ERROR: missing {VERSION_B}")
        return 2

    a = analyze(VERSION_A)
    b = analyze(VERSION_B)
    print_table(a, b)
    print_details(a, b)
    print_qualitative_summary()
    write_csv(a, b)
    print(f" CSV written to: {CSV_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
