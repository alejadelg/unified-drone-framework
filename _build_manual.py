"""Generate unified_drone_manual.docx from the current codebase state.

Run from the repo root:
    python _build_manual.py

Overwrites unified_drone_manual.docx in the working directory.
"""

from __future__ import annotations

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, Inches, RGBColor

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

CODE_FONT = "Consolas"
BODY_FONT = "Calibri"


def setup_styles(doc):
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)

    # Code style
    if "CodeBlock" not in styles:
        code = styles.add_style("CodeBlock", 1)  # 1 = paragraph
        code.font.name = CODE_FONT
        code.font.size = Pt(9)
        pf = code.paragraph_format
        pf.left_indent = Inches(0.3)
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)


def add_title_page(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Unified Drone Control Framework")
    r.bold = True
    r.font.size = Pt(28)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("User Manual")
    r.font.size = Pt(20)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Version 1.1 — May 2026")
    r.font.size = Pt(12)
    r.italic = True

    doc.add_paragraph()

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(
        "A reusable, extensible Python framework for unified control of "
        "multiple educational drone platforms."
    )
    r.italic = True

    doc.add_page_break()


def add_toc(doc, entries):
    doc.add_heading("Table of Contents", level=1)
    for i, e in enumerate(entries, start=1):
        p = doc.add_paragraph(f"{i}.  {e}")
        p.paragraph_format.space_after = Pt(2)
    doc.add_page_break()


def add_code(doc, lines):
    """Render a code block. Accepts a single multi-line string or a list."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    # Remove any leading/trailing empty lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    for line in lines:
        p = doc.add_paragraph(line, style="CodeBlock")
        p.paragraph_format.space_after = Pt(0)
    # Small gap after the block
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def add_bullets(doc, items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def add_table(doc, header, rows, widths=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(header):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        r = p.add_run(h)
        r.bold = True
    for ri, row in enumerate(rows, start=1):
        cells = table.rows[ri].cells
        for ci, val in enumerate(row):
            cells[ci].text = str(val)
    if widths:
        for i, w in enumerate(widths):
            for row in table.rows:
                row.cells[i].width = w
    # Space after table
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def para(doc, text):
    doc.add_paragraph(text)


# ---------------------------------------------------------------------
# Document content
# ---------------------------------------------------------------------


def build_document():
    doc = Document()
    setup_styles(doc)

    # --- Title page ---
    add_title_page(doc)

    # --- TOC ---
    add_toc(
        doc,
        [
            "Introduction",
            "Architecture Overview",
            "Installation and Setup",
            "Framework Components",
            "Supported Drone Platforms",
            "Quick Start Guide",
            "API Reference",
            "Command Reference",
            "Working with Multiple Drones",
            "Adding a New Drone Platform",
            "Error Handling",
            "Logging and Monitoring",
            "Empirical Evaluation Results",
            "Complete Code Examples",
            "Troubleshooting",
        ],
    )

    # =================================================================
    # 1. Introduction
    # =================================================================
    doc.add_heading("1. Introduction", level=1)
    para(
        doc,
        "The Unified Drone Control Framework is a Python software framework "
        "that exposes a single command interface across heterogeneous "
        "educational drone platforms. User code is written once, against the "
        "framework, and runs unchanged against any registered drone — "
        "whether the underlying SDK is event-driven (CodingRider), "
        "synchronous (CoDrone EDU), or raw serial (WIZWING).",
    )

    doc.add_heading("1.1 Purpose", level=2)
    para(
        doc,
        "Educational drone platforms each ship their own Python library with "
        "different APIs, naming conventions, communication protocols, and "
        "interaction paradigms. This framework solves the interoperability "
        "problem by providing a uniform interface that translates generic "
        "commands into platform-specific operations.",
    )

    doc.add_heading("1.2 Key Features", level=2)
    add_bullets(
        doc,
        [
            "Unified command interface across all supported drone platforms.",
            "Adapter pattern isolates platform-specific code from user logic.",
            "Open/Closed design — new drones are added without modifying existing code.",
            "Command pattern with immutable, replayable command objects.",
            "Multi-drone orchestration with broadcast and command sequencing.",
            "Async-to-sync paradigm bridging for event-driven SDKs (CodingRider).",
            "Built-in logging at every operation level.",
            "Clean exception hierarchy for structured error handling.",
            "Zero external dependencies beyond the drone libraries themselves.",
            "Python standard library only (abc, dataclasses, enum, typing, logging, struct, threading).",
        ],
    )

    doc.add_heading("1.3 Supported Platforms", level=2)
    add_table(
        doc,
        ["Platform", "Python library", "Communication", "Registry Key"],
        [
            ["CoDrone EDU", "codrone_edu.drone", "Radio Frequency", "codrone_edu"],
            ["CodingRider", "CodingRider.drone", "Radio Frequency", "coding_rider"],
            ["WIZWING", "pyserial", "Radio Frequency / Wi-Fi", "wizwing"],
            ["SimDrone (reference)", "(none — simulated)", "Wi-Fi / UDP (simulated)", "simdrone"],
        ],
    )
    para(
        doc,
        "SimDrone is a fully-simulated reference adapter shipped in "
        "unified_drone/adapters/simdrone_adapter.py. It implements every "
        "abstract method and is used as an empirical extensibility "
        "witness — see Chapter 13.",
    )

    doc.add_heading("1.4 Requirements", level=2)
    add_bullets(
        doc,
        [
            "Python 3.8 or later.",
            "Standard library modules: abc, dataclasses, enum, typing, logging, struct, threading.",
            "Drone-specific libraries are required only for the platforms you actually drive.",
        ],
    )

    doc.add_page_break()

    # =================================================================
    # 2. Architecture Overview
    # =================================================================
    doc.add_heading("2. Architecture Overview", level=1)
    para(
        doc,
        "The framework is organized into clearly separated layers that "
        "ensure loose coupling and high extensibility. Three design "
        "patterns form the architectural foundation.",
    )

    doc.add_heading("2.1 Layer Diagram", level=2)
    add_code(
        doc,
        """\
User Code / Application
        |
        v
DroneManager  -->  DroneRegistry  -->  DroneAdapter (ABC)
                                            |
            +-----------+-----------+-----------+-----------+
            |           |           |           |           |
            v           v           v           v           v
   CoDroneEduAdapter   CodingRiderAdapter   WizwingAdapter   MockDroneAdapter
   (codrone_edu)       (CodingRider.drone)  (pyserial)       (SimDrone, in-process)
""",
    )

    doc.add_heading("2.2 Design Patterns", level=2)

    doc.add_heading("Adapter Pattern", level=3)
    para(
        doc,
        "Each drone library has a dedicated adapter class that translates "
        "the unified interface into library-specific API calls. The "
        "DroneAdapter abstract base class defines the target interface; "
        "concrete adapters bridge each vendor SDK to that interface.",
    )
    doc.add_heading("Command Pattern", level=3)
    para(
        doc,
        "Flight operations are represented as immutable DroneCommand data "
        "objects that carry an action identifier (FlightAction enum) and a "
        "parameter dictionary. This decouples what to do from how to do it, "
        "and makes commands loggable, queueable, and replayable.",
    )
    doc.add_heading("Factory / Registry Pattern", level=3)
    para(
        doc,
        "The DroneRegistry maintains a class-level dictionary mapping "
        "string keys to adapter classes. New adapters register via the "
        "@register_drone decorator. DroneManager uses the registry to "
        "instantiate adapters by key, so the manager never references "
        "concrete adapter classes directly — this is the Open/Closed "
        "Principle in practice.",
    )

    doc.add_heading("2.3 Package Structure", level=2)
    add_code(
        doc,
        """\
unified_drone/
    __init__.py               # Public API re-exports
    scenarios.py              # Canonical STANDARD_MISSION (11 commands)
    core/
        __init__.py
        enums.py              # FlightAction, Direction, DroneStatus
        models.py             # DroneCommand, Position, LEDColor
        exceptions.py         # DroneError hierarchy
        base_adapter.py       # DroneAdapter ABC (11 abstract methods)
        registry.py           # DroneRegistry + @register_drone
        manager.py            # DroneManager orchestration
    adapters/
        __init__.py           # Auto-registers the 3 built-in adapters
        codrone_edu.py        # CoDrone EDU adapter
        coding_rider.py       # CodingRider adapter (async->sync bridge)
        wizwing.py            # WIZWING serial adapter
        simdrone_adapter.py   # Reference adapter (registers on explicit import)
    examples/
        __init__.py
        basic_usage.py        # Multi-platform unified-control demo
""",
    )

    doc.add_heading("2.4 Dependency Flow", level=2)
    para(
        doc,
        "The core package has zero imports from the adapters package. "
        "Adapters import only from core. This one-way dependency ensures "
        "that the framework compiles and loads even when no drone "
        "libraries are installed. Vendor libraries are imported lazily "
        "inside each adapter's connect() method.",
    )

    doc.add_page_break()

    # =================================================================
    # 3. Installation and Setup
    # =================================================================
    doc.add_heading("3. Installation and Setup", level=1)

    doc.add_heading("3.1 Framework Installation", level=2)
    para(
        doc,
        "Copy the unified_drone/ directory into your project or add its "
        "parent directory to your Python path. The framework uses only "
        "Python standard library modules and requires no pip installation.",
    )

    doc.add_heading("3.2 Drone Library Installation", level=2)
    para(
        doc,
        "Install only the libraries for the drone platforms you plan to "
        "drive. Each library is imported lazily inside the adapter's "
        "connect() method, so the framework loads successfully even if a "
        "library is missing.",
    )
    doc.add_heading("CoDrone EDU", level=3)
    add_code(doc, "pip install codrone-edu")
    doc.add_heading("CodingRider", level=3)
    add_code(doc, "pip install CodingRider")
    doc.add_heading("WIZWING (pyserial)", level=3)
    add_code(doc, "pip install pyserial")
    doc.add_heading("SimDrone (no install required)", level=3)
    para(
        doc,
        "SimDrone is a pure-Python simulator that ships with the "
        "framework. No additional install is needed; it is suitable for "
        "running every example without physical hardware.",
    )

    doc.add_heading("3.3 Verifying the Installation", level=2)
    add_code(
        doc,
        """\
from unified_drone import DroneRegistry
import unified_drone.adapters                                   # registers 3 built-ins
from unified_drone.adapters.simdrone_adapter import MockDroneAdapter  # registers SimDrone

print(DroneRegistry.available())
# ['codrone_edu', 'coding_rider', 'wizwing', 'simdrone']
""",
    )
    para(
        doc,
        "The three built-in adapters auto-register when "
        "unified_drone.adapters is imported. SimDrone registers on "
        "explicit import of simdrone_adapter, which keeps the production "
        "set free of test-only adapters by default.",
    )

    doc.add_page_break()

    # =================================================================
    # 4. Framework Components
    # =================================================================
    doc.add_heading("4. Framework Components", level=1)

    doc.add_heading("4.1 Enumerations (core/enums.py)", level=2)

    doc.add_heading("FlightAction", level=3)
    para(
        doc,
        "Defines every action supported by the unified interface. Used as "
        "the action identifier in DroneCommand objects.",
    )
    add_table(
        doc,
        ["Value", "Description"],
        [
            ["CONNECT", "Establish connection to the drone"],
            ["DISCONNECT", "Close the drone connection"],
            ["TAKEOFF", "Command the drone to take off"],
            ["LAND", "Command the drone to land"],
            ["EMERGENCY_STOP", "Immediately stop all motors"],
            ["MOVE", "Move in a specified direction"],
            ["TURN", "Rotate by a specified number of degrees"],
            ["HOVER", "Hold position for a specified duration"],
            ["SET_LED", "Set the drone LED color"],
            ["GET_BATTERY", "Query the battery level (%)"],
            ["GET_HEIGHT", "Query the current altitude (metres)"],
            ["GET_STATUS", "Query the current drone status"],
        ],
    )

    doc.add_heading("Direction", level=3)
    para(doc, "Normalised movement directions used by the move() command.")
    add_table(
        doc,
        ["Value", "Description"],
        [
            ["FORWARD", "Move forward along the drone's heading"],
            ["BACKWARD", "Move backward"],
            ["LEFT", "Move left (lateral)"],
            ["RIGHT", "Move right (lateral)"],
            ["UP", "Increase altitude"],
            ["DOWN", "Decrease altitude"],
        ],
    )

    doc.add_heading("DroneStatus", level=3)
    para(doc, "Lifecycle states tracked by each adapter.")
    add_table(
        doc,
        ["Value", "Description"],
        [
            ["DISCONNECTED", "No connection to the drone"],
            ["CONNECTED", "Connected but not airborne"],
            ["ARMED", "Motors armed, ready for takeoff"],
            ["FLYING", "Currently airborne"],
            ["LANDING", "Landing in progress"],
            ["ERROR", "An error has occurred"],
        ],
    )

    doc.add_heading("4.2 Data Models (core/models.py)", level=2)
    para(
        doc,
        "All models are frozen (immutable) dataclasses — thread-safe and "
        "suitable for logging, queuing, and replay.",
    )

    doc.add_heading("DroneCommand", level=3)
    para(
        doc,
        "The central command object. Carries a FlightAction and a "
        "dictionary of parameters. Construct commands with the factory "
        "classmethods (recommended) or directly.",
    )
    add_code(
        doc,
        """\
# Factory classmethods (recommended)
cmd = DroneCommand.takeoff()
cmd = DroneCommand.move(Direction.FORWARD, distance=2.0, speed=60)
cmd = DroneCommand.turn(degrees=-90)
cmd = DroneCommand.hover(duration=1.5)
cmd = DroneCommand.set_led(LEDColor(red=255, green=0, blue=128))

# Direct construction (advanced)
cmd = DroneCommand(
    action=FlightAction.MOVE,
    params={"direction": Direction.FORWARD, "distance": 2.0, "speed": 60},
)
""",
    )

    doc.add_heading("LEDColor", level=3)
    para(doc, "RGB colour with brightness for drone LED control.")
    add_code(
        doc,
        """\
color = LEDColor(red=255, green=0, blue=0, brightness=100)
# red, green, blue: 0-255
# brightness:       0-100 (default 100)
""",
    )

    doc.add_heading("Position", level=3)
    para(doc, "3-D position with yaw rotation, for spatial calculations.")
    add_code(doc, "pos = Position(x=1.0, y=2.0, z=0.5, yaw=45.0)")

    doc.add_heading("4.3 Exception Hierarchy (core/exceptions.py)", level=2)
    add_table(
        doc,
        ["Exception", "Raised when"],
        [
            ["DroneError", "Base exception for all framework errors"],
            ["DroneConnectionError", "Connection or disconnection fails"],
            ["DroneCommandError", "A command cannot be executed"],
            ["DroneTimeoutError", "An operation times out"],
            ["AdapterNotFoundError", "No adapter is registered for a given key"],
        ],
    )
    add_code(
        doc,
        """\
from unified_drone import DroneError, DroneConnectionError

try:
    manager.send_command("drone_1", DroneCommand.takeoff())
except DroneConnectionError as e:
    print(f"Connection issue: {e}")
except DroneError as e:
    print(f"Drone error: {e}")
""",
    )

    doc.add_page_break()

    # =================================================================
    # 5. Supported Drone Platforms
    # =================================================================
    doc.add_heading("5. Supported Drone Platforms", level=1)

    # 5.1 CoDrone EDU
    doc.add_heading("5.1 CoDrone EDU", level=2)
    para(doc, "Registry key: codrone_edu")
    para(doc, "Adapter class: CoDroneEduAdapter")
    para(doc, "Library: codrone_edu (Robolink)")
    para(
        doc,
        "Wraps the Robolink codrone_edu library. Supports radio-frequency "
        "pairing with an optional port specification, directional "
        "movement, turning, hovering, LED control, battery and altitude "
        "queries. The SDK aligns 1:1 with the unified interface — no "
        "compensatory mechanisms are required.",
    )
    doc.add_heading("Constructor parameters", level=3)
    add_table(
        doc,
        ["Parameter", "Type", "Default", "Description"],
        [
            ["name", "str", '"codrone_edu"', "Identifier for the adapter instance"],
            ["port", "str | None", "None", "Optional COM port for pairing"],
        ],
    )
    doc.add_heading("API translation", level=3)
    add_table(
        doc,
        ["Unified method", "CoDrone EDU SDK call"],
        [
            ["connect()", "Drone().pair(portname=...)"],
            ["disconnect()", "drone.close()"],
            ["takeoff()", "drone.takeoff()"],
            ["land()", "drone.land()"],
            ["emergency_stop()", "drone.emergency_stop()"],
            ["move(dir, dist, spd)", "drone.move_distance(x, y, z, v)"],
            ["turn(degrees)", "drone.turn(power, seconds)"],
            ["hover(duration)", "drone.hover(seconds)"],
            ["set_led(color)", "drone.set_drone_LED(r, g, b, brightness)"],
            ["get_battery()", "drone.get_battery()"],
            ["get_height()", "drone.get_height() / 100"],
        ],
    )

    # 5.2 CodingRider
    doc.add_heading("5.2 CodingRider", level=2)
    para(doc, "Registry key: coding_rider")
    para(doc, "Adapter class: CodingRiderAdapter")
    para(doc, "Library: CodingRider.drone")
    para(
        doc,
        "Wraps the CodingRider drone SDK. Two queries — battery and "
        "altitude — are exposed by CodingRider only through an "
        "event-driven callback API. The adapter bridges them to a "
        "synchronous call via a threading.Event() barrier: it registers a "
        "callback, sends the request, and blocks until the event fires.",
    )
    doc.add_heading("API translation", level=3)
    add_table(
        doc,
        ["Unified method", "CodingRider SDK call"],
        [
            ["connect()", "drone.open(port)"],
            ["disconnect()", "drone.close()"],
            ["takeoff()", "drone.sendTakeOff()"],
            ["land()", "drone.sendLanding()"],
            ["emergency_stop()", "drone.sendStop()"],
            ["move(dir, dist, spd)", "drone.sendControlWhile(...)"],
            ["turn(degrees)", "drone.sendControlWhile(0, 0, yaw, ...)"],
            ["hover(duration)", "drone.sendControlWhile(0, 0, 0, 0, ms)"],
            ["set_led(color)", "drone.sendLightModeColor(...)"],
            ["get_battery()", "setEventHandler + sendRequest (async->sync bridge)"],
            ["get_height()", "setEventHandler + sendRequest (async->sync bridge)"],
        ],
    )

    # 5.3 WIZWING
    doc.add_heading("5.3 WIZWING (pyserial)", level=2)
    para(doc, "Registry key: wizwing")
    para(doc, "Adapter class: WizwingAdapter")
    para(doc, "Library: pyserial")
    para(
        doc,
        "Communicates with WIZWING hardware via a text-based ASCII serial "
        "protocol (verbs such as connect, takeoff, land, forward, cw, "
        "battery?). Two compensatory mechanisms are required: hover is "
        "emulated with time.sleep() because the protocol has no native "
        "hover verb, and set_led collapses to the protocol's funled "
        "preset because the radio does not support arbitrary RGB.",
    )
    doc.add_heading("Constructor parameters", level=3)
    add_table(
        doc,
        ["Parameter", "Type", "Default", "Description"],
        [
            ["name", "str", '"wizwing"', "Identifier for the adapter instance"],
            ["port", "str", '"COM3"', "Serial port (e.g., COM3, /dev/ttyUSB0)"],
            ["baudrate", "int", "115200", "Serial communication baud rate"],
        ],
    )
    doc.add_heading("Serial protocol (selected verbs)", level=3)
    add_table(
        doc,
        ["Command", "Wire format", "Notes"],
        [
            ["takeoff", "takeoff\\r", "Acknowledged with ok"],
            ["land", "land\\r", "Acknowledged with ok"],
            ["emergency", "emergency\\r", "Cuts motors immediately"],
            ["move", "<verb> <strength> <ms>\\r", "verb in {forward, backward, left, right, up, down}"],
            ["turn", "cw|ccw <strength> <ms>\\r", "Sign of degrees selects verb"],
            ["battery?", "battery?\\r", "Reply parsed from readline()"],
            ["height?", "height?\\r", "Reply parsed from readline()"],
            ["funled", "funled\\r", "Preset cycle (compensation for RGB)"],
        ],
    )

    # 5.4 SimDrone
    doc.add_heading("5.4 SimDrone (reference adapter)", level=2)
    para(doc, "Registry key: simdrone")
    para(doc, "Adapter class: MockDroneAdapter")
    para(doc, "Library: standard library only (no external dependency)")
    para(
        doc,
        "SimDrone is a fully in-process simulator that ships with the "
        "framework as a reference implementation of the extensibility "
        "contract. It models a hypothetical Wi-Fi educational drone with "
        "three realistic quirks that exercise the adapter pattern:",
    )
    add_bullets(
        doc,
        [
            "Speed is expressed in metres per second (0.0–10.0), not 0–100%.",
            "Distances are expressed in millimetres, not metres.",
            "There is no combined RGB LED command; colour must be split into three single-channel commands.",
            "The drone must be ARMED before takeoff and DISARMED after disconnect.",
        ],
    )
    para(
        doc,
        "All four differences are absorbed by the adapter; user code keeps "
        "calling DroneCommand.move(...) and DroneCommand.set_led(...) "
        "without change. The default simulated=True mode does not open a "
        "real socket; it merely tracks internal state, which makes the "
        "class suitable for offline automated tests.",
    )

    doc.add_page_break()

    # =================================================================
    # 6. Quick Start Guide
    # =================================================================
    doc.add_heading("6. Quick Start Guide", level=1)

    doc.add_heading("6.1 Minimal Example", level=2)
    para(
        doc,
        "The following example shows the complete workflow: import, "
        "register adapters, create a manager, add a drone, send commands.",
    )
    add_code(
        doc,
        """\
from unified_drone import DroneManager, DroneCommand, Direction
import unified_drone.adapters   # triggers adapter registration

# Create the manager
manager = DroneManager()

# Add a drone (choose any supported platform)
manager.add_drone("my_drone", "codrone_edu", port="COM4")

# Connect, fly, and land
manager.send_command("my_drone", DroneCommand.connect())
manager.send_command("my_drone", DroneCommand.takeoff())
manager.send_command("my_drone",
    DroneCommand.move(Direction.FORWARD, distance=1.0, speed=50))
manager.send_command("my_drone", DroneCommand.land())
manager.send_command("my_drone", DroneCommand.disconnect())
""",
    )

    doc.add_heading("6.2 Switching Drone Platforms", level=2)
    para(
        doc,
        "To switch from one drone to another, only the add_drone() call "
        "changes. All command logic stays identical.",
    )
    add_code(
        doc,
        """\
# Switch from CoDrone EDU to WIZWING — only this line changes:
manager.add_drone("my_drone", "wizwing", port="COM3", baudrate=115200)

# All subsequent commands work exactly the same
manager.send_command("my_drone", DroneCommand.connect())
manager.send_command("my_drone", DroneCommand.takeoff())
# ...
""",
    )

    doc.add_heading("6.3 Running Without Hardware (SimDrone)", level=2)
    para(
        doc,
        "Every example in this manual can be executed without physical "
        "hardware by registering the SimDrone reference adapter:",
    )
    add_code(
        doc,
        """\
import unified_drone.adapters
from unified_drone.adapters.simdrone_adapter import MockDroneAdapter

manager = DroneManager()
manager.add_drone("sim_1", "simdrone")          # no port, no hardware
manager.send_command("sim_1", DroneCommand.connect())
manager.send_command("sim_1", DroneCommand.takeoff())
# ... etc.
""",
    )

    doc.add_page_break()

    # =================================================================
    # 7. API Reference
    # =================================================================
    doc.add_heading("7. API Reference", level=1)

    doc.add_heading("7.1 DroneManager", level=2)
    para(
        doc,
        "The central orchestration class. Manages multiple drones through "
        "the unified interface. Never references concrete adapter classes "
        "directly.",
    )
    add_table(
        doc,
        ["Method", "Parameters", "Returns", "Description"],
        [
            ["add_drone()", "drone_id, adapter_key, **kwargs", "DroneAdapter", "Create and register a drone instance"],
            ["remove_drone()", "drone_id", "None", "Remove a drone (disconnects first if needed)"],
            ["get_drone()", "drone_id", "DroneAdapter", "Retrieve a managed drone by ID"],
            ["send_command()", "drone_id, DroneCommand", "Any", "Send a single command to one drone"],
            ["broadcast_command()", "DroneCommand", "Dict[str, Any]", "Send the same command to every drone"],
            ["send_sequence()", "drone_id, List[DroneCommand]", "List[Any]", "Send N commands in order to one drone"],
            ["status_report()", "—", "Dict[str, str]", "Snapshot of every drone's current status"],
            ["drone_ids", "(property)", "List[str]", "List of registered drone IDs"],
        ],
    )

    doc.add_heading("7.2 DroneRegistry", level=2)
    para(
        doc,
        "Central registry mapping string keys to adapter classes. All "
        "methods are classmethods — no instantiation required.",
    )
    add_table(
        doc,
        ["Method", "Returns", "Description"],
        [
            ["register(key, cls)", "None", "Register an adapter class under a key"],
            ["create(key, **kwargs)", "DroneAdapter", "Instantiate an adapter by key"],
            ["available()", "List[str]", "List all registered adapter keys"],
            ["is_registered(key)", "bool", "Check whether a key is registered"],
        ],
    )

    doc.add_heading("7.3 DroneAdapter (Abstract Base Class)", level=2)
    para(
        doc,
        "The abstract interface every adapter must implement. Defines 11 "
        "abstract methods and a concrete execute() dispatcher.",
    )
    add_table(
        doc,
        ["Abstract method", "Signature"],
        [
            ["connect", "(self, **kwargs) -> None"],
            ["disconnect", "(self) -> None"],
            ["takeoff", "(self) -> None"],
            ["land", "(self) -> None"],
            ["emergency_stop", "(self) -> None"],
            ["move", "(self, direction, distance, speed) -> None"],
            ["turn", "(self, degrees) -> None"],
            ["hover", "(self, duration) -> None"],
            ["set_led", "(self, color: LEDColor) -> None"],
            ["get_battery", "(self) -> int"],
            ["get_height", "(self) -> float"],
        ],
    )
    para(
        doc,
        "execute(command: DroneCommand) is provided concretely by the "
        "base class: it dispatches on command.action and forwards "
        "params to the corresponding abstract method.",
    )

    doc.add_heading("7.4 @register_drone Decorator", level=2)
    para(
        doc,
        "Class decorator that automatically registers an adapter with "
        "DroneRegistry when its module is first imported.",
    )
    add_code(
        doc,
        """\
from unified_drone import DroneAdapter, register_drone

@register_drone("my_custom_drone")
class MyCustomAdapter(DroneAdapter):
    # implement all 11 abstract methods...
    pass
""",
    )

    doc.add_page_break()

    # =================================================================
    # 8. Command Reference
    # =================================================================
    doc.add_heading("8. Command Reference", level=1)
    para(
        doc,
        "DroneCommand provides factory classmethods for every supported "
        "command. All commands are immutable (frozen) dataclasses.",
    )
    add_table(
        doc,
        ["Factory method", "Parameters", "Description"],
        [
            ["DroneCommand.connect()", "**kwargs (e.g. port)", "Connect to the drone"],
            ["DroneCommand.disconnect()", "—", "Disconnect from the drone"],
            ["DroneCommand.takeoff()", "—", "Take off"],
            ["DroneCommand.land()", "—", "Land"],
            ["DroneCommand.emergency_stop()", "—", "Emergency motor stop"],
            ["DroneCommand.move()", "direction, distance=1.0, speed=50", "Move in a direction"],
            ["DroneCommand.turn()", "degrees", "Rotate (+CW / -CCW)"],
            ["DroneCommand.hover()", "duration=1.0", "Hold position (seconds)"],
            ["DroneCommand.set_led()", "color: LEDColor", "Set LED colour"],
            ["DroneCommand.get_battery()", "—", "Query battery level (%)"],
            ["DroneCommand.get_height()", "—", "Query altitude (metres)"],
            ["DroneCommand.get_status()", "—", "Query current drone status"],
        ],
    )

    doc.add_heading("8.1 move() Parameters", level=2)
    add_table(
        doc,
        ["Parameter", "Type", "Default", "Description"],
        [
            ["direction", "Direction", "(required)", "FORWARD / BACKWARD / LEFT / RIGHT / UP / DOWN"],
            ["distance", "float", "1.0", "Distance in metres"],
            ["speed", "int", "50", "Speed as a percentage (0–100)"],
        ],
    )

    doc.add_heading("8.2 turn() Parameters", level=2)
    add_table(
        doc,
        ["Parameter", "Type", "Default", "Description"],
        [
            ["degrees", "float", "(required)", "Positive = clockwise; negative = counter-clockwise"],
        ],
    )

    doc.add_page_break()

    # =================================================================
    # 9. Working with Multiple Drones
    # =================================================================
    doc.add_heading("9. Working with Multiple Drones", level=1)

    doc.add_heading("9.1 Adding Multiple Drones", level=2)
    para(
        doc,
        "DroneManager supports any number of drones, even of different "
        "types. Each drone is identified by a unique string ID.",
    )
    add_code(
        doc,
        """\
manager = DroneManager()

# Mix different drone platforms in the same manager
manager.add_drone("edu_1",   "codrone_edu", port="COM4")
manager.add_drone("rider_1", "coding_rider")
manager.add_drone("wiz_1",   "wizwing", port="COM3", baudrate=115200)

print(manager.drone_ids)
# ['edu_1', 'rider_1', 'wiz_1']
""",
    )

    doc.add_heading("9.2 Broadcasting Commands", level=2)
    para(
        doc,
        "broadcast_command() sends the same command to every managed "
        "drone. It returns a dictionary mapping each drone ID to either "
        "its result or the exception raised by that drone — one drone "
        "can fail without aborting the rest of the broadcast.",
    )
    add_code(
        doc,
        """\
# Connect, take off, then land everyone together
manager.broadcast_command(DroneCommand.connect())
manager.broadcast_command(DroneCommand.takeoff())
manager.broadcast_command(DroneCommand.land())

# Telemetry as a dictionary
batteries = manager.broadcast_command(DroneCommand.get_battery())
for drone_id, level in batteries.items():
    print(f"{drone_id}: {level}%")
""",
    )

    doc.add_heading("9.3 Command Sequences", level=2)
    para(
        doc,
        "send_sequence() executes a list of commands on a single drone "
        "in order. Each command waits for the previous one to complete.",
    )
    add_code(
        doc,
        """\
flight_plan = [
    DroneCommand.move(Direction.FORWARD, distance=2.0, speed=50),
    DroneCommand.turn(degrees=-45),
    DroneCommand.hover(duration=1.0),
    DroneCommand.move(Direction.LEFT, distance=1.0, speed=40),
]
manager.send_sequence("edu_1", flight_plan)
""",
    )

    doc.add_heading("9.4 Status Monitoring", level=2)
    add_code(
        doc,
        """\
# Get status of all drones at once
print(manager.status_report())
# {'edu_1': 'FLYING', 'rider_1': 'CONNECTED', 'wiz_1': 'FLYING'}
""",
    )

    doc.add_page_break()

    # =================================================================
    # 10. Adding a New Drone Platform
    # =================================================================
    doc.add_heading("10. Adding a New Drone Platform", level=1)
    para(
        doc,
        "The framework is designed so that adding a new drone requires "
        "exactly one new file and zero modifications to existing code. "
        "This is the Open/Closed Principle — and it is empirically "
        "verified by eval_extensibility.py (see Chapter 13).",
    )
    para(
        doc,
        "The worked example used throughout this chapter is the actual "
        "SimDrone reference adapter shipped with the framework "
        "(unified_drone/adapters/simdrone_adapter.py — 203 LOC of logic, "
        "one new file, zero modifications). Every code block below is "
        "verbatim from that file. The same adapter is what "
        "eval_extensibility.py exercises end-to-end to prove the "
        "zero-modification property.",
    )

    doc.add_heading("Step 1 — Header, Imports, and Registration", level=2)
    para(
        doc,
        "Create a new file under unified_drone/adapters/ (or anywhere in "
        "your project). Start with the module docstring, lazy-friendly "
        "imports, any protocol-level constants the vendor SDK needs, and "
        "the class declaration decorated with @register_drone.",
    )
    add_code(
        doc,
        """\
\"\"\"Adapter for the hypothetical SimDrone educational platform.

SimDrone is a Wi-Fi connected educational drone whose Python interface
exposes a text-based UDP socket protocol. It has several quirks that
require translation by the adapter:

  * Speed is specified in metres per second (0.0 - 10.0 m/s),
    not as a percentage (0 - 100).
  * Distances are specified in millimetres, not metres.
  * There is no combined RGB-LED command; the colour must be split into
    three independent single-channel commands.
  * The drone must be ARMED before takeoff and DISARMED after disconnect.
\"\"\"

from __future__ import annotations
import logging, socket, time
from typing import Any, Optional, Tuple

from ..core.base_adapter import DroneAdapter
from ..core.enums import Direction, DroneStatus
from ..core.exceptions import DroneCommandError, DroneConnectionError
from ..core.models import LEDColor
from ..core.registry import register_drone

logger = logging.getLogger(__name__)

# Protocol verbs (text)
_CMD_ARM, _CMD_DISARM        = "arm", "disarm"
_CMD_TAKEOFF, _CMD_LAND      = "takeoff", "land"
_CMD_EMERGENCY, _CMD_HOVER   = "emergency", "hover"
_CMD_GO, _CMD_ROTATE         = "go", "rotate"
_CMD_LED_R, _CMD_LED_G, _CMD_LED_B = "led_red", "led_green", "led_blue"

# Direction unit-vectors used to update internal position
_DIRECTION_VECTOR = {
    Direction.FORWARD: (0.0, 1.0, 0.0),
    Direction.BACKWARD: (0.0, -1.0, 0.0),
    Direction.LEFT:  (-1.0, 0.0, 0.0),
    Direction.RIGHT: ( 1.0, 0.0, 0.0),
    Direction.UP:    (0.0, 0.0,  1.0),
    Direction.DOWN:  (0.0, 0.0, -1.0),
}


@register_drone("simdrone")
class MockDroneAdapter(DroneAdapter):
    DEFAULT_HOST = "192.168.10.1"
    DEFAULT_PORT = 8889
    SPEED_MAX_MPS = 10.0   # SimDrone hardware limit

    def __init__(self, name="simdrone", host=DEFAULT_HOST,
                 port=DEFAULT_PORT, simulated=True) -> None:
        super().__init__(name=name)
        self._host, self._port, self._simulated = host, port, simulated
        self._socket: Optional[socket.socket] = None
        # Internal state
        self._x = self._y = self._z = 0.0
        self._yaw = 0.0
        self._battery = 100
        self._airborne = False
        self._led_state: Tuple[int, int, int] = (0, 0, 0)
        self._command_count = 0
""",
    )
    para(
        doc,
        "@register_drone(\"simdrone\") binds the class to the registry "
        "under the key \"simdrone\" the moment the module is imported. "
        "Internal state tracking (position, yaw, battery, command "
        "counter) is part of the adapter's contract — DroneManager "
        "never touches it directly.",
    )

    doc.add_heading("Step 2 — Lifecycle (connect, disconnect)", level=2)
    para(
        doc,
        "Connect is the canonical place to perform lazy imports of the "
        "vendor SDK and open transports. Disconnect should be best-effort "
        "(even if a final disarm packet fails, the socket must still close).",
    )
    add_code(
        doc,
        """\
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
            logger.info("SimDrone connected to %s:%d (sim=%s)",
                        host, port, self._simulated)
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
""",
    )

    doc.add_heading("Step 3 — Flight Primitives", level=2)
    para(
        doc,
        "takeoff, land, and emergency_stop are direct verb mappings. "
        "Each updates lifecycle status (DroneStatus) so DroneManager's "
        "status_report() reflects reality.",
    )
    add_code(
        doc,
        """\
    def takeoff(self) -> None:
        self._ensure_connected()
        self._send(_CMD_TAKEOFF)
        self._airborne = True
        self._z = 1.0          # default takeoff altitude
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
""",
    )

    doc.add_heading("Step 4 — Movement with Unit Translation", level=2)
    para(
        doc,
        "move() shows the heart of the Adapter pattern: framework units "
        "(metres, %) are translated to SimDrone units (mm, m/s) before "
        "the wire command is sent. The internal position is then updated "
        "from the direction vector so get_height() works without "
        "round-tripping the wire.",
    )
    add_code(
        doc,
        """\
    def move(self, direction: Direction,
             distance: float = 1.0, speed: float = 50.0) -> None:
        self._ensure_connected()
        vector = _DIRECTION_VECTOR.get(direction)
        if vector is None:
            raise DroneCommandError(f"Unsupported direction: {direction}")

        # Unit translation: framework -> SimDrone
        distance_mm = int(distance * 1000)                  # m  -> mm
        speed_mps = (max(0.0, min(speed, 100.0)) / 100.0) * self.SPEED_MAX_MPS  # % -> m/s

        cmd = (f"{_CMD_GO} {distance_mm} {speed_mps:.2f} "
               f"{vector[0]:.1f} {vector[1]:.1f} {vector[2]:.1f}")
        self._send(cmd)

        # Update tracked position
        self._x += vector[0] * distance
        self._y += vector[1] * distance
        self._z += vector[2] * distance
        self._consume_battery(1)

    def turn(self, degrees: float) -> None:
        self._ensure_connected()
        self._send(f"{_CMD_ROTATE} {int(degrees)}")
        self._yaw = (self._yaw + degrees) % 360.0
        self._consume_battery(1)

    def hover(self, duration: float = 1.0) -> None:
        self._ensure_connected()
        self._send(f"{_CMD_HOVER} {duration:.2f}")
        if not self._simulated:
            time.sleep(duration)
        self._consume_battery(1)
""",
    )

    doc.add_heading("Step 5 — Compensatory Mechanism: Splitting set_led", level=2)
    para(
        doc,
        "SimDrone exposes no combined RGB command — only three "
        "single-channel verbs. The adapter therefore splits one logical "
        "set_led() call into three protocol commands, applying brightness "
        "in software. The unified API stays clean: the user keeps "
        "calling DroneCommand.set_led(LEDColor(r, g, b)). This is the "
        "exact pattern documented as a \"capability gap\" compensation "
        "in Chapter 13.",
    )
    add_code(
        doc,
        """\
    def set_led(self, color: LEDColor) -> None:
        self._ensure_connected()
        b = max(0, min(color.brightness, 100)) / 100.0
        r  = int(color.red   * b)
        g  = int(color.green * b)
        bl = int(color.blue  * b)
        # SimDrone has no combined RGB command: split into 3 channels
        self._send(f"{_CMD_LED_R} {r}")
        self._send(f"{_CMD_LED_G} {g}")
        self._send(f"{_CMD_LED_B} {bl}")
        self._led_state = (r, g, bl)
""",
    )

    doc.add_heading("Step 6 — Telemetry", level=2)
    para(
        doc,
        "Battery and height are returned from the state already tracked "
        "in software — no need to round-trip the wire for values "
        "incrementally updated by every flight call.",
    )
    add_code(
        doc,
        """\
    def get_battery(self) -> int:
        self._ensure_connected()
        return self._battery

    def get_height(self) -> float:
        # SimDrone exposes height via the same channel as position;
        # we already track it natively in self._z (metres).
        self._ensure_connected()
        return self._z
""",
    )

    doc.add_heading("Step 7 — Internal Helpers", level=2)
    para(
        doc,
        "Private helpers keep the public surface narrow. _send() is the "
        "single point that touches the socket (simulated mode short-"
        "circuits to a log line); _ensure_connected() guards every "
        "public method against use-after-disconnect.",
    )
    add_code(
        doc,
        """\
    def _send(self, cmd: str) -> None:
        \"\"\"Send a command string. In simulated mode this is a no-op.\"\"\"
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
""",
    )

    doc.add_heading("Step 8 — Register and Use", level=2)
    para(
        doc,
        "SimDrone is shipped in unified_drone/adapters/ but is not in "
        "adapters/__init__.py — production builds stay free of test-only "
        "adapters by default. Importing it explicitly triggers the "
        "@register_drone decorator and makes the key available:",
    )
    add_code(
        doc,
        """\
import unified_drone.adapters
from unified_drone.adapters.simdrone_adapter import MockDroneAdapter

print(DroneRegistry.available())
# ['codrone_edu', 'coding_rider', 'wizwing', 'simdrone']

manager = DroneManager()
manager.add_drone("sim_1", "simdrone")          # no port, no hardware
manager.send_command("sim_1", DroneCommand.connect())
manager.send_command("sim_1", DroneCommand.takeoff())
# ... every unified command works transparently
""",
    )
    para(
        doc,
        "Zero existing files were modified. The new adapter registered "
        "itself via the decorator, and DroneManager discovered it via "
        "the registry. To add your own platform, repeat steps 1–8 against "
        "your vendor SDK; the structure stays identical. See Chapter 13 "
        "for the empirical measurement of this property.",
    )

    doc.add_page_break()

    # =================================================================
    # 11. Error Handling
    # =================================================================
    doc.add_heading("11. Error Handling", level=1)
    para(
        doc,
        "The framework uses a structured exception hierarchy rooted at "
        "DroneError. All drone-related exceptions can be caught with a "
        "single except DroneError clause, or handled specifically by type.",
    )

    doc.add_heading("11.1 Exception Hierarchy", level=2)
    add_code(
        doc,
        """\
DroneError (base)
    DroneConnectionError    # connection / disconnection failures
    DroneCommandError       # command execution failures
    DroneTimeoutError       # timeout during operations
    AdapterNotFoundError    # unregistered adapter key
""",
    )

    doc.add_heading("11.2 Handling Errors", level=2)
    add_code(
        doc,
        """\
from unified_drone import (
    DroneError, DroneConnectionError,
    DroneCommandError, AdapterNotFoundError,
)

try:
    manager.add_drone("drone_1", "unknown_platform")
except AdapterNotFoundError as e:
    print(f"Platform not found: {e}")

try:
    manager.send_command("drone_1", DroneCommand.takeoff())
except DroneConnectionError:
    print("Drone is not connected")
except DroneCommandError as e:
    print(f"Command failed: {e}")
except DroneError as e:
    print(f"General drone error: {e}")
""",
    )

    doc.add_heading("11.3 Broadcast Error Handling", level=2)
    para(
        doc,
        "broadcast_command() never raises. Instead, it catches errors "
        "per-drone and includes them in the result dictionary, so one "
        "drone can fail without aborting the rest of the mission.",
    )
    add_code(
        doc,
        """\
results = manager.broadcast_command(DroneCommand.takeoff())
for drone_id, result in results.items():
    if isinstance(result, Exception):
        print(f"FAILED  {drone_id}: {result}")
    else:
        print(f"OK      {drone_id}")
""",
    )

    doc.add_page_break()

    # =================================================================
    # 12. Logging and Monitoring
    # =================================================================
    doc.add_heading("12. Logging and Monitoring", level=1)
    para(
        doc,
        "Every component uses Python's built-in logging module. "
        "Adapters log every operation at an appropriate level.",
    )

    doc.add_heading("12.1 Enabling Logging", level=2)
    add_code(
        doc,
        """\
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s | %(levelname)s | %(message)s",
)

