"""AuditLogPlugin (Module 6.3): one structured record per tool call, redacted to an allowlist
of safe fields -- never the sensitive values a call returns (balances, totals, free-text
error messages that can embed them). Uses caplog rather than mocking the logger: the actual
emitted record, not just "a log call happened", is what these tests need to check."""

import logging
from dataclasses import dataclass
from typing import Any, cast

import pytest
from google.adk.tools import ToolContext

from hr_agent.audit import AUDIT_LOGGER_NAME, AuditLogPlugin, _unwrap_tool_result
from hr_agent.toolsets import CALLER_EMPLOYEE_ID_STATE_KEY


@dataclass
class _FakeTool:
    name: str


def _mcp_success(result: dict[str, Any]) -> dict[str, Any]:
    return {"isError": False, "structuredContent": {"result": result}}


def _last_record(caplog: pytest.LogCaptureFixture) -> dict[str, Any]:
    # LogRecord.msg is typed str in typeshed even though logging never enforces that at
    # runtime; AuditLogPlugin passes a dict, so the cast reflects what's actually there.
    return cast(dict[str, Any], caplog.records[0].msg)


@pytest.fixture(autouse=True)
def _capture_audit_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER_NAME)


@pytest.fixture
def plugin() -> AuditLogPlugin:
    return AuditLogPlugin()


async def test_before_tool_callback_does_not_override_the_call(
    plugin: AuditLogPlugin, tool_context: ToolContext
) -> None:
    result = await plugin.before_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={"employee_id": "E1002"},
        tool_context=tool_context,
    )
    assert result is None


async def test_before_tool_callback_logs_tool_and_agent(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    await plugin.before_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={"employee_id": "E1002"},
        tool_context=tool_context,
    )
    record = _last_record(caplog)
    assert record["event"] == "tool_call"
    assert record["tool"] == "get_employee"
    assert record["agent"] == "test_agent"
    assert record["args"] == {"employee_id": "E1002"}


async def test_caller_employee_id_read_from_session_state(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    tool_context.state[CALLER_EMPLOYEE_ID_STATE_KEY] = "E1002"
    await plugin.before_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={},
        tool_context=tool_context,
    )
    assert _last_record(caplog)["caller_employee_id"] == "E1002"


async def test_missing_caller_identity_logs_as_none(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    await plugin.before_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={},
        tool_context=tool_context,
    )
    assert _last_record(caplog)["caller_employee_id"] is None


async def test_args_are_redacted_to_the_allowlist(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    await plugin.before_tool_callback(
        tool=_FakeTool("submit_pto_request"),  # ty: ignore[invalid-argument-type]
        tool_args={
            "employee_id": "E1002",
            "start_date": "2026-10-12",
            "end_date": "2026-10-14",
            "idempotency_key": "k1",
            "some_future_field": "should not appear",
        },
        tool_context=tool_context,
    )
    assert _last_record(caplog)["args"] == {
        "employee_id": "E1002",
        "start_date": "2026-10-12",
        "end_date": "2026-10-14",
        "idempotency_key": "k1",
    }


async def test_mcp_success_result_is_unwrapped_and_redacted(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    response = _mcp_success(
        {"status": "success", "employee_id": "E1002", "name": "Bob Smith", "title": "Engineer"}
    )
    await plugin.after_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={"employee_id": "E1002"},
        tool_context=tool_context,
        result=response,
    )
    result = _last_record(caplog)["result"]
    assert result == {"status": "success", "employee_id": "E1002"}
    assert "name" not in result
    assert "title" not in result


async def test_business_error_keeps_code_drops_message_text(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    # The message can embed a sensitive figure (e.g. "Request needs 16h but balance is 8h.").
    response = _mcp_success(
        {
            "status": "error",
            "code": "insufficient_balance",
            "error": "Request needs 16h but balance is 8h.",
        }
    )
    await plugin.after_tool_callback(
        tool=_FakeTool("submit_pto_request"),  # ty: ignore[invalid-argument-type]
        tool_args={},
        tool_context=tool_context,
        result=response,
    )
    result = _last_record(caplog)["result"]
    assert result == {"status": "error", "code": "insufficient_balance"}
    assert "error" not in result


async def test_schema_rejection_has_no_result_to_unwrap(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    await plugin.after_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={},
        tool_context=tool_context,
        result={"isError": True},
    )
    assert "result" not in _last_record(caplog)


def test_local_tool_plain_result_passes_through_unwrap() -> None:
    unwrapped = _unwrap_tool_result({"status": "success", "year": 2026, "holidays": []})
    assert unwrapped == {"status": "success", "year": 2026, "holidays": []}


async def test_confirmation_pause_result_leaks_nothing_sensitive(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    # ADK's own pause/reject shape for a require_confirmation tool: no "status"/"code", so it
    # passes through _unwrap_tool_result unchanged, then gets redacted like any other dict.
    await plugin.after_tool_callback(
        tool=_FakeTool("submit_pto_request"),  # ty: ignore[invalid-argument-type]
        tool_args={},
        tool_context=tool_context,
        result={"error": "This tool call requires confirmation, please approve or reject."},
    )
    result = _last_record(caplog)["result"]
    assert result == {}


async def test_on_tool_error_logs_exception_type_not_message(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    await plugin.on_tool_error_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={"employee_id": "E1002"},
        tool_context=tool_context,
        error=ValueError("some possibly sensitive detail"),
    )
    record = _last_record(caplog)
    assert record["event"] == "tool_error"
    assert record["error"] == "ValueError"
    assert "some possibly sensitive detail" not in str(record)


async def test_record_includes_invocation_and_session_ids(
    plugin: AuditLogPlugin, tool_context: ToolContext, caplog: pytest.LogCaptureFixture
) -> None:
    await plugin.before_tool_callback(
        tool=_FakeTool("get_employee"),  # ty: ignore[invalid-argument-type]
        tool_args={},
        tool_context=tool_context,
    )
    record = _last_record(caplog)
    assert record["invocation_id"] == "test-invocation"
    assert record["session_id"]
    assert record["timestamp"]
