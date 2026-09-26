import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents import Agent

from hr_agent.tools import find_employee, get_pto_balance, list_holidays

load_dotenv(Path(__file__).parent / ".env")

# Default keeps import working without secrets (unit tests, CI); override via MODEL_ID in .env.
# TODO: retest gemini-3.8-flash (slow on 2026-09-25; see .env.example)
DEFAULT_MODEL_ID = "gemini-3.5-flash-lite"

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
- If a request is outside your tools (e.g. salary, submitting requests), say you can't help
  with it.
"""

root_agent = Agent(
    name="hr_ops_agent",
    model=os.environ.get("MODEL_ID", DEFAULT_MODEL_ID),
    description="Answers HR questions about PTO/sick balances and company holidays.",
    instruction=INSTRUCTION,
    tools=[find_employee, get_pto_balance, list_holidays],
)
