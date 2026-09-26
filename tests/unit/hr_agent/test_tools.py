from hr_agent.tools import find_employee, get_pto_balance, list_holidays


def test_get_pto_balance_success() -> None:
    result = get_pto_balance("E1002")
    assert result == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "pto_hours": 64.5,
        "sick_hours": 24.0,
    }


def test_get_pto_balance_normalizes_id() -> None:
    result = get_pto_balance(" e1002 ")
    assert result["status"] == "success"
    assert result["employee_id"] == "E1002"


def test_get_pto_balance_zero_balance_is_success() -> None:
    result = get_pto_balance("E1003")
    assert result["status"] == "success"
    assert result["pto_hours"] == 0.0


def test_get_pto_balance_unknown_id_returns_error_not_exception() -> None:
    result = get_pto_balance("E9999")
    assert result["status"] == "error"
    assert "E9999" in result["error"]


def test_get_pto_balance_name_instead_of_id_is_error() -> None:
    assert get_pto_balance("Bob Smith")["status"] == "error"


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


def test_find_employee_single_match_returns_minimal_fields() -> None:
    assert find_employee("Bob Smith") == {
        "status": "success",
        "matches": [{"employee_id": "E1002", "name": "Bob Smith", "title": "Software Engineer"}],
    }


def test_find_employee_multiple_matches_is_ambiguous() -> None:
    result = find_employee("alice")
    assert result["status"] == "ambiguous"
    assert {m["employee_id"] for m in result["matches"]} == {"E1001", "E1005"}


def test_find_employee_full_name_disambiguates() -> None:
    result = find_employee("alice nguyen")
    assert result["status"] == "success"
    assert result["matches"][0]["employee_id"] == "E1005"


def test_find_employee_case_and_whitespace_insensitive() -> None:
    assert find_employee("  BOB   smith ")["status"] == "success"


def test_find_employee_does_not_leak_balances() -> None:
    match = find_employee("Bob")["matches"][0]
    assert set(match) == {"employee_id", "name", "title"}


def test_find_employee_no_match_returns_error() -> None:
    result = find_employee("Zed")
    assert result["status"] == "error"
    assert "Zed" in result["error"]


def test_find_employee_blank_name_returns_error() -> None:
    assert find_employee("   ")["status"] == "error"
