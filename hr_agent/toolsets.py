from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from hr_agent.config import HCM_MCP_URL

# Only the PTO-related HCM tools; payroll stays unexposed until a read-only payroll agent
# (Module 3) and server-side authorization (Module 6) exist.
hcm_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(url=HCM_MCP_URL),
    tool_filter=["get_employee", "submit_pto_request"],
)
