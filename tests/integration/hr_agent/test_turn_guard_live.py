"""TurnGuardPlugin through a real ADK Runner (M8.4 RCA items 3 and 4): an agent whose MCP
server is unreachable ends the turn with the fixed message instead of running tool-less.

No model call is made -- the plugin answers before the first one -- so this is cheap and
deterministic, but it does exercise ADK's real toolset-load failure path."""

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from hr_agent.config import MODEL_ID
from hr_agent.turn_guard import TOOLS_UNAVAILABLE_MESSAGE, TurnGuardPlugin

from .conftest import run_turn

# Port 1 is never listening: connection refused immediately, regardless of any local server.
_DEAD_MCP_URL = "http://127.0.0.1:1/mcp"


async def test_unreachable_hcm_ends_the_turn_with_the_fixed_message() -> None:
    agent = Agent(
        name="pto_agent",
        model=MODEL_ID,
        tools=[
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(url=_DEAD_MCP_URL),
                tool_filter=["get_pto_balance"],
            )
        ],
    )
    app = App(name="hr_agent_it", root_agent=agent, plugins=[TurnGuardPlugin()])
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(app_name="hr_agent_it", user_id="u1")

    turn = await run_turn(runner, session.id, "How much PTO do I have?")

    assert turn.text == TOOLS_UNAVAILABLE_MESSAGE
    assert turn.tool_calls == []
    assert turn.transfers == []
