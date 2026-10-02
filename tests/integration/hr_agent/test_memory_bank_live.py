"""Live model calls against the real Agent Engine Memory Bank (M4.2), not the
InMemoryMemoryService stub test_memory_live.py exercises.

Same cross-session recall scenario as test_memory_live.py, but backed by
VertexAiMemoryBankService pointed at the deployed M7.1 Agent Engine resource -- a different
memory service with real LLM-based fact extraction, its own retrieval relevance model, and a
real network/billing dependency instead of a process-local dict. Uses a dedicated user_id so
these runs don't mix with M7's own live-deploy verification traffic on the same resource. See
docs/COURSE.md's API currency notes: no separate Memory Bank resource exists to create --
MEMORY_BANK_AGENT_ENGINE_ID is the existing reasoning engine ID.

Found live: VertexAiMemoryBankService.add_events_to_memory fires the server-side ingest/extract
as a background task and does not await it (confirmed by reading
google.adk.memory.vertex_ai_memory_bank_service -- the comment there says awaiting isn't
"necessary outside debugging", which assumes the caller doesn't need read-after-write). The
in-memory stub is synchronous, so test_memory_live.py's identical scenario never needed this;
here, searching immediately after the first session reliably found nothing. Poll
search_memory directly (cheap, no model call) before spending a second real agent turn on it.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable

import pytest
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import VertexAiMemoryBankService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from hr_agent.agent import root_agent
from hr_agent.toolsets import CALLER_EMPLOYEE_ID_STATE_KEY
from tests.integration.hr_agent.conftest import Turn, run_turn

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("hcm_server")]

_APP_NAME = "hr_agent_it_live_memory"
_LIVE_MEMORY_USER_ID = "m4.2-live-memory-test"
_CALLER_EMPLOYEE_ID = "E1002"
_MEMORY_POLL_ATTEMPTS = 10
_MEMORY_POLL_INTERVAL_SECONDS = 3

NewLiveSession = Callable[[], Awaitable[Callable[[str], Awaitable[Turn]]]]


@pytest.fixture(autouse=True)
def require_memory_bank() -> None:
    if not os.environ.get("MEMORY_BANK_AGENT_ENGINE_ID"):
        pytest.skip("MEMORY_BANK_AGENT_ENGINE_ID not set (see .env.example)")


@pytest.fixture
def live_memory_service() -> VertexAiMemoryBankService:
    return VertexAiMemoryBankService(
        project=os.environ["GOOGLE_CLOUD_PROJECT"],
        location=os.environ.get("MEMORY_BANK_LOCATION", "us-central1"),
        agent_engine_id=os.environ["MEMORY_BANK_AGENT_ENGINE_ID"],
    )


@pytest.fixture
def live_memory_sessions(live_memory_service: VertexAiMemoryBankService) -> NewLiveSession:
    """Same shape as conftest.py's `sessions`, but the real Memory Bank instead of the stub."""
    runner = Runner(
        app_name=_APP_NAME,
        agent=root_agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=live_memory_service,
    )

    async def _new_session() -> Callable[[str], Awaitable[Turn]]:
        session = await runner.session_service.create_session(
            app_name=_APP_NAME,
            user_id=_LIVE_MEMORY_USER_ID,
            state={CALLER_EMPLOYEE_ID_STATE_KEY: _CALLER_EMPLOYEE_ID},
        )

        async def _turn(prompt: str) -> Turn:
            return await run_turn(runner, session.id, prompt, user_id=_LIVE_MEMORY_USER_ID)

        return _turn

    return _new_session


async def test_second_session_recalls_employee_via_live_memory_bank(
    live_memory_service: VertexAiMemoryBankService,
    live_memory_sessions: NewLiveSession,
) -> None:
    first_session = await live_memory_sessions()
    first = await first_session("How much PTO does E1002 have?")
    assert first.tool_calls == [("get_pto_balance", {"employee_id": "E1002"})]

    for attempt in range(_MEMORY_POLL_ATTEMPTS):
        response = await live_memory_service.search_memory(
            app_name=_APP_NAME, user_id=_LIVE_MEMORY_USER_ID, query="employee"
        )
        if response.memories:
            break
        if attempt + 1 == _MEMORY_POLL_ATTEMPTS:
            pytest.fail("No memory appeared in the live Memory Bank within the poll window.")
        await asyncio.sleep(_MEMORY_POLL_INTERVAL_SECONDS)

    second_session = await live_memory_sessions()
    second = await second_session(
        "What's the PTO balance for the employee I asked about in an earlier conversation?"
    )

    # As in test_memory_live.py, the exact sequence varies run to run -- what matters is that
    # memory was consulted and the right employee's balance came back.
    assert "load_memory" in [name for name, _ in second.tool_calls]
    assert ("get_pto_balance", {"employee_id": "E1002"}) in second.tool_calls
