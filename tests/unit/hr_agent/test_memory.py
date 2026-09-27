"""M4.2: long-term memory. Verifies the write path (_persist_to_memory) and ADK's own
InMemoryMemoryService contract, with no model call and no live GCP service -- swapping in
VertexAiMemoryBankService later (Module 7) changes only the CLI's --memory_service_uri flag,
not this code (see docs/PROGRESS.md M4.2)."""

from google.adk.agents import Agent, Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.sessions import InMemorySessionService
from google.genai import types

from hr_agent.agents.pto import _persist_to_memory
from hr_agent.config import MODEL_ID


async def test_in_memory_memory_service_round_trips_by_user_not_session() -> None:
    """Sanity-checks ADK's own stub before relying on it: search_memory is scoped by
    (app_name, user_id), so it must find a memory written under a *different* session_id for
    the same user -- that's what makes cross-session recall possible at all."""
    memory_service = InMemoryMemoryService()
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="test", user_id="u1")
    await session_service.append_event(
        session,
        Event(
            author="user",
            content=types.Content(role="user", parts=[types.Part(text="I am employee E1002")]),
        ),
    )

    await memory_service.add_session_to_memory(session)
    response = await memory_service.search_memory(
        app_name="test", user_id="u1", query="employee id"
    )

    assert any(
        "E1002" in (part.text or "")
        for memory in response.memories
        for part in memory.content.parts or []
    )


async def test_persist_to_memory_writes_the_session() -> None:
    """_persist_to_memory (pto_agent's after_agent_callback) delegates to
    Context.add_session_to_memory, which reads memory_service off the InvocationContext --
    prove the wiring without going through a real agent turn."""
    memory_service = InMemoryMemoryService()
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name="test", user_id="u1")
    await session_service.append_event(
        session,
        Event(
            author="user",
            content=types.Content(role="user", parts=[types.Part(text="What's my balance?")]),
        ),
    )
    invocation_context = InvocationContext(
        invocation_id="test-invocation",
        agent=Agent(name="test_agent", model=MODEL_ID),
        session=session,
        session_service=session_service,
        memory_service=memory_service,
    )

    await _persist_to_memory(Context(invocation_context))

    response = await memory_service.search_memory(app_name="test", user_id="u1", query="balance")
    assert response.memories
