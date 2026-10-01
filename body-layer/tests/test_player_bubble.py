"""Tests for the player bubble (`todo/todo.md`, "Player bubble: 10 km,
settled 2026-09-28") at the level where it actually matters: a running
`NakedEyePerceptionSource`/`HybridPerceptionSource` poll, not just
`association.filter_player_bubble`'s own pure boundary logic (covered in
`test_association.py`).

Three things this file exists to pin, each named in the todo item as a
misreading that would be expensive if missed:

1. A candidate beyond the bubble is never handed to `check_visibility` at
   all -- it gets exactly one `PLAYER_BUBBLE` trace row, not a
   `RANGE_OR_SIZE`/`COCKPIT_MASK`/... row the gate chain would have
   produced had it run.
2. A contact observed inside the bubble and then left behind outside it is
   not forgotten -- `ContactStore` keeps it (BL-8's eventual decay/lifecycle
   machinery, not this feature, owns what happens to its certainty).
3. World-model geography (reached by proximity to a contact, never by
   scanning a candidate pool) has no seam into the bubble at all.

Fixture/monkeypatch posture mirrors `test_naked_eye_source.py`/
`test_emission_pipeline.py`: `association.wgs84_to_dcs` is identity-mapped
so `lat_deg`/`lon_deg` pass straight through as DCS-native x/z, and
`visibility.line_of_sight_clear` always returns `True` (no real world-model
`.sqlite` needed).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Final

import pytest

from belief.contacts import ContactStore
from perception import association, visibility
from perception.association import PLAYER_BUBBLE_RADIUS_M
from perception.detection_trace import DetectionTraceCollector, GateOutcome
from perception.hybrid_source import HybridPerceptionSource
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.source import OwnshipState

_THEATRE = "Syria"
_FAKE_CONN = sqlite3.connect(":memory:")


def _ownship() -> OwnshipState:
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _world_object(object_id: int, *, range_m: float) -> dict[str, Any]:
    # Dead ahead (lon_deg=0) so the default scan plan's dead-ahead gaze
    # cone never interferes with this file's own concern (the bubble, not
    # gaze) -- same placement choice test_emission_pipeline.py makes.
    return {
        "object_id": object_id,
        "object_type": "Infantry",
        "coalition": 1.0,
        "lat_deg": range_m,
        "lon_deg": 0.0,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": False,
    }


class FakeAircraftClient:
    def __init__(self, world_objects: dict[str, Any] | None) -> None:
        self._world_objects = world_objects

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        return self._world_objects

    def get_unit_velocity_latest(self) -> dict[str, Any] | None:
        return None

    def get_petrovich_indication_latest(self) -> dict[str, Any] | None:
        return {
            "fields": {"middle_list_text": "Infantry"},
        }


@pytest.fixture(autouse=True)
def identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


@pytest.fixture(autouse=True)
def clear_line_of_sight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: True)


# --- 1. Beyond the bubble is never handed to check_visibility -------------


def test_candidate_beyond_bubble_is_never_passed_to_check_visibility() -> None:
    world_objects = {
        "objects": [_world_object(1, range_m=PLAYER_BUBBLE_RADIUS_M + 1.0)]
    }
    client = FakeAircraftClient(world_objects)
    collector = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        trace_sink=collector,
    )

    observations = source.poll(0.0, _ownship())

    assert observations == []
    assert len(collector.records) == 1
    entry = collector.records[0]
    assert entry.outcome is GateOutcome.PLAYER_BUBBLE
    assert entry.range_threshold_m == PLAYER_BUBBLE_RADIUS_M
    assert entry.threshold_bound == "player_bubble"


def test_candidate_inside_bubble_still_reaches_check_visibility() -> None:
    # Infantry's own naked-eye lowres threshold is well under 10 km, so an
    # in-bubble candidate at a range check_visibility's own angular-size
    # gate rejects still proves the point: it got a RANGE_OR_SIZE row, not
    # PLAYER_BUBBLE -- the bubble did not short-circuit it.
    world_objects = {
        "objects": [_world_object(1, range_m=PLAYER_BUBBLE_RADIUS_M - 1.0)]
    }
    client = FakeAircraftClient(world_objects)
    collector = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        trace_sink=collector,
    )

    source.poll(0.0, _ownship())

    assert len(collector.records) == 1
    assert collector.records[0].outcome is not GateOutcome.PLAYER_BUBBLE


def test_hybrid_source_never_associates_a_candidate_beyond_the_bubble() -> None:
    # The hybrid channel has no trace instrumentation (CLAUDE.md: "only the
    # naked-eye channel is traced"), so the observable proof here is the
    # outcome: a detection whose only plausible world object sits beyond
    # the bubble is dropped, the same as if no candidate existed at all.
    world_objects = {
        "objects": [_world_object(1, range_m=PLAYER_BUBBLE_RADIUS_M + 1.0)]
    }
    client = FakeAircraftClient(world_objects)
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    assert source.poll(0.0, _ownship()) == []


# --- 2. Memory outlives the bubble -----------------------------------------


_INSIDE_RANGE_M: Final[float] = 100.0
_OUTSIDE_RANGE_M: Final[float] = PLAYER_BUBBLE_RADIUS_M + 500.0


def test_contact_that_drifts_outside_the_bubble_is_not_forgotten() -> None:
    """A contact observed inside the bubble, then left behind outside it on
    a later poll, must still be in `ContactStore.contacts` -- the bubble
    stops *detection computation*, never belief. Mirrors
    `test_emission_pipeline.py`'s real-source-plus-real-store integration
    posture."""
    client = FakeAircraftClient(None)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )
    store = ContactStore()

    client._world_objects = {"objects": [_world_object(1, range_m=_INSIDE_RANGE_M)]}
    first_observations = source.poll(0.0, _ownship())
    assert len(first_observations) == 1
    store.ingest(first_observations, now_sim=0.0)
    store.tick(0.0)
    assert len(store.contacts) == 1
    contact_id = store.contacts[0].id

    # Same object_id, now beyond the bubble -- as far as this poll's
    # computation is concerned, nothing was ever there.
    client._world_objects = {"objects": [_world_object(1, range_m=_OUTSIDE_RANGE_M)]}
    later_observations = source.poll(1.0, _ownship())
    assert later_observations == []
    store.ingest(later_observations, now_sim=1.0)
    store.tick(1.0)

    assert len(store.contacts) == 1
    assert store.contacts[0].id == contact_id


def test_source_object_permanence_state_is_not_cleared_by_the_bubble() -> None:
    # The perception-layer continuity map (`_object_id_to_last_observation_
    # id`, naked_eye_source.py module docstring point 6) is never cleared
    # on a gap -- only a missing world_objects snapshot entirely resets the
    # *visible-set* debounce state (poll()'s own docstring). A candidate
    # the bubble drops is exactly this kind of ordinary gap, not a special
    # case that should wipe anything.
    client = FakeAircraftClient(
        {"objects": [_world_object(1, range_m=_INSIDE_RANGE_M)]}
    )
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )
    source.poll(0.0, _ownship())
    assert source._object_id_to_last_observation_id

    client._world_objects = {"objects": [_world_object(1, range_m=_OUTSIDE_RANGE_M)]}
    source.poll(1.0, _ownship())

    assert source._object_id_to_last_observation_id


# --- 3. World features have no seam into the bubble at all ----------------


def test_enrichment_module_never_references_the_player_bubble() -> None:
    # World-model geography (landmarks, settlements, roads, beacons,
    # airports) is reached by proximity to a contact (belief.enrichment),
    # never by scanning a WorldObjectCandidate pool -- the bubble only ever
    # filters that pool (association.WorldObjectCandidate lists built from
    # LoGetWorldObjects). A name check against the module's own namespace
    # catches an accidental future import, not a substring search over
    # prose that might legitimately discuss the two in the same sentence.
    from belief import enrichment

    assert "PLAYER_BUBBLE_RADIUS_M" not in dir(enrichment)
    assert "filter_player_bubble" not in dir(enrichment)
