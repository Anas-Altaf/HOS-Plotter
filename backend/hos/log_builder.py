"""Per-day ELD log sheet builder.

Consumes engine Events, splits any segment crossing midnight, and emits one log
per calendar day with status segments, totals, remarks, total miles, and recap.
"""
from __future__ import annotations

from datetime import datetime, timedelta, date
from typing import List, Dict, Any
from collections import defaultdict

from .engine import Event
from . import rules as R


def _minute_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute + dt.second // 60


def _date_key(dt: datetime) -> date:
    return dt.date()


def build_logs(
    events: List[Event],
    cycle_type: str = "70_8",
    initial_cycle_hours: float = 0.0,
    trip_origin_label: str = "",
    trip_destination_label: str = "",
) -> List[Dict[str, Any]]:
    if not events:
        return []

    # Bucket events by date, splitting on midnight boundaries.
    by_date: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    miles_by_date: Dict[date, float] = defaultdict(float)
    remarks_by_date: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    location_by_date: Dict[date, Dict[str, str]] = defaultdict(dict)

    for ev in events:
        cur = ev.start
        end = ev.end
        ev_total_miles = ev.end_mile - ev.start_mile
        ev_total_min = ev.duration_min if ev.duration_min > 0 else 1e-9

        while cur < end:
            day = _date_key(cur)
            day_end = datetime.combine(day, datetime.min.time(), tzinfo=cur.tzinfo) + timedelta(days=1)
            seg_end = min(end, day_end)
            seg_min_of_day_start = _minute_of_day(cur) if cur.date() == day else 0
            seg_min_of_day_end = 1440 if seg_end >= day_end else _minute_of_day(seg_end)
            if seg_min_of_day_end <= seg_min_of_day_start and seg_end > cur:
                # Crossed boundary edge case
                seg_min_of_day_end = 1440

            seg_duration_min = (seg_end - cur).total_seconds() / 60
            frac = seg_duration_min / ev_total_min if ev_total_min > 0 else 0
            seg_miles = ev_total_miles * frac

            by_date[day].append({
                "status": ev.status,
                "start_min": seg_min_of_day_start,
                "end_min": seg_min_of_day_end,
                "type": ev.type,
            })
            if ev.type == "drive":
                miles_by_date[day] += seg_miles

            cur = seg_end

        # Remarks attach to the start time of meaningful events.
        if ev.type in ("pickup", "dropoff", "fuel", "break_30", "rest_10", "restart_34"):
            day = _date_key(ev.start)
            remarks_by_date[day].append({
                "time_min": _minute_of_day(ev.start),
                "text": ev.label,
            })
        if ev.type == "pickup":
            location_by_date[_date_key(ev.start)]["from"] = ev.label.replace("Pickup — ", "")
        if ev.type == "dropoff":
            location_by_date[_date_key(ev.start)]["to"] = ev.label.replace("Dropoff — ", "")

    sorted_dates = sorted(by_date.keys())
    logs: List[Dict[str, Any]] = []

    # Track rolling cycle for recap
    rolling_cycle_min = initial_cycle_hours * 60

    for idx, day in enumerate(sorted_dates):
        # Fill gaps with OFF status
        segs = sorted(by_date[day], key=lambda s: s["start_min"])
        filled: List[Dict[str, Any]] = []
        cursor = 0
        for s in segs:
            if s["start_min"] > cursor:
                filled.append({"status": "OFF", "start_min": cursor, "end_min": s["start_min"]})
            filled.append(s)
            cursor = max(cursor, s["end_min"])
        if cursor < 1440:
            filled.append({"status": "OFF", "start_min": cursor, "end_min": 1440})

        # Merge consecutive segments of same status
        merged: List[Dict[str, Any]] = []
        for s in filled:
            if merged and merged[-1]["status"] == s["status"] and merged[-1]["end_min"] == s["start_min"]:
                merged[-1]["end_min"] = s["end_min"]
            else:
                merged.append({"status": s["status"], "start_min": s["start_min"], "end_min": s["end_min"]})

        # Totals (hours)
        totals = {"OFF": 0.0, "SB": 0.0, "D": 0.0, "ON": 0.0}
        for s in merged:
            mins = s["end_min"] - s["start_min"]
            totals[s["status"]] = totals.get(s["status"], 0) + mins / 60.0
        # Round to 2 decimals
        totals = {k: round(v, 2) for k, v in totals.items()}

        # Day's on-duty contribution to cycle
        day_on_duty_hours = totals["D"] + totals["ON"]
        rolling_cycle_min += day_on_duty_hours * 60

        # Locations
        from_loc = location_by_date[day].get("from", "")
        to_loc = location_by_date[day].get("to", "")
        if not from_loc:
            from_loc = trip_origin_label if idx == 0 else "En route"
        if not to_loc:
            to_loc = trip_destination_label if idx == len(sorted_dates) - 1 else "En route"

        # Recap (simplified): A = day on-duty hours, B = available remaining in cycle, C = available tomorrow
        cycle_max = R.cycle_max_min(cycle_type) / 60.0
        cycle_used_h = rolling_cycle_min / 60.0
        recap = {
            cycle_type: {
                "A": round(day_on_duty_hours, 2),
                "B": round(max(0.0, cycle_max - cycle_used_h), 2),
                "C": round(day_on_duty_hours, 2),
            }
        }
        # Also fill the other cycle box with same A/C, B w.r.t its max
        other = "60_7" if cycle_type == "70_8" else "70_8"
        other_max = R.cycle_max_min(other) / 60.0
        recap[other] = {
            "A": round(day_on_duty_hours, 2),
            "B": round(max(0.0, other_max - cycle_used_h), 2),
            "C": round(day_on_duty_hours, 2),
        }

        logs.append({
            "date": day.isoformat(),
            "from_location": from_loc,
            "to_location": to_loc,
            "segments": merged,
            "totals": totals,
            "total_miles_today": round(miles_by_date[day], 1),
            "remarks": sorted(remarks_by_date[day], key=lambda r: r["time_min"]),
            "recap": recap,
        })

    return logs