# Or configure specific loggers
logging.getLogger("unified_drone.adapters.codrone_edu").setLevel(logging.DEBUG)
""",
    )

    doc.add_heading("12.2 Log Levels", level=2)
    add_table(
        doc,
        ["Level", "Used for"],
        [
            ["DEBUG", "Raw serial data, internal dispatch"],
            ["INFO", "Successful operations (connect, takeoff, move, land)"],
            ["WARNING", "Emergency stops, paradigm bridges, unsupported features"],
            ["ERROR", "Failed operations during broadcasts"],
        ],
    )

    doc.add_page_break()

    # =================================================================
    # 13. Empirical Evaluation Results
    # =================================================================
    doc.add_heading("13. Empirical Evaluation Results", level=1)
    para(
        doc,
        "The framework is empirically evaluated across three dimensions. "
        "All experiments share one canonical Standard Mission "
        "(unified_drone/scenarios.py) so their measurements are directly "
        "comparable. Every experiment is reproducible: each script writes "
        "a CSV that the visualisation pipeline consumes.",
    )

    doc.add_heading("13.1 Standard Mission (11 commands)", level=2)
    add_table(
        doc,
        ["#", "Step", "Command", "Parameters"],
        [
            ["1", "connect", "DroneCommand.connect()", "—"],
            ["2", "takeoff", "DroneCommand.takeoff()", "—"],
            ["3", "hover", "DroneCommand.hover()", "duration=3.0"],
            ["4", "move", "DroneCommand.move()", "direction=FORWARD, distance=50, speed=30"],
            ["5", "turn", "DroneCommand.turn()", "degrees=90"],
            ["6", "get_battery", "DroneCommand.get_battery()", "— (first read)"],
            ["7", "get_height", "DroneCommand.get_height()", "—"],
            ["8", "set_led", "DroneCommand.set_led()", "LEDColor(red=255, green=0, blue=0)"],
            ["9", "get_battery_2", "DroneCommand.get_battery()", "— (drain check)"],
            ["10", "land", "DroneCommand.land()", "—"],
            ["11", "disconnect", "DroneCommand.disconnect()", "—"],
        ],
    )

    doc.add_heading("13.2 Extensibility (zero-modification proof)", level=2)
    para(
        doc,
        "Hypothesis: adding a new platform requires exactly one new file "
        "and zero modifications to existing framework code.",
    )
    para(
        doc,
        "Method: added a 4th drone — the SimDrone reference adapter "
        "(simdrone_adapter.py) — then measured what changed.",
    )
    add_table(
        doc,
        ["Metric", "Result"],
        [
            ["Files created", "1 (simdrone_adapter.py)"],
            ["Files modified", "0 (verified via git diff HEAD)"],
            ["Abstract methods implemented", "11 / 11"],
            ["Registry contains new key", "PASS (4 adapters registered)"],
            ["Factory creates correct type", "PASS"],
            ["All 4 drones respond to broadcast", "PASS (4 / 4)"],
            ["Original 3-drone workflow still works", "PASS"],
            ["Originals intact (no regression)", "PASS"],
        ],
    )
    para(
        doc,
        "Effort estimate (productivity range 15–35 LOC/h, midpoint 25 "
        "LOC/h; McConnell, Code Complete 2nd ed., §27.3):",
    )
    add_table(
        doc,
        ["Approach", "Hours (midpoint)", "Range", "LOC added"],
        [
            ["Extensible (this framework)", "8.12 h", "5.80–13.54 h", "203 LOC in one new file"],
            ["Non-extensible (hypothetical)", "12.92 h", "9.23–21.53 h", "203 + 120 LOC across 5 files"],
            ["Time saved", "4.80 h (37.1%)", "3.43–8.00 h", "—"],
        ],
    )
    para(
        doc,
        "The savings percentage is invariant under the productivity rate "
        "(37.1% at every point in the range); only the absolute hours "
        "scale, which makes the conclusion robust to criticism of the "
        "LOC/h figure.",
    )
    para(doc, "Adapter size comparison (LOC, logic only):")
    add_table(
        doc,
        ["Adapter file", "LOC"],
        [
            ["codrone_edu.py", "159"],
            ["coding_rider.py", "202"],
            ["wizwing.py", "211"],
            ["simdrone_adapter.py (NEW)", "203"],
            ["Average existing", "190.7"],
        ],
    )
    para(
        doc,
        "The new adapter is 1.06× the average of the existing three — "
        "well within the same order of magnitude, indicating predictable "
        "and consistent extension cost.",
    )

    doc.add_heading("13.3 Development Effort (Version A vs Version B)", level=2)
    para(
        doc,
        "Hypothesis: using the framework drastically reduces code and "
        "complexity compared to using native libraries directly.",
    )
    para(
        doc,
        "Method: the canonical 11-command Standard Mission is implemented "
        "twice — once with the framework (Version A: a 2-line loop over "
        "STANDARD_MISSION calling broadcast_command) and once with the "
        "native libraries side-by-side (Version B: per-vendor helper "
        "functions with explicit branching at every step). Both files are "
        "then statically analysed with Python's ast module.",
    )
    add_table(
        doc,
        ["Metric", "Version A (framework)", "Version B (native)", "Reduction"],
        [
            ["Lines of code (logic only)", "19", "169", "89%"],
            ["Import statements", "7", "11", "36%"],
            ["Distinct API method names", "3", "23", "87%"],
            ["Drone-object variables", "1 (manager)", "6", "83%"],
            ["If/elif decision blocks", "1", "27", "96%"],
            ["Try/except blocks", "0", "11", "100%"],
            ["Reusable code (%)", "73.7%", "40.8%", "+32.9 pp"],
        ],
    )
    para(
        doc,
        "The framework eliminates virtually all conditional branching "
        "and defensive exception handling in the user's code: one "
        "broadcast loop replaces 27 if/elif branches and 11 try/except "
        "blocks. Version A uses only 3 distinct method names while "
        "Version B requires 23 distinct vendor-specific calls.",
    )

    doc.add_heading("13.4 Interoperability (per-command verdicts)", level=2)
    para(
        doc,
        "Hypothesis: the framework can execute every unified command on "
        "every supported platform, either natively or via a documented "
        "compensatory mechanism.",
    )
    para(
        doc,
        "Method: eval_interoperability.py runs the 11-command suite on 3 "
        "mock platforms (33 executions total) with realistic simulated "
        "timing, recording pass/fail, latency, implementation kind "
        "(NATIVE vs COMPENSATORY), state transitions, and warnings.",
    )
    add_table(
        doc,
        ["Platform", "Tested", "PASS", "PARTIAL", "FAIL", "SKIP", "NATIVE", "COMP", "Avg ms"],
        [
            ["mock_codrone_edu", "11", "11", "0", "0", "0", "11", "0", "10.1"],
            ["mock_coding_rider", "11", "11", "0", "0", "0", "8", "3", "9.8"],
            ["mock_wizwing", "11", "11", "0", "0", "0", "9", "2", "9.0"],
            ["TOTAL", "33", "33 (100%)", "0", "0", "0", "28", "5", "—"],
        ],
    )
    para(
        doc,
        "Pass rate: 33/33 = 100%. Zero failures, zero partial "
        "degradations, zero skips. The 5 COMPENSATORY executions "
        "correspond to 4 distinct mechanisms (the suite calls "
        "get_battery twice to verify drain).",
    )
    add_table(
        doc,
        ["Platform", "Mechanism", "Kind", "Why compensatory"],
        [
            ["CodingRider", "get_battery", "Paradigm bridge", "Battery only exposed via setEventHandler + sendRequest; adapter blocks on threading.Event() until callback fires."],
            ["CodingRider", "get_height", "Paradigm bridge", "Same pattern using DataType.Altitude."],
            ["WIZWING", "hover", "Missing primitive", "No hover verb in the WIZWING protocol; adapter emulates via time.sleep() (FC stabilises altitude)."],
            ["WIZWING", "set_led", "Capability gap", "Only the funled preset is supported; arbitrary RGB cannot be specified."],
        ],
    )
    para(
        doc,
        "Three distinct kinds of heterogeneity — paradigm mismatch, "
        "missing primitive, capability gap — are absorbed transparently "
        "by the Adapter pattern. User code calls "
        "DroneCommand.hover(2.0) without knowing whether the platform "
        "implements it natively or via time.sleep().",
    )

    doc.add_heading("13.5 Reproducibility", level=2)
    add_code(
        doc,
        """\
