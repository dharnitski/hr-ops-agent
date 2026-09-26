"""MCP server wiring. Keep thin: logic lives in handlers.py."""

from mcp.server.mcpserver import MCPServer

from mcp_server.handlers import get_employee, get_payroll_run, submit_pto_request

mcp = MCPServer("hcm")
mcp.tool()(get_employee)
mcp.tool()(get_payroll_run)
mcp.tool()(submit_pto_request)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
