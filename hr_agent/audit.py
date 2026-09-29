"""Audit log of every tool call (Module 6.3): who called what, on whose behalf, and the
outcome -- never the sensitive values a call returns (balances, totals, salary-adjacent
figures). Implemented as a plugin-level hook (google.adk.plugins.BasePlugin's
before_tool_callback/after_tool_callback/on_tool_error_callback), which fires once per tool
call across every specialist and both local and MCP tools -- unlike a per-agent
after_tool_callback (e.g. pto_agent's _track_mcp_results), which only sees that one agent's
own calls."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, override

from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from .toolsets import CALLER_EMPLOYEE_ID_STATE_KEY

AUDIT_LOGGER_NAME = "hr_agent.audit"
audit_logger = logging.getLogger(AUDIT_LOGGER_NAME)

# Allowlists, not blocklists: a field must be named here to reach the audit record. Covers
# identifiers and outcomes -- what an auditor needs to reconstruct "who did what to whom and
# was it allowed" -- never balances, totals, or free-text error messages (which can embed a
# balance, e.g. submit_pto_request's "insufficient_balance" message).
_SAFE_ARG_KEYS = frozenset({"employee_id", "run_id", "idempotency_key", "start_date", "end_date"})
_SAFE_RESULT_KEYS = frozenset(
    {"status", "code", "employee_id", "run_id", "request_id", "run_status", "replayed"}
)


def _redact(source: dict[str, Any], allowed_keys: frozenset[str]) -> dict[str, Any]:
    return {key: value for key, value in source.items() if key in allowed_keys}


def _unwrap_tool_result(result: dict[str, Any]) -> dict[str, Any] | None:
    """Reduces an MCP-wrapped result to the handler's own dict; returns it unchanged for a
    local tool's plain dict, or None for a schema-layer rejection or a not-yet-executed
    long-running/confirmation-paused call.

    MCP tools wrap the handler's dict as {"isError", "structuredContent": {"result": ...}}
    (docs/02-tool-contract-guidelines.md); mirrors hr_agent/agents/pto.py's
    _track_mcp_results, generalized to any tool rather than just submit_pto_request's shape.
    """
    if "structuredContent" not in result and "isError" not in result:
        return result
    if result.get("isError"):
        return None
    inner = result.get("structuredContent", {}).get("result")
    return inner if isinstance(inner, dict) else None


class AuditLogPlugin(BasePlugin):
    """Logs one structured record per tool call and its outcome, redacted to safe fields.

    A starting point for a real audit sink (Cloud Logging, BigQuery); this only emits
    structured log lines via the standard `logging` module -- Module 7+ decides where those
    lines actually go in production.
    """

    def __init__(self, name: str = "audit_log_plugin") -> None:
        super().__init__(name)

    @override
    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ) -> dict[str, Any] | None:
        self._emit("tool_call", tool, tool_context, args=tool_args)
        return None

    @override
    async def after_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        result: dict[str, Any],
    ) -> dict[str, Any] | None:
        # Typed as always a dict, but a tool may return any value at runtime (ADK's own
        # _as_callback_result passes it through unchanged) -- same defensive check as
        # hr_agent/agents/pto.py's _track_mcp_results.
        unwrapped = (
            _unwrap_tool_result(result)
            if isinstance(result, dict)  # ty: ignore[redundant-condition-strict]
            else None
        )
        self._emit(
            "tool_result",
            tool,
            tool_context,
            args=tool_args,
            result=_redact(unwrapped, _SAFE_RESULT_KEYS) if unwrapped else None,
        )
        return None

    @override
    async def on_tool_error_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
        error: Exception,
    ) -> dict[str, Any] | None:
        self._emit("tool_error", tool, tool_context, args=tool_args, error=type(error).__name__)
        return None

    def _emit(
        self,
        event: str,
        tool: BaseTool,
        tool_context: ToolContext,
        *,
        args: dict[str, Any],
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "tool": tool.name,
            "agent": tool_context.agent_name,
            "invocation_id": tool_context.invocation_id,
            "session_id": tool_context.session.id,
            "caller_employee_id": tool_context.state.get(CALLER_EMPLOYEE_ID_STATE_KEY),
            "args": _redact(args, _SAFE_ARG_KEYS),
        }
        if result is not None:
            record["result"] = result
        if error is not None:
            record["error"] = error
        audit_logger.info(record)
