"""Log builder tests."""
from datetime import datetime, timedelta, timezone

from hos.engine import Event, Leg, plan_trip
from hos.log_builder import build_logs


def _ev(t, st, start, dur_min, sm=0, em=0, label=""):
    return Event(
        type=t,
        status=st,
        start=start,
        end=start + timedelta(minutes=dur_min),
        duration_min=dur_min,
        start_mile=sm,
        end_mile=em,
        label=label,
    )


def test_empty_events_returns_empty_list():
    assert build_logs([], "70_8", 0, "A", "B") == []


def test_single_segment_one_day():
    start = datetime(2026, 4, 28, 0, 0, tzinfo=timezone.utc)
    events = [_ev("drive", "D", start, 60, sm=0, em=60)]
    logs = build_logs(events, "70_8", 0, "A", "B")
    assert len(logs) == 1
    assert logs[0]["totals"]["D"] == 1.0
    # remaining 23h filled with OFF
    assert abs(logs[0]["totals"]["OFF"] - 23.0) < 0.01


def test_segment_crosses_midnight_splits_two_days():
    start = datetime(2026, 4, 28, 23, 0, tzinfo=timezone.utc)
    events = [_ev("drive", "D", start, 120, sm=0, em=100)]  # 23:00 -> 01:00
    logs = build_logs(events, "70_8", 0, "A", "B")
    assert len(logs) == 2
    assert logs[0]["date"] == "2026-04-28"
    assert logs[1]["date"] == "2026-04-29"
    # Day 1: 1h drive (23-24), Day 2: 1h drive (00-01)
    assert abs(logs[0]["totals"]["D"] - 1.0) < 0.01
    assert abs(logs[1]["totals"]["D"] - 1.0) < 0.01


def test_totals_always_sum_to_24():
    start = datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc)
    legs = [
        Leg("A", "B", 0, 0, 1, 1, 200, 200, is_pickup_end=True),
        Leg("B", "C", 1, 1, 2, 2, 1500, 1500, is_dropoff_end=True),
    ]
    events = plan_trip(legs, start, 0, "70_8")
    logs = build_logs(events, "70_8", 0, "A", "C")
    for log in logs:
        s = sum(log["totals"].values())
        assert abs(s - 24.0) < 0.05, f"{log['date']} sum={s}"


def test_remarks_sorted_by_time():
    start = datetime(2026, 4, 28, 0, 0, tzinfo=timezone.utc)
    events = [
        _ev("dropoff", "ON", start + timedelta(hours=10), 60, label="Dropoff — X"),
        _ev("pickup", "ON", start + timedelta(hours=2), 60, label="Pickup — Y"),
    ]
    logs = build_logs(events, "70_8", 0, "Y", "X")
    rems = logs[0]["remarks"]
    assert rems[0]["time_min"] < rems[1]["time_min"]


def test_total_miles_counted_only_for_drive():
    start = datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc)
    events = [
        _ev("drive", "D", start, 60, sm=0, em=60),
        _ev("pickup", "ON", start + timedelta(hours=1), 60, sm=60, em=60),
    ]
    logs = build_logs(events, "70_8", 0, "A", "B")
    assert logs[0]["total_miles_today"] == 60.0


def test_recap_includes_both_cycles():
    start = datetime(2026, 4, 28, 0, 0, tzinfo=timezone.utc)
    events = [_ev("drive", "D", start, 600, sm=0, em=600)]
    logs = build_logs(events, "70_8", 0, "A", "B")
    assert "70_8" in logs[0]["recap"]
    assert "60_7" in logs[0]["recap"]
    for k in ("A", "B", "C"):
        assert k in logs[0]["recap"]["70_8"]


def test_consecutive_same_status_segments_merged():
    start = datetime(2026, 4, 28, 0, 0, tzinfo=timezone.utc)
    events = [
        _ev("drive", "D", start, 60, sm=0, em=60),
        _ev("drive", "D", start + timedelta(hours=1), 60, sm=60, em=120),
    ]
    logs = build_logs(events, "70_8", 0, "A", "B")
    drive_segs = [s for s in logs[0]["segments"] if s["status"] == "D"]
    assert len(drive_segs) == 1
    assert drive_segs[0]["start_min"] == 0
    assert drive_segs[0]["end_min"] == 120


def test_60_7_cycle_recap_max():
    start = datetime(2026, 4, 28, 0, 0, tzinfo=timezone.utc)
    events = [_ev("drive", "D", start, 600, sm=0, em=600)]
    logs = build_logs(events, "60_7", 0, "A", "B")
    # B should be available remaining for 60/7
    assert logs[0]["recap"]["60_7"]["B"] <= 60.0
    assert logs[0]["recap"]["70_8"]["B"] <= 70.0
