"""Tests for `schema.WorldObjectsSnapshot`/`WorldObjectSample` parsing."""

from __future__ import annotations

import pytest

from schema import WorldObjectParseError, WorldObjectsSnapshot

VALID_LINE = (
    '{"t":123.5,"objects":['
    '{"id":7,"type":"BMP-2","coalition":1,'
    '"lat":35.1,"lon":35.9,"alt_m":50.0,"heading_true_rad":1.2},'
    '{"id":12,"type":"T-72B","coalition":1,'
    '"lat":35.2,"lon":36.0,"alt_m":60.0,"heading_true_rad":0.0}'
    "]}\n"
)


def test_from_json_line_parses_all_objects() -> None:
    snapshot = WorldObjectsSnapshot.from_json_line(
        VALID_LINE, received_wall_clock_s=1000.0
    )

    assert snapshot.dcs_model_time_s == 123.5
    assert snapshot.received_wall_clock_s == 1000.0
    assert len(snapshot.objects) == 2

    first = snapshot.objects[0]
    assert first.object_id == 7
    assert first.object_type == "BMP-2"
    assert first.coalition == 1.0
    assert first.lat_deg == 35.1
    assert first.lon_deg == 35.9
    assert first.altitude_m == 50.0
    assert first.heading_true_rad == 1.2
    assert first.is_ownship is None  # key absent from VALID_LINE entirely


def test_from_json_line_accepts_empty_objects_list() -> None:
    line = '{"t":1.0,"objects":[]}\n'

    snapshot = WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)

    assert snapshot.objects == ()


def test_from_json_line_accepts_string_coalition() -> None:
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"Structure","coalition":"red",'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0}]}\n'
    )

    snapshot = WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)

    assert snapshot.objects[0].coalition == "red"


def test_from_json_line_rejects_empty_line() -> None:
    with pytest.raises(WorldObjectParseError):
        WorldObjectsSnapshot.from_json_line("\n", received_wall_clock_s=1.0)


def test_from_json_line_rejects_invalid_json() -> None:
    with pytest.raises(WorldObjectParseError):
        WorldObjectsSnapshot.from_json_line("{not json", received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_object_json() -> None:
    with pytest.raises(WorldObjectParseError):
        WorldObjectsSnapshot.from_json_line("[1, 2, 3]", received_wall_clock_s=1.0)


def test_from_json_line_rejects_missing_t() -> None:
    line = '{"objects":[]}\n'

    with pytest.raises(WorldObjectParseError, match="missing required field"):
        WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_list_objects() -> None:
    line = '{"t":1.0,"objects":"nope"}\n'

    with pytest.raises(WorldObjectParseError, match="must be a list"):
        WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_object_missing_required_field() -> None:
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"x","coalition":1,"lat":1.0,"lon":2.0}]}\n'
    )

    with pytest.raises(WorldObjectParseError, match="missing required field"):
        WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_boolean_for_numeric_id() -> None:
    # bool is a subclass of int in Python -- must not silently pass isinstance(x, int|float).
    line = (
        '{"t":1.0,"objects":[{"id":true,"type":"x","coalition":1,'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0}]}\n'
    )

    with pytest.raises(WorldObjectParseError, match="must be a number"):
        WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_accepts_true_is_ownship() -> None:
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"Mi-24P","coalition":1,'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0,'
        '"is_ownship":true}]}\n'
    )

    snapshot = WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)

    assert snapshot.objects[0].is_ownship is True


def test_from_json_line_accepts_false_is_ownship() -> None:
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"BMP-2","coalition":1,'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0,'
        '"is_ownship":false}]}\n'
    )

    snapshot = WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)

    assert snapshot.objects[0].is_ownship is False


def test_from_json_line_accepts_null_is_ownship() -> None:
    # LoGetPlayerPlaneId() itself failed that poll -- genuinely unknown,
    # must not be coerced to False (see WorldObjectSample.is_ownship's
    # docstring).
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"BMP-2","coalition":1,'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0,'
        '"is_ownship":null}]}\n'
    )

    snapshot = WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)

    assert snapshot.objects[0].is_ownship is None


def test_from_json_line_rejects_non_boolean_is_ownship() -> None:
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"BMP-2","coalition":1,'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0,'
        '"is_ownship":"yes"}]}\n'
    )

    with pytest.raises(WorldObjectParseError, match="must be a boolean or null"):
        WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)


def test_to_dict_round_trips_is_ownship() -> None:
    line = (
        '{"t":1.0,"objects":[{"id":1,"type":"Mi-24P","coalition":1,'
        '"lat":1.0,"lon":2.0,"alt_m":3.0,"heading_true_rad":0.0,'
        '"is_ownship":true}]}\n'
    )

    snapshot = WorldObjectsSnapshot.from_json_line(line, received_wall_clock_s=1.0)

    assert snapshot.to_dict()["objects"][0]["is_ownship"] is True


def test_to_dict_round_trips_field_names() -> None:
    snapshot = WorldObjectsSnapshot.from_json_line(
        VALID_LINE, received_wall_clock_s=1000.0
    )

    data = snapshot.to_dict()

    assert data["dcs_model_time_s"] == 123.5
    assert data["received_wall_clock_s"] == 1000.0
    assert data["objects"][0]["object_id"] == 7
    assert data["objects"][0]["object_type"] == "BMP-2"