python eval_extensibility.py            # ~0.3 s
python analyze_effort.py                # ~0.1 s
python eval_interoperability.py --fast  # ~0.3 s  (scaled timing)
python eval_interoperability.py         # ~30 s   (realistic timing)
python visualize_results.py             # regenerate all 11 charts
""",
    )
    para(
        doc,
        "All scripts exit with code 0 on success and 1 on failure, so "
        "they are suitable for CI gating.",
    )

    doc.add_page_break()

    # =================================================================
    # 14. Complete Code Examples
    # =================================================================
    doc.add_heading("14. Complete Code Examples", level=1)

    doc.add_heading("14.1 Multi-Platform Flight Demo", level=2)
    para(
        doc,
        "Manages three different drones simultaneously, demonstrating "
        "broadcasting, individual commands, and sequences.",
    )
    add_code(
        doc,
        """\
import logging
from unified_drone import (
    DroneManager, DroneCommand, Direction,
    DroneRegistry, LEDColor,
)
import unified_drone.adapters

logging.basicConfig(level=logging.INFO,
                    format="%(name)s | %(levelname)s | %(message)s")

print(DroneRegistry.available())
# ['codrone_edu', 'coding_rider', 'wizwing']

manager = DroneManager()
manager.add_drone("edu_1",   "codrone_edu", port="COM4")
manager.add_drone("rider_1", "coding_rider")
manager.add_drone("wiz_1",   "wizwing", port="COM3", baudrate=115200)

