"""Scratch space: ReAct loop built from scratch (no ADK) for learning purposes.

Not imported by production code, not covered by CI.

Run: uv run python -m scratch.react_from_scratch
"""

import functools
import os
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from hr_agent import tools as hr_tools
from hr_agent.config import DEFAULT_MODEL_ID
from mcp_server.mock_data import EMPLOYEES

load_dotenv(Path(__file__).parent.parent / "hr_agent" / ".env")

MAX_STEPS = 6
MODEL_ID = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)

# The ADK agent's own find_employee/get_pto_balance were retired in favor of MCP tools with a
# caller-identity check (Module 6) -- machinery this framework-free loop has no session to carry,
# so it keeps its own local copies against the same mock data instead of depending on a tool
# contract that now lives behind the MCP boundary. _session_state is this loop's stand-in for
# ADK session state (Module 4): a plain dict tracking which employee the conversation is about.
_session_state: dict[str, Any] = {}


def find_employee(name: str) -> dict[str, Any]:
    """Find employees by name to resolve an employee ID.

    Use when the user refers to an employee by name and you need their ID for another tool.
    Matching is case-insensitive and every word of the query must appear in the name, so
    "alice" matches all Alices and "alice nguyen" matches one. If more than one employee
    matches, do NOT choose: show the candidates and ask the user which one they mean.

    Args:
        name: Full or partial employee name, e.g. "Bob Smith" or "alice".

    Returns:
        {"status": "success", "matches": [{"employee_id", "name", "title"}]} for exactly one
        match; {"status": "ambiguous", "matches": [...]} for several; {"status": "error",
        "error": <reason>} for a blank name or no match (ask the user for the ID or a fuller name).
    """
    tokens = name.lower().split()
    if not tokens:
        return {"status": "error", "error": "Name is empty. Provide a full or partial name."}
    matches = [
        {"employee_id": employee_id, "name": e["name"], "title": e["title"]}
        for employee_id, e in EMPLOYEES.items()
        if all(t in e["name"].lower() for t in tokens)
    ]
    if not matches:
        return {
            "status": "error",
            "error": f"No employee found matching '{name}'. Ask for the employee ID.",
        }
    if len(matches) == 1:
        _session_state[hr_tools.CURRENT_EMPLOYEE_ID_KEY] = matches[0]["employee_id"]
        return {"status": "success", "matches": matches}
    return {"status": "ambiguous", "matches": matches}


def get_pto_balance(employee_id: str) -> dict[str, Any]:
    """Look up an employee's remaining PTO and sick-leave balance.

    Use when the user asks how much PTO, vacation, or sick time an employee has left.
    Requires an employee ID; if the user gave only a name, ask for the ID instead of guessing.

    Args:
        employee_id: Employee ID in the form "E" plus four digits, e.g. "E1002".

    Returns:
        On success: {"status": "success", "employee_id", "name", "pto_hours", "sick_hours"},
        with balances in hours. On failure: {"status": "error", "error": <reason>}.
    """
    normalized_id = employee_id.strip().upper()
    employee = EMPLOYEES.get(normalized_id)
    if employee is None:
        return {
            "status": "error",
            "error": f"No employee found with ID '{employee_id}'. IDs look like 'E1002'.",
        }
    _session_state[hr_tools.CURRENT_EMPLOYEE_ID_KEY] = normalized_id
    return {
        "status": "success",
        "employee_id": normalized_id,
        "name": employee["name"],
        "pto_hours": employee["pto_hours"],
        "sick_hours": employee["sick_hours"],
    }


INSTRUCTION = """\
You are an HR operations assistant with no memory beyond this conversation. Answer only from
tool results; never guess or infer an employee ID.

Rules:
- If the user gives a name, resolve it with find_employee. If it returns "ambiguous" or an
  error, ask the user to clarify or give the employee ID (format like E1002); never pick a
  candidate yourself.
- If a tool returns status "error", tell the user plainly what went wrong; do not retry with
  made-up input.
- If a question needs several lookups, make each one and answer every part.
- If the request is outside employee lookup, PTO/sick balances, and holidays, say you can't
  help with it.
"""

TOOLS = {fn.__name__: fn for fn in (find_employee, get_pto_balance, hr_tools.list_holidays)}

config = types.GenerateContentConfig(
    system_instruction=INSTRUCTION,
    tools=list(TOOLS.values()),
    # We run the loop; the SDK must not execute tool calls for us.
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


@functools.cache
def get_client() -> genai.Client:
    return genai.Client()  # lazy: importing this module must not need credentials


def generate(history: list[types.Content]) -> types.GenerateContentResponse:
    return get_client().models.generate_content(model=MODEL_ID, contents=history, config=config)


class Stats:
    def __init__(self) -> None:
        self.model_calls = 0
        self.tool_calls = 0
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.latencies: list[float] = []

    def summary(self) -> str:
        lat = ", ".join(f"{s:.1f}s" for s in self.latencies)
        return (
            f"model_calls={self.model_calls} tool_calls={self.tool_calls} "
            f"prompt_tokens={self.prompt_tokens} output_tokens={self.output_tokens} "
            f"latency=[{lat}]"
        )


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run one tool; every failure becomes an observation the model can read."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"status": "error", "error": f"Unknown tool '{name}'. Available: {sorted(TOOLS)}."}
    try:
        return fn(**args)
    except TypeError as e:
        return {"status": "error", "error": f"Bad arguments for {name}: {e}"}
    except Exception as e:  # tool bug: surface it, don't crash the loop
        return {"status": "error", "error": f"{name} failed: {type(e).__name__}: {e}"}


def run(user_message: str, stats: Stats) -> str:
    history: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=user_message)])
    ]
    for step in range(1, MAX_STEPS + 1):
        start = time.perf_counter()
        response = generate(history)
        stats.latencies.append(time.perf_counter() - start)
        stats.model_calls += 1
        if response.usage_metadata:
            stats.prompt_tokens += response.usage_metadata.prompt_token_count or 0
            stats.output_tokens += response.usage_metadata.candidates_token_count or 0

        if not response.candidates or response.candidates[0].content is None:
            return "Stopped: model returned no content."
        model_turn = response.candidates[0].content
        # Append unmodified: thought signatures must round-trip on Gemini 3.x.
        history.append(model_turn)

        calls = [p.function_call for p in (model_turn.parts or []) if p.function_call]
        if not calls:
            return response.text or ""

        # Parallel calls arrive in one turn; answer all of them in a single user turn.
        result_parts: list[types.Part] = []
        for call in calls:
            name = call.name or ""
            args = dict(call.args or {})
            result = execute_tool(name, args)
            stats.tool_calls += 1
            print(f"  [step {step}] {name}({args}) -> {result}")
            result_parts.append(
                types.Part.from_function_response(name=name, response={"result": result})
            )
        history.append(types.Content(role="user", parts=result_parts))

    return f"Stopped: no final answer after {MAX_STEPS} steps."


if __name__ == "__main__":
    prompts = [
        "Is Christmas 2026 a holiday, and how much sick time does E1003 have?",
        "PTO for E9999",
    ]
    for prompt in prompts:
        print(f"\n> {prompt}")
        stats = Stats()
        print(run(prompt, stats))
        print(f"  {stats.summary()}")
