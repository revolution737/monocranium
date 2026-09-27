# Monocranium — Decision Log

Every non-trivial decision is recorded here. This is a living document.

Format for each entry:
- **Date**: YYYY-MM-DD
- **Context**: What problem or question prompted this decision
- **Decision**: What was decided
- **Rationale**: Why this option was chosen
- **Alternatives Considered**: What other options existed

---

## DECISION-001: Two-Process Architecture

- **Date**: 2026-09-14
- **Context**: The rover simulator needs pygame (which requires the main thread on Linux) and the Core Bridge needs asyncio. These conflict if run in the same process.
- **Decision**: Run the rover simulator and the Core Bridge as two separate Python processes. They communicate over TCP using MAVLink.
- **Rationale**: This mirrors real-world deployment (Raspberry Pi is a separate device from the rover board). It also avoids the pygame/asyncio main-thread conflict.
- **Alternatives Considered**: (1) Run both in one process using threading — rejected because pygame's event loop must run on the main thread. (2) Use multiprocessing — rejected because TCP communication is simpler and more realistic.

---

## DECISION-002: Pygame on Main Thread, Asyncio in Background Thread

- **Date**: 2026-09-14
- **Context**: The rover simulator process needs both pygame (main thread) and an asyncio TCP server (for MAVLink).
- **Decision**: Run the asyncio event loop in a background daemon thread. Run the pygame loop on the main thread.
- **Rationale**: pygame requires the main thread on Linux/macOS. asyncio can run in any thread via `asyncio.run_coroutine_threadsafe()` or thread-safe state sharing.
- **Alternatives Considered**: (1) Use `pygame.event.set_grab()` with asyncio on main — rejected because pygame still needs main thread for display init.

---

## DECISION-003: pymavlink Quarantined to protocol.py (and rover_sim.py)

- **Date**: 2026-09-14
- **Context**: pymavlink has a complex API surface and inconsistent naming. Spreading it across the codebase would make maintenance hard.
- **Decision**: Only `src/core/protocol.py` (for the Core Bridge) and `src/simulators/rover_sim.py` (for simulator MAVLink synthesis) may import pymavlink. All other files call functions in `protocol.py`.
- **Rationale**: Single point of change if pymavlink API changes. Easier to test (mock one module). Cleaner interfaces.
- **Alternatives Considered**: (1) Let any file import pymavlink — rejected for maintainability reasons.

---

## DECISION-004: Differential-Drive Kinematics

- **Date**: 2026-09-14
- **Context**: Need a motion model for the virtual rover.
- **Decision**: Use differential-drive (skid-steer) kinematic equations: `v = (v_r + v_l) / 2`, `ω = (v_r - v_l) / L`.
- **Rationale**: Matches real 4WD skid-steer rovers. Simple to implement. No physics engine dependency.
- **Alternatives Considered**: (1) Ackermann steering — rejected because our rover is skid-steer. (2) Full physics engine (pymunk) — rejected as unnecessary complexity.

---

## DECISION-005: React + Vite, No Additional Frameworks

- **Date**: 2026-09-14
- **Context**: Need a frontend framework for the PWA dashboard.
- **Decision**: Plain React with Vite bundler. No Next.js, no Vue, no React Router, no Redux, no TailwindCSS.
- **Rationale**: Minimum dependency surface. State-based routing is sufficient for 3 pages. React Context + hooks handles state. CSS design system provides styling.
- **Alternatives Considered**: (1) Next.js — rejected, SSR unnecessary. (2) Vue — rejected per user preference. (3) TailwindCSS — rejected per user preference.

---

## DECISION-006: pygame-ce and Pure-Python pymavlink for Modern Python Compatibility

- **Date**: 2026-09-14
- **Context**: Python 3.14 on Linux lacks prebuilt wheels for legacy `pygame` and lacks OS-level `python3-devel` headers for compiling Cython extensions (`dfindexer_cy`).
- **Decision**: Use `pygame-ce>=2.5` (Community Edition, exact drop-in `import pygame` API) and build `pymavlink` with `PYMAVLINK_FAST_INDEX=0` (pure Python mode).
- **Rationale**: Ensures zero build failures, eliminates C-header dependencies on Linux distributions, and maintains 100% protocol and runtime compatibility.
- **Alternatives Considered**: (1) Require system `sudo dnf install python3-devel sdl2-devel` — rejected to keep environment self-contained and reproducible.

---

## DECISION-007: Outbound MAVLink Message Builders Centralized in protocol.py

- **Date**: 2026-09-14
- **Context**: `AutoConfigEngine` needs to construct outgoing MAVLink frames (`PARAM_REQUEST_LIST`, `PARAM_SET`, and `RC_CHANNELS_OVERRIDE`) to query parameters, update values, and send actuator overrides.
- **Decision**: Implement all outbound MAVLink message builder factory functions inside `src/core/protocol.py` (`create_param_request_list_msg`, `create_param_set_msg`, `create_rc_override_msg`).
- **Rationale**: Strictly preserves the Rule 6 quarantine boundary. `AutoConfigEngine` and all other Core Bridge modules remain completely independent of `pymavlink`.
- **Alternatives Considered**: (1) Allow `auto_config.py` to import `pymavlink` directly — rejected as violation of Rule 6 and architectural modularity.

---

## DECISION-008: Explicit Virtualenv Interpreter Resolution and Strict Test Typing

