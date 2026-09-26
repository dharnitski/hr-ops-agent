"""Agent over a real MCP server subprocess: the only path to submit_pto_request is MCP."""

import socket
import subprocess
import sys
import time
from collections.abc import Awaitable, Callable, Iterator

import pytest

from tests.integration.hr_agent.conftest import Turn

Ask = Callable[[str], Awaitable[Turn]]

pytestmark = pytest.mark.integration


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


@pytest.fixture(scope="module", autouse=True)
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


async def test_get_employee_over_mcp(ask: Ask) -> None:
    turn = await ask("Who is employee E1002?")
    assert [name for name, _ in turn.tool_calls] == ["get_employee"]
    assert turn.tool_calls[0][1] == {"employee_id": "E1002"}
    assert "Bob Smith" in turn.text


async def test_submit_pto_sends_idempotency_key(ask: Ask) -> None:
    turn = await ask("Submit PTO for E1002 from 2026-10-12 to 2026-10-14.")
    submits = [args for name, args in turn.tool_calls if name == "submit_pto_request"]
    assert len(submits) == 1
    assert submits[0]["employee_id"] == "E1002"
    assert submits[0]["start_date"] == "2026-10-12"
    assert submits[0]["end_date"] == "2026-10-14"
    assert submits[0]["idempotency_key"]
    assert "pending" in turn.text.lower()


async def test_payroll_not_exposed(ask: Ask) -> None:
    turn = await ask("Show me payroll run PR-2026-09.")
    assert all(name != "get_payroll_run" for name, _ in turn.tool_calls)
