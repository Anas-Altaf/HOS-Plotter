"""HOS engine tests."""
from datetime import datetime, timezone

import pytest

from hos.engine import Leg, plan_trip
from hos.log_builder import build_logs


def _legs(distance_to_pickup_mi=200, distance_to_dropoff_mi=600, speed=60):
    return [
        Leg("A", "B", 0, 0, 1, 1,
            distance_mi=distance_to_pickup_mi,
            duration_min=distance_to_pickup_mi / speed * 60,
            is_pickup_end=True),
        Leg("B", "C", 1, 1, 2, 2,
            distance_mi=distance_to_dropoff_mi,
            duration_min=distance_to_dropoff_mi / speed * 60,
            is_dropoff_end=True),
    ]


def _start():
    return datetime(2026, 4, 28, 8, 0, tzinfo=timezone.utc)


def test_short_trip_single_day():
    legs = _legs(50, 100)  # 150mi total
    events = plan_trip(legs, _start(), 0, "70_8")
    types = [e.type for e in events]
    assert "pickup" in types
    assert "dropoff" in types
    # No long resets needed
    assert "rest_10" not in types
    assert "restart_34" not in types


def test_pickup_and_dropoff_durations():
    legs = _legs(50, 50)
    events = plan_trip(legs, _start(), 0, "70_8")
    pickup = next(e for e in events if e.type == "pickup")
    dropoff = next(e for e in events if e.type == "dropoff")
    assert pickup.duration_min == 60
    assert dropoff.duration_min == 60
    assert pickup.status == "ON"
    assert dropoff.status == "ON"


def test_break_inserted_after_8h_drive():
    # 9h drive forces 30-min break
    legs = _legs(60, 480)  # 60 + 480 = 540mi at 60mph = 9h drive
    events = plan_trip(legs, _start(), 0, "70_8")
    breaks = [e for e in events if e.type == "break_30"]
    assert len(breaks) >= 1
    assert breaks[0].duration_min == 30


def test_10h_reset_after_11h_drive():
    # 12h of driving needed -> requires 10h reset
    legs = _legs(60, 660)  # 720mi at 60mph = 12h drive
    events = plan_trip(legs, _start(), 0, "70_8")
    rests = [e for e in events if e.type == "rest_10"]
    assert len(rests) >= 1
    assert rests[0].duration_min == 600


def test_fuel_every_1000mi():
    legs = _legs(100, 2100)  # 2200mi -> at least 2 fuel stops
    events = plan_trip(legs, _start(), 0, "70_8")
    fuels = [e for e in events if e.type == "fuel"]
    assert len(fuels) >= 2
    for f in fuels:
        assert f.duration_min == 15


def test_cycle_exhaustion_triggers_restart():
    # Driver starts with 68h used; long trip should hit cycle and need restart
    legs = _legs(100, 900)  # 1000mi
    events = plan_trip(legs, _start(), 68, "70_8")
    restarts = [e for e in events if e.type == "restart_34"]
    assert len(restarts) >= 1
    assert restarts[0].duration_min == 34 * 60


def test_60_7_cycle_lower_threshold():
    legs = _legs(100, 700)
    events = plan_trip(legs, _start(), 58, "60_7")
    restarts = [e for e in events if e.type == "restart_34"]
    assert len(restarts) >= 1


def test_total_distance_preserved():
    legs = _legs(120, 380)  # 500mi
    events = plan_trip(legs, _start(), 0, "70_8")
    drive_events = [e for e in events if e.type == "drive"]
    total_driven = sum(e.end_mile - e.start_mile for e in drive_events)
    assert abs(total_driven - 500) < 0.5


def test_log_builder_totals_sum_to_24():
    legs = _legs(200, 800)
    events = plan_trip(legs, _start(), 0, "70_8")
    logs = build_logs(events, "70_8", 0, "A", "C")
    for log in logs:
        s = sum(log["totals"].values())
        assert abs(s - 24.0) < 0.01, f"Day {log['date']} totals = {s}"


def test_log_builder_emits_at_least_one_day():
    legs = _legs(50, 100)
    events = plan_trip(legs, _start(), 0, "70_8")
    logs = build_logs(events, "70_8", 0, "A", "C")
    assert len(logs) >= 1
    assert logs[0]["from_location"]
    assert logs[-1]["to_location"]


def test_long_trip_multiple_days():
    legs = _legs(100, 1700)  # 1800mi -> definitely multi-day
    events = plan_trip(legs, _start(), 0, "70_8")
    logs = build_logs(events, "70_8", 0, "A", "C")
    assert len(logs) >= 2


def test_remarks_include_pickup_and_dropoff():
    legs = _legs(50, 200)
    events = plan_trip(legs, _start(), 0, "70_8")
    logs = build_logs(events, "70_8", 0, "A", "C")
    all_remarks = [r["text"] for log in logs for r in log["remarks"]]
    assert any("Pickup" in r for r in all_remarks)
    assert any("Dropoff" in r for r in all_remarks)


def test_segments_are_within_24_hour_grid():
    legs = _legs(200, 1200)
    events = plan_trip(legs, _start(), 0, "70_8")
    logs = build_logs(events, "70_8", 0, "A", "C")
    for log in logs:
        for s in log["segments"]:
            assert 0 <= s["start_min"] < s["end_min"] <= 1440


def test_zero_cycle_used_starts_fresh():
    legs = _legs(60, 60)
    events = plan_trip(legs, _start(), 0, "70_8")
    # No reset on tiny trip
    assert not any(e.type in ("rest_10", "restart_34") for e in events)


def test_status_only_off_sb_d_on():
    legs = _legs(150, 1000)
    events = plan_trip(legs, _start(), 0, "70_8")
    for e in events:
        assert e.status in {"OFF", "SB", "D", "ON"}