- **Date**: 2026-09-14
- **Context**: Shell activation (`source .venv/bin/activate`) can fall back to system Python if symlinks break or shell subshells do not preserve PATH. In addition, IDE type-checkers flagged unparameterized generic dicts and property type-narrowing collisions across asynchronous mutation in tests.
- **Decision**: (1) Update all launcher scripts (`start_all.sh`, `start_rover_sim.sh`, `start_bridge.sh`) to detect and directly execute `$ROOT_DIR/.venv/bin/python` if present; (2) Create `.vscode/settings.json` specifying `python.defaultInterpreterPath`; (3) Strongly type test fixtures/callbacks with `dict[str, Any]` and split narrowed property assertions across async mutations.
- **Rationale**: Guarantees deterministic execution regardless of user shell state, eliminates IDE redlines, and keeps the test suite passing under strict Mypy and IDE analyzers.
- **Alternatives Considered**: (1) Rely on manual user virtualenv activation — rejected as fragile across varying shell configurations.

---

## DECISION-009: ArduPilot Copter SITL Support and 4-Axis Actuation

- **Date**: 2026-09-26
- **Author**: Aditi
- **Context**: Monocranium originally supported only 4WD differential-drive skid-steer rovers. Extending the architecture to support ArduPilot Copter SITL quadcopters requires detecting copter heartbeats, classifying multirotor vehicle types, expanding the MAVLink RC override channel mapping from 2 channels (throttle, steering) to 4 channels (roll, pitch, throttle, yaw), supporting dual-endpoint background discovery in the Core Bridge, and adapting dashboard controls while maintaining 100% backward compatibility with rovers and strictly preserving pymavlink quarantine boundaries.
- **Decision**: (1) Extend `VehicleType.COPTER` in `src/core/types.py` mapping MAVLink multirotor types (2, 3, 4, 13, 14, 15) to `COPTER`; (2) Generalize `create_rc_override_msg()` in `src/core/protocol.py` and `send_rc_override()` in `src/core/auto_config.py` with default arguments (`pitch=0, yaw=0`), ensuring backward compatibility with 2-argument rover callers; (3) Extract helper in `src/server/ws_handlers.py` to route 2-axis rover commands and 4-axis drone commands without exceeding 40-line function limits; (4) Implement decoupled ArduPilot Copter simulation modules in `src/simulators/drone_config.py`, `src/simulators/drone_physics.py`, and `src/simulators/drone_sim.py` (listening on TCP port 5771 with System ID 3), keeping `pymavlink` quarantined to `drone_sim.py`; (5) Wire both endpoints into `src/main.py` scanner and provide `scripts/start_drone_sim.sh`; (6) Add a context-sensitive 4-axis flight controller interface in `dashboard/src/pages/DashboardPage.jsx` when active vehicle is a copter while preserving the existing skid-steer control pad for rovers.
- **Rationale**: Follows the repository's established "Arm Stump" architecture. Core abstractions (`TelemetryBus`, `ParameterStore`, `VehicleRegistry`, `AutoConfigEngine`) remain completely vehicle-agnostic. Rover tests and functionality are fully preserved without regression.
- **Consequences**: Both Rover (port 5770, sysid 2) and ArduPilot Copter (port 5771, sysid 3) can be simulated and controlled simultaneously or individually. Test suite expanded from 76 to 101 tests, all passing cleanly.
- **Alternatives Considered**: (1) Create separate core bridges for rovers and copters — rejected as violating Monocranium's unified "one brain to rule them all" philosophy; (2) Modify core types to include vehicle-specific flight fields — rejected as violation of Rule 7 in AGENTS.md; (3) Allow direct pymavlink usage in drone physics — rejected as violation of Rule 6 quarantine.

---

## DECISION-010: Arm/Disarm and Flight Mode Command Architecture

- **Date**: 2026-09-27
- **Context**: Real ArduPilot vehicles start disarmed and ignore RC overrides until armed in an RC-accepting flight mode. The mock simulator had no arm/disarm or mode support.
- **Decision**: (1) Add `create_arm_disarm_msg()` and `create_set_mode_msg()` factory functions in `protocol.py` generating MAVLink COMMAND_LONG packets (MAV_CMD_COMPONENT_ARM_DISARM=400 and MAV_CMD_DO_SET_MODE=176). (2) Expose `arm_vehicle()` and `set_mode()` on `AutoConfigEngine`. (3) Wire `arm_vehicle` and `set_flight_mode` WebSocket actions in `ws_handlers.py`. (4) Add ARM/DISARM toggle and flight mode dropdown to dashboard copter view. Constants for ArduPilot Copter flight modes (STABILIZE through BRAKE) defined as a dict in `protocol.py`.
- **Rationale**: Follows existing quarantine boundary — all pymavlink usage stays in protocol.py. COMMAND_LONG is the standard MAVLink command for arming and mode changes. Dashboard controls are copter-only (rovers don't need arming in most configurations).
- **Alternatives Considered**: (1) Use SET_MODE message instead of COMMAND_LONG — rejected because COMMAND_LONG is the recommended approach for ArduPilot. (2) Auto-arm on first RC override — rejected as unsafe.

---

## DECISION-011: Multi-Vehicle Telemetry Filtering by Active System ID

- **Date**: 2026-09-27
- **Context**: When both rover (SYSID 2) and drone (SYSID 3) simulators are connected, the dashboard telemetry gauges flickered between values from both vehicles because `useTelemetry.js` did not filter incoming telemetry events by the active vehicle.
- **Decision**: Add a `system_id` check against `activeSystemId` in the telemetry event handler for `telemetry.attitude`, `telemetry.gps`, `telemetry.battery`, and `telemetry.rc` events. Events from non-active vehicles are silently dropped.
- **Rationale**: Simple and effective. The telemetry bus already includes `system_id` in every event payload. No backend changes needed.
- **Alternatives Considered**: (1) Maintain separate telemetry state per vehicle — rejected as premature complexity for a single-view dashboard.



