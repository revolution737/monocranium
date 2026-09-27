#!/bin/bash
set -e

# Monocranium ArduPilot Copter SITL Launcher
# Launches real ArduPilot Copter SITL (C++ firmware) via Docker if available,
# falling back to a local sim_vehicle.py installation.

DEFAULT_PORT=5771
DOCKER_TARGET_PORT=5760
DOCKER_IMAGE="radarku/ardupilot-sitl"

PORT="$DEFAULT_PORT"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)
            if [[ -z "$2" || "$2" =~ ^-- ]]; then
                echo "Error: --port requires a port number argument" >&2
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        --port=*)
            PORT="${1#*=}"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--port <port>]"
            echo "  --port <port>  MAVLink TCP port to expose (default: 5771)"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            echo "Usage: $0 [--port <port>]" >&2
            exit 1
            ;;
    esac
done

# Check Docker availability first (CLI installed and daemon responsive)
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    echo "=== Launching ArduPilot SITL in Docker container on port $PORT ==="
    exec docker run --rm -it -p "$PORT:$DOCKER_TARGET_PORT" "$DOCKER_IMAGE" \
        sim_vehicle.py -v ArduCopter -f quad --out=tcp:0.0.0.0:$DOCKER_TARGET_PORT
elif command -v sim_vehicle.py >/dev/null 2>&1; then
    echo "=== Docker unavailable; launching local ArduPilot SITL on port $PORT ==="
    exec sim_vehicle.py -v ArduCopter -f quad --out=tcp:127.0.0.1:"$PORT"
else
    echo "Error: Neither Docker nor local sim_vehicle.py is available on this system." >&2
    echo "" >&2
    echo "To run ArduPilot Copter SITL, please install one of the following:" >&2
    echo "  1. Docker Desktop: https://docs.docker.com/get-docker/" >&2
    echo "     Ensure the Docker daemon is running, then re-run this script." >&2
    echo "  2. Local ArduPilot Development Environment:" >&2
    echo "     Follow the ArduPilot setup documentation: https://ardupilot.org/dev/docs/setting-up-sitl-on-linux.html" >&2
    echo "     Ensure sim_vehicle.py is available in your PATH." >&2
    exit 1
fi
