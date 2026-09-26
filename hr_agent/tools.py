"""Model-facing HR tools. Docstrings and type hints are the contract the model sees."""

from typing import Any

from hr_agent.mock_data import EMPLOYEES, HOLIDAYS


# Temporary: mcp_server/handlers.py duplicates the ID lookup. These local tools are replaced
# by MCP equivalents in M2.3; do not share code across that boundary.
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


def find_employee(name: str) -> dict[str, Any]:
    """Find employees by name to resolve an employee ID.

    Use when the user refers to an employee by name and you need their ID for another tool.
    Matching is case-insensitive and every word of the query must appear in the name, so
    "alice" matches all Alices and "alice nguyen" matches one. If more than one employee
    matches, do NOT choose: show the candidates and ask the user which one they mean.

    Args:
        name: Full or partial employee name, e.g. "Bob Smith" or "alice".

    Returns:
        {"status": "success", "matches": [{"employee_id", "name", "title"}]} for exactly one
        match; {"status": "ambiguous", "matches": [...]} for several; {"status": "error",
        "error": <reason>} for a blank name or no match (ask the user for the ID or a fuller name).
    """
    # TODO(Module 6): no caller identity check; any user can enumerate employees by name.
    tokens = name.lower().split()
    if not tokens:
        return {"status": "error", "error": "Name is empty. Provide a full or partial name."}
    matches = [
        {"employee_id": employee_id, "name": e["name"], "title": e["title"]}
        for employee_id, e in EMPLOYEES.items()
        if all(t in e["name"].lower() for t in tokens)
    ]
    if not matches:
        return {
            "status": "error",
            "error": f"No employee found matching '{name}'. Ask for the employee ID.",
        }
    return {"status": "success" if len(matches) == 1 else "ambiguous", "matches": matches}
