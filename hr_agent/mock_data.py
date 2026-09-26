"""Mock HCM data. Stands in for a real HCM system; replaced by the MCP server in Module 2."""

from typing import Any

EMPLOYEES: dict[str, dict[str, Any]] = {
    "E1001": {
        "name": "Alice Johnson",
        "title": "Engineering Manager",
        "manager_id": None,
        "pto_hours": 96.0,
        "sick_hours": 40.0,
    },
    "E1002": {
        "name": "Bob Smith",
        "title": "Software Engineer",
        "manager_id": "E1001",
        "pto_hours": 64.5,
        "sick_hours": 24.0,
    },
    "E1003": {
        "name": "Carla Gomez",
        "title": "Payroll Specialist",
        "manager_id": "E1004",
        "pto_hours": 0.0,
        "sick_hours": 16.0,
    },
    "E1004": {
        "name": "Dev Patel",
        "title": "Finance Director",
        "manager_id": None,
        "pto_hours": 120.0,
        "sick_hours": 40.0,
    },
    # Same first name as E1001: exercises multiple-match handling in find_employee (step 8).
    "E1005": {
        "name": "Alice Nguyen",
        "title": "Recruiter",
        "manager_id": "E1004",
        "pto_hours": 32.0,
        "sick_hours": 8.0,
    },
}

# 2026 US company holidays: ISO date -> name.
HOLIDAYS: dict[int, dict[str, str]] = {
    2026: {
        "2026-01-01": "New Year's Day",
        "2026-01-19": "Martin Luther King Jr. Day",
        "2026-05-25": "Memorial Day",
        "2026-06-19": "Juneteenth",
        "2026-07-03": "Independence Day (observed)",
        "2026-09-07": "Labor Day",
        "2026-11-26": "Thanksgiving Day",
        "2026-11-27": "Day after Thanksgiving",
        "2026-12-25": "Christmas Day",
    },
}

# Payroll runs, aggregates only (no per-employee pay).
PAYROLL_RUNS: dict[str, dict[str, Any]] = {
    "PR-2026-08": {
        "period_start": "2026-08-01",
        "period_end": "2026-08-31",
        "pay_date": "2026-09-04",
        "status": "paid",
        "employee_count": 5,
        "total_gross": 61250.00,
    },
    "PR-2026-09": {
        "period_start": "2026-09-01",
        "period_end": "2026-09-30",
        "pay_date": "2026-10-02",
        "status": "draft",
        "employee_count": 5,
        "total_gross": 61250.00,
    },
}
