import pytest

from mcp_server.handlers import get_employee


def test_get_employee_success() -> None:
    assert get_employee("E1002") == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "title": "Software Engineer",
    }


def test_get_employee_normalizes_id() -> None:
    result = get_employee("  e1002 ")
    assert result["status"] == "success"
    assert result["employee_id"] == "E1002"


@pytest.mark.parametrize("bad_id", ["E9999", "", "Bob", "1002"])
def test_get_employee_unknown_or_malformed_id(bad_id: str) -> None:
    result = get_employee(bad_id)
    assert result["status"] == "error"
    assert "E1002" in result["error"]


def test_get_employee_omits_sensitive_fields() -> None:
    result = get_employee("E1002")
    assert set(result) == {"status", "employee_id", "name", "title"}
