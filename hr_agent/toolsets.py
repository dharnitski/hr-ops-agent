from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from .config import HCM_MCP_URL

# Params are shared; each toolset still opens its own MCP session (one extra connection per
# specialist is the price of independent tool_filters).
_hcm_connection = StreamableHTTPConnectionParams(url=HCM_MCP_URL)

hcm_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["get_employee", "submit_pto_request"],
)

# Read-only. tool_filter is a soft, in-process boundary; the hard one is server-side
# authorization (Module 6).
payroll_toolset = McpToolset(
    connection_params=_hcm_connection,
    tool_filter=["get_payroll_run"],
)
