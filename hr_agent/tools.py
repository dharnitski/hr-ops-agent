"""Model-facing HR tools. Docstrings and type hints are the contract the model sees."""

from typing import Any

from hr_agent.mock_data import EMPLOYEES, HOLIDAYS


def get_pto_balance(employee_id: str) -> dict[str, Any]:
    """Look up an employee's remaining PTO and sick-leave balance.

    Use when the user asks how much PTO, vacation, or sick time an employee has left.
    Requires an employee ID; if the user gave only a name, ask for the ID instead of guessing.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".

    Returns:
        On success: {"status": "success", "employee_id", "name", "pto_hours", "sick_hours"},
        with balances in hours. On failure: {"status": "error", "error": <reason>}.
    """
    normalized_id = employee_id.strip().upper()
    employee = EMPLOYEES.get(normalized_id)
    if employee is None:
        return {
            "status": "error",
            "error": f"No employee found with ID '{employee_id}'. IDs look like 'E1002'.",
        }
    return {
        "status": "success",
        "employee_id": normalized_id,
        "name": employee["name"],
        "pto_hours": employee["pto_hours"],
        "sick_hours": employee["sick_hours"],
    }


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
