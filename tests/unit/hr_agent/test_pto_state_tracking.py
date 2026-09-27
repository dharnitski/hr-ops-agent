"""_track_mcp_results reads the MCP wire shape (structuredContent.result / isError), not the
handler's return value directly -- see docs/02-tool-contract-guidelines.md and M2 findings in
docs/PROGRESS.md. These tests fabricate that shape rather than running a real MCP server."""

from dataclasses import dataclass
from typing import Any

from google.adk.tools import ToolContext

from hr_agent.agents.pto import PENDING_PTO_REQUEST_KEY, _track_mcp_results
from hr_agent.tools import CURRENT_EMPLOYEE_ID_KEY


@dataclass
class _FakeTool:
    name: str


def _mcp_success(result: dict[str, Any]) -> dict[str, Any]:
    return {"isError": False, "structuredContent": {"result": result}}


async def test_get_employee_success_sets_current_employee(tool_context: ToolContext) -> None:
    response = _mcp_success(
        {"status": "success", "employee_id": "E1002", "name": "Bob Smith", "title": "Engineer"}
    )
    _track_mcp_results(_FakeTool("get_employee"), {}, tool_context, response)  # ty: ignore[invalid-argument-type]
    assert tool_context.state[CURRENT_EMPLOYEE_ID_KEY] == "E1002"


async def test_get_employee_business_error_does_not_set_state(tool_context: ToolContext) -> None:
    response = _mcp_success({"status": "error", "error": "not found"})
    _track_mcp_results(_FakeTool("get_employee"), {}, tool_context, response)  # ty: ignore[invalid-argument-type]
    assert CURRENT_EMPLOYEE_ID_KEY not in tool_context.state


async def test_get_employee_schema_rejection_does_not_set_state(tool_context: ToolContext) -> None:
    response = {"isError": True}
    _track_mcp_results(_FakeTool("get_employee"), {}, tool_context, response)  # ty: ignore[invalid-argument-type]
    assert CURRENT_EMPLOYEE_ID_KEY not in tool_context.state


async def test_none_response_does_not_raise(tool_context: ToolContext) -> None:
    # A long-running/deferred tool can reach the callback with no result yet (ADK docs).
    _track_mcp_results(_FakeTool("submit_pto_request"), {}, tool_context, None)  # ty: ignore[invalid-argument-type]
    assert PENDING_PTO_REQUEST_KEY not in tool_context.state


async def test_submit_pto_success_sets_pending_request(tool_context: ToolContext) -> None:
    response = _mcp_success(
        {
            "status": "success",
            "request_id": "PTO-1",
            "employee_id": "E1002",
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
            "hours": 24.0,
            "request_status": "pending",
            "replayed": False,
        }
    )
    _track_mcp_results(_FakeTool("submit_pto_request"), {}, tool_context, response)  # ty: ignore[invalid-argument-type]
    assert tool_context.state[PENDING_PTO_REQUEST_KEY] == {
        "request_id": "PTO-1",
        "employee_id": "E1002",
        "start_date": "2026-10-12",
        "end_date": "2026-10-14",
        "hours": 24.0,
        "status": "pending",
    }


async def test_submit_pto_business_error_does_not_set_pending_request(
    tool_context: ToolContext,
) -> None:
    response = _mcp_success({"status": "error", "code": "insufficient_balance", "error": "no"})
    _track_mcp_results(_FakeTool("submit_pto_request"), {}, tool_context, response)  # ty: ignore[invalid-argument-type]
    assert PENDING_PTO_REQUEST_KEY not in tool_context.state


async def test_unrelated_tool_is_ignored(tool_context: ToolContext) -> None:
    response = _mcp_success({"status": "success", "year": 2026, "holidays": []})
    _track_mcp_results(_FakeTool("list_holidays"), {}, tool_context, response)  # ty: ignore[invalid-argument-type]
    assert CURRENT_EMPLOYEE_ID_KEY not in tool_context.state
    assert PENDING_PTO_REQUEST_KEY not in tool_context.state
