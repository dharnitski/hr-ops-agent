from collections.abc import Iterator

import pytest

from hr_agent.mock_data import PAYROLL_RUNS
from mcp_server import handlers
from mcp_server.handlers import (
    approve_payroll_run,
    get_employee,
    get_payroll_run,
    get_pto_balance,
    submit_pto_request,
)


def test_get_employee_success() -> None:
    assert get_employee("E1002", caller_employee_id="E1002") == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "title": "Software Engineer",
    }


def test_get_employee_normalizes_id() -> None:
    result = get_employee("  e1002 ", caller_employee_id="e1002")
    assert result["status"] == "success"
    assert result["employee_id"] == "E1002"


@pytest.mark.parametrize("bad_id", ["E9999", "", "Bob", "1002"])
def test_get_employee_unknown_or_malformed_id(bad_id: str) -> None:
    # Caller matches the (malformed/unknown) id exactly, so this exercises not_found/lookup
    # failure specifically, not the caller-mismatch path covered separately below.
    result = get_employee(bad_id, caller_employee_id=bad_id)
    assert result["status"] == "error"


def test_get_employee_omits_sensitive_fields() -> None:
    result = get_employee("E1002", caller_employee_id="E1002")
    assert set(result) == {"status", "employee_id", "name", "title"}


@pytest.fixture(autouse=True)
def _reset_requests() -> Iterator[None]:
    handlers._pto_requests.clear()
    yield
    handlers._pto_requests.clear()


@pytest.fixture(autouse=True)
def _reset_payroll_state() -> Iterator[None]:
    # approve_payroll_run mutates PAYROLL_RUNS[...]["status"] in place (unlike
    # submit_pto_request, which never touches EMPLOYEES) -- restore it so approval tests don't
    # leak "approved" into get_payroll_run tests that assume PR-2026-09 starts "draft".
    original_statuses = {run_id: run["status"] for run_id, run in PAYROLL_RUNS.items()}
    handlers._payroll_approvals.clear()
    yield
    handlers._payroll_approvals.clear()
    for run_id, status in original_statuses.items():
        PAYROLL_RUNS[run_id]["status"] = status


def test_get_employee_error_has_code() -> None:
    result = get_employee("E9999", caller_employee_id="E9999")
    assert result["status"] == "error"
    assert result["code"] == "not_found"


def test_get_employee_forbidden_for_someone_elses_id() -> None:
    result = get_employee("E1002", caller_employee_id="E1001")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_employee_forbidden_when_no_caller_identity() -> None:
    result = get_employee("E1002", caller_employee_id=None)
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_employee_forbidden_does_not_confirm_target_exists() -> None:
    # An unauthorized caller shouldn't learn whether an arbitrary ID even exists.
    result = get_employee("E9999", caller_employee_id="E1002")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_employee_caller_id_normalized_case_and_whitespace() -> None:
    result = get_employee("E1002", caller_employee_id="  e1002 ")
    assert result["status"] == "success"


def test_get_pto_balance_success() -> None:
    assert get_pto_balance("E1002", caller_employee_id="E1002") == {
        "status": "success",
        "employee_id": "E1002",
        "name": "Bob Smith",
        "pto_hours": 64.5,
        "sick_hours": 24.0,
    }


def test_get_pto_balance_normalizes_id() -> None:
    result = get_pto_balance("  e1002 ", caller_employee_id="e1002")
    assert result["status"] == "success"
    assert result["employee_id"] == "E1002"


def test_get_pto_balance_zero_balance_is_success() -> None:
    result = get_pto_balance("E1003", caller_employee_id="E1003")
    assert result["status"] == "success"
    assert result["pto_hours"] == 0.0


def test_get_pto_balance_not_found() -> None:
    result = get_pto_balance("E9999", caller_employee_id="E9999")
    assert result["status"] == "error"
    assert result["code"] == "not_found"


def test_get_pto_balance_omits_sensitive_fields() -> None:
    result = get_pto_balance("E1002", caller_employee_id="E1002")
    assert set(result) == {"status", "employee_id", "name", "pto_hours", "sick_hours"}


