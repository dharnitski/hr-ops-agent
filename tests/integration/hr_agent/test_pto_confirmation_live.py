"""Live model calls: submit_pto_request pauses for human confirmation (Module 6.2) instead of
executing the moment the model decides to call it. Uses the raw Runner/Event API rather than
conftest's `ask`/`conversation` fixtures because resuming a paused call needs the confirmation
function call's id and the turn's invocation_id -- see google/adk/cli/cli.py's
`_prompt_for_function_call`/`_collect_pending_function_calls` for the reference contract this
mirrors."""

from typing import Any

from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types

from hr_agent.agent import root_agent
from hr_agent.agents.pto import PENDING_PTO_REQUEST_KEY
from hr_agent.toolsets import CALLER_EMPLOYEE_ID_STATE_KEY

_CALLER_EMPLOYEE_ID = "E1002"
_SUBMIT_PROMPT = (
    "I'm employee E1002. Please submit a PTO request for me from 2026-10-12 to 2026-10-14."
)


def _pending_confirmation(events: list[Event]) -> tuple[str, dict[str, Any]] | None:
    """Returns (function_call_id, args) for the adk_request_confirmation call, if any."""
    for event in events:
        if not event.long_running_tool_ids:
            continue
        for call in event.get_function_calls():
            if call.id in event.long_running_tool_ids and call.name == "adk_request_confirmation":
                return call.id, dict(call.args or {})
    return None


async def _run(
    runner: InMemoryRunner,
    session_id: str,
    message: types.Content,
    invocation_id: str | None = None,
) -> list[Event]:
    return [
        event
        async for event in runner.run_async(
            user_id="u1",
            session_id=session_id,
            new_message=message,
            invocation_id=invocation_id,
        )
    ]


def _final_text(events: list[Event]) -> str:
    for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            return "".join(p.text or "" for p in event.content.parts)
    return ""


async def test_submit_pto_request_pauses_for_confirmation() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")
    session = await runner.session_service.create_session(
        app_name="hr_agent_it",
        user_id="u1",
        state={CALLER_EMPLOYEE_ID_STATE_KEY: _CALLER_EMPLOYEE_ID},
    )
    message = types.Content(role="user", parts=[types.Part(text=_SUBMIT_PROMPT)])
    events = await _run(runner, session.id, message)

    pending = _pending_confirmation(events)
    assert pending is not None, "expected an adk_request_confirmation call, got none"
    _, args = pending
    original_call = args.get("originalFunctionCall", {})
    assert original_call.get("name") == "submit_pto_request"

    updated = await runner.session_service.get_session(
        app_name="hr_agent_it", user_id="u1", session_id=session.id
    )
    assert updated is not None
    assert PENDING_PTO_REQUEST_KEY not in updated.state


async def test_confirming_the_pause_submits_the_request() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")
    session = await runner.session_service.create_session(
        app_name="hr_agent_it",
        user_id="u1",
        state={CALLER_EMPLOYEE_ID_STATE_KEY: _CALLER_EMPLOYEE_ID},
    )
    first_message = types.Content(role="user", parts=[types.Part(text=_SUBMIT_PROMPT)])
    first_events = await _run(runner, session.id, first_message)
    fc_id, _ = _pending_confirmation(first_events) or (None, None)
    assert fc_id is not None
    invocation_id = first_events[-1].invocation_id

    resume_message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=fc_id,
                    name="adk_request_confirmation",
                    response={"confirmed": True},
                )
            )
        ],
    )
    resume_events = await _run(runner, session.id, resume_message, invocation_id=invocation_id)

    updated = await runner.session_service.get_session(
        app_name="hr_agent_it", user_id="u1", session_id=session.id
    )
    assert updated is not None
    pending_request = updated.state.get(PENDING_PTO_REQUEST_KEY)
    assert pending_request is not None, _final_text(resume_events)
    assert pending_request["employee_id"] == _CALLER_EMPLOYEE_ID


async def test_rejecting_the_pause_does_not_submit_the_request() -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")
    session = await runner.session_service.create_session(
        app_name="hr_agent_it",
        user_id="u1",
        state={CALLER_EMPLOYEE_ID_STATE_KEY: _CALLER_EMPLOYEE_ID},
    )
    first_message = types.Content(role="user", parts=[types.Part(text=_SUBMIT_PROMPT)])
    first_events = await _run(runner, session.id, first_message)
    fc_id, _ = _pending_confirmation(first_events) or (None, None)
    assert fc_id is not None
    invocation_id = first_events[-1].invocation_id

    resume_message = types.Content(
        role="user",
        parts=[
            types.Part(
                function_response=types.FunctionResponse(
                    id=fc_id,
                    name="adk_request_confirmation",
                    response={"confirmed": False},
                )
            )
        ],
    )
    resume_events = await _run(runner, session.id, resume_message, invocation_id=invocation_id)

    updated = await runner.session_service.get_session(
        app_name="hr_agent_it", user_id="u1", session_id=session.id
    )
    assert updated is not None
    assert PENDING_PTO_REQUEST_KEY not in updated.state
    assert _final_text(resume_events)
