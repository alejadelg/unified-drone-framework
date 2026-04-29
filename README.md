# Unified Drone Control Framework

A reusable, extensible Python framework that abstracts the differences between
heterogeneous educational drone control libraries behind a single unified
interface. Write your control logic once, deploy it across multiple drone
platforms.

[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

---

## Overview

Educational drone platforms each ship their own Python library with different
APIs, naming conventions, and communication protocols. This framework solves
the interoperability problem by providing a single, consistent interface that
translates generic commands into platform-specific operations.

The same `DroneCommand.takeoff()` works on a CoDrone EDU, a CodingRider, and a
WIZWING drone — the framework handles the translation transparently.

## Key Features

- **Unified command interface** across multiple drone platforms
- **Adapter pattern** isolates platform-specific code from user logic
- **Open/Closed design** — add new drones without modifying existing code
- **Command pattern** with immutable, replayable command objects
- **Multi-drone orchestration** with broadcast and command sequencing
- **Built-in logging** at every operation level
- **Clean exception hierarchy** for structured error handling
- **Zero external dependencies** beyond the drone libraries themselves
- **Python standard library only** — uses only `abc`, `dataclasses`, `enum`, `typing`, `logging`, `struct`

## Supported Drone Platforms

| Platform     | Library              | Communication    | Registry Key      |
|--------------|----------------------|------------------|-------------------|
| CoDrone EDU  | CoDrone (Robolink)   | Bluetooth        | `codrone_edu`     |
| CodingRider  | CodingRider.drone    | Bluetooth/Wi-Fi  | `coding_rider`    |
| WIZWING      | pyserial             | Serial (USB)     | `wizwing`         |

## Architecture

```
User Code / Application
        |
        v
DroneManager  -->  DroneRegistry  -->  DroneAdapter (ABC)
                                            |
            +-------------------------------+-------------------------------+
            |                               |                               |
            v                               v                               v
   CoDroneEduAdapter            CodingRiderAdapter                  WizwingAdapter
   (CoDrone library)            (CodingRider.drone)                 (pyserial)
```

Three design patterns form the architectural foundation:

- **Adapter Pattern** — Each drone library has a dedicated adapter class
  (`CoDroneEduAdapter`, `CodingRiderAdapter`, `WizwingAdapter`) that translates
  the unified interface into library-specific API calls.
- **Command Pattern** — Flight operations are immutable `DroneCommand` data
  objects that decouple *what to do* from *how to do it*.
- **Factory/Registry Pattern** — `DroneRegistry` maps string keys to adapter
  classes via the `@register_drone` decorator, enforcing the Open/Closed
  Principle.

## Installation

### Requirements

- Python 3.8 or later
- Drone-specific libraries (only those you plan to use)

### Get the framework

```bash
git clone https://github.com/YOUR_USERNAME/unified-drone-framework.git
cd unified-drone-framework
```

### Install drone libraries (only what you need)

```bash
pip install CoDrone        # for CoDrone EDU
pip install CodingRider    # for CodingRider
pip install pyserial       # for WIZWING
```

### Verify the installation

```bash
python -c "from unified_drone import DroneRegistry; import unified_drone.adapters; print(DroneRegistry.available())"
```

Expected output:

```
['codrone_edu', 'coding_rider', 'wizwing']
```

## Quick Start

```python
from unified_drone import DroneManager, DroneCommand, Direction
import unified_drone.adapters  # triggers adapter registration

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
```

To switch platforms, only the `add_drone()` line changes — all command logic
stays identical:

```python
# Same script, different drone:
manager.add_drone("my_drone", "wizwing", port="COM5", baudrate=115200)
```

## Multi-Drone Orchestration

```python
manager = DroneManager()
manager.add_drone("edu_1", "codrone_edu", port="COM4")
manager.add_drone("rider_1", "coding_rider")
manager.add_drone("wiz_1", "wizwing", port="COM5")

# Broadcast: send the same command to ALL drones
manager.broadcast_command(DroneCommand.connect())
manager.broadcast_command(DroneCommand.takeoff())

# Send a sequence of commands to one drone
flight_plan = [
    DroneCommand.move(Direction.FORWARD, distance=2.0, speed=50),
    DroneCommand.turn(degrees=-45),
    DroneCommand.hover(duration=1.0),
    DroneCommand.move(Direction.LEFT, distance=1.0, speed=40),
]
manager.send_sequence("edu_1", flight_plan)

# Land everyone
manager.broadcast_command(DroneCommand.land())
```

## Adding a New Drone Platform

The framework is designed so adding a new platform requires **one new file
and zero modifications to existing code**.

```python
# unified_drone/adapters/tello.py
from unified_drone import DroneAdapter, register_drone
from unified_drone.core.enums import Direction, DroneStatus

@register_drone("tello")
class TelloAdapter(DroneAdapter):

    def __init__(self, name: str = "tello") -> None:
        super().__init__(name=name)
        self._tello = None

    def connect(self, **kwargs) -> None:
        from djitellopy import Tello
        self._tello = Tello()
        self._tello.connect()
        self._status = DroneStatus.CONNECTED

    def takeoff(self) -> None:
        self._tello.takeoff()
        self._status = DroneStatus.FLYING

    # ... implement remaining abstract methods
```

After importing the new module, the registry recognizes the new platform:

```python
import unified_drone.adapters.tello

manager = DroneManager()
manager.add_drone("my_tello", "tello")  # works immediately
```

## Project Structure

```
unified_drone/
├── __init__.py                # Public API re-exports
├── core/
│   ├── enums.py               # FlightAction, Direction, DroneStatus
│   ├── models.py              # DroneCommand, Position, LEDColor (frozen dataclasses)
│   ├── exceptions.py          # DroneError hierarchy
│   ├── base_adapter.py        # DroneAdapter abstract base class
│   ├── registry.py            # DroneRegistry + @register_drone decorator
│   └── manager.py             # DroneManager: multi-drone orchestration
├── adapters/
│   ├── __init__.py            # Auto-registers built-in adapters
│   ├── codrone_edu.py         # CoDrone EDU adapter
│   ├── coding_rider.py        # CodingRider adapter
│   └── wizwing.py             # WIZWING serial adapter
└── examples/
    ├── basic_usage.py         # Multi-platform unified control demo
    └── add_new_drone.py       # Extensibility demo (DJI Tello)
```

## Available Commands

| Factory Method                | Parameters                              | Description                |
|-------------------------------|-----------------------------------------|----------------------------|
| `DroneCommand.connect()`      | `**kwargs` (e.g., port)                 | Connect to drone           |
| `DroneCommand.disconnect()`   | none                                    | Disconnect from drone      |
| `DroneCommand.takeoff()`      | none                                    | Take off                   |
| `DroneCommand.land()`         | none                                    | Land                       |
| `DroneCommand.emergency_stop()` | none                                  | Emergency motor stop       |
| `DroneCommand.move()`         | `direction`, `distance=1.0`, `speed=50` | Move in a direction        |
| `DroneCommand.turn()`         | `degrees`                               | Rotate (+CW / -CCW)        |
| `DroneCommand.hover()`        | `duration=1.0`                          | Hold position (seconds)    |
| `DroneCommand.set_led()`      | `color: LEDColor`                       | Set LED color              |
| `DroneCommand.get_battery()`  | none                                    | Query battery level        |
| `DroneCommand.get_status()`   | none                                    | Query drone status         |

## Error Handling

```python
from unified_drone import DroneError, DroneConnectionError, AdapterNotFoundError

try:
    manager.send_command("drone_1", DroneCommand.takeoff())
except DroneConnectionError:
    print("Drone is not connected")
except DroneError as e:
    print(f"General drone error: {e}")
```

Exception hierarchy:

```
DroneError (base)
    DroneConnectionError    # connection / disconnection failures
    DroneCommandError       # command execution failures
    DroneTimeoutError       # operation timeouts
    AdapterNotFoundError    # unregistered adapter key
```

## Logging

Every framework component uses Python's standard `logging` module.

```python
import logging
logging.basicConfig(level=logging.INFO,
                    format="%(name)s | %(levelname)s | %(message)s")
```

| Level   | Used for                                                   |
|---------|------------------------------------------------------------|
| DEBUG   | Raw serial data, internal dispatch                         |
| INFO    | Successful operations (connect, takeoff, move, land)       |
| WARNING | Emergency stops, unsupported features, adapter overwrites  |
| ERROR   | Failed operations during broadcasts                        |

## Documentation

A complete user manual is included as `unified_drone_manual.docx` covering:

- Architecture and design patterns
- Detailed API reference for every class
- Per-platform documentation with API translation tables
- Step-by-step extension tutorial
- Complete code examples
- Troubleshooting guide

## Examples

The `unified_drone/examples/` directory includes runnable demos:

- **`basic_usage.py`** — Multi-platform unified control across all 3 drones
- **`add_new_drone.py`** — Adding a 4th drone (DJI Tello) without modifying existing code

Run them with:

```bash
python -m unified_drone.examples.basic_usage
python -m unified_drone.examples.add_new_drone
```

## Design Principles

This framework follows core software engineering principles:

- **Single Responsibility** — Each class has one clear purpose
- **Open/Closed** — Open for extension, closed for modification
- **Liskov Substitution** — Any adapter is interchangeable through the base interface
- **Interface Segregation** — Clean, focused abstract interface
- **Dependency Inversion** — `DroneManager` depends on abstractions, not concrete classes

## License

This project is released under the MIT License. See `LICENSE` for details.

## Contributing

Contributions are welcome. To add a new drone platform:

1. Create a new file in `unified_drone/adapters/`
2. Subclass `DroneAdapter` and implement all abstract methods
3. Decorate the class with `@register_drone("your_key")`
4. Add the import to `unified_drone/adapters/__init__.py`
5. Open a pull request

No existing files need to be modified.

---

Built as a clean-architecture demonstration for educational drone interoperability.