def test_get_pto_balance_forbidden_for_someone_elses_id() -> None:
    result = get_pto_balance("E1002", caller_employee_id="E1001")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_pto_balance_forbidden_when_no_caller_identity() -> None:
    result = get_pto_balance("E1002", caller_employee_id=None)
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_pto_balance_forbidden_does_not_confirm_target_exists() -> None:
    result = get_pto_balance("E9999", caller_employee_id="E1002")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


@pytest.mark.parametrize("reader_id", ["E1003", "E1004"])
def test_get_payroll_run_success(reader_id: str) -> None:
    result = get_payroll_run(" pr-2026-09 ", caller_employee_id=reader_id)
    assert result["status"] == "success"
    assert result["run_id"] == "PR-2026-09"
    assert result["run_status"] == "draft"


def test_get_payroll_run_omits_per_employee_pay() -> None:
    result = get_payroll_run("PR-2026-09", caller_employee_id="E1003")
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
    result = get_payroll_run("PR-1999-01", caller_employee_id="E1003")
    assert result["status"] == "error"
    assert result["code"] == "not_found"
    assert "PR-2026-09" in result["error"]


def test_get_payroll_run_forbidden_for_non_payroll_role() -> None:
    # E1002 is a Software Engineer, not Payroll Specialist/Finance Director.
    result = get_payroll_run("PR-2026-09", caller_employee_id="E1002")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_payroll_run_forbidden_when_no_caller_identity() -> None:
    result = get_payroll_run("PR-2026-09", caller_employee_id=None)
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_get_payroll_run_forbidden_does_not_confirm_run_exists() -> None:
    # An unauthorized caller shouldn't learn whether a run ID even exists.
    result = get_payroll_run("PR-1999-01", caller_employee_id="E1002")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_submit_pto_success_skips_weekend() -> None:
    # 2026-09-11 is a Friday; Sat/Sun excluded, Mon 09-14 included.
    result = submit_pto_request(
        "E1002", "2026-09-11", "2026-09-14", "k1", caller_employee_id="E1002"
    )
    assert result["status"] == "success"
    assert result["hours"] == 16.0
    assert result["request_status"] == "pending"
    assert result["replayed"] is False


def test_submit_pto_skips_holiday() -> None:
    # Labor Day 2026-09-07 (Monday) is a company holiday.
    result = submit_pto_request(
        "E1002", "2026-09-07", "2026-09-08", "k1", caller_employee_id="E1002"
    )
    assert result["status"] == "success"
    assert result["hours"] == 8.0


def test_submit_pto_replay_returns_original() -> None:
    first = submit_pto_request(
        "E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1002"
    )
    again = submit_pto_request(
        "e1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="e1002"
    )
    assert first["status"] == "success"
    assert again["status"] == "success"
    assert again["replayed"] is True
    assert again["request_id"] == first["request_id"]
    assert len(handlers._pto_requests) == 1


def test_submit_pto_key_reuse_with_different_args() -> None:
    submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1002")
    result = submit_pto_request(
        "E1002", "2026-09-14", "2026-09-14", "k1", caller_employee_id="E1002"
    )
    assert result["status"] == "error"
    assert result["code"] == "idempotency_conflict"


def test_submit_pto_distinct_keys_create_distinct_requests() -> None:
    a = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1002")
    b = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k2", caller_employee_id="E1002")
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
    # Caller matches args[0] (the employee_id under test) so each case reaches the specific
    # error it's meant to exercise, not the forbidden check covered separately below.
    result = submit_pto_request(*args, caller_employee_id=args[0])
    assert result["status"] == "error"
    assert result["code"] == code
    assert not handlers._pto_requests


