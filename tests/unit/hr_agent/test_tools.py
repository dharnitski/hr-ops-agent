from google.adk.tools import ToolContext

from hr_agent.tools import CURRENT_EMPLOYEE_ID_KEY, find_employee, get_pto_balance, list_holidays


async def test_get_pto_balance_success(tool_context: ToolContext) -> None:
    result = get_pto_balance("E1002", tool_context)
    assert result == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "pto_hours": 64.5,
        "sick_hours": 24.0,
    }


async def test_get_pto_balance_normalizes_id(tool_context: ToolContext) -> None:
    result = get_pto_balance(" e1002 ", tool_context)
    assert result["status"] == "success"
    assert result["employee_id"] == "E1002"


async def test_get_pto_balance_zero_balance_is_success(tool_context: ToolContext) -> None:
    result = get_pto_balance("E1003", tool_context)
    assert result["status"] == "success"
    assert result["pto_hours"] == 0.0


async def test_get_pto_balance_unknown_id_returns_error_not_exception(
    tool_context: ToolContext,
) -> None:
    result = get_pto_balance("E9999", tool_context)
    assert result["status"] == "error"
    assert "E9999" in result["error"]


async def test_get_pto_balance_name_instead_of_id_is_error(tool_context: ToolContext) -> None:
    assert get_pto_balance("Bob Smith", tool_context)["status"] == "error"


async def test_get_pto_balance_success_sets_current_employee(tool_context: ToolContext) -> None:
    get_pto_balance("E1002", tool_context)
    assert tool_context.state[CURRENT_EMPLOYEE_ID_KEY] == "E1002"


async def test_get_pto_balance_error_does_not_set_current_employee(
    tool_context: ToolContext,
) -> None:
    get_pto_balance("E9999", tool_context)
    assert CURRENT_EMPLOYEE_ID_KEY not in tool_context.state


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


async def test_find_employee_single_match_returns_minimal_fields(
    tool_context: ToolContext,
) -> None:
    assert find_employee("Bob Smith", tool_context) == {
        "status": "success",
        "matches": [{"employee_id": "E1002", "name": "Bob Smith", "title": "Software Engineer"}],
    }


async def test_find_employee_multiple_matches_is_ambiguous(tool_context: ToolContext) -> None:
    result = find_employee("alice", tool_context)
    assert result["status"] == "ambiguous"
    assert {m["employee_id"] for m in result["matches"]} == {"E1001", "E1005"}


async def test_find_employee_full_name_disambiguates(tool_context: ToolContext) -> None:
    result = find_employee("alice nguyen", tool_context)
    assert result["status"] == "success"
    assert result["matches"][0]["employee_id"] == "E1005"


async def test_find_employee_case_and_whitespace_insensitive(tool_context: ToolContext) -> None:
    assert find_employee("  BOB   smith ", tool_context)["status"] == "success"


async def test_find_employee_does_not_leak_balances(tool_context: ToolContext) -> None:
    match = find_employee("Bob", tool_context)["matches"][0]
    assert set(match) == {"employee_id", "name", "title"}


async def test_find_employee_no_match_returns_error(tool_context: ToolContext) -> None:
    result = find_employee("Zed", tool_context)
    assert result["status"] == "error"
    assert "Zed" in result["error"]


async def test_find_employee_blank_name_returns_error(tool_context: ToolContext) -> None:
    assert find_employee("   ", tool_context)["status"] == "error"


async def test_find_employee_single_match_sets_current_employee(
    tool_context: ToolContext,
) -> None:
    find_employee("Bob Smith", tool_context)
    assert tool_context.state[CURRENT_EMPLOYEE_ID_KEY] == "E1002"


async def test_find_employee_ambiguous_does_not_set_current_employee(
    tool_context: ToolContext,
) -> None:
    find_employee("alice", tool_context)
    assert CURRENT_EMPLOYEE_ID_KEY not in tool_context.state
