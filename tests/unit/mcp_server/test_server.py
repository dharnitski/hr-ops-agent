"""Tests through the MCP server object: registration, schema, validation, wire results."""

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from mcp.server.context import ServerRequestContext
from mcp.server.mcpserver.context import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult
from pydantic import TypeAdapter

from mcp_server import handlers
from mcp_server.handlers import IsoDate
from mcp_server.server import mcp

TOOLS = {"get_employee", "get_pto_balance", "get_payroll_run", "submit_pto_request"}


@pytest.fixture(autouse=True)
def _reset_requests() -> Iterator[None]:
    handlers._pto_requests.clear()
    yield
    handlers._pto_requests.clear()


def _ctx_for(caller_employee_id: str) -> Context:
    """A Context carrying a caller-identity header, standing in for a real HTTP request.

    `mcp.call_tool` builds a context with no request at all when none is given, so
    `get_employee`'s caller check has nothing to read; this fakes only the one attribute
    (`request.headers`) that `server.py`'s `_caller_employee_id` actually touches. `session`/
    `lifespan_context` are required fields on `ServerRequestContext` but unused by that path.
    """
    request = SimpleNamespace(headers={"x-caller-employee-id": caller_employee_id})
    request_context = ServerRequestContext(
        session=None,  # ty: ignore[invalid-argument-type]
        lifespan_context={},
        protocol_version="2026-06-18",
        method="tools/call",
        request=request,
    )
    return Context(mcp_server=mcp, request_context=request_context)


def call(name: str, args: dict[str, Any], *, caller_employee_id: str = "E1002") -> dict[str, Any]:
    """Call a tool over the server's dispatch path; return its structured result.

    Defaults the caller identity to E1002 so existing self-only-safe call sites (payroll,
    idempotency, schema-rejection tests) don't each need to know about Module 6's auth check;
    tests of the check itself pass caller_employee_id explicitly.
    """
    result = asyncio.run(mcp.call_tool(name, args, context=_ctx_for(caller_employee_id)))
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


ISO_DATE_SCHEMA = {
    "type": "string",
    "pattern": r"^\d{4}-\d{2}-\d{2}$",
    "description": "ISO date YYYY-MM-DD.",
    "examples": ["2026-09-11"],
}


def test_iso_date_field_json_schema() -> None:
    # Pydantic (the framework's schema generator) turns the Field into this exact schema.
    assert TypeAdapter(IsoDate).json_schema() == ISO_DATE_SCHEMA


def test_iso_date_field_published_on_tool_input_schema() -> None:
    # The MCP layer adds only a title derived from the parameter name.
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    props = tools["submit_pto_request"].input_schema["properties"]
    assert props["start_date"] == {**ISO_DATE_SCHEMA, "title": "Start Date"}
    assert props["end_date"] == {**ISO_DATE_SCHEMA, "title": "End Date"}


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
    result = call("get_employee", {"employee_id": "E9999"}, caller_employee_id="E9999")
    assert result["status"] == "error"
    assert result["code"] == "not_found"


def test_get_employee_forbidden_over_dispatch() -> None:
    result = call("get_employee", {"employee_id": "E1002"}, caller_employee_id="E1001")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_pto_balance_success_over_dispatch() -> None:
    assert call("get_pto_balance", {"employee_id": "E1002"}) == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "pto_hours": 64.5,
        "sick_hours": 24.0,
    }


def test_get_pto_balance_forbidden_over_dispatch() -> None:
    result = call("get_pto_balance", {"employee_id": "E1002"}, caller_employee_id="E1001")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_payroll_run_success_for_payroll_role_over_dispatch() -> None:
    result = call("get_payroll_run", {"run_id": "PR-2026-09"}, caller_employee_id="E1003")
    assert result["status"] == "success"
    assert result["run_id"] == "PR-2026-09"


def test_get_payroll_run_forbidden_for_non_payroll_role_over_dispatch() -> None:
    result = call("get_payroll_run", {"run_id": "PR-2026-09"})  # default caller: E1002
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_employee_forbidden_with_no_context_at_all() -> None:
    # No context= passed: the real shape of a call with no transport-carried identity.
    result = asyncio.run(mcp.call_tool("get_employee", {"employee_id": "E1002"}))
    assert isinstance(result, CallToolResult)
    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["result"]["code"] == "forbidden"


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


def test_submit_pto_forbidden_over_dispatch() -> None:
    args = {
        "employee_id": "E1002",
        "start_date": "2026-09-11",
        "end_date": "2026-09-11",
        "idempotency_key": "k1",
    }
    result = call("submit_pto_request", args, caller_employee_id="E1001")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"
    assert not handlers._pto_requests


def test_responses_never_leak_sensitive_fields() -> None:
    result = call("get_employee", {"employee_id": "E1002"})
    assert not {"salary", "pto_hours", "manager"} & set(result)


def test_every_input_schema_forbids_additional_properties() -> None:
    # Published contract: clients (and model tool-calling) see that unknown keys are invalid.
    for tool in asyncio.run(mcp.list_tools()):
        assert tool.input_schema.get("additionalProperties") is False, tool.name


def test_unknown_argument_rejected_not_silently_dropped() -> None:
    # An undeclared field (here a smuggled `salary`) must fail loudly, not be dropped.
    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        asyncio.run(mcp.call_tool("get_employee", {"employee_id": "E1002", "salary": True}))


def test_misspelled_write_argument_creates_nothing() -> None:
    args = {
        "employee_id": "E1002",
        "start_date": "2026-09-11",
        "end_date": "2026-09-11",
        "idempotency_key": "k1",
        "end_dat": "2026-09-14",
    }
    with pytest.raises(ToolError, match="Extra inputs are not permitted"):
        asyncio.run(mcp.call_tool("submit_pto_request", args))
    assert not handlers._pto_requests
