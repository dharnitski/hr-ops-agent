"""HCM tool handlers. Pure functions: no transport, so they test without a server."""

import time
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
    "invalid_state",
    "forbidden",
    "rate_limited",
    "exceeds_limit",
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


class PtoBalanceResult(TypedDict):
    status: Literal["success"]
    employee_id: str
    name: str
    pto_hours: float
    sick_hours: float


class PayrollRunResult(TypedDict):
    status: Literal["success"]
    run_id: str
    period_start: str
    period_end: str
    pay_date: str
    run_status: Literal["draft", "approved", "paid"]
    employee_count: int
    total_gross: float


class PayrollApprovalResult(TypedDict):
    status: Literal["success"]
    run_id: str
    run_status: Literal["approved"]
    approved_by: str
    replayed: bool


class PtoRequestResult(TypedDict):
    status: Literal["success"]
    request_id: str
    employee_id: str
    start_date: str
    end_date: str
    hours: float
    request_status: Literal["pending"]
    replayed: bool


def get_employee(
    employee_id: EmployeeId, *, caller_employee_id: str | None
) -> EmployeeResult | ErrorResult:
    """Look up the caller's own basic profile by employee ID.

    Self-service only: returns "forbidden" unless employee_id is the caller's own ID. Does
    not return pay, balances, or reporting lines.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".
        caller_employee_id: The requesting session's own employee ID, established by the
            transport layer -- never a model-supplied argument (Module 6).

    Returns:
        On success: {"status": "success", "employee_id", "name", "title"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found, forbidden.
    """
    normalized_id, employee = _lookup(employee_id)
    normalized_caller = _normalize_id(caller_employee_id or "")
    if not normalized_caller or normalized_caller != normalized_id:
        return _forbidden(normalized_id)
    if employee is None:
        return _not_found(employee_id)
    return {
        "status": "success",
        "employee_id": normalized_id,
        "name": employee["name"],
        "title": employee["title"],
    }


def get_pto_balance(
    employee_id: EmployeeId, *, caller_employee_id: str | None
) -> PtoBalanceResult | ErrorResult:
    """Look up the caller's own remaining PTO and sick-leave balance.

    Self-service only: returns "forbidden" unless employee_id is the caller's own ID.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".
        caller_employee_id: The requesting session's own employee ID, established by the
            transport layer -- never a model-supplied argument (Module 6).

    Returns:
        On success: {"status": "success", "employee_id", "name", "pto_hours", "sick_hours"},
        with balances in hours. On failure: {"status": "error", "code", "error"}; code is one
        of not_found, forbidden.
    """
    normalized_id, employee = _lookup(employee_id)
    normalized_caller = _normalize_id(caller_employee_id or "")
    if not normalized_caller or normalized_caller != normalized_id:
        return _forbidden(normalized_id)
    if employee is None:
        return _not_found(employee_id)
    return {
        "status": "success",
        "employee_id": normalized_id,
        "name": employee["name"],
        "pto_hours": employee["pto_hours"],
        "sick_hours": employee["sick_hours"],
    }


HOURS_PER_DAY = 8.0
LAST_WEEKDAY = 4  # Friday; date.weekday() is Monday=0.

# Blast-radius limit (Module 6.4): the largest a single PTO request may be, regardless of
# balance or confirmation -- 20 working days, so one call can't book more than about a month
# even for an employee with a large balance. Complements RATE_LIMIT_* above, which bounds how
# OFTEN a caller writes, not how much any one write can do. approve_payroll_run has no
# equivalent: one call approves exactly one run, an already-bounded unit of work, so its
# blast-radius protection is the role gate, confirmation, and rate limit alone.
MAX_REQUEST_HOURS = 20 * HOURS_PER_DAY

# In-memory stand-in for the HCM write path: idempotency_key -> (arguments, stored result).
_pto_requests: dict[str, tuple[tuple[str, str, str], PtoRequestResult]] = {}


def _error(code: ErrorCode, message: str) -> ErrorResult:
    return {"status": "error", "code": code, "error": message}


def _normalize_id(value: str) -> str:
    """The ID normalization every handler applies before comparing or looking up: strip
    whitespace, uppercase. Shared so employee/run IDs and caller identity are always
    compared on the same terms (e.g. "e1002" vs "E1002" don't spuriously mismatch)."""
    return value.strip().upper()


def _lookup(employee_id: str) -> tuple[str, dict[str, Any] | None]:
    normalized_id = _normalize_id(employee_id)
    return normalized_id, EMPLOYEES.get(normalized_id)


def _not_found(employee_id: str) -> ErrorResult:
    return _error(
        "not_found",
        f"No employee found with ID '{employee_id}'. IDs look like 'E1002'.",
    )


def _forbidden(employee_id: str) -> ErrorResult:
    return _error(
        "forbidden",
        f"Not authorized to access employee '{employee_id}'. You may only access your own record.",
    )


