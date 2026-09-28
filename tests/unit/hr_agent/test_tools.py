from hr_agent.tools import list_holidays


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
