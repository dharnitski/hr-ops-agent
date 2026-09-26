"""HCM tool handlers. Pure functions: no transport, so they test without a server."""

from datetime import date, timedelta
from typing import Annotated, Any, Literal, TypedDict

from pydantic import Field

# Temporary: reuses the agent's mock data. M2.3 moves the data into mcp_server/ and removes
# the agent's local tools; the agent must reach the server only over MCP.
from hr_agent.mock_data import EMPLOYEES, HOLIDAYS, PAYROLL_RUNS

# Wire contract: Field constraints are enforced by the MCP layer before a handler runs, so
# malformed input is rejected at the boundary. Handlers still normalize and validate
# defensively (they are also called directly), so direct calls stay lenient.
EmployeeId = Annotated[
    str,
    Field(
        pattern=r"^E\d{4}$", description="Employee ID: 'E' plus four digits.", examples=["E1002"]
    ),
]
RunId = Annotated[
    str,
    Field(pattern=r"^PR-\d{4}-\d{2}$", description="Payroll run ID.", examples=["PR-2026-09"]),
]
IsoDate = Annotated[
    str,
    Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$", description="ISO date YYYY-MM-DD.", examples=["2026-09-11"]
    ),
]
IdempotencyKey = Annotated[
    str,
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description="Caller-chosen unique key; reuse only when retrying the same request.",
    ),
]

ErrorCode = Literal[
    "not_found",
    "invalid_dates",
    "insufficient_balance",
    "no_working_days",
    "idempotency_conflict",
    "invalid_key",
]


class ErrorResult(TypedDict):
    status: Literal["error"]
    code: ErrorCode
    error: str


class EmployeeResult(TypedDict):
    status: Literal["success"]
    employee_id: str
    name: str
    title: str


class PayrollRunResult(TypedDict):
    status: Literal["success"]
    run_id: str
    period_start: str
    period_end: str
    pay_date: str
    run_status: Literal["draft", "approved", "paid"]
    employee_count: int
    total_gross: float


class PtoRequestResult(TypedDict):
    status: Literal["success"]
    request_id: str
    employee_id: str
    start_date: str
    end_date: str
    hours: float
    request_status: Literal["pending"]
    replayed: bool


# The ID normalize/lookup/not-found logic below duplicates hr_agent/tools.py:get_pto_balance
# on purpose: sharing code across the MCP boundary would couple deploy and versioning. The
# agent-side copy goes away in M2.3. Once a second handler lands here (M2.2), extract a
# private _lookup(employee_id) within this module.
def get_employee(employee_id: EmployeeId) -> EmployeeResult | ErrorResult:
    """Look up an employee's basic profile by employee ID.

    Use to confirm who an ID belongs to. Does not return pay, balances, or reporting lines.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".

    Returns:
        On success: {"status": "success", "employee_id", "name", "title"}.
        On failure: {"status": "error", "error": <reason>}.
    """
    normalized_id, employee = _lookup(employee_id)
    if employee is None:
        return _not_found(employee_id)
    return {
        "status": "success",
        "employee_id": normalized_id,
        "name": employee["name"],
        "title": employee["title"],
    }


HOURS_PER_DAY = 8.0
LAST_WEEKDAY = 4  # Friday; date.weekday() is Monday=0.

# In-memory stand-in for the HCM write path: idempotency_key -> (arguments, stored result).
_pto_requests: dict[str, tuple[tuple[str, str, str], PtoRequestResult]] = {}


def _error(code: ErrorCode, message: str) -> ErrorResult:
    return {"status": "error", "code": code, "error": message}


def _lookup(employee_id: str) -> tuple[str, dict[str, Any] | None]:
    normalized_id = employee_id.strip().upper()
    return normalized_id, EMPLOYEES.get(normalized_id)


def _not_found(employee_id: str) -> ErrorResult:
    return _error(
        "not_found",
        f"No employee found with ID '{employee_id}'. IDs look like 'E1002'.",
    )