# Rate limiting (Module 6.4): how OFTEN a caller may write, independent of whether any given
# call succeeds. Blast-radius limits (MAX_REQUEST_HOURS below) are the complementary bound on
# HOW MUCH a single call can do -- together they cap total damage even if identity (M6.1) and
# confirmation (M6.2) both pass, e.g. a compromised or scripted caller that auto-confirms.
#
# In-memory stand-in for a real limiter (Cloud Armor, a token-bucket service) in production
# (Module 7+): sliding window of recent call timestamps per (caller, tool). Every call attempt
# counts, including one that fails later validation or is rejected for role/state reasons --
# otherwise a caller could probe with malformed input for unlimited free attempts.
_write_call_times: dict[tuple[str, str], list[float]] = {}

RATE_LIMIT_WINDOW_SECONDS = 60.0
RATE_LIMIT_MAX_CALLS = 20


def _check_rate_limit(caller_id: str, tool_name: str) -> ErrorResult | None:
    now = time.monotonic()
    key = (caller_id, tool_name)
    window_start = now - RATE_LIMIT_WINDOW_SECONDS
    recent = [t for t in _write_call_times.get(key, []) if t > window_start]
    if len(recent) >= RATE_LIMIT_MAX_CALLS:
        _write_call_times[key] = recent
        return _error(
            "rate_limited",
            f"Too many {tool_name} calls from this caller ({RATE_LIMIT_MAX_CALLS} per "
            f"{int(RATE_LIMIT_WINDOW_SECONDS)}s). Wait and retry.",
        )
    recent.append(now)
    _write_call_times[key] = recent
    return None


# Titles authorized to read payroll run summaries. Role, not identity: unlike
# get_employee/submit_pto_request (self-only), any caller holding one of these titles may
# read any run -- there's no per-employee data to scope here, only who does payroll for a
# living. Sourced from EMPLOYEES["title"] since no separate role field exists yet.
PAYROLL_READER_TITLES = frozenset({"Payroll Specialist", "Finance Director"})


def get_payroll_run(
    run_id: RunId, *, caller_employee_id: str | None
) -> PayrollRunResult | ErrorResult:
    """Look up a payroll run's summary by run ID. Read-only; aggregates only.

    Restricted to callers whose title is Payroll Specialist or Finance Director. Does not
    return per-employee pay. Use for questions about run status and timing.

    Args:
        run_id: Payroll run ID such as "PR-2026-09".
        caller_employee_id: The requesting session's own employee ID, established by the
            transport layer -- never a model-supplied argument (Module 6).

    Returns:
        On success: {"status": "success", "run_id", "period_start", "period_end",
        "pay_date", "run_status" ("draft" | "approved" | "paid"), "employee_count",
        "total_gross"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found, forbidden.
    """
    _, caller = _lookup(caller_employee_id or "")
    if caller is None or caller["title"] not in PAYROLL_READER_TITLES:
        return _error(
            "forbidden",
            "Not authorized to view payroll run data. Requires the Payroll Specialist or "
            "Finance Director role.",
        )
    normalized_id = _normalize_id(run_id)
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


# Titles authorized to approve a payroll run -- a subset of PAYROLL_READER_TITLES, not the
# same set: separation of duties. A Payroll Specialist prepares/reads a run but only a Finance
# Director (the "manager" in "payroll needs manager approval") can approve it.
PAYROLL_APPROVER_TITLES = frozenset({"Finance Director"})

# In-memory stand-in for the HCM write path: idempotency_key -> (run_id, stored result).
_payroll_approvals: dict[str, tuple[str, PayrollApprovalResult]] = {}


def _check_approver_and_key(
    caller_employee_id: str | None, idempotency_key: str
) -> str | ErrorResult:
    """Role, key-format, and rate-limit checks that must run before the idempotency store or
    any run lookup is touched -- merged into one helper only to keep approve_payroll_run's
    return-statement count under the linter's limit, same as submit_pto_request's
    _check_caller_and_key. Returns the stripped key on success, or an error dict."""
    normalized_caller, caller = _lookup(caller_employee_id or "")
    if caller is None or caller["title"] not in PAYROLL_APPROVER_TITLES:
        return _error(
            "forbidden",
            "Not authorized to approve payroll runs. Requires the Finance Director role.",
        )
    key = idempotency_key.strip()
    if not key:
        return _error("invalid_key", "idempotency_key must be a non-empty string.")
    rate_limit_error = _check_rate_limit(normalized_caller, "approve_payroll_run")
    if rate_limit_error is not None:
        return rate_limit_error
    return key


