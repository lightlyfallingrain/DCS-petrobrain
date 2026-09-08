"""Tests for `schema.PetrovichIndicationSample`/`parse_indication_text`."""

from __future__ import annotations

import json

import pytest

from schema import PetrovichIndicationParseError, PetrovichIndicationSample
from schema.petrovich_indication import parse_indication_text

DELIM = "-----------------------------------------"

# A hand-built recursive dump, matching the live-confirmed wire format
# (aircraft-layer/research/2026-09-08-pb1-live-spike-results.md finding 1):
# a populated leaf sibling (middle_list_text) next to a present-but-empty
# subtree (crosshair, no children at all).
RAW_DUMP = (
    f"{DELIM}\n"
    "middle_list_text\n"
    "Ural truck\n"
    "children are {\n"
    "}\n"
    f"{DELIM}\n"
    "lower_list_text\n"
    "BMP-2\n"
    "children are {\n"
    "}\n"
    f"{DELIM}\n"
    "crosshair\n"
    "children are {\n"
    "}"
)


def _line(t: float, raw: str) -> str:
    return json.dumps({"t": t, "indication": raw}) + "\n"


def test_parse_indication_text_extracts_populated_leaves() -> None:
    fields = parse_indication_text(RAW_DUMP)

    assert fields == {
        "middle_list_text": "Ural truck",
        "lower_list_text": "BMP-2",
    }


def test_parse_indication_text_ignores_childless_valueless_node() -> None:
    fields = parse_indication_text(RAW_DUMP)

    assert "crosshair" not in fields


def test_parse_indication_text_handles_nested_children() -> None:
    nested = (
        f"{DELIM}\n"
        "parent\n"
        "children are {\n"
        f"{DELIM}\n"
        "child_text\n"
        "T-72B\n"
        "children are {\n"
        "}\n"
        "}"
    )

    fields = parse_indication_text(nested)

    assert fields == {"child_text": "T-72B"}


def test_parse_indication_text_handles_empty_string() -> None:
    assert parse_indication_text("") == {}


def test_parse_indication_text_degrades_gracefully_on_garbage() -> None:
    # Not a raised error -- Export.lua pushes this string verbatim from an
    # unverified-in-detail DCS internal; a malformed dump should yield an
    # empty/partial record, not crash the parse.
    assert parse_indication_text("not the expected format at all") == {}


def test_from_json_line_parses_fields_and_timestamps() -> None:
    sample = PetrovichIndicationSample.from_json_line(
        _line(123.5, RAW_DUMP), received_wall_clock_s=1000.0
    )

    assert sample.dcs_model_time_s == 123.5
    assert sample.received_wall_clock_s == 1000.0
    assert sample.fields["middle_list_text"] == "Ural truck"


def test_from_json_line_rejects_empty_line() -> None:
    with pytest.raises(PetrovichIndicationParseError):
        PetrovichIndicationSample.from_json_line("\n", received_wall_clock_s=1.0)


def test_from_json_line_rejects_invalid_json() -> None:
    with pytest.raises(PetrovichIndicationParseError):
        PetrovichIndicationSample.from_json_line("{not json", received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_object_json() -> None:
    with pytest.raises(PetrovichIndicationParseError):
        PetrovichIndicationSample.from_json_line("[1, 2, 3]", received_wall_clock_s=1.0)


def test_from_json_line_rejects_missing_t() -> None:
    line = '{"indication":""}\n'

    with pytest.raises(PetrovichIndicationParseError, match="missing required field"):
        PetrovichIndicationSample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_missing_indication() -> None:
    line = '{"t":1.0}\n'

    with pytest.raises(PetrovichIndicationParseError, match="must be a string"):
        PetrovichIndicationSample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_string_indication() -> None:
    line = '{"t":1.0,"indication":42}\n'

    with pytest.raises(PetrovichIndicationParseError, match="must be a string"):
        PetrovichIndicationSample.from_json_line(line, received_wall_clock_s=1.0)


def test_to_dict_round_trips_field_names() -> None:
    sample = PetrovichIndicationSample.from_json_line(
        _line(123.5, RAW_DUMP), received_wall_clock_s=1000.0
    )

    data = sample.to_dict()

    assert data["dcs_model_time_s"] == 123.5
    assert data["received_wall_clock_s"] == 1000.0
    assert data["fields"]["middle_list_text"] == "Ural truck"
