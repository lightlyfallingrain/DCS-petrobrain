"""Tests for `schema.line_of_sight` -- `plans/dcs-driven-los/plan.md`
(X-B29)."""

from __future__ import annotations

import pytest

from schema.line_of_sight import (
    LineOfSightParseError,
    LineOfSightSnapshot,
    ProbeAnswers,
)


def test_parses_well_formed_payload_with_multiple_entries() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "172|12|12|3|45|1234.5|Truck-1:1:0;Truck-2:0:1",
        bridge_call_ms=1.6,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.dcs_model_time_s == 1234.5
    assert snapshot.received_wall_clock_s == 1000.0
    assert snapshot.hour_used == 3
    assert snapshot.fov_half_deg_used == 45
    assert snapshot.units_in_bubble == 172
    assert snapshot.units_in_wedge == 12
    assert snapshot.sightlines_computed == 12
    assert snapshot.bridge_call_ms == 1.6
    assert snapshot.verdicts["Truck-1"].building_clear is True
    assert snapshot.verdicts["Truck-1"].terrain_clear is False
    assert snapshot.verdicts["Truck-2"].building_clear is False
    assert snapshot.verdicts["Truck-2"].terrain_clear is True


def test_parses_empty_entries() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "0|0|0|0|45|1234.5|",
        bridge_call_ms=0.3,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts == {}
    assert snapshot.units_in_bubble == 0


def test_duplicate_unit_name_is_last_entry_wins() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Truck-1:1:1;Truck-1:0:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts["Truck-1"].building_clear is False
    assert snapshot.verdicts["Truck-1"].terrain_clear is False


@pytest.mark.parametrize(
    "payload",
    [
        "172|12|12|3|45|1234.5",  # missing a field
        "not_an_int|12|12|3|45|1234.5|",
        "172|12|12|3|45|not_a_float|",
        "172|12|12|3|45|1234.5|Truck-1:1",  # entry missing a flag
        "172|12|12|3|45|1234.5|Truck-1:2:1",  # flag not 0/1
        "172|12|12|3|45|1234.5|:1:1",  # empty unit_name
        # A ';' inside a unit_name splits one entry into two fragments, and
        # neither is a valid entry. Guarded Hook-side now (see the blast-radius
        # test below for why that is the only place it can be fixed).
        "172|12|12|3|45|1234.5|Depot; South:1:1",
    ],
)
def test_malformed_payloads_raise(payload: str) -> None:
    with pytest.raises(LineOfSightParseError):
        LineOfSightSnapshot.from_wire(
            payload, bridge_call_ms=1.0, received_wall_clock_s=1000.0
        )