def approve_payroll_run(
    run_id: RunId, idempotency_key: IdempotencyKey, *, caller_employee_id: str | None
) -> PayrollApprovalResult | ErrorResult:
    """Approve a payroll run, moving it from draft to approved.

    Restricted to callers whose title is Finance Director -- stricter than get_payroll_run's
    read access (also open to Payroll Specialist). Only a draft run can be approved; an
    already-approved or paid run returns invalid_state.

    Safe to retry: repeating a call with the same idempotency_key and run_id returns the
    original result ("replayed": true) and approves nothing twice.

    Args:
        run_id: Payroll run ID such as "PR-2026-09".
        idempotency_key: Caller-chosen unique string for this approval; reuse it only when
            retrying the same request.
        caller_employee_id: The requesting session's own employee ID, established by the
            transport -- never a model-supplied argument (Module 6).

    Returns:
        On success: {"status": "success", "run_id", "run_status": "approved", "approved_by",
        "replayed"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found,
        invalid_state, idempotency_conflict, invalid_key, forbidden, rate_limited.
    """
    checked = _check_approver_and_key(caller_employee_id, idempotency_key)
    if not isinstance(checked, str):
        return checked
    key = checked
    normalized_caller = _normalize_id(caller_employee_id or "")

    normalized_id = _normalize_id(run_id)
    prior = _payroll_approvals.get(key)
    if prior is not None:
        if prior[0] != normalized_id:
            return _error(
                "idempotency_conflict",
                f"idempotency_key '{key}' was already used with a different run_id. "
                "Use a new key for a new request.",
            )
        return {**prior[1], "replayed": True}

    run = PAYROLL_RUNS.get(normalized_id)
    if run is None:
        known = ", ".join(sorted(PAYROLL_RUNS))
        return _error("not_found", f"No payroll run with ID '{run_id}'. Known runs: {known}.")
    if run["status"] != "draft":
        return _error(
            "invalid_state",
            f"Run '{normalized_id}' is already '{run['status']}'; only a draft run can be "
            "approved.",
        )

    run["status"] = "approved"
    result: PayrollApprovalResult = {
        "status": "success",
        "run_id": normalized_id,
        "run_status": "approved",
        "approved_by": normalized_caller,
        "replayed": False,
    }
    _payroll_approvals[key] = (normalized_id, result)
    return result


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
    if hours > MAX_REQUEST_HOURS:
        return _error(
            "exceeds_limit",
            f"A single request may not exceed {MAX_REQUEST_HOURS:g}h; this one needs "
            f"{hours:g}h. Split it into smaller requests.",
        )
    if hours > employee["pto_hours"]:
        return _error(
            "insufficient_balance",
            f"Request needs {hours:g}h but balance is {employee['pto_hours']:g}h.",
        )
    return start, end, hours


def _check_caller_and_key(
    employee_id: str, caller_employee_id: str | None, idempotency_key: str
) -> str | ErrorResult:
    """Caller-identity, key-format, and rate-limit checks that must run before the idempotency
    store or any lookup is touched. Returns the stripped key on success, or an error dict.

    Merged into one helper (instead of separate guard clauses in submit_pto_request) only to
    keep that function's return-statement count under the linter's limit; the checks
    themselves are unrelated (identity vs. syntactic key validity vs. call volume) and would
    be separate ifs either way.
    """
    normalized_caller = _normalize_id(caller_employee_id or "")
    normalized_id = _normalize_id(employee_id)
    if not normalized_caller or normalized_caller != normalized_id:
        return _forbidden(normalized_id)
    key = idempotency_key.strip()
    if not key:
        return _error("invalid_key", "idempotency_key must be a non-empty string.")
    rate_limit_error = _check_rate_limit(normalized_caller, "submit_pto_request")
    if rate_limit_error is not None:
        return rate_limit_error
    return key


def submit_pto_request(
    employee_id: EmployeeId,
    start_date: IsoDate,
    end_date: IsoDate,
    idempotency_key: IdempotencyKey,
    *,
    caller_employee_id: str | None,
) -> PtoRequestResult | ErrorResult:
    """Submit a PTO request for an employee. Creates a record; not instantly approved.

    Self-service only: returns "forbidden" unless employee_id is the caller's own ID --
    checked first, before the idempotency store or any lookup, so an unauthorized caller can't
    probe either one for someone else's employee_id (manager-submits-for-a-report is Module
    6.2, not this check).

    Hours are computed by the server: 8h per weekday, excluding company holidays. Does not
    reduce the balance. A single request may not exceed 160h (20 working days); split a
    longer absence into multiple requests. Safe to retry: repeating a call with the same
    idempotency_key and same arguments returns the original request ("replayed": true) and
    creates nothing new.

    Args:
        employee_id: Employee ID such as "E1002".
        start_date: First day off, ISO format YYYY-MM-DD.
        end_date: Last day off (inclusive), ISO format YYYY-MM-DD, not before start_date.
        idempotency_key: Caller-chosen unique string for this request; reuse it only when
            retrying the same request.
        caller_employee_id: The requesting session's own employee ID, established by the
            transport -- never a model-supplied argument (Module 6).

    Returns:
        On success: {"status": "success", "request_id", "employee_id", "start_date",
        "end_date", "hours", "request_status": "pending", "replayed"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found,
        invalid_dates, insufficient_balance, no_working_days, exceeds_limit,
        idempotency_conflict, invalid_key, forbidden, rate_limited.
    """
    precheck = _check_caller_and_key(employee_id, caller_employee_id, idempotency_key)
    if not isinstance(precheck, str):
        return precheck
    key = precheck

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
    if not isinstance(checked, tuple):
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
