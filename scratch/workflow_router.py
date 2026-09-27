"""Deterministic Workflow router over the existing specialists (keyword rules, no router LLM call).

Compare with the LLM router in hr_agent/agent.py. PTO/payroll prompts need the MCP server:
  uv run python -m mcp_server.server   (port 8000)
Run: uv run python scratch/workflow_router.py
"""

import asyncio
import re

from google.adk import Event
from google.adk.agents import Agent
from google.adk.events import EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.workflow import Workflow

from hr_agent.agents.payroll import payroll_agent
from hr_agent.agents.policy import policy_agent
from hr_agent.agents.pto import pto_agent

# Order matters: first match wins. Policy before pto so "carryover policy" isn't a PTO lookup.
RULES = [
    ("policy", re.compile(r"\b(policy|handbook|carry ?over|accrual|remote work|reimburse)", re.I)),
    ("payroll", re.compile(r"\b(payroll|PR-\d{4}-\d{2}|pay date|gross)", re.I)),
    ("pto", re.compile(r"\b(pto|sick|holiday|vacation|time off|E\d{4})", re.I)),
]


def classify(node_input: str) -> Event:
    route = next((name for name, rx in RULES if rx.search(node_input)), "fallback")
    return Event(output=node_input, actions=EventActions(route=route))


def decline(node_input: str) -> str:  # noqa: ARG001
    return "I can't help with that. I handle PTO, payroll runs, and HR policy questions."


def single_turn(agent: Agent) -> Agent:
    return agent.model_copy(update={"mode": "single_turn"})


workflow_router = Workflow(
    name="workflow_router",
    edges=[
        ("START", classify),
        (
            classify,
            {
                "pto": single_turn(pto_agent),
                "payroll": single_turn(payroll_agent),
                "policy": single_turn(policy_agent),
                "fallback": decline,
            },
        ),
    ],
)

PROMPTS = [
    "How many PTO hours does E1001 have?",
    "What's the carryover policy?",
    "Who is employee E1002?",
    "Tell me a joke",
]


async def main() -> None:
    runner = Runner(
        app_name="workflow_router", node=workflow_router, session_service=InMemorySessionService()
    )
    for msg in PROMPTS:
        events = await runner.run_debug(msg, session_id=msg, quiet=True)
        route = next((e.actions.route for e in events if e.actions and e.actions.route), None)
        final = [e for e in events if e.output is not None or e.content][-1]
        parts = final.content.parts if final.content and final.content.parts else []
        out = final.output if final.output is not None else (parts[0].text if parts else None)
        print(f"{msg!r}\n  route={route}\n  final={out}\n")


if __name__ == "__main__":
    asyncio.run(main())
