"""Docker-based integration tests for bindle.

These tests build the project inside Docker, create bundles for various
executables, and verify that the bundled applications run correctly in a
clean environment.
"""

import pytest

from .conftest import docker_available, docker_build


pytestmark = pytest.mark.skipif(
    not docker_available(),
    reason="Docker is not available or the daemon is unreachable",
)


class TestBundleContents:
    """Verify that a built bundle has the expected structure and content."""

    def test_blacklisted_libs_are_excluded(self) -> None:
        """Blacklisted libraries must NOT appear in the bundle's lib/."""
        proc = docker_build("verify-blacklist")
        assert proc.returncode == 0, (
            f"Docker build (verify-blacklist) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )


class TestBundleExecution:
    """Verify that the bundled binary actually runs."""

    def test_bundle_runs(self) -> None:
        """The bundled testapp must execute successfully in a clean image."""
        proc = docker_build("test-run")
        assert proc.returncode == 0, (
            f"Docker build (test-run) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )


class TestUtilityRedeployment:
    """Bundle common Linux utilities and verify they work after redeployment."""

    def test_ls(self) -> None:
        """Bundled /bin/ls must list files correctly."""
        proc = docker_build("test-ls")
        assert proc.returncode == 0, (
            f"Docker build (test-ls) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    def test_ssh(self) -> None:
        """Bundled /usr/bin/ssh must print its version and exit 0."""
        proc = docker_build("test-ssh")
        assert proc.returncode == 0, (
            f"Docker build (test-ssh) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    def test_git(self) -> None:
        """Bundled /usr/bin/git must print its version and exit 0."""
        proc = docker_build("test-git")
        assert proc.returncode == 0, (
            f"Docker build (test-git) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    def test_ffmpeg(self) -> None:
        """Bundled /usr/bin/ffmpeg must print its version and exit 0."""
        proc = docker_build("test-ffmpeg")
        assert proc.returncode == 0, (
            f"Docker build (test-ffmpeg) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    def test_convert(self) -> None:
        """Bundled /usr/bin/convert must print its version and exit 0."""
        proc = docker_build("test-convert")
        assert proc.returncode == 0, (
            f"Docker build (test-convert) failed:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )
