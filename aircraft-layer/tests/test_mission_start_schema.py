"""Tests for `schema.MissionStartEvent` parsing/validation --
`plans/bl15-mission-start/plan.md` (BL-15 Stage 1)."""

from __future__ import annotations

import pytest

from schema import MissionStartEvent, MissionStartParseError


def test_from_dict_parses_sequence_and_theatre() -> None:
    event = MissionStartEvent.from_dict(
        {"sequence": 3, "theatre": "Syria"}, received_wall_clock_s=1000.0
    )

    assert event.sequence == 3
    assert event.theatre == "Syria"
    assert event.received_wall_clock_s == 1000.0


def test_from_dict_accepts_null_theatre() -> None:
    event = MissionStartEvent.from_dict(
        {"sequence": 1, "theatre": None}, received_wall_clock_s=1000.0
    )

    assert event.theatre is None


def test_to_dict_round_trips() -> None:
    event = MissionStartEvent(
        sequence=2,
        theatre="Afghanistan",
        received_wall_clock_s=1000.0,
        qnh=750.0,
        atmosphere_type=0,
    )

    assert event.to_dict() == {
        "sequence": 2,
        "qnh": 750.0,
        "atmosphere_type": 0,
        "theatre": "Afghanistan",
        "received_wall_clock_s": 1000.0,
    }


def test_from_dict_missing_sequence_raises() -> None:
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict({"theatre": None}, received_wall_clock_s=1000.0)


def test_from_dict_non_int_sequence_raises() -> None:
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict(
            {"sequence": "1", "theatre": None}, received_wall_clock_s=1000.0
        )


def test_from_dict_bool_sequence_raises() -> None:
    """`isinstance(True, int)` is `True` in Python -- the explicit `bool`
    exclusion this test guards matches every other numeric field parser in
    this codebase (e.g. `unit_velocity.py`'s `bridge_call_ms` check)."""
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict(
            {"sequence": True, "theatre": None}, received_wall_clock_s=1000.0
        )


def test_from_dict_non_string_theatre_raises() -> None:
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict(
            {"sequence": 1, "theatre": 42}, received_wall_clock_s=1000.0
        )


def test_from_dict_missing_theatre_defaults_to_none() -> None:
    """`theatre` is absent entirely (not just `null`) -- same lenient
    `.get()` handling as a genuinely-null value, matching the module
    docstring's "null when the Hook script could not resolve it"."""
    event = MissionStartEvent.from_dict({"sequence": 1}, received_wall_clock_s=1000.0)

    assert event.theatre is None


def test_from_dict_parses_qnh_and_atmosphere_type() -> None:
    """`[[BL-B118]]` -- a present, numeric `qnh` (an `int` in the wire
    payload is accepted and coerced to `float`, same as `qnh = 750` in the
    shipped `.miz`) and `atmosphere_type`."""
    event = MissionStartEvent.from_dict(
        {"sequence": 3, "theatre": "Syria", "qnh": 750, "atmosphere_type": 0},
        received_wall_clock_s=1000.0,
    )

    assert event.qnh == 750.0
    assert isinstance(event.qnh, float)
    assert event.atmosphere_type == 0


def test_from_dict_accepts_null_qnh_and_atmosphere_type() -> None:
    event = MissionStartEvent.from_dict(
        {"sequence": 1, "theatre": None, "qnh": None, "atmosphere_type": None},
        received_wall_clock_s=1000.0,
    )

    assert event.qnh is None
    assert event.atmosphere_type is None


def test_from_dict_missing_qnh_and_atmosphere_type_default_to_none() -> None:
    """Same lenient `.get()` handling as a missing `theatre` -- absent
    entirely, not just `null`."""
    event = MissionStartEvent.from_dict(
        {"sequence": 1, "theatre": None}, received_wall_clock_s=1000.0
    )

    assert event.qnh is None
    assert event.atmosphere_type is None


def test_from_dict_non_numeric_qnh_raises() -> None:
    """Rejected the same way a non-string `theatre` is."""
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict(
            {"sequence": 1, "theatre": None, "qnh": "750"},
            received_wall_clock_s=1000.0,
        )


def test_from_dict_bool_qnh_raises() -> None:
    """`isinstance(True, int)` is `True` in Python -- same bool exclusion
    as `sequence`'s own check."""
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict(
            {"sequence": 1, "theatre": None, "qnh": True},
            received_wall_clock_s=1000.0,
        )


def test_from_dict_non_int_atmosphere_type_raises() -> None:
    with pytest.raises(MissionStartParseError):
        MissionStartEvent.from_dict(
            {"sequence": 1, "theatre": None, "atmosphere_type": "1"},
            received_wall_clock_s=1000.0,
        )
