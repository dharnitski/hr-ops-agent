import os
from dataclasses import dataclass, field

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from hr_agent.agent import root_agent


@dataclass
class Turn:
    tool_calls: list[tuple[str, dict]] = field(default_factory=list)
    text: str = ""


@pytest.fixture(autouse=True)
def require_gcp():
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        pytest.skip("GOOGLE_CLOUD_PROJECT not set (see hr_agent/.env)")


@pytest.fixture
def ask():
    """Run one user message through root_agent; return the tool calls and final text."""

    async def _ask(prompt: str) -> Turn:
        runner = InMemoryRunner(agent=root_agent, app_name="hr_agent_it")
        session = await runner.session_service.create_session(app_name="hr_agent_it", user_id="u1")
        turn = Turn()
        message = types.Content(role="user", parts=[types.Part(text=prompt)])
        async for event in runner.run_async(
            user_id="u1", session_id=session.id, new_message=message
        ):
            for call in event.get_function_calls():
                turn.tool_calls.append((call.name, dict(call.args or {})))
            if event.is_final_response() and event.content and event.content.parts:
                turn.text = "".join(p.text or "" for p in event.content.parts)
        return turn

    return _ask