def test_a_semicolon_in_one_name_costs_the_whole_poll() -> None:
    """One ';' in one mission-author object name discards *every* verdict in
    that poll, not just its own entry -- the parse raises from inside
    `from_wire`, so the well-formed entries alongside it are unrecoverable.

    That blast radius is why the fix lives in the Hook's `considerCandidate`
    (which drops the one offending object and counts it as `name_rejects`)
    rather than here: this wire format has no escaping, and the parser's
    strictness is correct. Mission-editor names are free text, so this input
    is reachable from any mission this project does not control.

    Kept as a test rather than prose because a later tidy-up of the entry
    split would silently reintroduce it. Found by the 2026-10-08 security
    deep analysis of `fix/los-hook-statics`.
    """
    with pytest.raises(LineOfSightParseError):
        LineOfSightSnapshot.from_wire(
            "172|2|2|3|45|1234.5|Depot; South:1:1;Truck-1:1:0",
            bridge_call_ms=1.0,
            received_wall_clock_s=1000.0,
        )

    # The same poll minus the offending object -- what the Hook now sends --
    # parses, and Truck-1's verdict survives. This is the pair that makes the
    # test meaningful: without it, the raise above could be read as the
    # payload being malformed for some unrelated reason.
    snapshot = LineOfSightSnapshot.from_wire(
        "172|2|1|3|45|1234.5|Truck-1:1:0",
        bridge_call_ms=1.0,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts["Truck-1"].building_clear is True
    assert snapshot.verdicts["Truck-1"].terrain_clear is False


def test_to_dict_round_trip_shape() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Truck-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    data = snapshot.to_dict()
    assert data["verdicts"] == {
        "Truck-1": {
            "building_clear": True,
            "terrain_clear": False,
            "agl_m": None,
        }
    }
    assert data["hour_used"] == 0
    assert data["fov_half_deg_used"] == 45


def test_entry_with_agl_m_parses() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0:8.5",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts["Heli-1"].agl_m == 8.5
    assert snapshot.verdicts["Heli-1"].building_clear is True
    assert snapshot.verdicts["Heli-1"].terrain_clear is False


def test_entry_with_empty_agl_m_is_none() -> None:
    # The Hook's own land.getHeight pcall failed that poll -- never
    # coerced to 0.0.
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0:",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts["Heli-1"].agl_m is None


def test_entry_without_agl_field_is_none() -> None:
    # A pre-Stage-5 Hook script, three fields only.
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts["Heli-1"].agl_m is None


def test_entry_with_negative_agl_m_parses() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0:-3.2",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.verdicts["Heli-1"].agl_m == -3.2


def test_to_dict_round_trips_agl_m() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0:8.5",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.to_dict()["verdicts"]["Heli-1"]["agl_m"] == 8.5


# --- Point probes (`plans/expected-area-look/plan.md`, BL-B111, Stage 1) ---


def test_probes_absent_when_no_probes_raw_given() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.probes is None


def test_probes_absent_when_probes_raw_is_empty_string() -> None:
    # `N == 0` on the Hook side -- "no check open", not a malformed wire.
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
        probes_raw="",
    )
    assert snapshot.probes is None


def test_probes_parses_well_formed_sub_wire() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1234.5|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
        probes_raw="7|0:1;1:0;2:",
    )
    assert snapshot.probes is not None
    assert snapshot.probes.seq == 7
    # Shares this snapshot's own dcs_model_time_s -- not a second wire
    # field (module docstring: "not repeated on this sub-wire").
    assert snapshot.probes.dcs_model_time_s == 1234.5
    assert snapshot.probes.clear[0] is True
    assert snapshot.probes.clear[1] is False
    assert snapshot.probes.clear[2] is None
    # Every index this sub-wire did not mention stays None (fail closed).
    assert snapshot.probes.clear[3] is None
    assert snapshot.probes.clear[4] is None
    assert snapshot.probes.clear[5] is None
    assert len(snapshot.probes.clear) == 6


def test_probes_malformed_sub_wire_drops_probes_only_not_the_snapshot() -> None:
    """A bad `probes_raw` must not reject the (valid) LOS payload this
    method already parsed -- module docstring's own "a bad probe
    sub-wire says nothing about whether the LOS payload itself parsed"
    promise."""
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1234.5|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
        probes_raw="not_an_int|0:1",
    )
    assert snapshot.probes is None
    assert snapshot.verdicts["Heli-1"].building_clear is True


def test_probes_out_of_range_index_raises_in_from_wire_directly() -> None:
    with pytest.raises(LineOfSightParseError):
        ProbeAnswers.from_wire("1|6:1", dcs_model_time_s=1.0)


def test_probes_bad_flag_raises_in_from_wire_directly() -> None:
    with pytest.raises(LineOfSightParseError):
        ProbeAnswers.from_wire("1|0:maybe", dcs_model_time_s=1.0)


def test_probes_to_dict_round_trips() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1234.5|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
        probes_raw="3|0:1",
    )
    as_dict = snapshot.to_dict()["probes"]
    assert as_dict["seq"] == 3
    assert as_dict["dcs_model_time_s"] == 1234.5
    assert as_dict["clear"][0] is True
    assert as_dict["clear"][1] is None


def test_to_dict_probes_is_none_when_absent() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Heli-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.to_dict()["probes"] is None
