"""Live model calls through the hand-rolled loop: trajectory first, wording loosely."""

import os
from typing import Any

import pytest

from scratch import react_from_scratch as rfs

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def require_gcp() -> None:
    if not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        pytest.skip("GOOGLE_CLOUD_PROJECT not set (see hr_agent/.env)")


@pytest.fixture
def traced(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Record (name, args) for every tool the loop executes."""
    calls: list[tuple[str, dict[str, Any]]] = []
    real = rfs.execute_tool

    def spy(name: str, args: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, args))
        return real(name, args)

    monkeypatch.setattr(rfs, "execute_tool", spy)
    return calls


def test_two_questions_in_one_message(traced: list[tuple[str, dict[str, Any]]]) -> None:
    stats = rfs.Stats()
    text = rfs.run("Is Christmas 2026 a holiday, and how much sick time does E1003 have?", stats)
    calls = dict(traced)
    assert calls.get("list_holidays") == {"year": 2026}
    assert calls.get("get_pto_balance") == {"employee_id": "E1003"}
    assert "christmas" in text.lower()
    assert "16" in text
    assert stats.tool_calls == 2
    assert stats.model_calls >= 2
    assert stats.prompt_tokens > 0


def test_unknown_id_error_relayed_without_crash(traced: list[tuple[str, dict[str, Any]]]) -> None:
    text = rfs.run("PTO for E9999", rfs.Stats())
    assert traced
    assert all(name == "get_pto_balance" for name, _ in traced)
    assert "E9999" in text


def test_missing_id_asks_instead_of_calling_tool(traced: list[tuple[str, dict[str, Any]]]) -> None:
    stats = rfs.Stats()
    text = rfs.run("What's my PTO?", stats)
    assert traced == []
    assert stats.model_calls == 1
    assert "id" in text.lower()
