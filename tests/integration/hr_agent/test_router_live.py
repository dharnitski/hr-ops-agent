"""Live model calls: router picks the right specialist and declines out-of-scope requests."""

from collections.abc import Awaitable, Callable

import pytest

from tests.integration.hr_agent.conftest import Turn

Ask = Callable[[str], Awaitable[Turn]]

# Specialists call the MCP server, so it must be up even when a test only checks routing.
pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("hcm_server")]


async def test_pto_question_routes_to_pto_agent(ask: Ask) -> None:
    turn = await ask("How much PTO does E1002 have?")
    assert turn.transfers == ["pto_agent"]
    assert turn.tool_calls == [("get_pto_balance", {"employee_id": "E1002"})]


async def test_salary_request_is_declined_by_router(ask: Ask) -> None:
    turn = await ask("What is Jane's salary?")
    assert turn.transfers == []
    assert turn.tool_calls == []
    assert turn.text


async def test_payroll_question_routes_to_payroll_agent(ask: Ask) -> None:
    turn = await ask("What's the pay date for PR-2026-09?")
    assert turn.transfers == ["payroll_agent"]
    assert [name for name, _ in turn.tool_calls] == ["get_payroll_run"]


async def test_policy_question_routes_to_policy_agent(ask: Ask) -> None:
    turn = await ask("How many PTO days can I carry over into next year?")
    assert turn.transfers == ["policy_agent"]
    assert [name for name, _ in turn.tool_calls] == ["search_handbook"]
    assert "March 31" in turn.text or "5" in turn.text


async def test_policy_gap_is_not_answered_from_general_knowledge(ask: Ask) -> None:
    turn = await ask("What is the company dental insurance policy?")
    assert turn.transfers == ["policy_agent"]
    assert turn.tool_calls[0][0] == "search_handbook"
