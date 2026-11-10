"""Tests for due date / priority helpers."""

from datetime import date

from due_priority import (
    apply_due_and_priority,
    compute_due_date,
    compute_priority_rate,
    extract_explicit_due_date,
)


def test_explicit_due_date_from_query():
    assert extract_explicit_due_date("Please process by due date 2026-09-20") == date(
        2026, 9, 20
    )


def test_compute_due_date_prefers_explicit():
    due, source = compute_due_date(
        query="deadline 2026-10-01",
        effective_date="2026-09-14",
        calendar_cutoff="2026-09-18",
    )
    assert due == "2026-10-01"
    assert source == "explicit_email"


def test_compute_due_date_calendar_then_default():
    due, source = compute_due_date(
        query="raise rate",
        effective_date="2026-09-14",
        calendar_cutoff="2026-09-18",
    )
    assert due == "2026-09-18"
    assert source == "payroll_calendar"

    due2, source2 = compute_due_date(
        query="raise rate",
        effective_date="2026-09-14",
        today=date(2026, 9, 10),
    )
    assert due2 == "2026-09-20"
    assert source2 == "default_cutoff"


def test_compute_priority_urgent_near_deadline():
    rate = compute_priority_rate(
        due_date="2026-09-11",
        change_count=1,
        urgency_in_query=True,
        today=date(2026, 9, 10),
    )
    assert rate == "high"


def test_apply_due_and_priority_on_payload():
    out = apply_due_and_priority(
        {
            "parameters": {"effective_date": "2026-09-14"},
            "changes": [{"field": "hourly_pay_rate", "to": "22"}],
        },
        query="Please update ASAP due 2026-09-12",
    )
    assert out["due_date"] == "2026-09-12"
    assert out["due_date_source"] == "explicit_email"
    assert out["priority_rate"] in ("high", "medium", "low")