def test_failed_request_does_not_consume_key() -> None:
    submit_pto_request("E1003", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1003")
    ok = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1002")
    assert ok["status"] == "success"


def test_submit_pto_forbidden_for_someone_elses_id() -> None:
    result = submit_pto_request(
        "E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1001"
    )
    assert result["status"] == "error"
    assert result["code"] == "forbidden"
    assert not handlers._pto_requests


def test_submit_pto_forbidden_when_no_caller_identity() -> None:
    result = submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id=None)
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_submit_pto_forbidden_checked_before_idempotency_store() -> None:
    # A prior, legitimate request under this key exists; an unauthorized caller reusing it
    # for a different employee_id must still get "forbidden", not "idempotency_conflict" --
    # the identity check must run before the key is even looked up.
    submit_pto_request("E1002", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1002")
    result = submit_pto_request(
        "E1003", "2026-09-11", "2026-09-11", "k1", caller_employee_id="E1001"
    )
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_approve_payroll_run_success() -> None:
    result = approve_payroll_run("PR-2026-09", "k1", caller_employee_id="E1004")
    assert result["status"] == "success"
    assert result["run_id"] == "PR-2026-09"
    assert result["run_status"] == "approved"
    assert result["approved_by"] == "E1004"
    assert result["replayed"] is False
    assert PAYROLL_RUNS["PR-2026-09"]["status"] == "approved"


def test_approve_payroll_run_normalizes_ids() -> None:
    result = approve_payroll_run(" pr-2026-09 ", "k1", caller_employee_id="e1004")
    assert result["status"] == "success"
    assert result["run_id"] == "PR-2026-09"


def test_approve_payroll_run_forbidden_for_payroll_specialist() -> None:
    # E1003 (Carla Gomez) is a Payroll Specialist -- can read runs but not approve them.
    result = approve_payroll_run("PR-2026-09", "k1", caller_employee_id="E1003")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"
    assert PAYROLL_RUNS["PR-2026-09"]["status"] == "draft"


def test_approve_payroll_run_forbidden_for_non_payroll_role() -> None:
    result = approve_payroll_run("PR-2026-09", "k1", caller_employee_id="E1002")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_approve_payroll_run_forbidden_when_no_caller_identity() -> None:
    result = approve_payroll_run("PR-2026-09", "k1", caller_employee_id=None)
    assert result["status"] == "error"
    assert result["code"] == "forbidden"


def test_approve_payroll_run_not_found() -> None:
    result = approve_payroll_run("PR-1999-01", "k1", caller_employee_id="E1004")
    assert result["status"] == "error"
    assert result["code"] == "not_found"
    assert "PR-2026-09" in result["error"]


def test_approve_payroll_run_already_paid_is_invalid_state() -> None:
    # PR-2026-08 starts "paid" in mock data.
    result = approve_payroll_run("PR-2026-08", "k1", caller_employee_id="E1004")
    assert result["status"] == "error"
    assert result["code"] == "invalid_state"


def test_approve_payroll_run_twice_is_invalid_state_not_a_silent_success() -> None:
    approve_payroll_run("PR-2026-09", "k1", caller_employee_id="E1004")
    result = approve_payroll_run("PR-2026-09", "k2", caller_employee_id="E1004")
    assert result["status"] == "error"
    assert result["code"] == "invalid_state"


def test_approve_payroll_run_replay_returns_original() -> None:
    first = approve_payroll_run("PR-2026-09", "k1", caller_employee_id="E1004")
    again = approve_payroll_run("pr-2026-09", "k1", caller_employee_id="e1004")
    assert first["status"] == "success"
    assert again["status"] == "success"
    assert again["replayed"] is True
    assert len(handlers._payroll_approvals) == 1


def test_approve_payroll_run_key_reuse_with_different_run_conflicts() -> None:
    approve_payroll_run("PR-2026-09", "k1", caller_employee_id="E1004")
    result = approve_payroll_run("PR-2026-08", "k1", caller_employee_id="E1004")
    assert result["status"] == "error"
    assert result["code"] == "idempotency_conflict"


def test_approve_payroll_run_empty_key_is_invalid() -> None:
    result = approve_payroll_run("PR-2026-09", "  ", caller_employee_id="E1004")
    assert result["status"] == "error"
    assert result["code"] == "invalid_key"


def test_approve_payroll_run_forbidden_checked_before_run_lookup() -> None:
    # An unauthorized caller shouldn't learn whether a run ID even exists.
    result = approve_payroll_run("PR-1999-01", "k1", caller_employee_id="E1002")
    assert result["status"] == "error"
    assert result["code"] == "forbidden"
