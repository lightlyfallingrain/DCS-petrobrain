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
        sequence=2, theatre="Afghanistan", received_wall_clock_s=1000.0
    )

    assert event.to_dict() == {
        "sequence": 2,
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
