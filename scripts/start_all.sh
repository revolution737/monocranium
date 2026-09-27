#!/bin/bash
set -e

# Monocranium Unified Process Launcher
# Launches simulated vehicles (Rover and/or Drone SITL) and the Core Bridge.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

# Virtual environment python detection
if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

# Constants
SIMULATOR_STARTUP_DELAY_SECONDS=2

# Default mode
MODE="all"

# Parse CLI options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --all)
            MODE="all"
            shift
            ;;
        --rover)
            MODE="rover"
            shift
            ;;
        --drone)
            MODE="drone"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--rover | --drone | --all]"
            echo "  --all    Launch Rover sim, Drone sim, and Core Bridge (default)"
            echo "  --rover  Launch Rover sim and Core Bridge only"
            echo "  --drone  Launch Drone sim and Core Bridge only"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            echo "Usage: $0 [--rover | --drone | --all]" >&2
            exit 1
            ;;
    esac
done

# Ensure all background simulator processes are terminated upon exit
cleanup() {
    local pids
    pids=$(jobs -p)
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
    fi
}
trap cleanup INT TERM EXIT

# Launch requested vehicle simulators in background
case "$MODE" in
    all)
        echo "=== Starting Rover Simulator (port 5770) ==="
        "$PYTHON" -m src.simulators.rover_main &
        echo "=== Starting Drone Simulator (port 5771) ==="
        "$PYTHON" -m src.simulators.drone_main &
        ;;
    rover)
        echo "=== Starting Rover Simulator (port 5770) ==="
        "$PYTHON" -m src.simulators.rover_main &
        ;;
    drone)
        echo "=== Starting Drone Simulator (port 5771) ==="
        "$PYTHON" -m src.simulators.drone_main &
        ;;
esac

sleep "$SIMULATOR_STARTUP_DELAY_SECONDS"

echo "=== Starting Core Bridge ==="
"$PYTHON" -m src.main
