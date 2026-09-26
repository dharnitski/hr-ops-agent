"""MCP server wiring. Keep thin: logic lives in handlers.py."""

from mcp.server.mcpserver import MCPServer

from mcp_server.handlers import get_employee, get_payroll_run, submit_pto_request


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
