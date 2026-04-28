"""TripPlanRequestSerializer tests."""
import pytest

from trips.serializers import TripPlanRequestSerializer


def _base():
    return {
        "current_location": "Dallas, TX",
        "pickup_location": "Houston, TX",
        "dropoff_location": "Atlanta, GA",
        "current_cycle_hours": 10,
        "cycle_type": "70_8",
    }


def test_minimum_valid_payload():
    s = TripPlanRequestSerializer(data=_base())
    assert s.is_valid(), s.errors


def test_pickup_eq_dropoff_rejected():
    d = _base()
    d["dropoff_location"] = "Houston, TX"
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()
    assert "dropoff_location" in s.errors


def test_cycle_hours_over_70_rejected():
    d = _base()
    d["current_cycle_hours"] = 71
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()


def test_cycle_hours_over_60_rejected_for_60_7():
    d = _base()
    d["cycle_type"] = "60_7"
    d["current_cycle_hours"] = 65
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()


def test_cycle_hours_negative_rejected():
    d = _base()
    d["current_cycle_hours"] = -1
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()


def test_missing_required_field():
    d = _base()
    del d["pickup_location"]
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()
    assert "pickup_location" in s.errors


def test_invalid_cycle_type_rejected():
    d = _base()
    d["cycle_type"] = "100_10"
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()


def test_default_cycle_type_is_70_8():
    d = _base()
    del d["cycle_type"]
    s = TripPlanRequestSerializer(data=d)
    assert s.is_valid(), s.errors
    assert s.validated_data["cycle_type"] == "70_8"


def test_coord_pass_through_accepted():
    d = _base()
    d["pickup_coord"] = {"label": "Houston", "lat": 29.76, "lng": -95.36}
    s = TripPlanRequestSerializer(data=d)
    assert s.is_valid(), s.errors
    assert s.validated_data["pickup_coord"]["lat"] == 29.76


def test_coord_invalid_lat_rejected():
    d = _base()
    d["pickup_coord"] = {"label": "X", "lat": 95, "lng": 0}
    s = TripPlanRequestSerializer(data=d)
    assert not s.is_valid()
