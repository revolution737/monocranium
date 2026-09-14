# AGENTS.md — AI Coding Agent Directives

## 1. Purpose
This document governs the operational behavior, architectural constraints, and code generation standards for AI coding agents operating on the **Monocranium** repository.

---

## 2. Repository Context
Monocranium is a modular, high-reliability MAVLink control bridge engineered for unmanned vehicles. It eliminates complicated flight-controller configurations by pairing autonomous auto-calibration with a Betaflight/iNav-inspired PWA dashboard.

The architecture comprises two separate processes communicating over TCP:
- **Process 1 (Core Bridge)**: Asyncio event-driven MAVLink bridge, telemetry bus, vehicle registry, parameter store, auto-config engine, WebSocket and HTTP servers.
- **Process 2 (Virtual Rover)**: Pygame 4WD skid-steer simulation running kinematics on the main thread and a MAVLink TCP server in a background asyncio loop.

---

## 3. Import Quarantine Rules
- **`pymavlink` Quarantine**:
  - `pymavlink` may ONLY be imported in `src/core/protocol.py` (for Core Bridge) and `src/simulators/rover_sim.py` (for simulator MAVLink synthesis).
  - Under no circumstances may any other file import `pymavlink` or `pymavlink.mavutil`.
- **`pygame` Quarantine**:
  - `pygame` may ONLY be imported in `src/simulators/rover_renderer.py`.
  - All kinematics, physics, configuration, and server logic must remain completely decoupled from pygame.

---

## 4. File Ownership Matrix

| File | Owns | Strict Invariant: No other file may... |
|---|---|---|
| `src/core/types.py` | ALL shared dataclasses and enums | ...define dataclasses or enums |
| `src/core/protocol.py` | ALL pymavlink protocol decoding / factory | ...import pymavlink in core |
| `src/simulators/rover_renderer.py` | ALL pygame rendering and visual loop | ...import pygame |
| `src/simulators/rover_config.py` | ALL rover hardware constants & spec | ...define rover-specific hardware constants |
| `src/server/ws_handlers.py` | ALL WebSocket command routing & dispatch | ...parse WebSocket JSON commands |

---

## 5. Coding Invariants (The 12 Rules)

1. **Phase Order Is Mandatory**: Never begin a phase until preceding phases pass all verification gates.
2. **One File At A Time**: Work incrementally; write matching unit tests immediately.
3. **Never Use `print()`**: Use `logging.getLogger(__name__)`.
4. **Never Use Bare `except:`**: Catch explicit exception types; always log or re-raise.
5. **Every Public Function Needs Type Annotations AND A Docstring**: Strict typing throughout.
6. **Import Quarantine**: Adhere strictly to the quarantine rules above.
7. **No Magic Numbers**: Define constants with descriptive names.
8. **No Mutable Default Arguments**: Use `None` as default.
9. **Log Every Decision**: Append all design decisions and non-trivial trade-offs to `decisions.md`.
10. **No TODO or FIXME Comments**: Complete all implementations fully.
11. **Frozen Dataclasses Only**: Dataclasses in `types.py` and `rover_config.py` must declare `frozen=True`.
12. **Maximum Function Length**: 40 lines max (excluding docstrings). Extract private helpers when necessary.

---

## 6. Testing Rules
- Unit tests reside in `tests/test_<module>.py`.
- Mock all networking and hardware I/O. Unit tests must run offline in milliseconds.
- Minimum 2 tests per public method (covering nominal path and error/boundary path).
- All tests must pass: `python -m pytest tests/ -v --tb=short`.

---

## 7. What NOT To Do
- Do **NOT** modify `src/core/types.py` to inject vehicle-specific fields (keep types generic across rovers, drones, etc.).
- Do **NOT** place business logic inside `src/main.py` (wiring only).
- Do **NOT** introduce TailwindCSS, React Router, Redux, or Create React App.
- Do **NOT** use `time.sleep()` in asynchronous loops; use `asyncio.sleep()`.
- Do **NOT** catch `Exception` without logging or re-raising.
