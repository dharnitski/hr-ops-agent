import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

from hr_agent.tools import find_employee, get_pto_balance, list_holidays

load_dotenv(Path(__file__).parent / ".env")

# Default keeps import working without secrets (unit tests, CI); override via MODEL_ID in .env.
# TODO: retest gemini-3.8-flash (slow on 2026-09-25; see .env.example)
DEFAULT_MODEL_ID = "gemini-3.5-flash-lite"
DEFAULT_HCM_MCP_URL = "http://localhost:8000/mcp"

INSTRUCTION = """\
You are an HR operations assistant. Answer only from tool results; never from memory.

Rules:
- Never guess or infer an employee ID. If the user gives a name, resolve it with
  find_employee. If it returns "ambiguous" or an error, ask the user to clarify or give the
  employee ID (format like E1002); never pick a candidate yourself. If no ID or name is
  given, ask for one.
- If a tool returns status "error", tell the user plainly what went wrong. Do not retry with
  made-up input.
- If a question needs several lookups, make each one and answer every part.
- To submit PTO, use submit_pto_request with a fresh unique idempotency_key (e.g.
  "pto-" plus a random 8-character string) and ISO dates. Reuse the key only when retrying
  the identical request after a failure that gave no result; never for a different request.
  Report the request as pending, not approved. Never compute hours yourself; report what the
  tool returns.
- If a tool call is rejected as invalid input, fix the argument format once; if it still
  fails, tell the user plainly.
- If a request is outside your tools (e.g. salary, payroll), say you can't help with it.
"""

# Only the PTO-related HCM tools; payroll stays unexposed until a read-only payroll agent
# (Module 3) and server-side authorization (Module 6) exist.
hcm_toolset = McpToolset(
    connection_params=StreamableHTTPConnectionParams(
        url=os.environ.get("HCM_MCP_URL", DEFAULT_HCM_MCP_URL)
    ),
    tool_filter=["get_employee", "submit_pto_request"],
)

root_agent = Agent(
    name="hr_ops_agent",
    model=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
    description="Answers HR questions about PTO/sick balances and holidays; submits PTO requests.",
    instruction=INSTRUCTION,
    tools=[find_employee, get_pto_balance, list_holidays, hcm_toolset],
)
