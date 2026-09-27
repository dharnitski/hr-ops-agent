"""LangGraph router: routing functions and graph wiring with the model and agent faked."""

from types import SimpleNamespace
from typing import Any

import pytest

from scratch import langgraph_router as lgr


@pytest.mark.parametrize(
    ("message", "route"),
    [
        ("What's the carryover policy?", "policy"),
        ("What does the handbook say about expenses?", "policy"),
        ("Tell me a joke", "fallback"),
        ("How many PTO hours does E1001 have?", "fallback"),  # policy path only in this slice
    ],
)
def test_classify(message: str, route: str) -> None:
    assert lgr.classify({"message": message}) == {"route": route}


def test_pick_route_reads_state() -> None:
    assert lgr.pick_route({"route": "policy"}) == "policy"
    assert lgr.pick_route({"route": "fallback"}) == "fallback"


def test_fallback_answer() -> None:
    assert lgr.fallback({"message": "x"}) == {"answer": lgr.FALLBACK_TEXT}


class _FakeAgent:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(payload)
        return {"messages": [SimpleNamespace(text="from handbook")]}


@pytest.fixture
def fake_agent(monkeypatch: pytest.MonkeyPatch) -> _FakeAgent:
    agent = _FakeAgent()
    monkeypatch.setattr(lgr, "ChatGoogleGenerativeAI", lambda **_: object())
    monkeypatch.setattr(lgr, "create_agent", lambda *_, **__: agent)
    return agent


def test_policy_message_reaches_agent(fake_agent: _FakeAgent) -> None:
    out = lgr.build_graph().invoke({"message": "What's the carryover policy?"})
    assert out["route"] == "policy"
    assert out["answer"] == "from handbook"
    assert len(fake_agent.calls) == 1


def test_fallback_skips_agent(fake_agent: _FakeAgent) -> None:
    out = lgr.build_graph().invoke({"message": "Tell me a joke"})
    assert out["route"] == "fallback"
    assert out["answer"] == lgr.FALLBACK_TEXT
    assert fake_agent.calls == []
