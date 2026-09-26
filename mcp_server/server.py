"""MCP server wiring. Keep thin: logic lives in handlers.py."""

from mcp.server.mcpserver import MCPServer

from mcp_server.handlers import get_employee

mcp = MCPServer("hcm")
mcp.tool()(get_employee)


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
