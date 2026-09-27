import socket
import subprocess
import sys
import time
from collections.abc import Iterator

import pytest


def _wait_for_port(port: int, proc: subprocess.Popen[bytes], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            pytest.fail("MCP server exited during startup")
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.2)
    pytest.fail("MCP server did not start")


@pytest.fixture(scope="session")
def hcm_server() -> Iterator[None]:
    # The agent reads HCM_MCP_URL at import, so the default port must be free.
    with socket.socket() as s:
        if s.connect_ex(("127.0.0.1", 8000)) == 0:
            pytest.skip("port 8000 already in use")
    proc = subprocess.Popen([sys.executable, "-m", "mcp_server.server"])
    try:
        _wait_for_port(8000, proc)
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=10)
