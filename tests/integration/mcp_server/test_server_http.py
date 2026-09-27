"""HCM server over real Streamable HTTP, black-box: no mcp_server imports, no model."""

import uuid
from typing import Any

import pytest
from mcp import Client

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("hcm_server")]

URL = "http://localhost:8000/mcp"


def _pto_args(**overrides: str) -> dict[str, str]:
    return {
        "employee_id": "E1002",
        "start_date": "2026-10-12",
        "end_date": "2026-10-14",
        "idempotency_key": f"it-{uuid.uuid4()}",
        **overrides,
    }


async def _call(name: str, args: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    async with Client(URL) as client:
        result = await client.call_tool(name, args)
    return result.is_error, result.structured_content or {}


async def test_lists_exactly_the_hcm_tools_with_output_schemas() -> None:
    async with Client(URL) as client:
        tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == {"get_employee", "get_payroll_run", "submit_pto_request"}
    assert all(t.output_schema for t in tools)


async def test_success_and_error_results_are_wrapped_in_result() -> None:
    is_error, ok = await _call("get_employee", {"employee_id": "E1002"})
    assert not is_error
    assert ok["result"]["status"] == "success"
    assert ok["result"]["name"] == "Bob Smith"

    is_error, missing = await _call("get_employee", {"employee_id": "E9999"})
    assert not is_error  # business errors are data, not protocol errors
    assert missing["result"]["code"] == "not_found"


async def test_retry_with_same_key_replays_over_http() -> None:
    args = _pto_args()
    _, first = await _call("submit_pto_request", args)
    _, second = await _call("submit_pto_request", args)
    assert first["result"]["replayed"] is False
    assert second["result"]["replayed"] is True
    assert second["result"]["request_id"] == first["result"]["request_id"]


async def test_same_key_different_args_conflicts() -> None:
    args = _pto_args()
    await _call("submit_pto_request", args)
    is_error, conflict = await _call("submit_pto_request", {**args, "end_date": "2026-10-15"})
    assert not is_error
    assert conflict["result"]["code"] == "idempotency_conflict"


async def test_malformed_input_is_rejected_and_creates_nothing() -> None:
    args = _pto_args(employee_id="bob")
    is_error, _ = await _call("submit_pto_request", args)
    assert is_error
    # The key was not consumed: a valid request with the same key succeeds as new.
    is_error, fresh = await _call("submit_pto_request", {**args, "employee_id": "E1002"})
    assert not is_error
    assert fresh["result"]["replayed"] is False


async def test_unknown_argument_is_rejected() -> None:
    is_error, _ = await _call("get_employee", {"employee_id": "E1002", "salary": True})
    assert is_error
