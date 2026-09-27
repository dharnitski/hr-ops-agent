"""Live model calls: session state lets the PTO agent remember context across turns."""

from collections.abc import Awaitable, Callable

import pytest

from tests.integration.hr_agent.conftest import Turn

Conversation = Callable[[], Awaitable[Callable[[str], Awaitable[Turn]]]]

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("hcm_server")]


async def test_second_turn_uses_remembered_employee_without_reasking(
    conversation: Conversation,
) -> None:
    ask = await conversation()
    first = await ask("How much PTO does E1002 have?")
    assert first.tool_calls == [("get_pto_balance", {"employee_id": "E1002"})]

    second = await ask("Submit PTO from 2026-11-02 to 2026-11-03.")
    submits = [args for name, args in second.tool_calls if name == "submit_pto_request"]
    assert submits, "expected submit_pto_request without the agent asking for an ID first"
    assert submits[0]["employee_id"] == "E1002"


async def test_pending_pto_request_is_recalled_without_resubmitting(
    conversation: Conversation,
) -> None:
    ask = await conversation()
    first = await ask("Submit PTO for E1002 from 2026-11-02 to 2026-11-03.")
    assert [name for name, _ in first.tool_calls if name == "submit_pto_request"]

    second = await ask("What's the status of that request?")
    assert not [name for name, _ in second.tool_calls if name == "submit_pto_request"]
    assert "pending" in second.text.lower()
