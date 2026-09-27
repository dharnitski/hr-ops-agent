import pytest
from google.adk.agents import Agent, Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext

from hr_agent.config import MODEL_ID


@pytest.fixture
async def tool_context() -> ToolContext:
    """A real ToolContext backed by a fresh in-memory session (no network, hermetic).

    For tools that read/write session state (e.g. current_employee_id).
    """
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="test", user_id="u1")
    invocation_context = InvocationContext(
        invocation_id="test-invocation",
        agent=Agent(name="test_agent", model=MODEL_ID),
        session=session,
        session_service=session_service,
    )
    return ToolContext(invocation_context)


@pytest.fixture
async def callback_context() -> Context:
    """A real Context backed by a fresh in-memory session (no network, hermetic).

    For agent/model callbacks (e.g. after_agent_callback, before_model_callback).
    """
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="test", user_id="u1")
    invocation_context = InvocationContext(
        invocation_id="test-invocation",
        agent=Agent(name="test_agent", model=MODEL_ID),
        session=session,
        session_service=session_service,
    )
    return Context(invocation_context)
