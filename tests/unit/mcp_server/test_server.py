"""Tests through the MCP server object: registration, schema, validation, wire results."""

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult

from mcp_server import handlers
from mcp_server.server import mcp

TOOLS = {"get_employee", "get_payroll_run", "submit_pto_request"}


@pytest.fixture(autouse=True)
def _reset_requests() -> Iterator[None]:
    handlers._pto_requests.clear()
    yield
    handlers._pto_requests.clear()


def call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool over the server's dispatch path; return its structured result."""
    result = asyncio.run(mcp.call_tool(name, args))
    assert isinstance(result, CallToolResult)
    assert not result.is_error
    assert result.structured_content is not None
    payload: dict[str, Any] = result.structured_content["result"]
    return payload


def test_exposes_exactly_the_hcm_tools() -> None:
    assert {t.name for t in asyncio.run(mcp.list_tools())} == TOOLS


def test_every_tool_has_description_and_output_schema() -> None:
    for tool in asyncio.run(mcp.list_tools()):
        assert tool.description, tool.name
        assert tool.output_schema is not None, tool.name


def test_published_schemas_enforce_constraints() -> None:
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    pto = tools["submit_pto_request"].input_schema["properties"]
    assert pto["employee_id"]["pattern"] == r"^E\d{4}$"
    assert pto["start_date"]["pattern"] == r"^\d{4}-\d{2}-\d{2}$"
    assert pto["idempotency_key"]["maxLength"] == 64
    assert tools["get_payroll_run"].input_schema["properties"]["run_id"]["pattern"]


def test_submit_schema_requires_all_arguments() -> None:
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    required = set(tools["submit_pto_request"].input_schema["required"])
    assert required == {"employee_id", "start_date", "end_date", "idempotency_key"}


def test_success_result_over_dispatch() -> None:
    assert call("get_employee", {"employee_id": "E1002"}) == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "title": "Software Engineer",
    }


def test_handler_errors_are_data_not_protocol_errors() -> None:
    result = call("get_employee", {"employee_id": "E9999"})
    assert result["status"] == "error"
    assert result["code"] == "not_found"


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("get_employee", {"employee_id": " e1002"}),
        ("get_employee", {"employee_id": "1002"}),
        ("get_employee", {}),
        ("get_employee", {"employee_id": 1002}),
        ("get_payroll_run", {"run_id": "2026-09"}),
        (
            "submit_pto_request",
            {
                "employee_id": "E1002",
                "start_date": "09/11/2026",
                "end_date": "2026-09-11",
                "idempotency_key": "k",
            },
        ),
        (
            "submit_pto_request",
            {
                "employee_id": "E1002",
                "start_date": "2026-09-11",
                "end_date": "2026-09-11",
                "idempotency_key": "",
            },
        ),
        (
            "submit_pto_request",
            {
                "employee_id": "E1002",
                "start_date": "2026-09-11",
                "end_date": "2026-09-11",
                "idempotency_key": "x" * 65,
            },
        ),
        (
            "submit_pto_request",
            {
                "employee_id": "E1002",
                "start_date": "2026-09-11",
                "end_date": "2026-09-11",
                "idempotency_key": "has space",
            },
        ),
    ],
)
def test_malformed_input_rejected_before_handler_runs(tool: str, args: dict[str, Any]) -> None:
    with pytest.raises(ToolError, match="validation error"):
        asyncio.run(mcp.call_tool(tool, args))
    assert not handlers._pto_requests


def test_unknown_tool_rejected() -> None:
    with pytest.raises(ToolError, match="Unknown tool"):
        asyncio.run(mcp.call_tool("get_salary", {"employee_id": "E1002"}))


def test_semantic_date_error_passes_schema_but_returns_error_data() -> None:
    # Matches the date pattern but is not a real date; the handler owns that check.
    result = call(
        "submit_pto_request",
        {
            "employee_id": "E1002",
            "start_date": "2026-02-30",
            "end_date": "2026-03-02",
            "idempotency_key": "k1",
        },
    )
    assert result["code"] == "invalid_dates"


def test_pto_retry_replays_over_dispatch() -> None:
    args = {
        "employee_id": "E1002",
        "start_date": "2026-09-11",
        "end_date": "2026-09-11",
        "idempotency_key": "retry-1",
    }
    first = call("submit_pto_request", args)
    again = call("submit_pto_request", args)
    assert first["replayed"] is False
    assert again["replayed"] is True
    assert again["request_id"] == first["request_id"]
    assert len(handlers._pto_requests) == 1


def test_pto_key_conflict_over_dispatch() -> None:
    base = {"employee_id": "E1002", "idempotency_key": "k1"}
    call("submit_pto_request", {**base, "start_date": "2026-09-11", "end_date": "2026-09-11"})
    result = call(
        "submit_pto_request", {**base, "start_date": "2026-09-14", "end_date": "2026-09-14"}
    )
    assert result["code"] == "idempotency_conflict"


def test_responses_never_leak_sensitive_fields() -> None:
    result = call("get_employee", {"employee_id": "E1002"})
    assert not {"salary", "pto_hours", "manager"} & set(result)
