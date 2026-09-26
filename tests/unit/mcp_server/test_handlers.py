from collections.abc import Iterator

import pytest

from mcp_server import handlers
from mcp_server.handlers import (
    get_employee,
    get_payroll_run,
    submit_pto_request,
)


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


@pytest.fixture(autouse=True)
def _reset_requests() -> Iterator[None]:
    handlers._pto_requests.clear()
    yield
    handlers._pto_requests.clear()


def test_get_employee_error_has_code() -> None:
    result = get_employee("E9999")
    assert result["status"] == "error"
    assert result["code"] == "not_found"


def test_get_payroll_run_success() -> None:
    result = get_payroll_run(" pr-2026-09 ")
    assert result["status"] == "success"
    assert result["run_id"] == "PR-2026-09"
    assert result["run_status"] == "draft"


def test_get_payroll_run_omits_per_employee_pay() -> None:
    result = get_payroll_run("PR-2026-09")
    assert set(result) == {
        "status",
        "run_id",
        "period_start",
        "period_end",
        "pay_date",
        "run_status",
        "employee_count",
        "total_gross",
    }


def test_get_payroll_run_not_found() -> None:
    result = get_payroll_run("PR-1999-01")
    assert result["status"] == "error"
    assert result["code"] == "not_found"
    assert "PR-2026-09" in result["error"]


def test_submit_pto_success_skips_weekend() -> None:
    # 2026-09-11 is a Friday; Sat/Sun excluded, Mon 09-14 included.
    result = submit_pto_request("E1002", "2026-09-11", "2026-09-14", "k1")
    assert result["status"] == "success"
    assert result["hours"] == 16.0
    assert result["request_status"] == "pending"
    assert result["replayed"] is False


def test_submit_pto_skips_holiday() -> None:
    # Labor Day 2026-09-07 (Monday) is a company holiday.
    result = submit_pto_request("E1002", "2026-09-07", "2026-09-08", "k1")
    assert result["status"] == "success"
    assert result["hours"] == 8.0


def test_submit_pto_replay_returns_original() -> None:
    first = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1")
    again = submit_pto_request("e1002", "2026-09-11", "2026-09-11", "k1")
    assert first["status"] == "success"
    assert again["status"] == "success"
    assert again["replayed"] is True
    assert again["request_id"] == first["request_id"]
    assert len(handlers._pto_requests) == 1


def test_submit_pto_key_reuse_with_different_args() -> None:
    submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1")
    result = submit_pto_request("E1002", "2026-09-14", "2026-09-14", "k1")
    assert result["status"] == "error"
    assert result["code"] == "idempotency_conflict"


def test_submit_pto_distinct_keys_create_distinct_requests() -> None:
    a = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1")
    b = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k2")
    assert a["status"] == "success"
    assert b["status"] == "success"
    assert a["request_id"] != b["request_id"]


@pytest.mark.parametrize(
    ("args", "code"),
    [
        (("E9999", "2026-09-11", "2026-09-11", "k"), "not_found"),
        (("E1002", "09/11/2026", "2026-09-11", "k"), "invalid_dates"),
        (("E1002", "2026-09-12", "2026-09-11", "k"), "invalid_dates"),
        (("E1002", "2026-09-12", "2026-09-13", "k"), "no_working_days"),
        (("E1003", "2026-09-11", "2026-09-11", "k"), "insufficient_balance"),
        (("E1002", "2026-09-11", "2026-09-11", "  "), "invalid_key"),
    ],
)
def test_submit_pto_errors(args: tuple[str, str, str, str], code: str) -> None:
    result = submit_pto_request(*args)
    assert result["status"] == "error"
    assert result["code"] == code
    assert not handlers._pto_requests


def test_failed_request_does_not_consume_key() -> None:
    submit_pto_request("E1003", "2026-09-11", "2026-09-11", "k1")
    ok = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1")
    assert ok["status"] == "success"
