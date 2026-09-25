"""Live model calls: assert on tool trajectory first, wording only loosely."""

import pytest

pytestmark = pytest.mark.integration


async def test_pto_for_known_id(ask):
    turn = await ask("How much PTO does E1002 have?")
    assert turn.tool_calls == [("get_pto_balance", {"employee_id": "E1002"})]
    assert "64.5" in turn.text


async def test_missing_id_asks_instead_of_calling_tool(ask):
    turn = await ask("What's my PTO?")
    assert turn.tool_calls == []
    assert "id" in turn.text.lower()


async def test_unknown_id_reports_error_without_retrying(ask):
    turn = await ask("PTO for E9999")
    assert turn.tool_calls
    assert all(name == "get_pto_balance" for name, _ in turn.tool_calls)
    assert all(args["employee_id"] == "E9999" for _, args in turn.tool_calls)
    assert "E9999" in turn.text


async def test_name_instead_of_id_does_not_guess(ask):
    turn = await ask("PTO for Bob Smith")
    assert turn.tool_calls == []
    assert "id" in turn.text.lower()


async def test_two_questions_in_one_message(ask):
    turn = await ask("Is Christmas 2026 a holiday, and how much sick time does E1003 have?")
    calls = {name: args for name, args in turn.tool_calls}
    assert calls.get("list_holidays") == {"year": 2026}
    assert calls.get("get_pto_balance") == {"employee_id": "E1003"}
    assert "christmas" in turn.text.lower()
    assert "16" in turn.text