def get_payroll_run(run_id: RunId) -> PayrollRunResult | ErrorResult:
    """Look up a payroll run's summary by run ID. Read-only; aggregates only.

    Does not return per-employee pay. Use for questions about run status and timing.

    Args:
        run_id: Payroll run ID such as "PR-2026-09".

    Returns:
        On success: {"status": "success", "run_id", "period_start", "period_end",
        "pay_date", "run_status" ("draft" | "approved" | "paid"), "employee_count",
        "total_gross"}.
        On failure: {"status": "error", "code": "not_found", "error": <reason>}.
    """
    normalized_id = run_id.strip().upper()
    run = PAYROLL_RUNS.get(normalized_id)
    if run is None:
        known = ", ".join(sorted(PAYROLL_RUNS))
        return _error("not_found", f"No payroll run with ID '{run_id}'. Known runs: {known}.")
    return {
        "status": "success",
        "run_id": normalized_id,
        "period_start": run["period_start"],
        "period_end": run["period_end"],
        "pay_date": run["pay_date"],
        "run_status": run["status"],
        "employee_count": run["employee_count"],
        "total_gross": run["total_gross"],
    }


def _working_hours(start: date, end: date) -> float:
    holidays = HOLIDAYS.get(start.year, {}) | HOLIDAYS.get(end.year, {})
    days = (start + timedelta(n) for n in range((end - start).days + 1))
    return HOURS_PER_DAY * sum(
        1 for d in days if d.weekday() <= LAST_WEEKDAY and d.isoformat() not in holidays
    )


def _check_request(
    employee: dict[str, Any], start_text: str, end_text: str
) -> tuple[date, date, float] | ErrorResult:
    """Validate dates and balance. Returns (start, end, hours) or an error dict."""
    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except ValueError:
        return _error("invalid_dates", "Dates must be ISO format YYYY-MM-DD.")
    if end < start:
        return _error("invalid_dates", "end_date must not be before start_date.")
    hours = _working_hours(start, end)
    if hours == 0:
        return _error("no_working_days", "The range contains only weekends and holidays.")
    if hours > employee["pto_hours"]:
        return _error(
            "insufficient_balance",
            f"Request needs {hours:g}h but balance is {employee['pto_hours']:g}h.",
        )
    return start, end, hours


def submit_pto_request(
    employee_id: EmployeeId,
    start_date: IsoDate,
    end_date: IsoDate,
    idempotency_key: IdempotencyKey,
) -> PtoRequestResult | ErrorResult:
    """Submit a PTO request for an employee. Creates a record; not instantly approved.

    Hours are computed by the server: 8h per weekday, excluding company holidays. Does not
    reduce the balance. Safe to retry: repeating a call with the same idempotency_key and
    same arguments returns the original request ("replayed": true) and creates nothing new.

    Args:
        employee_id: Employee ID such as "E1002".
        start_date: First day off, ISO format YYYY-MM-DD.
        end_date: Last day off (inclusive), ISO format YYYY-MM-DD, not before start_date.
        idempotency_key: Caller-chosen unique string for this request; reuse it only when
            retrying the same request.

    Returns:
        On success: {"status": "success", "request_id", "employee_id", "start_date",
        "end_date", "hours", "request_status": "pending", "replayed"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found,
        invalid_dates, insufficient_balance, no_working_days, idempotency_conflict,
        invalid_key.
    """
    key = idempotency_key.strip()
    if not key:
        return _error("invalid_key", "idempotency_key must be a non-empty string.")

    normalized_id, employee = _lookup(employee_id)
    args = (normalized_id, start_date.strip(), end_date.strip())

    prior = _pto_requests.get(key)
    if prior is not None:
        if prior[0] != args:
            return _error(
                "idempotency_conflict",
                f"idempotency_key '{key}' was already used with different arguments. "
                "Use a new key for a new request.",
            )
        return {**prior[1], "replayed": True}

    if employee is None:
        return _not_found(employee_id)
    checked = _check_request(employee, args[1], args[2])
    if isinstance(checked, dict):
        return checked
    start, end, hours = checked

    result: PtoRequestResult = {
        "status": "success",
        "request_id": f"PTO-{len(_pto_requests) + 1:05d}",
        "employee_id": normalized_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hours": hours,
        "request_status": "pending",
        "replayed": False,
    }
    _pto_requests[key] = (args, result)
    return result
