"""Tests for `schema.PetrovichWheelSample` -- BL-6 (`plans/
bl6-commands-inspect-adapt/plan.md`). Reuses `parse_indication_text`'s own
tests (`test_petrovich_indication_schema.py`) for tree-parsing coverage --
this module only checks `PetrovichWheelSample`'s own wire-format contract
(the `"wheel"` key, not `"indication"`)."""

from __future__ import annotations

import json

import pytest

from schema import PetrovichWheelParseError, PetrovichWheelSample

DELIM = "-----------------------------------------"

RAW_DUMP = f"{DELIM}\nstate\nSEARCHING\nchildren are {{\n}}"


def _line(t: float, raw: str) -> str:
    return json.dumps({"t": t, "wheel": raw}) + "\n"


def test_from_json_line_parses_fields_and_timestamps() -> None:
    sample = PetrovichWheelSample.from_json_line(
        _line(123.5, RAW_DUMP), received_wall_clock_s=1000.0
    )

    assert sample.dcs_model_time_s == 123.5
    assert sample.received_wall_clock_s == 1000.0
    assert sample.fields["state"] == "SEARCHING"


def test_from_json_line_rejects_empty_line() -> None:
    with pytest.raises(PetrovichWheelParseError):
        PetrovichWheelSample.from_json_line("\n", received_wall_clock_s=1.0)


def test_from_json_line_rejects_invalid_json() -> None:
    with pytest.raises(PetrovichWheelParseError):
        PetrovichWheelSample.from_json_line("{not json", received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_object_json() -> None:
    with pytest.raises(PetrovichWheelParseError):
        PetrovichWheelSample.from_json_line("[1, 2, 3]", received_wall_clock_s=1.0)


def test_from_json_line_rejects_missing_t() -> None:
    line = '{"wheel":""}\n'

    with pytest.raises(PetrovichWheelParseError, match="missing required field"):
        PetrovichWheelSample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_missing_wheel() -> None:
    line = '{"t":1.0}\n'

    with pytest.raises(PetrovichWheelParseError, match="must be a string"):
        PetrovichWheelSample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_string_wheel() -> None:
    line = '{"t":1.0,"wheel":42}\n'

    with pytest.raises(PetrovichWheelParseError, match="must be a string"):
        PetrovichWheelSample.from_json_line(line, received_wall_clock_s=1.0)


def test_to_dict_round_trips_field_names() -> None:
    sample = PetrovichWheelSample.from_json_line(
        _line(123.5, RAW_DUMP), received_wall_clock_s=1000.0
    )

    data = sample.to_dict()

    assert data["dcs_model_time_s"] == 123.5
    assert data["received_wall_clock_s"] == 1000.0
    assert data["fields"]["state"] == "SEARCHING"
