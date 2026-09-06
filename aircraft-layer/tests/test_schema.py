"""Tests for `schema.TelemetrySample` parsing/validation."""

from __future__ import annotations

import pytest

from schema import TelemetryParseError, TelemetrySample

VALID_LINE = (
    '{"t":123.5,"x":1000.0,"y":500.0,"z":-2000.0,'
    '"pitch":0.01,"bank":-0.02,"yaw":0.0,"hdg":1.57,'
    '"ias":80.0,"tas":85.0,'
    '"alt_msl":600.0,"alt_agl":450.0,"alt_radar":448.5}\n'
)


def test_from_json_line_parses_all_fields() -> None:
    sample = TelemetrySample.from_json_line(VALID_LINE, received_wall_clock_s=1000.0)

    assert sample.dcs_model_time_s == 123.5
    assert sample.received_wall_clock_s == 1000.0
    assert sample.position_x_m == 1000.0
    assert sample.position_y_m == 500.0
    assert sample.position_z_m == -2000.0
    assert sample.pitch_rad == 0.01
    assert sample.bank_rad == -0.02
    assert sample.yaw_rad == 0.0
    assert sample.heading_true_rad == 1.57
    assert sample.ias_mps == 80.0
    assert sample.tas_mps == 85.0
    assert sample.altitude_msl_m == 600.0
    assert sample.altitude_agl_m == 450.0
    assert sample.altitude_radar_m == 448.5


def test_from_json_line_accepts_null_radar_altitude() -> None:
    line = VALID_LINE.replace('"alt_radar":448.5', '"alt_radar":null')

    sample = TelemetrySample.from_json_line(line, received_wall_clock_s=1000.0)

    assert sample.altitude_radar_m is None


def test_from_json_line_missing_radar_field_defaults_to_none() -> None:
    line = VALID_LINE.replace(',"alt_radar":448.5', "")

    sample = TelemetrySample.from_json_line(line, received_wall_clock_s=1000.0)

    assert sample.altitude_radar_m is None


def test_from_json_line_strips_whitespace_and_newline() -> None:
    sample = TelemetrySample.from_json_line(
        "  " + VALID_LINE + "  \n", received_wall_clock_s=1.0
    )

    assert sample.dcs_model_time_s == 123.5


def test_from_json_line_rejects_empty_line() -> None:
    with pytest.raises(TelemetryParseError):
        TelemetrySample.from_json_line("\n", received_wall_clock_s=1.0)


def test_from_json_line_rejects_invalid_json() -> None:
    with pytest.raises(TelemetryParseError):
        TelemetrySample.from_json_line("{not json", received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_object_json() -> None:
    with pytest.raises(TelemetryParseError):
        TelemetrySample.from_json_line("[1, 2, 3]", received_wall_clock_s=1.0)


def test_from_json_line_rejects_missing_required_field() -> None:
    line = VALID_LINE.replace('"t":123.5,', "")

    with pytest.raises(TelemetryParseError, match="missing required field"):
        TelemetrySample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_numeric_required_field() -> None:
    line = VALID_LINE.replace('"t":123.5', '"t":"not a number"')

    with pytest.raises(TelemetryParseError, match="must be a number"):
        TelemetrySample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_boolean_for_numeric_field() -> None:
    # bool is a subclass of int in Python -- must not silently pass isinstance(x, int|float).
    line = VALID_LINE.replace('"t":123.5', '"t":true')

    with pytest.raises(TelemetryParseError, match="must be a number"):
        TelemetrySample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_json_line_rejects_non_numeric_optional_field() -> None:
    line = VALID_LINE.replace('"alt_radar":448.5', '"alt_radar":"invalid"')

    with pytest.raises(TelemetryParseError, match="alt_radar"):
        TelemetrySample.from_json_line(line, received_wall_clock_s=1.0)


def test_from_dict_accepts_int_values() -> None:
    data = {
        "t": 100,
        "x": 1000,
        "y": 500,
        "z": -2000,
        "pitch": 0,
        "bank": 0,
        "yaw": 0,
        "hdg": 0,
        "ias": 80,
        "tas": 85,
        "alt_msl": 600,
        "alt_agl": 450,
    }

    sample = TelemetrySample.from_dict(data, received_wall_clock_s=1.0)

    assert sample.dcs_model_time_s == 100.0
    assert isinstance(sample.dcs_model_time_s, float)
