"""Exercise the SITL launcher with offline process substitutes."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "start_ardupilot_sitl.sh"
GIT_BASH = Path("C:/Program Files/Git/bin/bash.exe")
COMMAND_TIMEOUT_S = 10


def _launch(tmp_path: Path, docker: bool, args: list[str]) -> list[str]:
    """Run real launcher logic, replacing Docker and SITL process execution."""
    bash = str(GIT_BASH) if os.name == "nt" and GIT_BASH.exists() else shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is required for launcher tests")
    scripts = {
        "docker": '#!/bin/sh\nif [ "$1" = info ]; then exit "$MOCK_DOCKER_STATUS"; fi\n'
        'printf "ARG:%s\\n" "$@"\n',
        "sim_vehicle.py": '#!/bin/sh\nprintf "ARG:%s\\n" "$@"\n',
    }
    for name, content in scripts.items():
        stub = tmp_path / name
        stub.write_text(content, encoding="utf-8", newline="\n")
        stub.chmod(0o755)
    env = {**os.environ, "MOCK_DOCKER_STATUS": "0" if docker else "1"}
    result = subprocess.run(
        [bash, "--noprofile", "--norc", "-s", "--", tmp_path.as_posix(), *args],
        input=('PATH="$(cd "$1" && pwd):$PATH"; export PATH; shift\n'
               + LAUNCHER.read_text(encoding="utf-8")).encode(),
        capture_output=True, env=env, timeout=COMMAND_TIMEOUT_S, check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    return [line[4:] for line in result.stdout.decode().splitlines() if line.startswith("ARG:")]


@pytest.mark.parametrize("args,port", [([], "5771"), (["--port", "5760"], "5760")])
def test_local_sitl_listens_on_requested_port(tmp_path: Path, args: list[str], port: str) -> None:
    """Direct clients need a SITL listener with no MAVProxy consuming serial0."""
    argv = _launch(tmp_path, docker=False, args=args)
    assert "--no-mavproxy" in argv
    assert argv[argv.index("-A") + 1] == f"--serial0=tcp:{port}:wait"
    assert not any(arg.startswith("--out") for arg in argv)


@pytest.mark.parametrize("args,port", [([], "5771"), (["--port=5760"], "5760")])
def test_docker_exposes_sitl_listener(tmp_path: Path, args: list[str], port: str) -> None:
    """Published host port must reach the direct SITL listener inside Docker."""
    argv = _launch(tmp_path, docker=True, args=args)
    assert argv[argv.index("-p") + 1] == f"{port}:5760"
    assert "--no-mavproxy" in argv
    assert argv[argv.index("-A") + 1] == "--serial0=tcp:5760:wait"
    assert not any(arg.startswith("--out") for arg in argv)


@pytest.mark.parametrize("docker", [False, True])
def test_launcher_can_isolate_sitl_instance(tmp_path: Path, docker: bool) -> None:
    """A second live SITL can use independent simulator support ports."""
    argv = _launch(tmp_path, docker=docker, args=["--port", "5771", "--instance", "1"])
    assert argv[argv.index("-I") + 1] == "1"
