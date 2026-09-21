"""Tests for `schema.unit_velocity` -- `plans/movement-detection/plan.md`
Stage 1."""

from __future__ import annotations

import pytest

from schema.unit_velocity import (
    UnitVelocityParseError,
    UnitVelocitySnapshot,
)


def test_parses_well_formed_payload_with_multiple_entries() -> None:
    snapshot = UnitVelocitySnapshot.from_wire(
        "2|1234.5|Truck-1:1.0:0.0:2.0;Truck-2:-3.5:0.1:0.0",
        bridge_call_ms=4.2,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.dcs_model_time_s == 1234.5
    assert snapshot.received_wall_clock_s == 1000.0
    assert snapshot.unit_count == 2
    assert snapshot.bridge_call_ms == 4.2
    assert set(snapshot.samples) == {"Truck-1", "Truck-2"}
    assert snapshot.samples["Truck-1"].vx == 1.0
    assert snapshot.samples["Truck-1"].vy == 0.0
    assert snapshot.samples["Truck-1"].vz == 2.0
    assert snapshot.samples["Truck-2"].vx == -3.5


def test_parses_empty_entries() -> None:
    snapshot = UnitVelocitySnapshot.from_wire(
        "0|1234.5|", bridge_call_ms=0.1, received_wall_clock_s=1000.0
    )
    assert snapshot.unit_count == 0
    assert snapshot.samples == {}


def test_duplicate_unit_name_is_last_entry_wins() -> None:
    """Module docstring's documented resolution -- a dict has no other way
    to hold two values under one key."""
    snapshot = UnitVelocitySnapshot.from_wire(
        "2|1234.5|Truck-1:1.0:0.0:0.0;Truck-1:9.0:0.0:0.0",
        bridge_call_ms=0.1,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.samples["Truck-1"].vx == 9.0


def test_unit_name_containing_colon_is_handled_via_rsplit() -> None:
    snapshot = UnitVelocitySnapshot.from_wire(
        "1|1.0|Weird:Name:1.0:2.0:3.0",
        bridge_call_ms=0.1,
        received_wall_clock_s=1000.0,
    )
    assert snapshot.samples["Weird:Name"].vx == 1.0
    assert snapshot.samples["Weird:Name"].vy == 2.0
    assert snapshot.samples["Weird:Name"].vz == 3.0


@pytest.mark.parametrize(
    "payload",
    [
        "not-well-formed",
        "1|not-a-number|Truck-1:1.0:0.0:0.0",
        "not-an-int|1.0|Truck-1:1.0:0.0:0.0",
        "1|1.0|Truck-1:not-a-number:0.0:0.0",
        "1|1.0|:1.0:0.0:0.0",
    ],
)
def test_malformed_payload_raises(payload: str) -> None:
    with pytest.raises(UnitVelocityParseError):
        UnitVelocitySnapshot.from_wire(
            payload, bridge_call_ms=0.1, received_wall_clock_s=1000.0
        )


def test_to_dict_round_trips_samples() -> None:
    snapshot = UnitVelocitySnapshot.from_wire(
        "1|1234.5|Truck-1:1.0:0.0:2.0",
        bridge_call_ms=4.2,
        received_wall_clock_s=1000.0,
    )
    data = snapshot.to_dict()
    assert data["dcs_model_time_s"] == 1234.5
    assert data["unit_count"] == 1
    assert data["bridge_call_ms"] == 4.2
    assert data["samples"] == {"Truck-1": {"vx": 1.0, "vy": 0.0, "vz": 2.0}}
