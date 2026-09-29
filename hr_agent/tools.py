"""Model-facing HR tools. Docstrings and type hints are the contract the model sees."""

from typing import Any

from mcp_server.mock_data import HOLIDAYS

# Session state key: the employee ID the conversation is currently about. Set by any tool
# that resolves or confirms one; read by agent instructions via `{current_employee_id?}`.
CURRENT_EMPLOYEE_ID_KEY = "current_employee_id"


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
