# Monocranium — System Walkthrough & Architectural Review

> **One brain to rule them all.**
> Complete operational guide and file-by-file audit of the Monocranium MAVLink control bridge and virtual rover system.

---

## SECTION 1: How To Run

Monocranium is organized as a clean two-process system communicating over MAVLink TCP on port `5770`:
- **Process 1 (Core Bridge)**: Asyncio event bus, auto-configuration engine, WebSocket server (`:8765`), and HTTP static server (`:8080`).
- **Process 2 (Virtual Rover)**: 4WD skid-steer kinematics simulation with Pygame GUI and background MAVLink TCP server (`:5770`).

### 1. Prerequisites & Installation

Open a terminal in the project root:

```bash
cd monocranium

# 1. Create and activate Python 3.11+ virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (pure Python pymavlink & pygame-ce)
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 3. Build dashboard production bundle
cd dashboard
npm install
npm run build
cd ..
```

---

### 2. Launching the System

You can run Monocranium using the unified supervisor script or with two separate terminals.

#### Option A: Unified Launcher (One Command)
```bash
./scripts/start_all.sh
```
*This automatically starts the Virtual Rover simulator in the background, waits 2 seconds for the MAVLink TCP server to bind, and launches the Core Bridge in the foreground.*

#### Option B: Two-Terminal Execution

**Terminal 1 — Start the Rover Simulator (Process 2):**
```bash
./scripts/start_rover_sim.sh
```
*Expected Output & Window:*
- A **800×600 Pygame window** opens with a dark grid background (`#1a1a2e`).
- The 4WD skid-steer rover is centered on screen with 4 purple wheels and a red chassis.
- A yellow arrow indicates current heading orientation.
- The HUD in the top-left displays live speed, heading angle, pixel coordinates, connected client count, and FPS.
- Terminal log:
  ```text
  [src.simulators.rover_main] INFO: Initializing Monocranium Virtual Rover Simulator on TCP port 5770
  [src.simulators.rover_sim] INFO: MAVLink server listening on 0.0.0.0:5770
  ```

**Terminal 2 — Start the Core Bridge (Process 1):**
```bash
./scripts/start_bridge.sh
```
*Expected Output:*
```text
[src.server.http_server] INFO: HTTP dashboard server listening on http://0.0.0.0:8080
[src.server.ws_server] INFO: WebSocket server listening on 0.0.0.0:8765
[src.main] INFO: Core Bridge running: WS port 8765, HTTP port 8080
[src.core.connection] INFO: Opening MAVLink connection to tcp:127.0.0.1:5770
[src.core.connection] INFO: Connection 127.0.0.1 state transition: disconnected -> connecting
[src.simulators.rover_sim] INFO: New MAVLink client connected from ('127.0.0.1', ...)
[src.core.connection] INFO: Connection 127.0.0.1 state transition: connecting -> connected
[src.core.auto_config] INFO: AutoConfig requesting parameters for vehicle 2
```

---

### 3. Open the Dashboard

