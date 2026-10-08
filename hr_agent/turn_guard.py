"""Per-turn guard (M8.4 RCA items 3 and 4): bounds a turn and fails it cleanly when HCM is
unreachable, instead of letting a tool-less agent loop.

ADK logs a toolset that fails to load and carries on without its tools; the model then
compensates with `load_memory` and `transfer_to_agent` until the run ends (drill: 112s, ~20x
cost per turn). Two checks in `before_model_callback`, each ending the turn with a fixed
message and an audit `turn_aborted` line:

- the agent's MCP tools didn't load (compared with the toolsets' own `tool_filter`);
- the turn already made `MAX_MODEL_CALLS_PER_TURN` model calls.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from google.adk.agents.context import Context
from google.adk.agents.invocation_context import InvocationContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.genai import types

# Same Python 3.11 reason as audit.py.
from typing_extensions import override  # noqa: UP035

from .audit import audit_logger

# Healthy turns take 3-6 calls (router, identify_caller, lookup, answer). 12 leaves room for
# a legitimate retry or follow-up lookup; unmeasured, revisit with real traffic.
MAX_MODEL_CALLS_PER_TURN = 12

TOOLS_UNAVAILABLE_MESSAGE = (
    "I can't reach the HR system right now, so I can't look that up or submit requests. "
    "Please try again in a few minutes."
)
BUDGET_EXCEEDED_MESSAGE = (
    "I wasn't able to complete that request. Please try again, or contact HR directly."
)

# Reasons are a closed set: they are the only free-form field in the `turn_aborted` line.
REASON_TOOLS_UNAVAILABLE = "tools_unavailable"
REASON_BUDGET_EXCEEDED = "model_call_budget_exceeded"


def _canned(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _expected_mcp_tools(agent: object) -> set[str]:
    """Tool names the agent's MCP toolsets are configured to serve. A toolset without a
    list-form `tool_filter` contributes nothing (nothing to compare against)."""
    expected: set[str] = set()
    for tool in getattr(agent, "tools", []):
        if isinstance(tool, McpToolset) and isinstance(tool.tool_filter, list):
            expected.update(tool.tool_filter)
    return expected


class TurnGuardPlugin(BasePlugin):
    def __init__(
        self,
        name: str = "turn_guard_plugin",
        max_model_calls: int = MAX_MODEL_CALLS_PER_TURN,
    ) -> None:
        super().__init__(name)
        self._max_model_calls = max_model_calls
        self._model_calls: dict[str, int] = {}

    @override
    async def after_run_callback(self, *, invocation_context: InvocationContext) -> None:
        self._model_calls.pop(invocation_context.invocation_id, None)

    @override
    async def before_model_callback(
        self, *, callback_context: Context, llm_request: LlmRequest
    ) -> LlmResponse | None:
        agent = callback_context.get_invocation_context().agent
        missing = _expected_mcp_tools(agent) - llm_request.tools_dict.keys()
        if missing:
            self._abort(callback_context, REASON_TOOLS_UNAVAILABLE)
            return _canned(TOOLS_UNAVAILABLE_MESSAGE)

        calls = self._model_calls.get(callback_context.invocation_id, 0) + 1
        self._model_calls[callback_context.invocation_id] = calls
        if calls > self._max_model_calls:
            self._abort(callback_context, REASON_BUDGET_EXCEEDED)
            return _canned(BUDGET_EXCEEDED_MESSAGE)
        return None

    def _abort(self, callback_context: Context, reason: str) -> None:
        # ERROR level so the line is a log-based-metric / alert source on its own.
        audit_logger.log(
            logging.ERROR,
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "turn_aborted",
                "reason": reason,
                "agent": callback_context.agent_name,
                "invocation_id": callback_context.invocation_id,
                "session_id": callback_context.session.id,
            },
        )
