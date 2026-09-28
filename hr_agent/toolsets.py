from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from .config import HCM_MCP_URL

# Params are shared; each toolset still opens its own MCP session (one extra connection per
# specialist is the price of independent tool_filters).
_hcm_connection = StreamableHTTPConnectionParams(url=HCM_MCP_URL)

# Session-state key for "which employee this session belongs to", set by whoever creates the
# session (test fixtures today; a real auth layer would set it post-login). Deliberately not
# current_employee_id: that key names the *subject* a conversation is currently about and
# changes turn to turn, while this names the *caller* and must not (Module 6).
CALLER_EMPLOYEE_ID_STATE_KEY = "caller_employee_id"
CALLER_EMPLOYEE_ID_HEADER = "x-caller-employee-id"


def _caller_headers(ctx: ReadonlyContext) -> dict[str, str]:
    """Turns the session's own identity into a header for the MCP server -- never a tool
    argument the model could pass a different value for.

    Unset state means the server sees no caller-identity header at all and fails closed
    (mcp_server/handlers.py's `forbidden`), not "trust employee_id instead."
    """
    caller_id = ctx.state.get(CALLER_EMPLOYEE_ID_STATE_KEY)
    return {CALLER_EMPLOYEE_ID_HEADER: caller_id} if caller_id else {}


hcm_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["get_employee", "submit_pto_request"],
    header_provider=_caller_headers,
)

# Read-only. tool_filter is a soft, in-process boundary; the hard one is server-side
# authorization (Module 6).
payroll_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["get_payroll_run"],
)
