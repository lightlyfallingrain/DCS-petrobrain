"""Tests for `schema.line_of_sight` -- `plans/dcs-driven-los/plan.md`
(X-B29)."""

from __future__ import annotations

import pytest

from schema.line_of_sight import (
    LineOfSightParseError,
    LineOfSightSnapshot,
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
    ],
)
def test_malformed_payloads_raise(payload: str) -> None:
    with pytest.raises(LineOfSightParseError):
        LineOfSightSnapshot.from_wire(
            payload, bridge_call_ms=1.0, received_wall_clock_s=1000.0
        )


def test_to_dict_round_trip_shape() -> None:
    snapshot = LineOfSightSnapshot.from_wire(
        "1|1|1|0|45|1.0|Truck-1:1:0",
        bridge_call_ms=0.5,
        received_wall_clock_s=1000.0,
    )
    data = snapshot.to_dict()
    assert data["verdicts"] == {
        "Truck-1": {"building_clear": True, "terrain_clear": False}
    }
    assert data["hour_used"] == 0
    assert data["fov_half_deg_used"] == 45
