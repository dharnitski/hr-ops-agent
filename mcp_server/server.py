"""MCP server wiring. Keep thin: logic lives in handlers.py."""

from mcp.server.mcpserver import Context, MCPServer

from mcp_server import handlers
from mcp_server.handlers import (
    EmployeeId,
    EmployeeResult,
    ErrorResult,
    IdempotencyKey,
    IsoDate,
    PayrollRunResult,
    PtoRequestResult,
    RunId,
)

# Carries the caller's own employee ID, set by the ADK-side header_provider
# (hr_agent/toolsets.py) from session state -- never read from a tool argument, so a model
# can't spoof it by passing a different employee_id.
CALLER_EMPLOYEE_ID_HEADER = "x-caller-employee-id"


def _caller_employee_id(ctx: Context) -> str | None:
    """The requesting session's own employee ID, from the transport.

    None when there's no request context at all (e.g. a direct `mcp.call_tool` with no
    `context=` passed) or the header is simply absent -- both mean "no identity established",
    not "trust the argument instead."
    """
    try:
        headers = ctx.headers
    except ValueError:
        return None
    if not headers:
        return None
    value = headers.get(CALLER_EMPLOYEE_ID_HEADER)
    return value if isinstance(value, str) else None


async def get_employee(employee_id: EmployeeId, ctx: Context) -> EmployeeResult | ErrorResult:
    """Look up the caller's own basic profile by employee ID.

    Self-service only: returns "forbidden" unless employee_id is the caller's own ID. Does
    not return pay, balances, or reporting lines.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".

    Returns:
        On success: {"status": "success", "employee_id", "name", "title"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found, forbidden.
    """
    return handlers.get_employee(employee_id, caller_employee_id=_caller_employee_id(ctx))


async def get_payroll_run(run_id: RunId, ctx: Context) -> PayrollRunResult | ErrorResult:
    """Look up a payroll run's summary by run ID. Read-only; aggregates only.

    Restricted to callers whose title is Payroll Specialist or Finance Director. Does not
    return per-employee pay. Use for questions about run status and timing.

    Args:
        run_id: Payroll run ID such as "PR-2026-09".

    Returns:
        On success: {"status": "success", "run_id", "period_start", "period_end",
        "pay_date", "run_status" ("draft" | "approved" | "paid"), "employee_count",
        "total_gross"}.
        On failure: {"status": "error", "code", "error"}; code is one of not_found, forbidden.
    """
    return handlers.get_payroll_run(run_id, caller_employee_id=_caller_employee_id(ctx))


async def submit_pto_request(
    employee_id: EmployeeId,
    start_date: IsoDate,
    end_date: IsoDate,
    idempotency_key: IdempotencyKey,
    ctx: Context,
) -> PtoRequestResult | ErrorResult:
    """Submit a PTO request for an employee. Creates a record; not instantly approved.

    Self-service only: returns "forbidden" unless employee_id is the caller's own ID.
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
        invalid_key, forbidden.
    """
    return handlers.submit_pto_request(
        employee_id,
        start_date,
        end_date,
        idempotency_key,
        caller_employee_id=_caller_employee_id(ctx),
    )


def _forbid_extra_arguments(server: MCPServer) -> None:
    """Reject arguments a tool does not declare, and publish `additionalProperties: false`.

    Why this matters: pydantic ignores unknown keys by default, so a model that misspells
    an argument (`end_dat`, `employe_id`) gets a silent success with that value dropped.
    For a write tool that means a request created with the wrong scope and no signal to
    the caller. Rejecting turns a silent wrong action into a loud, correctable error, and
    it stops clients from smuggling in fields (e.g. `salary`, `approve`) that a future
    handler change might start honoring.

    MCPServer has no public option for this, so we patch each tool's generated argument
    model. That touches private internals (`_tool_manager`); the tests in test_server.py
    fail if an mcp upgrade changes them, rather than silently loosening the contract.
    """
    for tool in server._tool_manager.list_tools():
        arg_model = tool.fn_metadata.arg_model
        arg_model.model_config["extra"] = "forbid"
        arg_model.model_rebuild(force=True)
        tool.parameters = arg_model.model_json_schema(by_alias=True)


mcp = MCPServer("hcm")
mcp.tool()(get_employee)
mcp.tool()(get_payroll_run)
mcp.tool()(submit_pto_request)
_forbid_extra_arguments(mcp)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
