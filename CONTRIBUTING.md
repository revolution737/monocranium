# Contributing to Monocranium

Thank you for contributing to Monocranium! Monocranium is a modular MAVLink control bridge engineered for precision, reliability, and modularity. This project prioritises code quality, modular boundaries, and clean architecture over rapid, hacky prototypes.

---

## 1. Code of Conduct

All contributors, maintainers, and participants are expected to uphold a welcoming, respectful, and professional environment. Treat everyone with dignity, offer constructive critiques, and maintain high standards of collaboration.

---

## 2. Getting Started

1. **Clone repository**:
   ```bash
   git clone <repo-url>
   cd monocranium
   ```
2. **Create Python virtual environment** (Python 3.11+ required):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. **Run existing test suite**:
   ```bash
   pytest tests/ -v
   ```

---

## 3. Branch Naming

All branches must adhere to the following naming conventions:
- `feature/<name>`: New vehicle support, dashboard views, protocol enhancements.
- `fix/<name>`: Bug fixes and defect corrections.
- `docs/<name>`: Documentation improvements, architectural blueprints.
- `refactor/<name>`: Code restructuring without functional alterations.

---

## 4. Commit Messages

Commits must follow the Conventional Commits specification:
```text
<type>(<scope>): <short description>
```

- **Allowed Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- **Allowed Scopes**: `core`, `rover-sim`, `dashboard`, `server`
- **Example**: `feat(core): implement automatic parameter sync over MAVLink`

---

## 5. Code Standards

All code submitted to Monocranium must adhere to the following 12 foundational rules:

1. **Phase Order Is Mandatory**: Build components foundation-first, verify, then integrate.
2. **One File At A Time**: Develop incrementally with matching tests.
3. **Never Use `print()`**: Always use standard logging:
   ```python
   import logging
   logger = logging.getLogger(__name__)
   logger.info("Message: %s", value)
   ```
4. **Never Use Bare `except:`**: Always capture specific exceptions (`except (ValueError, OSError) as e:`) and log or re-raise. Never swallow errors silently.
5. **Every Public Function Needs Type Annotations AND A Docstring**:
   - Strict static typing for all arguments and return types.
   - Comprehensive docstrings explaining arguments, return values, and raised exceptions.
6. **Import Quarantine for pymavlink**:
   - `pymavlink` may ONLY be imported in `src/core/protocol.py` and `src/simulators/rover_sim.py`.
   - Never import `pymavlink` in any other core or application module.
7. **Import Quarantine for pygame**:
   - `pygame` may ONLY be imported in `src/simulators/rover_renderer.py`.
8. **No Magic Numbers**: Extract all constants into named constants or configuration dataclasses.
9. **No Mutable Default Arguments**: Use `None` and initialize in the function body.
10. **Log Every Decision**: Record any non-trivial design decisions in `decisions.md`.
11. **No TODO or FIXME Comments**: Implement complete solutions immediately.
12. **Frozen Dataclasses Only**: Core data structures must use `@dataclass(frozen=True)` to prevent unintended mutations.

### Frontend Standards (React / JS)
- Functional components with hooks only.
- Strict use of CSS design system custom properties and classes; no ad-hoc inline styles.
- Pure component design with separation between state management and rendering.

---

## 6. Maximum Function Length

Functions must not exceed **40 lines of code** (excluding docstrings). If a function approaches this limit, decompose it into private helper functions with single responsibilities.

---

## 7. Testing Requirements

- Every pull request must include comprehensive automated tests.
- Each public method must have at least one test covering the happy path and one test covering edge/error conditions.
- Test suites must pass cleanly without warnings:
  ```bash
  pytest tests/ -v --tb=short
  ruff check src/ tests/
  mypy src/
  ```

---

## 8. Anti-Patchwork Policy

Monocranium strictly rejects "patchwork" or "band-aid" fixes:
- Never wrap broken logic in generic `try...except Exception: pass` blocks.
- Never rely on global mutable state or module-level singletons.
- Never duplicate logic across files; establish clean abstractions.
- Never introduce import-time side effects (e.g., establishing connections or launching threads upon import).
- Always address the root cause of failures, never merely suppress symptoms.

---

## 9. Pull Request Process

1. Provide a clear description of the change and refer to relevant issue tickets.
2. Ensure full test coverage and ensure all gates pass.
3. Require at least one review approval before merging.
4. Merge using Squash and Merge to maintain a linear and clean git history.

---

## 10. Adding a New Vehicle Type (Extending the "Arm Stump")

Monocranium is designed around a modular "arm stump" architecture:
1. To support a new vehicle (e.g., copter, plane, boat), create a new simulator in `src/simulators/<vehicle>_sim.py`.
2. Do **NOT** modify existing files in `src/core/` unless updating the generic `VehicleType` enum or protocol mappings.
3. Wire the new vehicle endpoint into `src/main.py`.
4. Add vehicle-specific visualization or telemetry panels in the dashboard if necessary.