Open your web browser and navigate to:
**[http://localhost:8080](http://localhost:8080)**

What you will see:
1. **Header**: Live system time, green `CONNECTED` status badge, and active vehicle badge (`SYSID #2 (rover)`).
2. **Sidebar**: Monocranium branding, navigation links (`Setup & Scan`, `Telemetry & Flight`, `Parameters`), and active vehicle card.
3. **Telemetry & Flight View**:
   - Live metric cards: **Heading (Yaw)** with dynamic Recharts sparkline, **Speed (m/s)**, **Battery Voltage (11.1 V)**, **Battery Current**, **Battery %**, and **GPS Satellites (12)**.
   - **Interactive RC Actuator Override**: Dual sliders for Throttle (CH3) and Steering (CH1), plus a quick D-pad (`▲ Fwd`, `◀ Left`, `■ Stop`, `Right ▶`, `▼ Rev`). Moving sliders or clicking buttons drives the Pygame rover in real-time!
   - **Spatial Coordinates**: Real-time simulated GPS coordinates (Lat/Lon/Alt) and roll/pitch/yaw angles.
   - **Event & Diagnostic Console**: Real-time monospace event stream of all telemetry events and MAVLink messages.
4. **Parameters View**:
   - Full searchable table of all 19 MAVLink parameters (`WHEEL_DIA_MM`, `WHEEL_BASE_MM`, `MOT_MAX_RPM`, `BATT_VOLT`, `PWM_CENTER`, etc.).
   - Click **Edit** on any row to adjust a value inline (e.g., change `CRUISE_SPEED` to `2.5`). Click **Save** — the Core Bridge sends `PARAM_SET` over MAVLink, the rover simulator updates its internal register, responds with `PARAM_VALUE`, and updates the UI.
   - Click **Export JSON** to download all 19 parameters as a formatted JSON document.
5. **Setup & Scan View**:
   - Endpoint connection manager and autonomous handshake verification checklist.

---

### 4. Running the Automated Test Suite

Monocranium has **76 automated tests** (all passing cleanly, with zero lint or mypy errors):

```bash
# Run all unit, mock, and end-to-end integration tests
pytest tests/ -v --tb=short

# Run static type checking and linting
ruff check src/ tests/
mypy src/
```

---

## SECTION 2: File-by-File Architectural Review

Below is the complete file-by-file audit of every file in the Monocranium repository.

### Root Configuration & Documentation

#### 1. [monocranium/pyproject.toml](monocranium/pyproject.toml)
- **Purpose**: Defines project metadata, build settings, Ruff linting rules, Mypy strict typing configurations, and Pytest asyncio options.
- **Dependencies**: None.

#### 2. [monocranium/requirements.txt](monocranium/requirements.txt)
- **Purpose**: Specifies production runtime dependencies (`pymavlink`, `websockets`, `aiohttp`, `pygame-ce`).
- **Dependencies**: None.

#### 3. [monocranium/requirements-dev.txt](monocranium/requirements-dev.txt)
- **Purpose**: Specifies development, testing, and linting dependencies (`pytest`, `pytest-asyncio`, `mypy`, `ruff`).
- **Dependencies**: None.

#### 4. [monocranium/README.md](monocranium/README.md)
- **Purpose**: Comprehensive user and developer overview, architecture diagrams, prerequisites, run instructions, and roadmap.
- **Dependencies**: None.

#### 5. [monocranium/CONTRIBUTING.md](monocranium/CONTRIBUTING.md)
- **Purpose**: Contributor guidelines, branch/commit conventions, anti-patchwork policy, and rules for extending new vehicles.
- **Dependencies**: None.

#### 6. [monocranium/AGENTS.md](monocranium/AGENTS.md)
- **Purpose**: Directives and strict invariants for AI coding agents (file ownership matrix, import quarantine rules, testing standards).
- **Dependencies**: None.

#### 7. [monocranium/decisions.md](monocranium/decisions.md)
- **Purpose**: Living architectural decision log recording context, rationale, and alternatives for DECISION-001 through DECISION-007.
- **Dependencies**: None.

---

### Shell Launchers (`scripts/`)

#### 8. [monocranium/scripts/start_rover_sim.sh](monocranium/scripts/start_rover_sim.sh)
- **Purpose**: Shell launcher that activates `.venv` and runs the Pygame rover simulator (`python -m src.simulators.rover_main`).
- **Dependencies**: Bash, Python.

#### 9. [monocranium/scripts/start_bridge.sh](monocranium/scripts/start_bridge.sh)
- **Purpose**: Shell launcher that activates `.venv` and runs the Core Bridge (`python -m src.main`).
- **Dependencies**: Bash, Python.

#### 10. [monocranium/scripts/start_all.sh](monocranium/scripts/start_all.sh)
- **Purpose**: Supervisor script that launches the rover simulator in background, waits 2s, launches the bridge in foreground, and handles SIGINT/SIGTERM cleanup.
- **Dependencies**: Bash, Python.

---

### Core Bridge Engine (`src/core/`)

#### 11. [monocranium/src/core/types.py](monocranium/src/core/types.py)
- **Purpose**: Single source of truth for all shared data models, frozen dataclasses, and enums. Zero local imports.
- **Key Entities**:
  - `VehicleType(Enum)`: `ROVER`, `UNKNOWN`, with `from_mav_type()`.
  - `AutopilotType(Enum)`: `ARDUPILOT`, `GENERIC`, `UNKNOWN`, with `from_mav_autopilot()`.
  - `ConnectionState(Enum)`: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `HEARTBEAT_LOST`.
  - `AttitudeData`: Frozen dataclass for roll, pitch, yaw radians.
  - `GpsData`: Frozen dataclass for lat, lon, alt, fix_type, satellites.
  - `BatteryData`: Frozen dataclass for voltage, current, remaining %.
  - `ConnectionEndpoint`: Frozen dataclass for address, port, protocol.
  - `Parameter`: Frozen dataclass for param_id, value, param_type, param_index.
  - `VehicleIdentity`: Frozen dataclass with custom `to_dict()` converting enums to strings.
  - `TelemetrySnapshot`: Frozen dataclass with nested serialization.
  - `BridgeCommand`: TypedDict for client WebSocket commands.
- **Dependencies**: `dataclasses`, `enum`, `typing`, `logging`.

#### 12. [monocranium/src/core/telemetry_bus.py](monocranium/src/core/telemetry_bus.py)
- **Purpose**: Thread-safe, asynchronous in-process publish/subscribe event bus.
- **Key Entities**:
  - `TelemetryBus`: Async event bus with `subscribe()`, `unsubscribe()`, and `publish()`.
- **Dependencies**: `asyncio`, `collections`, `logging`, `typing`.

#### 13. [monocranium/src/core/parameter_store.py](monocranium/src/core/parameter_store.py)
- **Purpose**: In-memory cache of MAVLink parameters keyed by system ID and parameter name. Emits bus update events.
- **Key Entities**:
  - `ParameterStore`: Manages parameter storage with `upsert()`, `bulk_load()`, `get()`, `get_all()`, `get_count()`, `clear()`, `export_json()`.
- **Dependencies**: `json`, `logging`, `src.core.types.Parameter`, `src.core.telemetry_bus.TelemetryBus`.

#### 14. [monocranium/src/core/vehicle_registry.py](monocranium/src/core/vehicle_registry.py)
- **Purpose**: Manages active vehicle lifecycle states, registrations, and lifecycle events (`vehicle.discovered`, `vehicle.updated`, `vehicle.lost`).
- **Key Entities**:
  - `VehicleRegistry`: Vehicle directory with `register()`, `unregister()`, `get()`, `list_all()`, `is_registered()`.
- **Dependencies**: `logging`, `src.core.types.VehicleIdentity`, `src.core.telemetry_bus.TelemetryBus`.

#### 15. [monocranium/src/core/protocol.py](monocranium/src/core/protocol.py)
- **Purpose**: Quarantine boundary for all `pymavlink` parsing and message encoding on the Core Bridge side.
- **Key Entities**:
  - `parse_heartbeat()`: Decodes HEARTBEAT into `VehicleIdentity`.
  - `parse_param_value()`: Decodes PARAM_VALUE into `Parameter`.
  - `parse_attitude()`: Decodes ATTITUDE into `AttitudeData`.
  - `parse_gps()`: Decodes GPS_RAW_INT into `GpsData`.
  - `parse_battery()`: Decodes SYS_STATUS into `BatteryData`.
  - `parse_rc_channels()`: Decodes RC_CHANNELS into 18-element int list.
  - `create_mav_connection()`: Instantiates `mavutil.mavlink_connection`.
  - `create_param_request_list_msg()`: Encodes PARAM_REQUEST_LIST message.
  - `create_param_set_msg()`: Encodes PARAM_SET message.
  - `create_rc_override_msg()`: Encodes RC_CHANNELS_OVERRIDE message.
- **Dependencies**: `pymavlink.mavutil`, `src.core.types`, `logging`.

#### 16. [monocranium/src/core/connection.py](monocranium/src/core/connection.py)
- **Purpose**: Connection lifecycle management, asynchronous polling loop, and heartbeat timeout health watchdog.
- **Key Entities**:
  - `MavlinkConnection`: Single connection wrapper with `connect()`, `disconnect()`, `send_message()`, `on_message()`, `on_state_change()`, `_read_loop()`, and `_health_monitor_loop()`.
  - `ConnectionManager`: Pool manager with `add_connection()`, `remove_connection()`, `get_connection()`, `list_connections()`, `close_all()`.
- **Dependencies**: `asyncio`, `time`, `logging`, `src.core.types`, `src.core.protocol.create_mav_connection`.

#### 17. [monocranium/src/core/auto_config.py](monocranium/src/core/auto_config.py)
- **Purpose**: Autonomous vehicle discovery, automatic parameter downloading, telemetry ingestion, and actuator commands.
- **Key Entities**:
  - `AutoConfigEngine`: Orchestrator with `run_scan()`, `run_full_scan()`, `send_rc_override()`, `set_parameter()`, and internal message decoders.
- **Dependencies**: `asyncio`, `time`, `logging`, `src.core.connection`, `src.core.protocol`, `src.core.parameter_store`, `src.core.vehicle_registry`, `src.core.telemetry_bus`, `src.core.types`.

---

### Simulator Components (`src/simulators/`)

#### 18. [monocranium/src/simulators/rover_config.py](monocranium/src/simulators/rover_config.py)
- **Purpose**: Physical hardware parameters for the 4WD skid-steer rover and default MAVLink parameter generator.
- **Key Entities**:
  - `RoverHardwareConfig`: Frozen dataclass for wheel dimensions, gear ratio (30:1), 775 DC motor RPM (6000), LiPo battery (11.1V 3S), PWM ranges (1000-2000). Calculates `max_wheel_speed_mps` and `max_angular_velocity_rps`.
  - `build_default_parameter_list()`: Builds the complete list of 19 MAVLink parameters.
- **Dependencies**: `math`, `dataclasses`, `typing`.

#### 19. [monocranium/src/simulators/rover_physics.py](monocranium/src/simulators/rover_physics.py)
- **Purpose**: Differential-drive kinematics model calculating linear velocity, angular velocity, heading, and pixel/GPS positions.
- **Key Entities**:
  - `RoverKinematics`: Kinematic solver with `update(throttle_pwm, steering_pwm, dt)`, `reset()`, and properties `position`, `heading_rad`, `heading_deg`, `speed_mps`, `angular_velocity_rps`, `gps_data`, `attitude_data`.
- **Dependencies**: `math`, `logging`, `src.core.types`, `src.simulators.rover_config`.

#### 20. [monocranium/src/simulators/rover_sim.py](monocranium/src/simulators/rover_sim.py)
- **Purpose**: MAVLink TCP flight controller server. Broadcasts HEARTBEAT (1 Hz) and Telemetry (10 Hz); handles RC_CHANNELS_OVERRIDE, PARAM_REQUEST_LIST, and PARAM_SET.
- **Key Entities**:
  - `RoverMavlinkServer`: TCP server with `start()`, `stop()`, `current_rc`, `client_count`, `endpoint`, `_broadcast()`, `_handle_rc_override()`, `_handle_param_set()`, `_handle_param_request_list()`.
- **Dependencies**: `asyncio`, `time`, `logging`, `pymavlink.dialects.v20.ardupilotmega`, `src.core.types`, `src.simulators.rover_config`, `src.simulators.rover_physics`.

#### 21. [monocranium/src/simulators/rover_renderer.py](monocranium/src/simulators/rover_renderer.py)
- **Purpose**: Pygame 2D graphics rendering. Draws 1-meter grid, rotated 4WD chassis with wheels and heading arrow, and HUD diagnostic text.
- **Key Entities**:
  - `RoverRenderer`: Visual renderer with `render_frame()`, `handle_events()`, `cleanup()`.
- **Dependencies**: `pygame`, `math`, `logging`, `src.simulators.rover_physics`.

#### 22. [monocranium/src/simulators/rover_main.py](monocranium/src/simulators/rover_main.py)
- **Purpose**: Entry point for Process 2. Runs Pygame on the main thread and asyncio TCP MAVLink server on a background daemon thread.
- **Key Entities**:
  - `parse_args()`, `start_background_server()`, `main()`.
- **Dependencies**: `argparse`, `asyncio`, `threading`, `logging`, `pygame`, `src.simulators.*`.

---

### Gateway & Server Layer (`src/server/` & `src/main.py`)

#### 23. [monocranium/src/server/ws_handlers.py](monocranium/src/server/ws_handlers.py)
- **Purpose**: Sole owner of WebSocket JSON command parsing and action dispatching (`get_vehicles`, `get_parameters`, `set_parameter`, `rc_override`, `run_autoconfig`, `get_connection_status`).
- **Key Entities**:
  - `dispatch_command()`, `_execute_action()`, `_handle_run_autoconfig()`.
- **Dependencies**: `json`, `logging`, `src.core.*`.

#### 24. [monocranium/src/server/ws_server.py](monocranium/src/server/ws_server.py)
- **Purpose**: WebSocket server bridging browser clients with the Core Bridge and broadcasting live TelemetryBus events.
- **Key Entities**:
  - `WebSocketServer`: Server with `start()`, `stop()`, `broadcast()`, `_handler()`, `_on_bus_event()`.
- **Dependencies**: `websockets`, `json`, `logging`, `src.core.*`, `src.server.ws_handlers`.

#### 25. [monocranium/src/server/http_server.py](monocranium/src/server/http_server.py)
- **Purpose**: Aiohttp static web server serving the React SPA bundle from `dashboard/dist/` with fallback to `index.html`.
- **Key Entities**:
  - `HttpServer`: Static file server with `start()`, `stop()`, `_handle_request()`.
- **Dependencies**: `aiohttp.web`, `pathlib`, `logging`.

#### 26. [monocranium/src/main.py](monocranium/src/main.py)
- **Purpose**: Wiring file ONLY for Process 1. Instantiates subsystems, binds endpoints, starts servers, and handles graceful shutdown.
- **Key Entities**:
  - `parse_args()`, `run_bridge()`, `main()`.
- **Dependencies**: `argparse`, `asyncio`, `pathlib`, `logging`, `src.core.*`, `src.server.*`.

---

### Test Suite (`tests/`)

#### 27. [monocranium/tests/conftest.py](monocranium/tests/conftest.py)
- **Purpose**: Pytest shared fixtures (`telemetry_bus`, `param_store`, `vehicle_registry`, `sample_rover_identity`, `sample_parameters`).

#### 28. [monocranium/tests/test_types.py](monocranium/tests/test_types.py) (6 tests)
- **Purpose**: Tests enum conversions, dataclass immutability (`FrozenInstanceError`), and dictionary serialization.

#### 29. [monocranium/tests/test_telemetry_bus.py](monocranium/tests/test_telemetry_bus.py) (5 tests)
- **Purpose**: Tests subscribe, publish, unsubscribe, error handling, and multi-subscriber resilience.

#### 30. [monocranium/tests/test_parameter_store.py](monocranium/tests/test_parameter_store.py) (8 tests)
- **Purpose**: Tests upsert, bulk_load, get, get_all (sorted by index), clear, get_count, and export_json.

#### 31. [monocranium/tests/test_vehicle_registry.py](monocranium/tests/test_vehicle_registry.py) (6 tests)
- **Purpose**: Tests vehicle registration, event emission (`discovered` vs `updated`), unregistration, and listing.

#### 32. [monocranium/tests/test_protocol.py](monocranium/tests/test_protocol.py) (12 tests)
- **Purpose**: Tests decoding of HEARTBEAT, PARAM_VALUE, ATTITUDE, GPS_RAW_INT, SYS_STATUS, RC_CHANNELS, and connection URI generation.

#### 33. [monocranium/tests/test_rover_config.py](monocranium/tests/test_rover_config.py) (4 tests)
- **Purpose**: Tests hardware config physical constants, wheel radius, max wheel speed, and 19-parameter list generation.

#### 34. [monocranium/tests/test_rover_physics.py](monocranium/tests/test_rover_physics.py) (8 tests)
- **Purpose**: Tests initial state, center PWM stationary behavior, forward/reverse movement, in-place rotation, PWM deadband, GPS conversion, and reset.

#### 35. [monocranium/tests/test_rover_sim.py](monocranium/tests/test_rover_sim.py) (6 tests)
- **Purpose**: Tests server initialization, parameter counts, endpoint descriptors, RC override handling, parameter set, and parameter request list generation.

#### 36. [monocranium/tests/test_connection.py](monocranium/tests/test_connection.py) (6 tests)
- **Purpose**: Tests MavlinkConnection lifecycle states, connect success/failure, heartbeat state transition, message callbacks, and ConnectionManager.

#### 37. [monocranium/tests/test_auto_config.py](monocranium/tests/test_auto_config.py) (5 tests)
- **Purpose**: Tests heartbeat discovery triggering vehicle registration and parameter queries, parameter updates, telemetry bus dispatch, scan timeouts, and actuator command dispatch.

#### 38. [monocranium/tests/test_ws_server.py](monocranium/tests/test_ws_server.py) (7 tests)
- **Purpose**: Tests command parsing, vehicle queries, parameter updates, RC overrides, WebSocket event broadcasting, and HTTP static fallback.

#### 39. [monocranium/tests/test_integration.py](monocranium/tests/test_integration.py) (3 tests)
- **Purpose**: End-to-end TCP integration tests: starts live `RoverMavlinkServer`, receives real HEARTBEAT, executes full PARAM_REQUEST_LIST sync (19 parameters), and tests live RC_CHANNELS_OVERRIDE state update.

---

### Frontend PWA Dashboard (`dashboard/`)

#### 40. [monocranium/dashboard/index.html](monocranium/dashboard/index.html)
- **Purpose**: HTML entry point with Google Fonts (Inter & JetBrains Mono) and PWA metadata.

#### 41. [monocranium/dashboard/src/index.css](monocranium/dashboard/src/index.css)
- **Purpose**: Complete design system stylesheet with dark tokens (`--bg-primary`, `--accent-blue`, etc.), utility classes, and custom animations.

#### 42. [monocranium/dashboard/src/hooks/useWebSocket.js](monocranium/dashboard/src/hooks/useWebSocket.js)
- **Purpose**: Custom React hook for auto-reconnecting WebSocket connection with exponential backoff.

#### 43. [monocranium/dashboard/src/hooks/useTelemetry.js](monocranium/dashboard/src/hooks/useTelemetry.js)
- **Purpose**: Centralized telemetry, parameter, and vehicle state management hook with action dispatchers.

#### 44. [monocranium/dashboard/src/context/VehicleContext.jsx](monocranium/dashboard/src/context/VehicleContext.jsx)
- **Purpose**: React context for sharing active vehicle system ID across components.

#### 45. [monocranium/dashboard/src/components/ConnectionBadge.jsx](monocranium/dashboard/src/components/ConnectionBadge.jsx)
- **Purpose**: Pulsing status badge indicating real-time WebSocket connection health.

#### 46. [monocranium/dashboard/src/components/VehicleCard.jsx](monocranium/dashboard/src/components/VehicleCard.jsx)
- **Purpose**: Selectable vehicle card displaying system ID, vehicle type, and firmware version.

#### 47. [monocranium/dashboard/src/components/TelemetryGauge.jsx](monocranium/dashboard/src/components/TelemetryGauge.jsx)
- **Purpose**: High-aesthetic metric card featuring live Recharts sparklines.

#### 48. [monocranium/dashboard/src/components/ParameterRow.jsx](monocranium/dashboard/src/components/ParameterRow.jsx)
- **Purpose**: Single table row supporting inline editing, saving, and cancelling of vehicle parameters.

#### 49. [monocranium/dashboard/src/components/ParameterTable.jsx](monocranium/dashboard/src/components/ParameterTable.jsx)
- **Purpose**: Filterable, sortable table displaying all 19 MAVLink parameters with JSON export.

#### 50. [monocranium/dashboard/src/components/LogConsole.jsx](monocranium/dashboard/src/components/LogConsole.jsx)
- **Purpose**: Scrollable monospace diagnostic log console with level filtering and auto-scroll.

#### 51. [monocranium/dashboard/src/components/Sidebar.jsx](monocranium/dashboard/src/components/Sidebar.jsx)
- **Purpose**: Fixed sidebar providing Monocranium branding, navigation tabs, and connected vehicle cards.

#### 52. [monocranium/dashboard/src/components/Header.jsx](monocranium/dashboard/src/components/Header.jsx)
- **Purpose**: Header bar displaying current page title, active vehicle status, connection badge, and live clock.

#### 53. [monocranium/dashboard/src/pages/SetupPage.jsx](monocranium/dashboard/src/pages/SetupPage.jsx)
- **Purpose**: Endpoint management page with scan triggering and handshake verification checklist.

#### 54. [monocranium/dashboard/src/pages/DashboardPage.jsx](monocranium/dashboard/src/pages/DashboardPage.jsx)
- **Purpose**: Primary flight telemetry dashboard with attitude/speed/battery gauges, interactive RC override sliders and D-pad, and log console.

#### 55. [monocranium/dashboard/src/pages/ParametersPage.jsx](monocranium/dashboard/src/pages/ParametersPage.jsx)
- **Purpose**: Parameter inspection and live configuration page.

#### 56. [monocranium/dashboard/src/App.jsx](monocranium/dashboard/src/App.jsx)
- **Purpose**: Main application layout combining sidebar, header, and state-based page routing.

#### 57. [monocranium/dashboard/src/main.jsx](monocranium/dashboard/src/main.jsx)
- **Purpose**: React root mounting script importing global design system styles.
