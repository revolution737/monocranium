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

