"""Pure routing logic of the Workflow probe: no model, no runner."""

from scratch import workflow_probe as probe


def test_classify_routes_policy_case_insensitively() -> None:
    event = probe.classify("What is the carryover POLICY?")
    assert event.actions.route == "policy"
    assert event.output == "What is the carryover POLICY?"


def test_classify_falls_to_other() -> None:
    assert probe.classify("hello").actions.route == "other"


def test_handlers_echo_input() -> None:
    assert probe.handle_policy("x") == "policy path got: x"
    assert probe.handle_other("x") == "other path got: x"
