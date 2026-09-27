"""LangGraph rebuild of the router flow (policy path only) for the ADK comparison.

classify -> policy (ReAct agent over search_handbook) | fallback. Reuses the ADK router's
keyword rules, the policy instruction, and the handbook tool unchanged.
Run: uv run python -m scratch.langgraph_router
"""

from typing import Literal

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from hr_agent.agents.policy import INSTRUCTION
from hr_agent.config import MODEL_ID
from hr_agent.handbook import search_handbook
from scratch.workflow_router import RULES

FALLBACK_TEXT = "I can't help with that. I handle policy questions here."


class State(TypedDict, total=False):
    message: str
    route: Literal["policy", "fallback"]
    answer: str


def classify(state: State) -> State:
    """Only the policy rule applies in this slice; everything else falls back."""
    policy_rx = next(rx for name, rx in RULES if name == "policy")
    return {"route": "policy" if policy_rx.search(state["message"]) else "fallback"}


def pick_route(state: State) -> str:
    return state["route"]


def fallback(state: State) -> State:  # noqa: ARG001
    return {"answer": FALLBACK_TEXT}


def build_graph():  # noqa: ANN201
    # Vertex AI via ADC, same as the ADK agents (GOOGLE_CLOUD_PROJECT from the environment).
    model = ChatGoogleGenerativeAI(model=MODEL_ID, vertexai=True, location="global")
    policy_agent = create_agent(model, [search_handbook], system_prompt=INSTRUCTION)

    def policy(state: State) -> State:
        result = policy_agent.invoke({"messages": [HumanMessage(state["message"])]})
        return {"answer": result["messages"][-1].text}

    graph = StateGraph(State)  # ty: ignore[invalid-argument-type]
    graph.add_node("classify", classify)
    graph.add_node("policy", policy)
    graph.add_node("fallback", fallback)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify", pick_route, {"policy": "policy", "fallback": "fallback"}
    )
    graph.add_edge("policy", END)
    graph.add_edge("fallback", END)
    return graph.compile()


if __name__ == "__main__":
    app = build_graph()
    for msg in ("What's the carryover policy?", "Tell me a joke"):
        out = app.invoke({"message": msg})
        print(f"{msg!r}\n  route={out['route']}\n  final={out['answer']}\n")
