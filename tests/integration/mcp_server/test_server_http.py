"""HCM server over real Streamable HTTP, black-box: no mcp_server imports, no model."""

import uuid
from typing import Any

import pytest
from mcp import Client
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

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


async def _call(
    name: str, args: dict[str, Any], *, caller_employee_id: str = "E1002"
) -> tuple[bool, dict[str, Any]]:
    """Calls over real HTTP with a caller-identity header, the same shape the ADK-side
    header_provider sends (hr_agent/toolsets.py) -- proves the Module 6 auth check works on
    the actual wire, not just through in-process dispatch. Defaults to E1002 so existing
    non-auth-focused cases below don't each need to know about it.
    """
    http_client = create_mcp_http_client(headers={"x-caller-employee-id": caller_employee_id})
    async with Client(streamable_http_client(URL, http_client=http_client)) as client:
        result = await client.call_tool(name, args)
    return result.is_error, result.structured_content or {}


async def test_lists_exactly_the_hcm_tools_with_output_schemas() -> None:
    async with Client(URL) as client:
        tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == {
        "get_employee",
        "get_pto_balance",
        "get_payroll_run",
        "approve_payroll_run",
        "submit_pto_request",
    }
    assert all(t.output_schema for t in tools)


async def test_success_and_error_results_are_wrapped_in_result() -> None:
    is_error, ok = await _call("get_employee", {"employee_id": "E1002"})
    assert not is_error
    assert ok["result"]["status"] == "success"
    assert ok["result"]["name"] == "Bob Smith"

    is_error, missing = await _call(
        "get_employee", {"employee_id": "E9999"}, caller_employee_id="E9999"
    )
    assert not is_error  # business errors are data, not protocol errors
    assert missing["result"]["code"] == "not_found"


async def test_get_employee_forbidden_for_someone_elses_id_over_http() -> None:
    is_error, result = await _call(
        "get_employee", {"employee_id": "E1002"}, caller_employee_id="E1001"
    )
    assert not is_error
    assert result["result"]["code"] == "forbidden"


async def test_get_employee_forbidden_with_no_caller_header_over_http() -> None:
    async with Client(URL) as client:  # no custom headers at all
        result = await client.call_tool("get_employee", {"employee_id": "E1002"})
    assert not result.is_error
    assert result.structured_content is not None
    assert result.structured_content["result"]["code"] == "forbidden"


async def test_get_pto_balance_forbidden_for_someone_elses_id_over_http() -> None:
    is_error, result = await _call(
        "get_pto_balance", {"employee_id": "E1002"}, caller_employee_id="E1001"
    )
    assert not is_error
    assert result["result"]["code"] == "forbidden"


async def test_get_pto_balance_succeeds_for_own_id_over_http() -> None:
    is_error, result = await _call("get_pto_balance", {"employee_id": "E1002"})
    assert not is_error
    assert result["result"]["status"] == "success"
    assert result["result"]["pto_hours"] == 64.5


async def test_get_payroll_run_succeeds_for_payroll_role_over_http() -> None:
    is_error, result = await _call(
        "get_payroll_run", {"run_id": "PR-2026-09"}, caller_employee_id="E1003"
    )
    assert not is_error
    assert result["result"]["status"] == "success"


async def test_get_payroll_run_forbidden_for_non_payroll_role_over_http() -> None:
    is_error, result = await _call("get_payroll_run", {"run_id": "PR-2026-09"})  # E1002 default
    assert not is_error
    assert result["result"]["code"] == "forbidden"


async def test_approve_payroll_run_forbidden_for_payroll_specialist_over_http() -> None:
    # Carla Gomez (E1003) is a Payroll Specialist -- can read runs but not approve them.
    is_error, result = await _call(
        "approve_payroll_run",
        {"run_id": "PR-2026-08", "idempotency_key": f"it-{uuid.uuid4()}"},
        caller_employee_id="E1003",
    )
    assert not is_error
    assert result["result"]["code"] == "forbidden"


async def test_approve_payroll_run_already_paid_is_invalid_state_over_http() -> None:
    # PR-2026-08 starts "paid" in mock data and never changes status in this suite.
    is_error, result = await _call(
        "approve_payroll_run",
        {"run_id": "PR-2026-08", "idempotency_key": f"it-{uuid.uuid4()}"},
        caller_employee_id="E1004",
    )
    assert not is_error
    assert result["result"]["code"] == "invalid_state"


async def test_approve_payroll_run_succeeds_and_replays_over_http() -> None:
    # The only test in this file that mutates PR-2026-09's status (draft -> approved) --
    # safe because no other test here asserts that run's status.
    args = {"run_id": "PR-2026-09", "idempotency_key": f"it-{uuid.uuid4()}"}
    is_error, first = await _call("approve_payroll_run", args, caller_employee_id="E1004")
    assert not is_error
    assert first["result"]["status"] == "success"
    assert first["result"]["run_status"] == "approved"
    assert first["result"]["replayed"] is False

    is_error, second = await _call("approve_payroll_run", args, caller_employee_id="E1004")
    assert not is_error
    assert second["result"]["replayed"] is True


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


async def test_submit_pto_forbidden_for_someone_elses_id_over_http() -> None:
    is_error, result = await _call("submit_pto_request", _pto_args(), caller_employee_id="E1001")
    assert not is_error
    assert result["result"]["code"] == "forbidden"


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
