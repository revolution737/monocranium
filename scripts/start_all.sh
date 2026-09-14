#!/bin/bash
set -e
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON="$ROOT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

trap 'kill $(jobs -p) 2>/dev/null; exit' INT TERM

echo "=== Starting Rover Simulator ==="
"$PYTHON" -m src.simulators.rover_main &
ROVER_PID=$!
sleep 2

echo "=== Starting Core Bridge ==="
"$PYTHON" -m src.main
kill $ROVER_PID 2>/dev/null

