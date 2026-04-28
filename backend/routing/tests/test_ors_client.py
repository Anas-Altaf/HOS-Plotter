"""ORS client tests with mocked requests."""
from unittest.mock import patch, MagicMock

import pytest
from django.test import override_settings

from routing import ors_client
from routing.ors_client import GeocodingError, RoutingError


@override_settings(ORS_API_KEY="test-key")
def test_geocode_returns_first_feature():
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "features": [
            {"geometry": {"coordinates": [-95.36, 29.76]}, "properties": {"label": "Houston, TX, USA"}}
        ]
    }
    fake.raise_for_status.return_value = None
    with patch("routing.ors_client.requests.get", return_value=fake):
        out = ors_client.geocode("Houston")
    assert out == {"label": "Houston, TX, USA", "lat": 29.76, "lng": -95.36}


@override_settings(ORS_API_KEY="test-key")
def test_geocode_no_features_raises():
    fake = MagicMock(status_code=200)
    fake.json.return_value = {"features": []}
    fake.raise_for_status.return_value = None
    with patch("routing.ors_client.requests.get", return_value=fake):
        with pytest.raises(GeocodingError):
            ors_client.geocode("xyzzy-no-such-place")


@override_settings(ORS_API_KEY="")
def test_geocode_missing_key_raises():
    with pytest.raises(GeocodingError):
        ors_client.geocode("Anywhere")


@override_settings(ORS_API_KEY="test-key")
def test_geocode_request_error_raises():
    import requests as r
    with patch("routing.ors_client.requests.get", side_effect=r.ConnectionError("boom")):
        with pytest.raises(GeocodingError):
            ors_client.geocode("Houston")


@override_settings(ORS_API_KEY="test-key")
def test_autocomplete_returns_results():
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "features": [
            {"geometry": {"coordinates": [-95.36, 29.76]}, "properties": {"label": "Houston, TX"}},
            {"geometry": {"coordinates": [-90.07, 29.95]}, "properties": {"label": "New Orleans, LA"}},
        ]
    }
    fake.raise_for_status.return_value = None
    with patch("routing.ors_client.requests.get", return_value=fake):
        out = ors_client.autocomplete("Hou")
    assert len(out) == 2
    assert out[0]["label"] == "Houston, TX"


@override_settings(ORS_API_KEY="")
def test_autocomplete_missing_key_returns_empty():
    assert ors_client.autocomplete("Hou") == []


@override_settings(ORS_API_KEY="test-key")
def test_autocomplete_swallows_errors():
    import requests as r
    with patch("routing.ors_client.requests.get", side_effect=r.Timeout("slow")):
        assert ors_client.autocomplete("Hou") == []


@override_settings(ORS_API_KEY="test-key")
def test_directions_parses_segments():
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "features": [
            {
                "geometry": {"coordinates": [[-96.8, 32.7], [-95.4, 29.8], [-84.4, 33.7]]},
                "properties": {
                    "summary": {"distance": 1_660_000, "duration": 60_000},
                    "segments": [
                        {"distance": 386_000, "duration": 14_000},
                        {"distance": 1_274_000, "duration": 46_000},
                    ],
                    "way_points": [0, 1, 2],
                },
            }
        ]
    }
    with patch("routing.ors_client.requests.post", return_value=fake):
        out = ors_client.directions([(-96.8, 32.7), (-95.4, 29.8), (-84.4, 33.7)])
    assert len(out["legs"]) == 2
    assert out["total_distance_mi"] > 1000
    assert out["legs"][0]["distance_mi"] < out["legs"][1]["distance_mi"]


@override_settings(ORS_API_KEY="test-key")
def test_directions_fallback_when_segments_missing():
    fake = MagicMock(status_code=200)
    fake.json.return_value = {
        "features": [
            {
                "geometry": {"coordinates": [[0, 0], [1, 1], [2, 2]]},
                "properties": {
                    "summary": {"distance": 100_000, "duration": 6_000},
                    "way_points": [0, 5, 10],
                    # No segments key
                },
            }
        ]
    }
    with patch("routing.ors_client.requests.post", return_value=fake):
        out = ors_client.directions([(0, 0), (1, 1), (2, 2)])
    assert len(out["legs"]) == 2
    # Fallback derives via way_points: half-half split
    assert abs(out["legs"][0]["distance_mi"] - out["legs"][1]["distance_mi"]) < 1


@override_settings(ORS_API_KEY="test-key")
def test_directions_4xx_raises_routing_error():
    fake = MagicMock(status_code=400)
    fake.text = "bad request"
    with patch("routing.ors_client.requests.post", return_value=fake):
        with pytest.raises(RoutingError):
            ors_client.directions([(0, 0), (1, 1), (2, 2)])


@override_settings(ORS_API_KEY="test-key")
def test_directions_too_few_coords_raises():
    with pytest.raises(RoutingError):
        ors_client.directions([(0, 0)])


@override_settings(ORS_API_KEY="")
def test_directions_missing_key_raises():
    with pytest.raises(RoutingError):
        ors_client.directions([(0, 0), (1, 1)])
