import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from hr_agent.agent import root_agent
from hr_agent.toolsets import CALLER_EMPLOYEE_ID_STATE_KEY

# Every prompt in this suite asks about E1002 (Bob Smith) unless a test says otherwise, so
# every session here is "E1002's own session" -- get_employee's Module 6 self-only check
# passes for the calls these tests actually expect to succeed. No fixture here yet lets a
# test be a *different* caller asking about E1002 (the forbidden path), so there's no
# live-agent-level coverage of that yet -- only mcp_server/handlers.py and the MCP-server-only
# integration test (tests/integration/mcp_server/test_server_http.py) cover it today.
_DEFAULT_CALLER_EMPLOYEE_ID = "E1002"


@dataclass
class Turn:
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    text: str = ""
    transfers: list[str] = field(default_factory=list)  # agents the router handed off to


@pytest.fixture(autouse=True)
def require_gcp() -> None:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        pytest.skip("GOOGLE_CLOUD_PROJECT not set (see hr_agent/.env)")


async def _run_turn(runner: InMemoryRunner, session_id: str, prompt: str) -> Turn:
    turn = Turn()
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    async for event in runner.run_async(user_id="u1", session_id=session_id, new_message=message):
        for call in event.get_function_calls():
            if call.name == "transfer_to_agent":
                turn.transfers.append(str((call.args or {}).get("agent_name")))
            else:
                turn.tool_calls.append((call.name or "", dict(call.args or {})))
        if event.is_final_response() and event.content and event.content.parts:
            turn.text = "".join(p.text or "" for p in event.content.parts)
    return turn


@pytest.fixture
def ask() -> Callable[[str], Awaitable[Turn]]:
    """Run one user message through root_agent; return the tool calls and final text.

    Each call starts a fresh session, so the agent has no memory of a prior `ask` call. Use
    `conversation` instead to send several turns into the same session.
    """

    async def _ask(prompt: str) -> Turn:
        runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")
        session = await runner.session_service.create_session(
            app_name="hr_agent_it",
            user_id="u1",
            state={CALLER_EMPLOYEE_ID_STATE_KEY: _DEFAULT_CALLER_EMPLOYEE_ID},
        )
        return await _run_turn(runner, session.id, prompt)

    return _ask


@pytest.fixture
def conversation() -> Callable[[], Awaitable[Callable[[str], Awaitable[Turn]]]]:
    """Start a multi-turn conversation: each call to the returned function is one more turn in
    the same session, so session state set on one turn (e.g. current_employee_id) is visible on
    the next.
    """

    async def _start() -> Callable[[str], Awaitable[Turn]]:
        runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")
        session = await runner.session_service.create_session(
            app_name="hr_agent_it",
            user_id="u1",
            state={CALLER_EMPLOYEE_ID_STATE_KEY: _DEFAULT_CALLER_EMPLOYEE_ID},
        )

        async def _turn(prompt: str) -> Turn:
            return await _run_turn(runner, session.id, prompt)

        return _turn

    return _start


@pytest.fixture
def sessions() -> Callable[[], Awaitable[Callable[[str], Awaitable[Turn]]]]:
    """Start a new session per call, all sharing one runner (and its memory_service) and user_id.

    Unlike `conversation` (one session, many turns -- for session-state tests), this is for
    long-term memory tests (M4.2): each call is a fresh session, so session state
    (current_employee_id, pending_pto_request) never carries over, but anything pto_agent's
    after_agent_callback persisted to memory from an earlier session does.
    """
    runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")

    async def _new_session() -> Callable[[str], Awaitable[Turn]]:
        session = await runner.session_service.create_session(
            app_name="hr_agent_it",
            user_id="u1",
            state={CALLER_EMPLOYEE_ID_STATE_KEY: _DEFAULT_CALLER_EMPLOYEE_ID},
        )

        async def _turn(prompt: str) -> Turn:
            return await _run_turn(runner, session.id, prompt)

        return _turn

    return _new_session
