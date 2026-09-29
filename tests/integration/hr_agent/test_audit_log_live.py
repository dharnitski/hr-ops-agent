"""Live model + MCP calls: AuditLogPlugin (Module 6.3) is only wired onto hr_agent.agent.app,
not root_agent (see that module's comment on why) -- conftest.py's ask/conversation/sessions
fixtures build their Runner around root_agent directly, so they never exercise it. This test
runs app instead, against the real MCP server, to prove the plugin's MCP-wire-shape unwrapping
(hand-fabricated in tests/unit/hr_agent/test_audit.py) actually matches what a real
MCPTool.run_async result looks like."""

import logging

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from hr_agent.agent import app
from hr_agent.audit import AUDIT_LOGGER_NAME
from hr_agent.toolsets import CALLER_EMPLOYEE_ID_STATE_KEY

_CALLER_EMPLOYEE_ID = "E1002"


@pytest.fixture(autouse=True)
def _capture_audit_log(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=AUDIT_LOGGER_NAME)


async def test_pto_balance_lookup_is_audited_end_to_end(
    caplog: pytest.LogCaptureFixture,
) -> None:
    runner = InMemoryRunner(app=app, app_name="hr_agent_it")
    session = await runner.session_service.create_session(
        app_name="hr_agent_it",
        user_id="u1",
        state={CALLER_EMPLOYEE_ID_STATE_KEY: _CALLER_EMPLOYEE_ID},
    )
    message = types.Content(role="user", parts=[types.Part(text="How much PTO does E1002 have?")])
    async for _ in runner.run_async(user_id="u1", session_id=session.id, new_message=message):
        pass

    records = [r.msg for r in caplog.records if r.name == AUDIT_LOGGER_NAME]
    results = [r for r in records if isinstance(r, dict) and r.get("event") == "tool_result"]
    balance_calls = [r for r in results if r["tool"] == "get_pto_balance"]
    assert balance_calls, [r.get("tool") for r in results]
    record = balance_calls[0]
    assert record["caller_employee_id"] == _CALLER_EMPLOYEE_ID
    assert record["result"]["status"] == "success"
    assert record["result"]["employee_id"] == _CALLER_EMPLOYEE_ID
    # The sensitive figure the real handler returns must not have leaked into the audit log.
    assert "pto_hours" not in record["result"]
