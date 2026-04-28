"""OpenRouteService client — geocode + truck directions."""
from __future__ import annotations

import logging
import time
from typing import List, Tuple, Dict, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _log_call(endpoint: str, status: int, elapsed_ms: float, extra: str = "") -> None:
    logger.info("ORS %s status=%s %.0fms %s", endpoint, status, elapsed_ms, extra)

METERS_PER_MILE = 1609.344


class RoutingError(Exception):
    pass


class GeocodingError(Exception):
    pass


def _headers() -> Dict[str, str]:
    return {
        "Authorization": settings.ORS_API_KEY,
        "Accept": "application/json, application/geo+json",
        "Content-Type": "application/json; charset=utf-8",
    }


def geocode(query: str) -> Dict[str, Any]:
    """Return {label, lat, lng} for the best match, or raise GeocodingError."""
    if not settings.ORS_API_KEY:
        raise GeocodingError("ORS_API_KEY is not configured")
    url = f"{settings.ORS_BASE_URL}/geocode/search"
    params = {
        "api_key": settings.ORS_API_KEY,
        "text": query,
        "size": 1,
        "boundary.country": "USA",
        "layers": "locality,region,address,neighbourhood,county",
    }
    t0 = time.perf_counter()
    try:
        resp = requests.get(url, params=params, timeout=10)
        elapsed = (time.perf_counter() - t0) * 1000
        _log_call("geocode/search", resp.status_code, elapsed, f"q_len={len(query)}")
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Geocode request failed: %s", exc)
        raise GeocodingError(f"Could not geocode '{query}'") from exc

    data = resp.json()
    feats = data.get("features", [])
    if not feats:
        raise GeocodingError(f"Could not geocode '{query}'")
    f = feats[0]
    lng, lat = f["geometry"]["coordinates"][:2]
    label = f["properties"].get("label", query)
    return {"label": label, "lat": lat, "lng": lng}


def autocomplete(query: str, size: int = 5) -> List[Dict[str, Any]]:
    if not settings.ORS_API_KEY:
        return []
    url = f"{settings.ORS_BASE_URL}/geocode/autocomplete"
    params = {
        "api_key": settings.ORS_API_KEY,
        "text": query,
        "size": size,
        "boundary.country": "USA",
        "layers": "locality,region,address",
    }
    t0 = time.perf_counter()
    try:
        resp = requests.get(url, params=params, timeout=8)
        elapsed = (time.perf_counter() - t0) * 1000
        _log_call("geocode/autocomplete", resp.status_code, elapsed)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Autocomplete failed: %s", exc)
        return []
    out = []
    for f in resp.json().get("features", []):
        lng, lat = f["geometry"]["coordinates"][:2]
        out.append({"label": f["properties"].get("label", ""), "lat": lat, "lng": lng})
    return out


def directions(coords: List[Tuple[float, float]]) -> Dict[str, Any]:
    """coords: list of (lng, lat). Returns geometry, distance_mi, duration_min, legs."""
    if not settings.ORS_API_KEY:
        raise RoutingError("ORS_API_KEY is not configured")
    if len(coords) < 2:
        raise RoutingError("At least two coordinates required")

    url = f"{settings.ORS_BASE_URL}/v2/directions/driving-hgv/geojson"
    body = {"coordinates": [[lng, lat] for lng, lat in coords], "instructions": False}
    t0 = time.perf_counter()
    try:
        resp = requests.post(url, json=body, headers=_headers(), timeout=20)
        elapsed = (time.perf_counter() - t0) * 1000
        _log_call("directions/driving-hgv", resp.status_code, elapsed, f"waypoints={len(coords)}")
        if resp.status_code >= 400:
            logger.warning("ORS directions error %s: %s", resp.status_code, resp.text[:300])
            raise RoutingError(f"Routing service error ({resp.status_code})")
    except requests.RequestException as exc:
        logger.warning("Directions request failed: %s", exc)
        raise RoutingError("Routing service unavailable") from exc

    data = resp.json()
    feat = data["features"][0]
    geometry = feat["geometry"]["coordinates"]  # list of [lng, lat]
    props = feat["properties"]
    summary = props.get("summary") or {}
    legs_raw = props.get("segments", []) or []
    way_points = props.get("way_points") or []

    expected_legs = max(0, len(coords) - 1)

    if len(legs_raw) < expected_legs:
        logger.warning(
            "ORS returned %d segments, expected %d. props keys=%s way_points=%s",
            len(legs_raw), expected_legs, list(props.keys()), way_points,
        )

    legs: List[Dict[str, Any]] = []
    if len(legs_raw) >= expected_legs:
        for i, seg in enumerate(legs_raw[:expected_legs]):
            legs.append({
                "distance_mi": seg["distance"] / METERS_PER_MILE,
                "duration_min": seg["duration"] / 60.0,
                "from_index": i,
                "to_index": i + 1,
            })
    elif way_points and len(way_points) == expected_legs + 1 and summary:
        # Fallback: split summary proportionally by geometry index distances.
        total_dist_m = summary.get("distance", 0)
        total_dur_s = summary.get("duration", 0)
        total_pts = max(1, way_points[-1] - way_points[0])
        for i in range(expected_legs):
            seg_pts = way_points[i + 1] - way_points[i]
            frac = seg_pts / total_pts if total_pts else 1.0 / expected_legs
            legs.append({
                "distance_mi": (total_dist_m * frac) / METERS_PER_MILE,
                "duration_min": (total_dur_s * frac) / 60.0,
                "from_index": i,
                "to_index": i + 1,
            })
        logger.info("Used way_points fallback to derive %d legs.", expected_legs)
    else:
        # Last resort: equal split.
        total_dist_m = summary.get("distance", 0)
        total_dur_s = summary.get("duration", 0)
        for i in range(expected_legs):
            legs.append({
                "distance_mi": (total_dist_m / expected_legs) / METERS_PER_MILE,
                "duration_min": (total_dur_s / expected_legs) / 60.0,
                "from_index": i,
                "to_index": i + 1,
            })
        logger.warning("Used equal-split fallback for legs.")

    return {
        "geometry": geometry,
        "total_distance_mi": summary.get("distance", 0) / METERS_PER_MILE,
        "total_duration_min": summary.get("duration", 0) / 60.0,
        "legs": legs,
    }
