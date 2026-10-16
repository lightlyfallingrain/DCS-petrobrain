"""Tests for `schema.firing.FiringEventBatch` -- `plans/emitter-visibility/
plan.md` Stage B, `AC-B8`."""

from __future__ import annotations

import pytest

from schema.firing import FiringEventBatch, FiringParseError


def test_empty_entries_is_a_well_formed_empty_batch() -> None:
    batch = FiringEventBatch.from_wire(
        "0|120.5|", bridge_call_ms=1.2, received_wall_clock_s=99.0
    )
    assert batch.dcs_model_time_s == 120.5
    assert batch.bridge_call_ms == 1.2
    assert batch.received_wall_clock_s == 99.0
    assert batch.events == ()


def test_one_shooting_start_targeting_ownship() -> None:
    batch = FiringEventBatch.from_wire(
        "1|60.3|S_EVENT_SHOOTING_START:60.3:Unit_013:1:nil:nil",
        bridge_call_ms=0.5,
        received_wall_clock_s=1.0,
    )
    (event,) = batch.events
    assert event.kind == "S_EVENT_SHOOTING_START"
    assert event.t_sim == 60.3
    assert event.initiator == "Unit_013"
    assert event.targets_ownship is True
    assert event.x is None
    assert event.z is None


def test_shot_event_carries_a_frozen_position() -> None:
    batch = FiringEventBatch.from_wire(
        "1|10.0|S_EVENT_SHOT:10.0:SAM-1:0:1234.5:-678.9",
        bridge_call_ms=0.5,
        received_wall_clock_s=1.0,
    )
    (event,) = batch.events
    assert event.kind == "S_EVENT_SHOT"
    assert event.x == 1234.5
    assert event.z == -678.9
    assert event.targets_ownship is False


def test_initiator_name_containing_a_colon_is_handled() -> None:
    """Mission-editor unit names are free text -- the same defensive
    posture `unit_velocity.py`/`line_of_sight.py` already take."""
    batch = FiringEventBatch.from_wire(
        "1|5.0|S_EVENT_SHOOTING_END:5.0:Unit: With: Colons:0:nil:nil",
        bridge_call_ms=0.5,
        received_wall_clock_s=1.0,
    )
    (event,) = batch.events
    assert event.initiator == "Unit: With: Colons"


def test_multiple_events_in_one_batch() -> None:
    batch = FiringEventBatch.from_wire(
        "2|60.0|"
        "S_EVENT_SHOOTING_START:60.0:Unit_1:0:nil:nil;"
        "S_EVENT_SHOOTING_END:60.5:Unit_1:0:nil:nil",
        bridge_call_ms=0.5,
        received_wall_clock_s=1.0,
    )
    assert len(batch.events) == 2
    assert batch.events[0].kind == "S_EVENT_SHOOTING_START"
    assert batch.events[1].kind == "S_EVENT_SHOOTING_END"


def test_unrecognized_kind_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "1|1.0|S_EVENT_UNKNOWN:1.0:Unit_1:0:nil:nil",
            bridge_call_ms=0.5,
            received_wall_clock_s=1.0,
        )


def test_empty_initiator_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "1|1.0|S_EVENT_SHOOTING_START::1.0:0:nil:nil",
            bridge_call_ms=0.5,
            received_wall_clock_s=1.0,
        )


def test_malformed_targets_ownship_flag_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "1|1.0|S_EVENT_SHOOTING_START:1.0:Unit_1:yes:nil:nil",
            bridge_call_ms=0.5,
            received_wall_clock_s=1.0,
        )


def test_malformed_x_field_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "1|1.0|S_EVENT_SHOT:1.0:Unit_1:0:not-a-number:0.0",
            bridge_call_ms=0.5,
            received_wall_clock_s=1.0,
        )


def test_malformed_envelope_shape_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "not-enough-pipes", bridge_call_ms=0.5, received_wall_clock_s=1.0
        )


def test_non_numeric_count_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "notanumber|1.0|", bridge_call_ms=0.5, received_wall_clock_s=1.0
        )


def test_non_numeric_model_time_raises() -> None:
    with pytest.raises(FiringParseError):
        FiringEventBatch.from_wire(
            "0|notanumber|", bridge_call_ms=0.5, received_wall_clock_s=1.0
        )
