"""Model-facing HR tools. Docstrings and type hints are the contract the model sees."""

import re
from typing import Any

from google.adk.tools import ToolContext

from mcp_server.mock_data import HOLIDAYS

from .toolsets import CALLER_EMPLOYEE_ID_STATE_KEY

# Session state key: the employee ID the conversation is currently about. Set by any tool
# that resolves or confirms one; read by agent instructions via `{current_employee_id?}`.
CURRENT_EMPLOYEE_ID_KEY = "current_employee_id"

_EMPLOYEE_ID_PATTERN = re.compile(r"^E\d{4}$")


def list_holidays(year: int) -> dict[str, Any]:
    """List the company holidays for a calendar year.

    Use when the user asks which days are company holidays or whether a date is a holiday.

    Args:
        year: Four-digit calendar year, e.g. 2026.

    Returns:
        On success: {"status": "success", "year", "holidays": [{"date": "YYYY-MM-DD",
        "name": <holiday name>}, ...]} sorted by date. On failure: {"status": "error",
        "error": <reason>} listing the years that have data.
    """
    holidays = HOLIDAYS.get(year)
    if holidays is None:
        available = ", ".join(str(y) for y in sorted(HOLIDAYS))
        return {
            "status": "error",
            "error": f"No holiday data for {year}. Available years: {available}.",
        }
    return {
        "status": "success",
        "year": year,
        "holidays": [{"date": d, "name": n} for d, n in sorted(holidays.items())],
    }


def identify_caller(employee_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Records which employee this chat session is speaking as, from the user's own stated
    ID -- NOT real authentication. Use once per conversation, before any self-service or
    role-restricted tool, when no caller identity is established yet.

    This is a stand-in for a real login: a production deployment would set the caller's
    identity from a verified sign-in before the conversation starts, never from a tool call
    the model can be asked to make. Every self-only and role check (get_employee,
    get_pto_balance, submit_pto_request, get_payroll_run, approve_payroll_run) still runs
    unconditionally against whatever ID is set here -- this only answers "which identity is
    this session claiming", not "is that claim true".

    Args:
        employee_id: The employee ID this session claims to be, e.g. "E1002".

    Returns:
        On success: {"status": "success", "caller_employee_id": <normalized ID>}.
        On failure: {"status": "error", "error": <reason>} if the ID isn't the right shape.
    """
    normalized = employee_id.strip().upper()
    if not _EMPLOYEE_ID_PATTERN.match(normalized):
        return {
            "status": "error",
            "error": f"'{employee_id}' isn't a valid employee ID. Expected format: E1002.",
        }
    tool_context.state[CALLER_EMPLOYEE_ID_STATE_KEY] = normalized
    return {"status": "success", "caller_employee_id": normalized}
