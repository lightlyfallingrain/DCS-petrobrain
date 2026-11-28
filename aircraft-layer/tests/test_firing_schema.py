"""Tests for `schema.firing.FiringEventBatch` -- `plans/emitter-visibility/
plan.md` Stage B, `AC-B8`."""

from __future__ import annotations

import pytest

from schema.firing import (
    MAX_OWN_WEAPON_TYPE_NAME_LEN,
    FiringEventBatch,
    FiringParseError,
    MissionClockSample,
    OwnWeaponRawEvent,
)


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


def test_mission_clock_absent_by_default() -> None:
    batch = FiringEventBatch.from_wire(
        "0|120.5|", bridge_call_ms=1.2, received_wall_clock_s=99.0
    )
    assert batch.mission_clock is None


def test_mission_clock_parses_from_wire() -> None:
    batch = FiringEventBatch.from_wire(
        "0|120.5|",
        bridge_call_ms=1.2,
        received_wall_clock_s=99.0,
        mission_clock_raw="18300.5|2020|6|1",
    )
    assert batch.mission_clock == MissionClockSample(
        abs_time_s=18300.5, year=2020, month=6, day=1
    )


def test_mission_clock_unavailable_sentinel_parses_to_none() -> None:
    batch = FiringEventBatch.from_wire(
        "0|120.5|",
        bridge_call_ms=1.2,
        received_wall_clock_s=99.0,
        mission_clock_raw="unavailable",
    )
    assert batch.mission_clock is None


def test_mission_clock_malformed_sub_wire_is_dropped_not_raised() -> None:
    """A malformed `mission_clock` sub-wire drops to `None` -- it does not
    fail the rest of the batch, mirroring `LineOfSightSnapshot.from_wire`'s
    own `probes` posture."""
    batch = FiringEventBatch.from_wire(
        "1|60.3|S_EVENT_SHOOTING_START:60.3:Unit_013:1:nil:nil",
        bridge_call_ms=0.5,
        received_wall_clock_s=1.0,
        mission_clock_raw="garbage",
    )
    assert batch.mission_clock is None
    assert len(batch.events) == 1


class TestMissionClockSample:
    def test_from_wire_round_trips(self) -> None:
        sample = MissionClockSample.from_wire("12345.6|2024|1|1")
        assert sample == MissionClockSample(
            abs_time_s=12345.6, year=2024, month=1, day=1
        )

    def test_unavailable_sentinel_is_none(self) -> None:
        assert MissionClockSample.from_wire("unavailable") is None

    def test_wrong_field_count_raises(self) -> None:
        with pytest.raises(FiringParseError):
            MissionClockSample.from_wire("12345.6|2024|1")

    def test_non_numeric_field_raises(self) -> None:
        with pytest.raises(FiringParseError):
            MissionClockSample.from_wire("notanumber|2024|1|1")

    @pytest.mark.parametrize("abs_str", ["nan", "inf", "-inf", "Infinity"])
    def test_non_finite_abs_time_s_raises(self, abs_str: str) -> None:
        """`[[BL-B137]]` -- `float()` parses these strings without
        raising (unlike `int()` on `year`/`month`/`day`), and an
        unguarded NaN/Infinity here silently resolves, on the body-layer
        side, to a forced full-daylight light factor. Confirms the fix:
        `from_wire` now rejects them the same way it rejects any other
        malformed sub-wire."""
        with pytest.raises(FiringParseError):
            MissionClockSample.from_wire(f"{abs_str}|2024|1|1")

    def test_non_finite_abs_time_s_is_dropped_not_raised_at_batch_level(self) -> None:
        """Mirrors `test_mission_clock_malformed_sub_wire_is_dropped_not_
        raised` -- a non-finite `abs_time_s` drops the whole
        `mission_clock` sub-wire to `None` without failing the batch's
        other events, the same posture every other malformed sub-wire
        gets."""
        batch = FiringEventBatch.from_wire(
            "1|60.3|S_EVENT_SHOOTING_START:60.3:Unit_013:1:nil:nil",
            bridge_call_ms=0.5,
            received_wall_clock_s=1.0,
            mission_clock_raw="nan|2024|1|1",
        )
        assert batch.mission_clock is None
        assert len(batch.events) == 1

    def test_to_dict(self) -> None:
        sample = MissionClockSample(abs_time_s=1.0, year=2024, month=1, day=1)
        assert sample.to_dict() == {
            "abs_time_s": 1.0,
            "year": 2024,
            "month": 1,
            "day": 1,
        }


