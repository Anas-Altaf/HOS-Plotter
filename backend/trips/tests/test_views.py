"""End-to-end API tests with mocked ORS."""
from unittest.mock import patch

import pytest
from django.test import override_settings
from rest_framework.test import APIClient


def _payload(**kw):
    base = {
        "current_location": "Dallas, TX",
        "pickup_location": "Houston, TX",
        "dropoff_location": "Atlanta, GA",
        "current_cycle_hours": 5,
        "cycle_type": "70_8",
    }
    base.update(kw)
    return base


def _fake_geocode(query):
    table = {
        "Dallas, TX": {"label": "Dallas, TX, USA", "lat": 32.776, "lng": -96.797},
        "Houston, TX": {"label": "Houston, TX, USA", "lat": 29.760, "lng": -95.369},
        "Atlanta, GA": {"label": "Atlanta, GA, USA", "lat": 33.749, "lng": -84.388},
    }
    return table.get(query, {"label": query, "lat": 0, "lng": 0})


def _fake_directions(coords):
    return {
        "geometry": [list(c) for c in coords],
        "total_distance_mi": 1030.0,
        "total_duration_min": 990.0,
        "legs": [
            {"distance_mi": 240.0, "duration_min": 230.0, "from_index": 0, "to_index": 1},
            {"distance_mi": 790.0, "duration_min": 760.0, "from_index": 1, "to_index": 2},
        ],
    }


@pytest.fixture
def client():
    return APIClient()


@override_settings(ORS_API_KEY="test")
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@override_settings(ORS_API_KEY="test")
def test_plan_trip_happy_path(client):
    with patch("trips.views.ors_client.geocode", side_effect=_fake_geocode), \
         patch("trips.views.ors_client.directions", side_effect=_fake_directions):
        r = client.post("/api/trip/plan", data=_payload(), format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["route"]["total_distance_mi"] == 1030.0
    assert len(body["route"]["legs"]) == 2
    assert any(s["type"] == "pickup" for s in body["stops"])
    assert any(s["type"] == "dropoff" for s in body["stops"])
    assert len(body["logs"]) >= 1


@override_settings(ORS_API_KEY="test")
def test_plan_trip_validation_pickup_eq_dropoff(client):
    r = client.post(
        "/api/trip/plan",
        data=_payload(pickup_location="Houston, TX", dropoff_location="Houston, TX"),
        format="json",
    )
    assert r.status_code == 400


@override_settings(ORS_API_KEY="test")
def test_plan_trip_geocode_failure_returns_422(client):
    from routing.ors_client import GeocodingError

    def _bad(query):
        raise GeocodingError(f"Could not geocode '{query}'")

    with patch("trips.views.ors_client.geocode", side_effect=_bad):
        r = client.post("/api/trip/plan", data=_payload(), format="json")
    assert r.status_code == 422
    assert "Could not geocode" in r.json()["detail"]


@override_settings(ORS_API_KEY="test")
def test_plan_trip_routing_failure_returns_502(client):
    from routing.ors_client import RoutingError

    with patch("trips.views.ors_client.geocode", side_effect=_fake_geocode), \
         patch("trips.views.ors_client.directions", side_effect=RoutingError("ORS down")):
        r = client.post("/api/trip/plan", data=_payload(), format="json")
    assert r.status_code == 502


@override_settings(ORS_API_KEY="test")
def test_plan_trip_uses_coord_hints_skips_geocode(client):
    coord_hint = {"label": "Houston, TX, USA", "lat": 29.76, "lng": -95.36}
    payload = _payload(
        current_coord={"label": "Dallas, TX, USA", "lat": 32.776, "lng": -96.797},
        pickup_coord=coord_hint,
        dropoff_coord={"label": "Atlanta, GA, USA", "lat": 33.749, "lng": -84.388},
    )
    geocode_mock = patch("trips.views.ors_client.geocode", side_effect=_fake_geocode).start()
    try:
        with patch("trips.views.ors_client.directions", side_effect=_fake_directions):
            r = client.post("/api/trip/plan", data=payload, format="json")
        assert r.status_code == 200
        assert geocode_mock.call_count == 0  # all coords supplied -> no geocoding
    finally:
        patch.stopall()


@override_settings(ORS_API_KEY="test")
def test_plan_trip_response_shape(client):
    with patch("trips.views.ors_client.geocode", side_effect=_fake_geocode), \
         patch("trips.views.ors_client.directions", side_effect=_fake_directions):
        r = client.post("/api/trip/plan", data=_payload(), format="json")
    body = r.json()
    for k in ("route", "stops", "logs", "summary"):
        assert k in body
    for k in ("geometry", "total_distance_mi", "total_drive_minutes", "legs", "waypoints"):
        assert k in body["route"]
    assert len(body["route"]["waypoints"]) == 3
    for k in ("total_distance_mi", "total_duration_min", "trip_start", "trip_end", "log_days"):
        assert k in body["summary"]


@override_settings(ORS_API_KEY="test")
def test_plan_trip_returns_request_id_header(client):
    with patch("trips.views.ors_client.geocode", side_effect=_fake_geocode), \
         patch("trips.views.ors_client.directions", side_effect=_fake_directions):
        r = client.post("/api/trip/plan", data=_payload(), format="json")
    assert "X-Request-Id" in r
    assert len(r["X-Request-Id"]) >= 8


@override_settings(ORS_API_KEY="test")
def test_autocomplete_endpoint(client):
    with patch("trips.views.ors_client.autocomplete",
               return_value=[{"label": "Houston, TX", "lat": 29.76, "lng": -95.36}]):
        r = client.get("/api/geocode/autocomplete?q=Hou")
    assert r.status_code == 200
    assert r.json()["results"][0]["label"] == "Houston, TX"


def test_autocomplete_short_query_empty(client):
    r = client.get("/api/geocode/autocomplete?q=H")
    assert r.status_code == 200
    assert r.json()["results"] == []