manager.broadcast_command(DroneCommand.connect())
manager.broadcast_command(DroneCommand.takeoff())

manager.send_command("edu_1",
    DroneCommand.move(Direction.FORWARD, distance=1.5, speed=60))
manager.send_command("rider_1", DroneCommand.turn(degrees=90))
manager.send_command("wiz_1",
    DroneCommand.set_led(LEDColor(red=255, green=0, blue=0)))

batteries = manager.broadcast_command(DroneCommand.get_battery())
for drone_id, level in batteries.items():
    print(f"  {drone_id}: battery = {level}%")

flight_plan = [
    DroneCommand.move(Direction.FORWARD, distance=2.0, speed=50),
    DroneCommand.turn(degrees=-45),
    DroneCommand.hover(duration=1.0),
    DroneCommand.move(Direction.LEFT, distance=1.0, speed=40),
]
manager.send_sequence("edu_1", flight_plan)

manager.broadcast_command(DroneCommand.land())
manager.broadcast_command(DroneCommand.disconnect())
print(manager.status_report())
""",
    )

    doc.add_heading("14.2 Reusable Flight Logic", level=2)
    para(
        doc,
        "Because the interface is unified, you can write functions that "
        "accept a drone ID and a manager and work with any platform.",
    )
    add_code(
        doc,
        """\
