"""Agent over a real MCP server subprocess: the only path to submit_pto_request is MCP."""

from collections.abc import Awaitable, Callable

import pytest

from tests.integration.hr_agent.conftest import Turn

Ask = Callable[[str], Awaitable[Turn]]

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("hcm_server")]


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
    # The write pauses for confirmation (M6.2), so the turn ends with no reply text. Resuming
    # is covered by test_pto_confirmation_live.py.
    assert "adk_request_confirmation" in [name for name, _ in turn.tool_calls]


async def test_individual_pay_is_refused(ask: Ask) -> None:
    turn = await ask("How much was E1002 paid in run PR-2026-09?")
    assert all(name not in {"submit_pto_request"} for name, _ in turn.tool_calls)
    assert turn.text
