"""TurnGuardPlugin (M8.4 RCA items 3 and 4): a turn whose MCP tools didn't load, or that runs
past the model-call budget, ends with a fixed message and an audit `turn_aborted` line."""

import logging
from typing import Any, cast

import pytest
from google.adk.agents import Agent, Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions import InMemorySessionService
from google.adk.tools import BaseTool

from hr_agent.agent import app
from hr_agent.agents.payroll import payroll_agent
from hr_agent.agents.pto import pto_agent
from hr_agent.audit import AUDIT_LOGGER_NAME
from hr_agent.config import MODEL_ID
from hr_agent.turn_guard import (
    BUDGET_EXCEEDED_MESSAGE,
    REASON_BUDGET_EXCEEDED,
    REASON_TOOLS_UNAVAILABLE,
    TOOLS_UNAVAILABLE_MESSAGE,
    TurnGuardPlugin,
)

PTO_MCP_TOOLS = ("get_employee", "get_pto_balance", "submit_pto_request")


async def _context(agent: Agent, invocation_id: str = "inv-1") -> Context:
    service = InMemorySessionService()
    session = await service.create_session(app_name="test", user_id="u1")
    return Context(
        InvocationContext(
            invocation_id=invocation_id, agent=agent, session=session, session_service=service
        )
    )


def _request(*tool_names: str) -> LlmRequest:
    request = LlmRequest()
    for name in tool_names:
        request.tools_dict[name] = cast(BaseTool, object())
    return request


def _text(response: LlmResponse) -> str:
    assert response.content is not None
    assert response.content.parts is not None
    text = response.content.parts[0].text
    assert text is not None
    return text


@pytest.fixture(autouse=True)
def _capture_audit_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER_NAME)


def _abort_record(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    return cast(dict[str, Any], caplog.records[-1].msg)


def test_plugin_is_wired_into_the_app() -> None:
    assert any(isinstance(p, TurnGuardPlugin) for p in app.plugins)


async def test_missing_mcp_tools_end_the_turn_with_a_fixed_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = await TurnGuardPlugin().before_model_callback(
        callback_context=await _context(pto_agent),
        llm_request=_request("identify_caller", "load_memory"),
    )
    assert response is not None
    assert _text(response) == TOOLS_UNAVAILABLE_MESSAGE
    record = _abort_record(caplog)
    assert record["event"] == "turn_aborted"
    assert record["reason"] == REASON_TOOLS_UNAVAILABLE
    assert record["agent"] == "pto_agent"


async def test_one_missing_mcp_tool_is_enough() -> None:
    response = await TurnGuardPlugin().before_model_callback(
        callback_context=await _context(pto_agent),
        llm_request=_request(*PTO_MCP_TOOLS[:2]),
    )
    assert response is not None


async def test_all_mcp_tools_loaded_proceeds() -> None:
    response = await TurnGuardPlugin().before_model_callback(
        callback_context=await _context(pto_agent),
        llm_request=_request(*PTO_MCP_TOOLS, "identify_caller"),
    )
    assert response is None


async def test_agent_without_mcp_toolsets_is_never_blocked_for_tools() -> None:
    router = Agent(name="router", model=MODEL_ID)
    response = await TurnGuardPlugin().before_model_callback(
        callback_context=await _context(router), llm_request=_request()
    )
    assert response is None


async def test_payroll_agent_is_checked_against_its_own_tools() -> None:
    response = await TurnGuardPlugin().before_model_callback(
        callback_context=await _context(payroll_agent),
        llm_request=_request(*PTO_MCP_TOOLS),
    )
    assert response is not None


async def test_message_names_no_internal_agent_or_tool() -> None:
    for message in (TOOLS_UNAVAILABLE_MESSAGE, BUDGET_EXCEEDED_MESSAGE):
        assert "_agent" not in message
        assert "loop" not in message.lower()


async def test_model_call_budget_ends_the_turn(caplog: pytest.LogCaptureFixture) -> None:
    plugin = TurnGuardPlugin(max_model_calls=3)
    context = await _context(pto_agent)
    request = _request(*PTO_MCP_TOOLS)
    for _ in range(3):
        assert (
            await plugin.before_model_callback(callback_context=context, llm_request=request)
            is None
        )

    response = await plugin.before_model_callback(callback_context=context, llm_request=request)

    assert response is not None
    assert _text(response) == BUDGET_EXCEEDED_MESSAGE
    assert _abort_record(caplog)["reason"] == REASON_BUDGET_EXCEEDED


async def test_budget_is_per_turn() -> None:
    plugin = TurnGuardPlugin(max_model_calls=1)
    request = _request(*PTO_MCP_TOOLS)
    first = await _context(pto_agent, "inv-1")
    second = await _context(pto_agent, "inv-2")

    assert await plugin.before_model_callback(callback_context=first, llm_request=request) is None
    assert await plugin.before_model_callback(callback_context=second, llm_request=request) is None
    assert (
        await plugin.before_model_callback(callback_context=first, llm_request=request) is not None
    )


async def test_after_run_releases_the_turn_counter() -> None:
    plugin = TurnGuardPlugin(max_model_calls=1)
    context = await _context(pto_agent)
    request = _request(*PTO_MCP_TOOLS)
    await plugin.before_model_callback(callback_context=context, llm_request=request)

    await plugin.after_run_callback(invocation_context=context.get_invocation_context())

    assert await plugin.before_model_callback(callback_context=context, llm_request=request) is None


async def test_abort_line_carries_ids_and_reason_only(caplog: pytest.LogCaptureFixture) -> None:
    await TurnGuardPlugin().before_model_callback(
        callback_context=await _context(pto_agent), llm_request=_request()
    )
    assert set(_abort_record(caplog)) == {
        "timestamp",
        "event",
        "reason",
        "agent",
        "invocation_id",
        "session_id",
    }
