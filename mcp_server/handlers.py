"""HCM tool handlers. Pure functions: no transport, so they test without a server."""

from typing import Any

# Temporary: reuses the agent's mock data. M2.3 moves the data into mcp_server/ and removes
# the agent's local tools; the agent must reach the server only over MCP.
from hr_agent.mock_data import EMPLOYEES


# The ID normalize/lookup/not-found logic below duplicates hr_agent/tools.py:get_pto_balance
# on purpose: sharing code across the MCP boundary would couple deploy and versioning. The
# agent-side copy goes away in M2.3. Once a second handler lands here (M2.2), extract a
# private _lookup(employee_id) within this module.
def get_employee(employee_id: str) -> dict[str, Any]:
    """Look up an employee's basic profile by employee ID.

    Use to confirm who an ID belongs to. Does not return pay, balances, or reporting lines.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".

    Returns:
        On success: {"status": "success", "employee_id", "name", "title"}.
        On failure: {"status": "error", "error": <reason>}.
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
        "title": employee["title"],
    }
