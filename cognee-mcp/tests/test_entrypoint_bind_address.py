"""Focused entrypoint tests for BIND_ADDRESS env var behavior.

Tests three cases per the DC immutable build spec:
1. Unset/default BIND_ADDRESS → uses 0.0.0.0
2. BIND_ADDRESS=:: → uses :: (IPv6 dual-stack for Railway)
3. BIND_ADDRESS=localhost → uses localhost

These tests run the actual entrypoint.sh via bash with a mock cognee-mcp
that echoes its arguments, then assert the --host value in the output.
"""
import os
import platform
import subprocess
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[1] / "entrypoint.sh"

pytestmark = pytest.mark.skipif(
    platform.system() != "Linux",
    reason="entrypoint tests require bash (run in CI on Linux)",
)


def _run_entrypoint(env_overrides: dict) -> str:
    """Run the entrypoint with a mock cognee-mcp that echoes its args.

    Returns the combined stdout+stderr output.
    """
    mock_dir = Path(__file__).parent / ".mock_bin"
    mock_dir.mkdir(exist_ok=True)
    mock_cognee_mcp = mock_dir / "cognee-mcp"
    mock_cognee_mcp.write_text(
        "#!/bin/bash\necho \"MOCK_ARGS: $@\"\n",
        encoding="utf-8",
    )
    mock_cognee_mcp.chmod(0o755)

    env = {
        "PATH": f"{mock_dir}:{os.environ.get('PATH', '')}",
        "TRANSPORT_MODE": "http",
        "HTTP_PORT": "8000",
        "EXTRAS": "",
        "API_URL": "",
        "DEBUG": "false",
        "HOME": str(Path(__file__).parent),
    }
    env.update(env_overrides)

    result = subprocess.run(
        ["bash", str(ENTRYPOINT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout + result.stderr


def test_bind_address_unset_defaults_to_0000():
    """When BIND_ADDRESS is unset, the entrypoint defaults to 0.0.0.0."""
    output = _run_entrypoint({})
    assert "Bind address: 0.0.0.0" in output
    assert "--host 0.0.0.0" in output


def test_bind_address_ipv6_dual_stack():
    """When BIND_ADDRESS=::, the entrypoint uses :: (IPv6 dual-stack)."""
    output = _run_entrypoint({"BIND_ADDRESS": "::"})
    assert "Bind address: ::" in output
    assert "--host ::" in output


def test_bind_address_localhost():
    """When BIND_ADDRESS=localhost, the entrypoint uses localhost."""
    output = _run_entrypoint({"BIND_ADDRESS": "localhost"})
    assert "Bind address: localhost" in output
    assert "--host localhost" in output
