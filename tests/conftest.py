"""Shared fixtures and helpers for bindle tests."""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def docker_available() -> bool:
    """Return True if Docker is installed and the daemon is reachable."""
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


def docker_build(
    target: str, dockerfile: str = "tests/Dockerfile.test"
) -> subprocess.CompletedProcess[str]:
    """Run ``docker build`` targeting a specific stage."""
    return subprocess.run(
        [
            "docker",
            "build",
            "--target",
            target,
            "-f",
            dockerfile,
            str(PROJECT_ROOT),
        ],
        capture_output=True,
        text=True,
    )