class TestOwnWeaponEvents:
    """`[[BL-B67]]` Stage 5 -- the own-weapon `own_events` fourth
    segment."""

    def test_three_segment_payload_parses_with_no_own_events(self) -> None:
        """A deployed Hook predating this stage sends only three
        segments -- the forward-compatible degrade the module docstring
        names."""
        batch = FiringEventBatch.from_wire(
            "0|12.5|", bridge_call_ms=1.0, received_wall_clock_s=2.0
        )
        assert batch.own_events == ()

    def test_own_shot_and_own_gone_parse(self) -> None:
        batch = FiringEventBatch.from_wire(
            "0|12.5||OWN_SHOT:12.3:5:Ataka_9M120:1:8:1;OWN_GONE:13.0:4",
            bridge_call_ms=1.0,
            received_wall_clock_s=2.0,
        )
        shot, gone = batch.own_events
        assert shot == OwnWeaponRawEvent(
            kind="OWN_SHOT",
            t_sim=12.3,
            seq=5,
            type_name="Ataka_9M120",
            category=1,
            guidance=8,
            exists_at_shot=True,
        )
        assert gone == OwnWeaponRawEvent(kind="OWN_GONE", t_sim=13.0, seq=4)

    def test_own_shot_with_nil_fields(self) -> None:
        """`typeName`/`category`/`guidance` all degrade to `None`
        independently -- the Hook's own guarded reads can each fail on
        their own."""
        batch = FiringEventBatch.from_wire(
            "0|1.0||OWN_SHOT:1.0:1:nil:nil:nil:0",
            bridge_call_ms=1.0,
            received_wall_clock_s=2.0,
        )
        (event,) = batch.own_events
        assert event.type_name is None
        assert event.category is None
        assert event.guidance is None
        assert event.exists_at_shot is False

    def test_unguided_rocket_shot_parses_like_any_other(self) -> None:
        """S-8 rockets also raise `S_EVENT_SHOT` -- category/guidance
        simply differ; nothing about parsing treats this specially (the
        guided-missile filter is `perception.own_weapons`'s job, not
        this module's)."""
        batch = FiringEventBatch.from_wire(
            "0|1.0||OWN_SHOT:1.0:1:C_8:2:nil:1",
            bridge_call_ms=1.0,
            received_wall_clock_s=2.0,
        )
        (event,) = batch.own_events
        assert event.category == 2
        assert event.guidance is None

    def test_unrecognized_own_entry_kind_raises(self) -> None:
        with pytest.raises(FiringParseError):
            FiringEventBatch.from_wire(
                "0|1.0||BOGUS:1.0:1",
                bridge_call_ms=1.0,
                received_wall_clock_s=2.0,
            )

    def test_own_gone_wrong_field_count_raises(self) -> None:
        with pytest.raises(FiringParseError):
            FiringEventBatch.from_wire(
                "0|1.0||OWN_GONE:1.0",
                bridge_call_ms=1.0,
                received_wall_clock_s=2.0,
            )

    def test_own_shot_wrong_field_count_raises(self) -> None:
        with pytest.raises(FiringParseError):
            FiringEventBatch.from_wire(
                "0|1.0||OWN_SHOT:1.0:1:nil:nil:nil",
                bridge_call_ms=1.0,
                received_wall_clock_s=2.0,
            )

    def test_own_weapon_type_name_at_the_bound_is_accepted(self) -> None:
        type_name = "x" * MAX_OWN_WEAPON_TYPE_NAME_LEN
        batch = FiringEventBatch.from_wire(
            f"0|1.0||OWN_SHOT:1.0:1:{type_name}:1:8:1",
            bridge_call_ms=1.0,
            received_wall_clock_s=2.0,
        )
        (event,) = batch.own_events
        assert event.type_name == type_name

    def test_own_weapon_type_name_over_the_bound_raises(self) -> None:
        """Security review carried-forward finding -- an independent
        parser-side bound on `<type>`, never trusting the Hook's own
        truncation happened."""
        type_name = "x" * (MAX_OWN_WEAPON_TYPE_NAME_LEN + 1)
        with pytest.raises(FiringParseError):
            FiringEventBatch.from_wire(
                f"0|1.0||OWN_SHOT:1.0:1:{type_name}:1:8:1",
                bridge_call_ms=1.0,
                received_wall_clock_s=2.0,
            )

    @pytest.mark.parametrize("bad_char", [":", ";", "|"])
    def test_own_weapon_type_name_with_forbidden_char_raises(
        self, bad_char: str
    ) -> None:
        with pytest.raises(FiringParseError):
            FiringEventBatch.from_wire(
                f"0|1.0||OWN_SHOT:1.0:1:bad{bad_char}name:1:8:1",
                bridge_call_ms=1.0,
                received_wall_clock_s=2.0,
            )

    def test_malformed_own_entry_fails_the_whole_batch(self) -> None:
        """Unlike a malformed `mission_clock` sub-wire, a malformed own-
        weapon entry is this feature's own Hook code, not a separately-
        evolving envelope key -- it fails the whole batch, module
        docstring."""
        with pytest.raises(FiringParseError):
            FiringEventBatch.from_wire(
                "1|60.3|S_EVENT_SHOOTING_START:60.3:Unit_013:1:nil:nil|BOGUS:1:1",
                bridge_call_ms=0.5,
                received_wall_clock_s=1.0,
            )
