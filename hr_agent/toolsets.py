import time

import google.auth.transport.requests
import google.oauth2.id_token
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from .config import HCM_MCP_AUDIENCE, HCM_MCP_URL

# Params are shared; each toolset still opens its own MCP session (one extra connection per
# specialist is the price of independent tool_filters).
_hcm_connection = StreamableHTTPConnectionParams(url=HCM_MCP_URL)

# Session-state key for "which employee this session belongs to", set by whoever creates the
# session (test fixtures today; a real auth layer would set it post-login). Deliberately not
# current_employee_id: that key names the *subject* a conversation is currently about and
# changes turn to turn, while this names the *caller* and must not (Module 6).
CALLER_EMPLOYEE_ID_STATE_KEY = "caller_employee_id"
CALLER_EMPLOYEE_ID_HEADER = "x-caller-employee-id"

# Google ID tokens from the metadata server are valid ~1h; refresh before that to avoid ever
# handing the MCP client an expired one. Keyed by audience even though this project only ever
# uses one, so the cache shape doesn't have to change if that stops being true.
_ID_TOKEN_REFRESH_SECONDS = 50 * 60
_id_token_cache: dict[str, tuple[str, float]] = {}


def _cached_id_token(audience: str) -> str:
    cached = _id_token_cache.get(audience)
    if cached is not None and time.monotonic() - cached[1] <= _ID_TOKEN_REFRESH_SECONDS:
        return cached[0]
    token = google.oauth2.id_token.fetch_id_token(
        google.auth.transport.requests.Request(), audience
    )
    if not isinstance(token, str):  # fetch_id_token is untyped; narrow before caching/returning.
        raise TypeError(f"fetch_id_token returned {type(token).__name__}, expected str")
    _id_token_cache[audience] = (token, time.monotonic())
    return token


def _caller_headers(ctx: ReadonlyContext) -> dict[str, str]:
    """Turns the session's own identity into a header for the MCP server -- never a tool
    argument the model could pass a different value for. Also attaches a Google ID token
    when HCM_MCP_AUDIENCE is configured, so Cloud Run's IAM invoker check (a separate,
    infra-level concern from caller identity) passes.

    Unset caller-identity state means the server sees no caller-identity header at all and
    fails closed (mcp_server/handlers.py's `forbidden`), not "trust employee_id instead." A
    failed ID-token fetch is left to raise -- swallowing it would trade a clear ADC error for
    a confusing 403 from Cloud Run.
    """
    headers: dict[str, str] = {}
    caller_id = ctx.state.get(CALLER_EMPLOYEE_ID_STATE_KEY)
    if caller_id:
        headers[CALLER_EMPLOYEE_ID_HEADER] = caller_id
    if HCM_MCP_AUDIENCE:
        headers["Authorization"] = f"Bearer {_cached_id_token(HCM_MCP_AUDIENCE)}"
    return headers


hcm_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["get_employee", "get_pto_balance"],
    header_provider=_caller_headers,
)

# Split from hcm_toolset because require_confirmation is a toolset-wide flag (McpToolset
# applies it to every tool it serves) -- reads must stay auto, so the one write tool needs its
# own toolset/session to carry the flag alone (Module 6.2). The pause itself (ADK's
# adk_request_confirmation flow) happens per-call regardless of session grouping.
pto_write_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["submit_pto_request"],
    header_provider=_caller_headers,
    require_confirmation=True,
)

# Read-only. tool_filter is a soft, in-process boundary; the hard one is server-side
# authorization -- a role check (Payroll Specialist/Finance Director) in mcp_server/handlers.py,
# using the same caller-identity header as hcm_toolset.
payroll_read_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["get_payroll_run"],
    header_provider=_caller_headers,
)

# Manager approval only (Module 6.2): require_confirmation pauses every call for human
# sign-off, same mechanism as pto_write_toolset above and split out for the same reason (the
# flag is toolset-wide). Server-side role check (Finance Director only, stricter than
# payroll_read_toolset's read access) is the hard boundary; confirmation is the added
# human-in-the-loop layer on top, not a replacement for it.
payroll_write_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["approve_payroll_run"],
    header_provider=_caller_headers,
    require_confirmation=True,
)
