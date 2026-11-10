from datetime import datetime, timezone

from triage.window import compute_processing_window


def test_first_run_uses_lookback():
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    window = compute_processing_window(
        lookback_days=7,
        last_successful_run=None,
        now=now,
    )
    assert window["basis"] == "lookback"
    assert window["window_end"] == now.isoformat()
    assert window["window_start"] == datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc).isoformat()


def test_later_run_uses_last_success_end():
    now = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
    last = {"window_end": "2026-09-22T08:00:00+00:00", "status": "succeeded"}
    window = compute_processing_window(
        lookback_days=7,
        last_successful_run=last,
        now=now,
    )
    assert window["basis"] == "last_success"
    assert window["window_start"] == "2026-09-22T08:00:00+00:00"
    assert window["window_end"] == now.isoformat()
