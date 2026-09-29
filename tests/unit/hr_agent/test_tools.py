from google.adk.tools import ToolContext

from hr_agent.tools import CALLER_EMPLOYEE_ID_STATE_KEY, identify_caller, list_holidays


def test_list_holidays_success_sorted() -> None:
    result = list_holidays(2026)
    assert result["status"] == "success"
    assert result["year"] == 2026
    dates = [h["date"] for h in result["holidays"]]
    assert dates == sorted(dates)
    assert {"date": "2026-12-25", "name": "Christmas Day"} in result["holidays"]


def test_list_holidays_unknown_year_lists_available() -> None:
    result = list_holidays(1999)
    assert result["status"] == "error"
    assert "2026" in result["error"]


async def test_identify_caller_sets_state(tool_context: ToolContext) -> None:
    result = identify_caller("e1002", tool_context)
    assert result == {"status": "success", "caller_employee_id": "E1002"}
    assert tool_context.state[CALLER_EMPLOYEE_ID_STATE_KEY] == "E1002"


async def test_identify_caller_rejects_bad_format(tool_context: ToolContext) -> None:
    result = identify_caller("bob", tool_context)
    assert result["status"] == "error"
    assert CALLER_EMPLOYEE_ID_STATE_KEY not in tool_context.state


async def test_identify_caller_overwrites_previous_claim(tool_context: ToolContext) -> None:
    identify_caller("E1002", tool_context)
    identify_caller("E1003", tool_context)
    assert tool_context.state[CALLER_EMPLOYEE_ID_STATE_KEY] == "E1003"
