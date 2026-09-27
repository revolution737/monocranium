# Monocranium 💀

> **One brain to rule them all.**
> A modular MAVLink control bridge and calibration dashboard for unmanned vehicles, featuring autonomous discovery, rover and drone simulation, real ArduPilot Copter SITL support, and a web interface.

---

## Architecture Overview

Monocranium is engineered with an "arm stump" architecture: the core communication engine is completely vehicle-agnostic, while vehicle simulators or flight controllers plug into modular endpoints without touching core logic.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Browser PWA Dashboard                           │
│  React + Vite  ←──────────── WebSocket :8765 ────────────→  WS Server │
└────────────────────────────────────────────────────────────────────────┘
                                            │
                              ┌─────────────┴─────────────┐
                              │    Core Bridge (Python)   │
                              │    Process 1              │
                              │                           │
                              │  • ConnectionManager      │
                              │  • AutoConfigEngine       │
                              │  • ParameterStore         │
                              │  • VehicleRegistry        │
                              │  • TelemetryBus           │
                              │  • HTTP Static Server     │
                              └─────────────┬─────────────┘
                                            │
                                     MAVLink TCP :5770
                                            │
                              ┌─────────────┴─────────────┐
                              │  Virtual 4WD Rover Sim    │
                              │  Process 2                │
                              │                           │
                              │  • Pygame Display Window  │
                              │  • MAVLink TCP Server     │
                              │  • Differential Kinematics│
                              └───────────────────────────┘
```

---

## Features

- **Autonomous Vehicle Discovery & Handshake**: Auto-detects connected vehicles via MAVLink `HEARTBEAT` frames.
- **Dynamic Parameter Sync**: Automatically requests, caches, and syncs onboard parameters (`PARAM_REQUEST_LIST`, `PARAM_VALUE`, `PARAM_SET`).
- **Telemetry Streaming**: 10 Hz broadcast of Attitude (`roll`, `pitch`, `yaw`), GPS coordinates, battery status, and raw RC channel inputs.
- **Direct Actuator Override**: Real-time skid-steer control over MAVLink `RC_CHANNELS_OVERRIDE` from both keyboard and web browser.
- **Pygame Physics Simulation**: 4WD skid-steer kinematics with deadband filtering, speed/heading calculations, and visual HUD.
- **High-Aesthetic PWA Dashboard**: Dark-mode React interface styled with curated CSS design tokens, Recharts sparklines, and diagnostic event log console.

---

## Prerequisites

- **Python**: Python 3.11+
- **Node.js**: Node 18+ and npm

---

## Quick Start

### 1. Environment Setup

```bash
# Clone repository
git clone <repo-url>
cd monocranium

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Build dashboard frontend
cd dashboard
npm install
npm run build
cd ..
```

### 2. Running the System

You can run the Python simulators together or connect to official ArduPilot Copter SITL.

#### Option A: Unified Launcher (Recommended)
```bash
./scripts/start_all.sh
```
Use `--rover` or `--drone` to start one Python simulator and the bridge. `--drone` also disables rover discovery in the bridge. The default `--all` starts both Python simulators; it does not launch official ArduPilot SITL.

#### Option B: Two-Terminal Execution
**Terminal 1 — Rover Simulator:**
```bash
./scripts/start_rover_sim.sh
```
*Opens a 800x600 Pygame window showing the simulated 4WD rover. You can drive it using WASD or arrow keys.*

**Terminal 2 — Core Bridge:**
```bash
./scripts/start_bridge.sh
```
*Connects to the rover over MAVLink TCP port 5770, discovers the vehicle, synchronizes all 19 parameters, and starts the Web interface.*

#### Option C: Official ArduPilot Copter SITL

Install ArduPilot's `sim_vehicle.py` in `PATH`, or run Docker with a working daemon. In one terminal:

```bash
bash scripts/start_ardupilot_sitl.sh
```

In another terminal, start the bridge:

```bash
python -m src.main --no-rover
```

The launcher starts compiled ArduCopter with a direct TCP listener on port 5771. It disables MAVProxy so the bridge can receive the heartbeat and request telemetry streams automatically. `--no-rover` (or `--rover-port 0`) keeps the absent rover out of discovery and reconnect attempts. Omit it when connecting both rover and drone. For a second local SITL alongside another instance, use `--instance 1`; `--port 5760` overrides the listener port, and the bridge must then use `--drone-port 5760`. Keep standalone heartbeat probes closed before starting the bridge because the SITL serial TCP listener serves one client at a time. Docker launch depends on the image being available in your environment.

The dashboard displays unknown values (`--`) until live MAVLink telemetry arrives. ARM/DISARM and mode responses require an accepted `COMMAND_ACK`; the control state reflects subsequent vehicle heartbeats. The bridge reconnects after a lost MAVLink session and clears disconnected vehicle state.

### 3. Open the Dashboard
Navigate to [http://localhost:8080](http://localhost:8080) in your web browser.

---

## Running Tests

Monocranium has unit, offline integration, and launcher argument tests:

```bash
# Run all automated tests
pytest tests/ -v --tb=short

