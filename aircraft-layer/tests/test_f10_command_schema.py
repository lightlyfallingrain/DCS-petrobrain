"""Tests for `schema.F10CommandEvent` parsing/validation --
`plans/f10-crew-commands/plan.md`."""

from __future__ import annotations

import pytest

from schema import F10CommandEvent, F10CommandParseError


def test_from_dict_parses_command() -> None:
    event = F10CommandEvent.from_dict(
        {"command": "watch_nearest"}, received_wall_clock_s=1000.0
    )

    assert event.command == "watch_nearest"
    assert event.received_wall_clock_s == 1000.0


def test_to_dict_round_trips() -> None:
    event = F10CommandEvent(command="scan_forward", received_wall_clock_s=1000.0)

    assert event.to_dict() == {
        "command": "scan_forward",
        "received_wall_clock_s": 1000.0,
    }


def test_from_dict_missing_command_raises() -> None:
    with pytest.raises(F10CommandParseError):
        F10CommandEvent.from_dict({}, received_wall_clock_s=1000.0)


def test_from_dict_non_string_command_raises() -> None:
    with pytest.raises(F10CommandParseError):
        F10CommandEvent.from_dict({"command": 42}, received_wall_clock_s=1000.0)


def test_from_dict_empty_string_command_raises() -> None:
    with pytest.raises(F10CommandParseError):
        F10CommandEvent.from_dict({"command": ""}, received_wall_clock_s=1000.0)
