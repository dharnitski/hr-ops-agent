"""Smallest ADK 2.x Workflow: two function nodes and one conditional route. No model call.

Run: uv run python scratch/workflow_probe.py
"""

import asyncio

from google.adk import Event
from google.adk.events import EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import Workflow


def classify(node_input: str) -> Event:
    """Emit a route based on the text; the route picks the outgoing edge."""
    route = "policy" if "policy" in node_input.lower() else "other"
    return Event(output=node_input, actions=EventActions(route=route))


def handle_policy(node_input: str) -> str:
    return f"policy path got: {node_input}"


def handle_other(node_input: str) -> str:
    return f"other path got: {node_input}"


probe = Workflow(
    name="probe",
    edges=[
        ("START", classify),
        (classify, {"policy": handle_policy, "other": handle_other}),
    ],
)


async def main() -> None:
    runner = Runner(app_name="probe", node=probe, session_service=InMemorySessionService())
    for msg in ("what is the carryover policy?", "hello"):
        events = await runner.run_debug(msg, session_id=msg, quiet=True)
        for e in events:
            print(msg, "->", e.node_info.path if e.node_info else None, e.output)


if __name__ == "__main__":
    asyncio.run(main())
