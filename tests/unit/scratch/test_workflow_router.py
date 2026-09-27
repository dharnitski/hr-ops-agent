"""Keyword routing rules and graph wiring of the Workflow router: no model calls."""

import pytest

from scratch import workflow_router as wr


@pytest.mark.parametrize(
    ("message", "route"),
    [
        ("How many PTO hours does E1001 have?", "pto"),
        ("Who is employee E1002?", "pto"),
        ("Which company holidays are in 2026?", "pto"),
        ("What's the carryover policy?", "policy"),
        ("What does the handbook say about remote work?", "policy"),
        ("Show me run PR-2026-09", "payroll"),
        ("When is the next pay date?", "payroll"),
        ("Tell me a joke", "fallback"),
        ("", "fallback"),
    ],
)
def test_classify_route(message: str, route: str) -> None:
    event = wr.classify(message)
    assert event.actions.route == route
    assert event.output == message


def test_policy_rule_wins_over_pto_keyword() -> None:
    """Rule order is a contract: 'PTO carryover policy' is a policy question."""
    assert wr.classify("What is the PTO carryover policy?").actions.route == "policy"


def test_first_match_wins_on_multi_intent() -> None:
    """Known limitation: mixed intent takes the first rule, not both."""
    assert wr.classify("What's the policy and my balance for E1001?").actions.route == "policy"


def test_rules_are_ordered_policy_payroll_pto() -> None:
    assert [name for name, _ in wr.RULES] == ["policy", "payroll", "pto"]


def test_decline_is_static() -> None:
    assert wr.decline("anything") == wr.decline("something else")


def test_single_turn_copies_without_mutating_original() -> None:
    copy = wr.single_turn(wr.pto_agent)
    assert copy.mode == "single_turn"
    assert copy.name == wr.pto_agent.name
    assert wr.pto_agent.mode != "single_turn"


def test_workflow_is_built() -> None:
    assert wr.workflow_router.name == "workflow_router"