def square_flight(manager, drone_id, side_length=1.0, speed=50):
    \"\"\"Fly a square pattern. Works with any drone platform.\"\"\"
    for _ in range(4):
        manager.send_command(drone_id,
            DroneCommand.move(Direction.FORWARD,
                              distance=side_length, speed=speed))
        manager.send_command(drone_id,
            DroneCommand.turn(degrees=90))

# Works identically on any drone, including SimDrone:
square_flight(manager, "edu_1", side_length=2.0)
square_flight(manager, "wiz_1", side_length=1.5)
square_flight(manager, "sim_1", side_length=1.0)
""",
    )

    doc.add_heading("14.3 Resilient Broadcast", level=2)
    para(
        doc,
        "Use the broadcast result dictionary to land healthy drones even "
        "if one fails to take off:",
    )
    add_code(
        doc,
        """\
results = manager.broadcast_command(DroneCommand.takeoff())
failed = [d for d, r in results.items() if isinstance(r, Exception)]
if failed:
    print(f"Takeoff failed for: {failed}. Landing the rest.")
manager.broadcast_command(DroneCommand.land())
""",
    )

    doc.add_page_break()

    # =================================================================
    # 15. Troubleshooting
    # =================================================================
    doc.add_heading("15. Troubleshooting", level=1)
    add_table(
        doc,
        ["Symptom", "Likely cause", "Fix"],
        [
            [
                "AdapterNotFoundError on add_drone()",
                "The adapter module was not imported, so its @register_drone never ran.",
                "Add `import unified_drone.adapters` (3 built-ins) or `from unified_drone.adapters.simdrone_adapter import MockDroneAdapter` (SimDrone).",
            ],
            [
                "ModuleNotFoundError: codrone_edu / CodingRider / serial",
                "Vendor library is not installed.",
                "pip install codrone-edu / CodingRider / pyserial — only the ones you need.",
            ],
            [
                "DroneConnectionError on connect()",
                "Wrong COM port or drone powered off.",
                "Verify the port number and pairing status; on Windows check Device Manager > Ports (COM & LPT).",
            ],
            [
                "broadcast_command result contains exceptions",
                "Per-drone error; broadcast does not raise.",
                "Iterate results and isinstance(r, Exception) to decide whether to abort or continue.",
            ],
            [
                "WIZWING set_led has no visible effect on requested colour",
                "Compensatory mechanism: WIZWING only supports the funled preset; arbitrary RGB is logged as a warning.",
                "Expected behaviour; check WARNING-level log messages.",
            ],
            [
                "CodingRider get_battery hangs",
                "Async->sync bridge timed out because the event callback never fired.",
                "Confirm the drone is connected and that DataType.State events are being delivered.",
            ],
            [
                "TypeError: missing 1 required positional argument: 'speed'",
                "DroneCommand.move() called without all required arguments.",
                "Pass direction, distance, and speed (or rely on defaults distance=1.0, speed=50).",
            ],
            [
                "Eval scripts exit with code 1 in CI",
                "An experiment failed an assertion (e.g., interop pass-rate dropped).",
                "Re-run with --verbose; check the CSV outputs in the repo root for the failing row.",
            ],
        ],
    )

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— End of Manual —")
    r.italic = True

    return doc


# ---------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    doc = build_document()
    out = "unified_drone_manual.docx"
    doc.save(out)
    print(f"Wrote {out}")
