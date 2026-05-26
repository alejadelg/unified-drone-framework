# Practical Usage Guide

A progressive walkthrough showing how a programmer interacts with the
Unified Drone Control Framework — from the simplest "hello world" to
a full multi-drone choreographed mission.

---

## Table of Contents

1. [Setup and Imports](#setup-and-imports)
2. [One Drone, One Command](#step-1--one-drone-one-command-hello-world)
3. [Sequence of Commands on One Drone](#step-2--a-sequence-of-commands-on-one-drone)
4. [Several Drones, Same Action (broadcast)](#step-3--several-drones-same-action-broadcast)
5. [Choreography: Each Drone Does Something Different](#step-4--choreography-each-drone-does-something-different)
6. [Parallel Per-Drone Sequences](#step-5--parallel-per-drone-sequences)
7. [Collecting Telemetry Across the Fleet](#step-6--collecting-telemetry-across-the-fleet)
8. [Error Handling](#step-7--error-handling)
9. [Complete Worked Example: 3-Drone Search Mission](#complete-worked-example--3-drone-search-mission)
10. [What the Programmer Never Has to Do](#what-the-programmer-never-has-to-do)
11. [Public API at a Glance](#public-api-at-a-glance)

---

## Setup and Imports

These five lines are the **only** imports the programmer needs to learn,
regardless of which drones will be controlled later:

```python
from unified_drone import (
    DroneManager,    # multi-drone orchestrator
    DroneCommand,    # commands (immutable objects)
    Direction,       # FORWARD / BACKWARD / LEFT / RIGHT / UP / DOWN
    LEDColor,        # RGB + brightness
)
import unified_drone.adapters   # registers the 3 built-in adapters

manager = DroneManager()
```

> **Testing without hardware?** The repository ships a 4th reference
> adapter — `simdrone_adapter.py` — that simulates a Wi-Fi drone
> entirely in-process. Register it with
> `from unified_drone.adapters.simdrone_adapter import MockDroneAdapter`
> followed by `manager.add_drone("sim_1", "simdrone")`. Every example
> below works against it with no hardware attached.

## Step 1 — One drone, one command ("hello world")

```python
# Register a drone (this is the ONLY line where the vendor key appears)
manager.add_drone("my_drone", "codrone_edu", port="COM4")

# Fly it
manager.send_command("my_drone", DroneCommand.connect())
manager.send_command("my_drone", DroneCommand.takeoff())
manager.send_command("my_drone", DroneCommand.hover(duration=2.0))
manager.send_command("my_drone", DroneCommand.land())
manager.send_command("my_drone", DroneCommand.disconnect())
```

To switch platforms, **only the second argument of `add_drone` changes**:

```python
manager.add_drone("my_drone", "coding_rider")                            # ← only this changes
manager.add_drone("my_drone", "wizwing", port="COM3", baudrate=9600)     # ← only this changes
```

The rest of the code is **untouched**. That is the value of the framework.

## Step 2 — A sequence of commands on one drone

```python
mission = [
    DroneCommand.takeoff(),
    DroneCommand.move(Direction.FORWARD, distance=1.0, speed=50),
    DroneCommand.turn(degrees=90),
    DroneCommand.move(Direction.FORWARD, distance=1.0, speed=50),
    DroneCommand.turn(degrees=90),
    DroneCommand.hover(duration=2.0),
    DroneCommand.land(),
]

manager.send_sequence("my_drone", mission)
```

Commands run in order; each one waits for the previous to finish. The
programmer expresses the mission as a list of `DroneCommand` objects
without worrying about synchronisation.

## Step 3 — Several drones, same action (broadcast)

```python
# Register three drones from three different vendors
manager.add_drone("alpha",   "codrone_edu", port="COM4")
manager.add_drone("bravo",   "coding_rider")
manager.add_drone("charlie", "wizwing", port="COM3", baudrate=9600)

# A single line makes all three drones take off together
manager.broadcast_command(DroneCommand.connect())
manager.broadcast_command(DroneCommand.takeoff())

# Formation flight
manager.broadcast_command(DroneCommand.move(Direction.FORWARD, distance=2.0, speed=50))
manager.broadcast_command(DroneCommand.turn(degrees=90))

# Land everyone
manager.broadcast_command(DroneCommand.land())
manager.broadcast_command(DroneCommand.disconnect())
```

**What's important:** one line controls all three drones. Internally the
framework:

1. Iterates over the registered drone dictionary.
2. Calls `adapter.execute(cmd)` on each one.
3. Captures per-drone errors (no abort if one fails).
4. Returns a `{drone_id: result_or_exception}` dictionary.

## Step 4 — Choreography: each drone does something different

This is the most interesting case. **Each drone has its own role**:

```python
# Register the fleet
manager.add_drone("leader",  "codrone_edu", port="COM4")
manager.add_drone("right",   "coding_rider")
manager.add_drone("left",    "wizwing", port="COM3", baudrate=9600)

# Synchronised takeoff (broadcast)
manager.broadcast_command(DroneCommand.connect())
manager.broadcast_command(DroneCommand.takeoff())
manager.broadcast_command(DroneCommand.hover(duration=2.0))   # stabilise

# --- Choreography: different roles per drone ---

# The leader climbs
manager.send_command("leader", DroneCommand.move(Direction.UP, distance=0.5, speed=40))

# The right drone moves right
manager.send_command("right", DroneCommand.move(Direction.RIGHT, distance=1.0, speed=40))

# The left drone moves left
manager.send_command("left", DroneCommand.move(Direction.LEFT, distance=1.0, speed=40))

# Each one turns on a different LED colour
manager.send_command("leader", DroneCommand.set_led(LEDColor(red=255, green=0,   blue=0)))   # red
manager.send_command("right",  DroneCommand.set_led(LEDColor(red=0,   green=255, blue=0)))   # green
manager.send_command("left",   DroneCommand.set_led(LEDColor(red=0,   green=0,   blue=255))) # blue

# Everyone hovers for 3 seconds (broadcast again)
manager.broadcast_command(DroneCommand.hover(duration=3.0))

# Synchronised landing
manager.broadcast_command(DroneCommand.land())
manager.broadcast_command(DroneCommand.disconnect())
```

The programmer freely mixes **two modes** as needed:

- `broadcast_command(cmd)` — when every drone should do the same thing.
- `send_command(drone_id, cmd)` — when a specific drone should do something specific.

## Step 5 — Parallel per-drone sequences

When each drone has its **own mission** (several ordered actions), use
`send_sequence`:

```python
# Each drone has its own ordered mission
leader_mission = [
    DroneCommand.takeoff(),
    DroneCommand.move(Direction.UP, distance=1.5, speed=30),
    DroneCommand.hover(duration=5.0),
    DroneCommand.land(),
]

explorer_mission = [
    DroneCommand.takeoff(),
    DroneCommand.move(Direction.FORWARD, distance=3.0, speed=40),
    DroneCommand.turn(degrees=180),
    DroneCommand.move(Direction.FORWARD, distance=3.0, speed=40),
    DroneCommand.land(),
]

observer_mission = [
    DroneCommand.takeoff(),
    DroneCommand.hover(duration=10.0),    # stays put, observing
    DroneCommand.land(),
]

manager.broadcast_command(DroneCommand.connect())

# Each drone executes its own mission
manager.send_sequence("leader", leader_mission)
manager.send_sequence("right",  explorer_mission)
manager.send_sequence("left",   observer_mission)

manager.broadcast_command(DroneCommand.disconnect())
```

## Step 6 — Collecting telemetry across the fleet

`broadcast_command` returns a dictionary with the result from each drone:

```python
# Query battery on all three at once
batteries = manager.broadcast_command(DroneCommand.get_battery())
# batteries = {'leader': 87, 'right': 91, 'left': 65}

for drone_id, battery in batteries.items():
    if isinstance(battery, int) and 0 <= battery < 30:
        print(f"WARNING: {drone_id} has low battery ({battery}%) — land soon")

# Query altitude
heights = manager.broadcast_command(DroneCommand.get_height())
# heights = {'leader': 1.5, 'right': 1.2, 'left': 1.4}
```

## Step 7 — Error handling

The framework exposes a clean exception hierarchy:

```python
from unified_drone import DroneError, DroneConnectionError

try:
    manager.send_command("leader", DroneCommand.takeoff())
except DroneConnectionError:
    print("The leader is not connected — aborting mission")
    manager.broadcast_command(DroneCommand.land())   # land the rest
except DroneError as e:
    print(f"Drone error: {e}")
```

For `broadcast_command`, exceptions do NOT propagate — they are stored
in the returned dictionary:

```python
results = manager.broadcast_command(DroneCommand.takeoff())

for drone_id, result in results.items():
    if isinstance(result, Exception):
        print(f"FAILED  {drone_id}: {result}")
    else:
        print(f"OK      {drone_id}")
```

This allows **one drone to fail without aborting the whole mission**.

---

## Complete worked example — 3-drone search mission

Putting all the concepts together in a realistic scenario:

```python
from unified_drone import (
    DroneManager, DroneCommand, Direction, LEDColor,
    DroneError, DroneConnectionError,
)
import unified_drone.adapters
import logging

logging.basicConfig(level=logging.INFO)


def search_mission():
    manager = DroneManager()

    # === SETUP ===
    # Three drones from different vendors (the ONLY vendor-specific configuration)
    manager.add_drone("scout_north", "codrone_edu", port="COM4")
    manager.add_drone("scout_south", "coding_rider")
    manager.add_drone("command",     "wizwing", port="COM3", baudrate=9600)

    # === PHASE 1: Connect and synchronised takeoff ===
    connected = manager.broadcast_command(DroneCommand.connect())
    failed = [d for d, r in connected.items() if isinstance(r, Exception)]
    if failed:
        print(f"Could not connect: {failed}. Aborting.")
        return

    manager.broadcast_command(DroneCommand.takeoff())
    manager.broadcast_command(DroneCommand.hover(duration=2.0))   # stabilise

    # === PHASE 2: Choreography — each drone searches its own zone ===

    # Scout North explores forward
    manager.send_sequence("scout_north", [
        DroneCommand.move(Direction.FORWARD, distance=3.0, speed=50),
        DroneCommand.turn(degrees=180),
        DroneCommand.move(Direction.FORWARD, distance=3.0, speed=50),
    ])

    # Scout South explores to the right
    manager.send_sequence("scout_south", [
        DroneCommand.move(Direction.RIGHT, distance=2.5, speed=50),
        DroneCommand.turn(degrees=180),
        DroneCommand.move(Direction.RIGHT, distance=2.5, speed=50),
    ])

    # Command drone holds centre, observing
    manager.send_command("command", DroneCommand.hover(duration=10.0))

    # === PHASE 3: Colour-coded signalling (each drone with its own LED) ===
    manager.send_command("scout_north", DroneCommand.set_led(LEDColor(255, 0, 0)))   # red
    manager.send_command("scout_south", DroneCommand.set_led(LEDColor(0, 255, 0)))   # green
    manager.send_command("command",     DroneCommand.set_led(LEDColor(0, 0, 255)))   # blue

    # === PHASE 4: Telemetry — check batteries ===
    batteries = manager.broadcast_command(DroneCommand.get_battery())
    print(f"Final batteries: {batteries}")

    for drone_id, battery in batteries.items():
        if isinstance(battery, int) and 0 <= battery < 30:
            print(f"WARNING  {drone_id}: low battery ({battery}%)")

    # === PHASE 5: Synchronised landing ===
    manager.broadcast_command(DroneCommand.land())
    manager.broadcast_command(DroneCommand.disconnect())

    print("Mission complete.")


if __name__ == "__main__":
    search_mission()
```

---

## What the programmer never has to do

| What the programmer does NOT write | Who handles it |
|---|---|
| `from codrone_edu.drone import Drone` | The CoDrone EDU adapter |
| `drone.sendTakeOff()` vs `drone.takeoff()` by vendor | The adapter |
| `serial.Serial(port=COM3, baudrate=9600, ...)` | The WIZWING adapter |
| `setEventHandler(DataType.State, callback)` + `sendRequest(...)` | The CodingRider adapter (async→sync bridge) |
| Building ASCII packets such as `b'forward 250 1000\r'` | The WIZWING adapter |
| Working around "WIZWING only has `funled`, no RGB" | The WIZWING adapter |
| Per-vendor `try/except` for every call | `broadcast_command` |

---

## Public API at a Glance

The programmer uses only **four manager methods** and a set of
`DroneCommand` factory classmethods. That is the entire surface area.

### DroneManager methods

| Method | Purpose |
|---|---|
| `manager.add_drone(id, key, **kwargs)` | Register a drone in the fleet (once per drone) |
| `manager.send_command(id, cmd)` | Send one command to one specific drone |
| `manager.broadcast_command(cmd)` | Send one command to ALL registered drones |
| `manager.send_sequence(id, [cmds])` | Send N commands in order to one drone |
| `manager.drone_ids` | Property: list of registered drone IDs |
| `manager.status_report()` | Snapshot dict of every drone's current status |
| `manager.remove_drone(id)` | Unregister a drone (disconnects first if needed) |

### DroneCommand factories

| Lifecycle | Movement | Telemetry / LED |
|---|---|---|
| `.connect()` | `.move(direction, distance, speed)` | `.get_battery()` |
| `.disconnect()` | `.turn(degrees)` | `.get_height()` |
| `.takeoff()` | `.hover(duration)` | `.get_status()` |
| `.land()` | | `.set_led(color)` |
| `.emergency_stop()` | | |

**That's all.** Any student with basic Python skills can read and modify
a choreographed mission script within their first hour with the framework.
