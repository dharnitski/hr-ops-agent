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

from hr_agent.agent import DEFAULT_MODEL_ID, INSTRUCTION
from hr_agent.tools import find_employee, get_pto_balance, list_holidays

load_dotenv(Path(__file__).parent.parent / "hr_agent" / ".env")

MAX_STEPS = 6
MODEL_ID = os.environ.get("MODEL_ID", DEFAULT_MODEL_ID)
TOOLS = {fn.__name__: fn for fn in (find_employee, get_pto_balance, list_holidays)}

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
