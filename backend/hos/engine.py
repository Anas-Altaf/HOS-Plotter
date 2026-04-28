"""HOS planning engine.

Pure-Python deterministic simulator. Given route legs (current -> pickup -> dropoff)
with distances and durations, plus driver cycle state, produces an ordered list of
events (drive segments + on/off-duty stops) that respects 49 CFR 395.3.

Greedy priority on each tick:
  1. Trip complete -> stop
  2. cycle_used >= cycle_max -> 34h restart
  3. window or drive limit hit -> 10h off-duty reset
  4. 8h cumulative drive without break -> 30min break
  5. 1000mi since last fuel -> 15min fuel stop
  6. At pickup/dropoff waypoint -> 1h on-duty
  7. Else drive a chunk
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional

from . import rules as R


@dataclass
class Leg:
    from_label: str
    to_label: str
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    distance_mi: float
    duration_min: float
    is_pickup_end: bool = False   # True if this leg ends at the pickup
    is_dropoff_end: bool = False  # True if this leg ends at the dropoff


@dataclass
class Event:
    type: str            # "drive" | "pickup" | "dropoff" | "fuel" | "break_30" | "rest_10" | "restart_34"
    status: str          # "OFF" | "SB" | "D" | "ON"
    start: datetime
    end: datetime
    duration_min: float
    start_mile: float
    end_mile: float
    label: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start"] = self.start.isoformat()
        d["end"] = self.end.isoformat()
        return d


@dataclass
class State:
    cycle_used_min: float                 # Minutes used in current cycle
    cycle_max_min: int
    window_remaining_min: float = R.WINDOW_LIMIT_MIN
    drive_remaining_min: float = R.DRIVE_LIMIT_MIN
    since_break_min: float = 0.0          # driving minutes since last >=30min off
    miles_since_fuel: float = 0.0
    clock: datetime = field(default_factory=datetime.utcnow)
    position_mi: float = 0.0


def _interp_latlng(leg: Leg, frac: float) -> tuple[float, float]:
    frac = max(0.0, min(1.0, frac))
    lat = leg.from_lat + (leg.to_lat - leg.from_lat) * frac
    lng = leg.from_lng + (leg.to_lng - leg.from_lng) * frac
    return lat, lng


def plan_trip(
    legs: List[Leg],
    start_time: datetime,
    current_cycle_hours: float,
    cycle_type: str = "70_8",
) -> List[Event]:
    cycle_max = R.cycle_max_min(cycle_type)
    state = State(
        cycle_used_min=current_cycle_hours * 60,
        cycle_max_min=cycle_max,
        clock=start_time,
    )
    events: List[Event] = []

    total_distance = sum(l.distance_mi for l in legs)
    cumulative_mi_at_leg_end = []
    acc = 0.0
    for l in legs:
        acc += l.distance_mi
        cumulative_mi_at_leg_end.append(acc)

    # Iterate over legs sequentially
    leg_idx = 0
    leg_position_mi = 0.0  # how far we've driven inside the current leg

    safety_iter = 0
    while leg_idx < len(legs):
        safety_iter += 1
        if safety_iter > 5000:
            raise RuntimeError("HOS planner safety break")

        leg = legs[leg_idx]
        leg_remaining_mi = leg.distance_mi - leg_position_mi

        # Speed within leg (mph). Guard zero-distance leg.
        if leg.distance_mi > 0 and leg.duration_min > 0:
            speed_mph = leg.distance_mi / (leg.duration_min / 60.0)
        else:
            speed_mph = 60.0  # sane default

        # 1. End of leg reached -> insert pickup/dropoff event then advance
        if leg_remaining_mi <= 1e-6:
            if leg.is_pickup_end:
                _add_on_duty(events, state, R.PICKUP_MIN, "pickup", f"Pickup — {leg.to_label}", leg.to_lat, leg.to_lng, cycle_max)
            elif leg.is_dropoff_end:
                _add_on_duty(events, state, R.DROPOFF_MIN, "dropoff", f"Dropoff — {leg.to_label}", leg.to_lat, leg.to_lng, cycle_max)
            leg_idx += 1
            leg_position_mi = 0.0
            continue

        # 2. Cycle exhausted -> 34h restart
        if state.cycle_used_min >= cycle_max:
            lat, lng = _interp_latlng(leg, leg_position_mi / leg.distance_mi if leg.distance_mi else 0)
            cum_mile = sum(l.distance_mi for l in legs[:leg_idx]) + leg_position_mi
            _add_off(events, state, R.RESTART_MIN, "restart_34", "34-hour restart", lat, lng, cum_mile, restart=True)
            continue

        # 3. Window/drive limit hit -> 10h reset
        if state.window_remaining_min <= 1e-6 or state.drive_remaining_min <= 1e-6:
            lat, lng = _interp_latlng(leg, leg_position_mi / leg.distance_mi if leg.distance_mi else 0)
            cum_mile = sum(l.distance_mi for l in legs[:leg_idx]) + leg_position_mi
            _add_off(events, state, R.OFF_DUTY_RESET_MIN, "rest_10", "10-hour off-duty reset", lat, lng, cum_mile)
            continue

        # 4. 8h drive without break -> 30min break
        if state.since_break_min >= R.BREAK_AFTER_DRIVE_MIN:
            lat, lng = _interp_latlng(leg, leg_position_mi / leg.distance_mi if leg.distance_mi else 0)
            cum_mile = sum(l.distance_mi for l in legs[:leg_idx]) + leg_position_mi
            _add_break(events, state, R.BREAK_DURATION_MIN, "break_30", "30-minute break", lat, lng, cum_mile)
            continue

        # 5. 1000mi since fuel -> fuel stop
        if state.miles_since_fuel >= R.FUEL_INTERVAL_MI:
            lat, lng = _interp_latlng(leg, leg_position_mi / leg.distance_mi if leg.distance_mi else 0)
            cum_mile = sum(l.distance_mi for l in legs[:leg_idx]) + leg_position_mi
            _add_fuel(events, state, R.FUEL_DURATION_MIN, "fuel", f"Fuel stop — mile {int(cum_mile)}", lat, lng, cum_mile, cycle_max)
            continue

        # 6. Drive a chunk
        miles_to_break = max(0.0, (R.BREAK_AFTER_DRIVE_MIN - state.since_break_min) / 60.0 * speed_mph)
        miles_to_fuel = max(0.0, R.FUEL_INTERVAL_MI - state.miles_since_fuel)
        miles_drive_cap = max(0.0, state.drive_remaining_min / 60.0 * speed_mph)
        miles_window_cap = max(0.0, state.window_remaining_min / 60.0 * speed_mph)

        chunk_mi = min(
            leg_remaining_mi,
            miles_to_break if miles_to_break > 0 else float("inf"),
            miles_to_fuel if miles_to_fuel > 0 else float("inf"),
            miles_drive_cap if miles_drive_cap > 0 else float("inf"),
            miles_window_cap if miles_window_cap > 0 else float("inf"),
        )
        if chunk_mi <= 1e-6:
            # Defensive: tiny chunk; force a tiny step to avoid infinite loop
            chunk_mi = min(leg_remaining_mi, 0.01)

        chunk_min = chunk_mi / speed_mph * 60.0
        cum_start_mile = sum(l.distance_mi for l in legs[:leg_idx]) + leg_position_mi
        cum_end_mile = cum_start_mile + chunk_mi

        start_clock = state.clock
        end_clock = start_clock + timedelta(minutes=chunk_min)

        events.append(
            Event(
                type="drive",
                status=R.STATUS_DRIVE,
                start=start_clock,
                end=end_clock,
                duration_min=chunk_min,
                start_mile=cum_start_mile,
                end_mile=cum_end_mile,
                label=f"Drive {leg.from_label} → {leg.to_label}",
            )
        )
        state.clock = end_clock
        state.position_mi = cum_end_mile
        state.window_remaining_min -= chunk_min
        state.drive_remaining_min -= chunk_min
        state.since_break_min += chunk_min
        state.miles_since_fuel += chunk_mi
        state.cycle_used_min += chunk_min
        leg_position_mi += chunk_mi

    return events


def _add_on_duty(events, state: State, dur_min: int, etype: str, label: str, lat, lng, cycle_max: int):
    start = state.clock
    end = start + timedelta(minutes=dur_min)
    events.append(
        Event(
            type=etype,
            status=R.STATUS_ON,
            start=start,
            end=end,
            duration_min=dur_min,
            start_mile=state.position_mi,
            end_mile=state.position_mi,
            label=label,
            lat=lat,
            lng=lng,
        )
    )
    state.clock = end
    state.window_remaining_min -= dur_min
    state.cycle_used_min += dur_min
    # On-duty doesn't consume drive_remaining; doesn't reset since_break.


def _add_break(events, state: State, dur_min: int, etype: str, label: str, lat, lng, cum_mile: float):
    start = state.clock
    end = start + timedelta(minutes=dur_min)
    events.append(
        Event(
            type=etype,
            status=R.STATUS_OFF,
            start=start,
            end=end,
            duration_min=dur_min,
            start_mile=cum_mile,
            end_mile=cum_mile,
            label=label,
            lat=lat,
            lng=lng,
        )
    )
    state.clock = end
    state.since_break_min = 0
    # 30-min off does NOT reset 14h window or 11h drive; it counts inside the window.
    state.window_remaining_min -= dur_min


def _add_off(events, state: State, dur_min: int, etype: str, label: str, lat, lng, cum_mile: float, restart: bool = False):
    start = state.clock
    end = start + timedelta(minutes=dur_min)
    events.append(
        Event(
            type=etype,
            status=R.STATUS_OFF,
            start=start,
            end=end,
            duration_min=dur_min,
            start_mile=cum_mile,
            end_mile=cum_mile,
            label=label,
            lat=lat,
            lng=lng,
        )
    )
    state.clock = end
    state.window_remaining_min = R.WINDOW_LIMIT_MIN
    state.drive_remaining_min = R.DRIVE_LIMIT_MIN
    state.since_break_min = 0
    if restart:
        state.cycle_used_min = 0


def _add_fuel(events, state: State, dur_min: int, etype: str, label: str, lat, lng, cum_mile: float, cycle_max: int):
    start = state.clock
    end = start + timedelta(minutes=dur_min)
    events.append(
        Event(
            type=etype,
            status=R.STATUS_ON,
            start=start,
            end=end,
            duration_min=dur_min,
            start_mile=cum_mile,
            end_mile=cum_mile,
            label=label,
            lat=lat,
            lng=lng,
        )
    )
    state.clock = end
    state.window_remaining_min -= dur_min
    state.cycle_used_min += dur_min
    state.miles_since_fuel = 0
