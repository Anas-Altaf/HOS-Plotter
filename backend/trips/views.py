"""Trip planning API views."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.throttling import AnonRateThrottle

from .serializers import TripPlanRequestSerializer
from routing import ors_client
from hos.engine import Leg, plan_trip
from hos.log_builder import build_logs

logger = logging.getLogger(__name__)


class PlanThrottle(AnonRateThrottle):
    rate = "30/min"


class GeoThrottle(AnonRateThrottle):
    rate = "60/min"


class TripPlanView(APIView):
    throttle_classes = [PlanThrottle]

    def post(self, request):
        ser = TripPlanRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        def _resolve(text_field: str, coord_field: str):
            c = data.get(coord_field)
            if c and "lat" in c and "lng" in c:
                return {"label": c.get("label") or data[text_field], "lat": c["lat"], "lng": c["lng"]}
            return ors_client.geocode(data[text_field])

        cur = _resolve("current_location", "current_coord")
        pickup = _resolve("pickup_location", "pickup_coord")
        dropoff = _resolve("dropoff_location", "dropoff_coord")

        # Route current -> pickup -> dropoff
        coords = [
            (cur["lng"], cur["lat"]),
            (pickup["lng"], pickup["lat"]),
            (dropoff["lng"], dropoff["lat"]),
        ]
        route = ors_client.directions(coords)

        # Build engine legs
        leg_summaries = route["legs"]
        if len(leg_summaries) < 2:
            logger.warning("Routing returned %d legs (expected 2). geometry_pts=%d total_mi=%.1f",
                           len(leg_summaries), len(route.get("geometry", [])), route.get("total_distance_mi", 0))
            return Response(
                {"detail": "Routing service returned an unexpected response. Please retry."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        legs = [
            Leg(
                from_label=cur["label"],
                to_label=pickup["label"],
                from_lat=cur["lat"], from_lng=cur["lng"],
                to_lat=pickup["lat"], to_lng=pickup["lng"],
                distance_mi=leg_summaries[0]["distance_mi"],
                duration_min=leg_summaries[0]["duration_min"],
                is_pickup_end=True,
            ),
            Leg(
                from_label=pickup["label"],
                to_label=dropoff["label"],
                from_lat=pickup["lat"], from_lng=pickup["lng"],
                to_lat=dropoff["lat"], to_lng=dropoff["lng"],
                distance_mi=leg_summaries[1]["distance_mi"],
                duration_min=leg_summaries[1]["duration_min"],
                is_dropoff_end=True,
            ),
        ]

        start_time = data.get("start_time") or datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        events = plan_trip(
            legs=legs,
            start_time=start_time,
            current_cycle_hours=data["current_cycle_hours"],
            cycle_type=data["cycle_type"],
        )

        # Build stops list (non-drive events only)
        stops = []
        for ev in events:
            if ev.type == "drive":
                continue
            stops.append({
                "type": ev.type,
                "label": ev.label,
                "lat": ev.lat,
                "lng": ev.lng,
                "mile": round(ev.start_mile, 1),
                "start": ev.start.isoformat(),
                "end": ev.end.isoformat(),
                "duration_min": int(ev.duration_min),
            })

        logs = build_logs(
            events,
            cycle_type=data["cycle_type"],
            initial_cycle_hours=data["current_cycle_hours"],
            trip_origin_label=cur["label"],
            trip_destination_label=dropoff["label"],
        )

        # Trim long polylines for transport (cap ~5000 pts)
        geom = route["geometry"]
        if len(geom) > 5000:
            step = max(1, len(geom) // 5000)
            geom = geom[::step]

        last_event_end = events[-1].end if events else start_time

        return Response({
            "route": {
                "geometry": geom,
                "total_distance_mi": round(route["total_distance_mi"], 1),
                "total_drive_minutes": int(route["total_duration_min"]),
                "legs": [
                    {"from": cur["label"], "to": pickup["label"],
                     "distance_mi": round(leg_summaries[0]["distance_mi"], 1),
                     "duration_min": int(leg_summaries[0]["duration_min"])},
                    {"from": pickup["label"], "to": dropoff["label"],
                     "distance_mi": round(leg_summaries[1]["distance_mi"], 1),
                     "duration_min": int(leg_summaries[1]["duration_min"])},
                ],
                "waypoints": [
                    {"label": cur["label"], "lat": cur["lat"], "lng": cur["lng"], "type": "current"},
                    {"label": pickup["label"], "lat": pickup["lat"], "lng": pickup["lng"], "type": "pickup"},
                    {"label": dropoff["label"], "lat": dropoff["lat"], "lng": dropoff["lng"], "type": "dropoff"},
                ],
            },
            "stops": stops,
            "logs": logs,
            "summary": {
                "total_distance_mi": round(route["total_distance_mi"], 1),
                "total_duration_min": int((last_event_end - start_time).total_seconds() / 60),
                "trip_start": start_time.isoformat(),
                "trip_end": last_event_end.isoformat(),
                "log_days": len(logs),
            },
        })


@api_view(["GET"])
@throttle_classes([GeoThrottle])
def autocomplete_view(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return Response({"results": []})
    return Response({"results": ors_client.autocomplete(q)})