# Run static analysis and linting
ruff check src/ tests/
mypy src/
```

---

## Project Structure

```
monocranium/
├── CONTRIBUTING.md             # Contributor rules and coding standards
├── AGENTS.md                   # AI agent rules and quarantine boundaries
├── decisions.md                # Living architectural decision log
├── pyproject.toml              # Tooling configuration (pytest, ruff, mypy)
├── requirements.txt            # Core dependencies (pymavlink, websockets, pygame-ce, aiohttp)
├── requirements-dev.txt        # Test dependencies (pytest, pytest-asyncio, mypy, ruff)
│
├── scripts/
│   ├── start_rover_sim.sh      # Launches Pygame rover simulation (Process 2)
│   ├── start_bridge.sh         # Launches Core Bridge (Process 1)
│   └── start_all.sh            # Starts both processes with graceful cleanup
│
├── src/
│   ├── core/                   # Pure MAVLink bridge logic (vehicle-agnostic)
│   │   ├── types.py            # Immutable frozen dataclasses and enums
│   │   ├── telemetry_bus.py    # Publish-subscribe async event bus
│   │   ├── parameter_store.py  # Thread-safe in-memory parameter cache
│   │   ├── vehicle_registry.py # Vehicle discovery and lifecycle registry
│   │   ├── protocol.py         # MAVLink serialization quarantine boundary
│   │   ├── connection.py       # TCP connection pool and heartbeat health monitor
│   │   └── auto_config.py      # Autonomous scan and calibration engine
│   │
│   ├── simulators/             # Virtual hardware simulation
│   │   ├── rover_config.py     # 4WD chassis and motor specifications
│   │   ├── rover_physics.py    # Differential-drive kinematic equations
│   │   ├── rover_sim.py        # MAVLink TCP flight controller server
│   │   ├── rover_renderer.py   # Pygame graphics and HUD overlay
│   │   └── rover_main.py       # Process 2 runner (Pygame + MAVLink thread)
│   │
│   ├── server/                 # Network gateway to dashboard
│   │   ├── ws_server.py        # WebSocket broadcaster and connection manager
│   │   ├── ws_handlers.py      # JSON command parser and action router
│   │   └── http_server.py      # SPA static asset file server
│   │
│   └── main.py                 # Core Bridge Process 1 wiring entry point
│
├── tests/                      # Automated unit and integration tests
│   ├── conftest.py             # Shared fixtures
│   ├── test_types.py
│   ├── test_telemetry_bus.py
│   ├── test_parameter_store.py
│   ├── test_vehicle_registry.py
│   ├── test_protocol.py
│   ├── test_rover_config.py
│   ├── test_rover_physics.py
│   ├── test_rover_sim.py
│   ├── test_connection.py
│   ├── test_auto_config.py
│   ├── test_ws_server.py
│   └── test_integration.py
│
└── dashboard/                  # React + Vite frontend PWA
    ├── src/
    │   ├── components/         # Modular UI components
    │   ├── hooks/              # useWebSocket, useTelemetry
    │   ├── context/            # VehicleContext
    │   ├── pages/              # SetupPage, DashboardPage, ParametersPage
    │   ├── index.css           # Curated dark-theme design system
    │   └── App.jsx             # State-based SPA layout
    └── package.json
```

---

## Future Roadmap: Extending the "Arm Stump"

Monocranium is designed to be extensible to other vehicle types without modifying existing bridge logic:
1. **Drones / Quadcopters**: Add `src/simulators/drone_sim.py` with 6-DOF physics and MAVLink type `MAV_TYPE_QUADROTOR`.
2. **Fixed-Wing Planes**: Add flight kinematics and aerodynamic surfaces.
3. **Marine Vehicles**: Surface boats and submersibles.
4. **Hardware Serial/Telemetry Support**: Support direct USB UART/Serial ports (`/dev/ttyUSB0`) alongside TCP/UDP.
