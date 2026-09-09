"""Tests for `perception.naked_eye_source.NakedEyePerceptionSource` and its
private bearing/range quantisation helpers.

Uses a fake `AircraftLayerClient`-shaped object (duck-typed, matching
`get_world_objects_latest`) -- no network I/O, mirroring
`test_hybrid_source.py`'s fake-client pattern. `association.wgs84_to_dcs`
is monkeypatched to an identity mapping (lat/lon pass straight through as
x/z) so candidate positions are plain numbers, and
`visibility.line_of_sight_clear` is monkeypatched to always return `True`
(no real world-model `.sqlite` needed) -- both mirroring
`test_hybrid_source.py`/`test_visibility.py`'s own fixture posture. The real
`visibility.check_visibility` still runs, so these tests exercise the whole
poll() pipeline (visibility filtering + quantisation + debounce + cap) with
a genuine, un-mocked detectability decision underneath.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from perception import association, visibility
from perception.naked_eye_source import (
    NAKED_EYE_MAX_NEW_PER_POLL,
    PROVENANCE_VISIBILITY_FILTER_ONLY,
    NakedEyePerceptionSource,
    _quantise_bearing,
    _quantise_range_m,
)
from perception.source import SOURCE_NAKED_EYE_VISUAL_FILTERED, OwnshipState

_THEATRE = "Syria"
_FAKE_CONN = sqlite3.connect(":memory:")


def _ownship() -> OwnshipState:
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _world_object(
    object_id: int, object_type: str, *, lat_deg: float, lon_deg: float
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": object_type,
        "coalition": 1.0,
        "lat_deg": lat_deg,
        "lon_deg": lon_deg,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
    }


class FakeAircraftClient:
    def __init__(self, world_objects: dict[str, Any] | None) -> None:
        self._world_objects = world_objects
        self.world_objects_calls = 0

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        self.world_objects_calls += 1
        return self._world_objects


@pytest.fixture(autouse=True)
def identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


@pytest.fixture(autouse=True)
def clear_line_of_sight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: True)


def _source(
    world_objects: dict[str, Any] | None,
) -> tuple[NakedEyePerceptionSource, FakeAircraftClient]:
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )
    return source, client


def test_no_world_objects_snapshot_returns_empty() -> None:
    source, _client = _source(None)

    assert source.poll(100.0, _ownship()) == []


def test_no_visible_candidates_returns_empty() -> None:
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=6000.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    assert source.poll(100.0, _ownship()) == []


def test_a_newly_visible_candidate_emits_one_observation() -> None:
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.source == SOURCE_NAKED_EYE_VISUAL_FILTERED
    assert obs.classification_raw == "OP_INFANTRY"
    assert obs.provenance == PROVENANCE_VISIBILITY_FILTER_ONLY
    assert obs.derived_world_position is not None
    assert obs.derived_world_position.x == 500.0
    assert obs.derived_world_position.z == 0.0


def test_still_visible_candidate_is_not_re_emitted_on_the_next_poll() -> None:
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == 1
    assert second == []


def test_candidate_leaving_and_re_entering_the_visible_set_re_emits() -> None:
    visible = {"objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]}
    empty: dict[str, Any] = {"objects": []}
    client = FakeAircraftClient(visible)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(100.0, _ownship())
    client._world_objects = empty
    second = source.poll(100.2, _ownship())
    client._world_objects = visible
    third = source.poll(100.4, _ownship())

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


def test_missing_snapshot_resets_visible_set_state() -> None:
    # A None snapshot (not just an empty one) must also reset debounce state
    # -- mirrors HybridPerceptionSource's debounce-reset-on-gap.
    visible = {"objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]}
    client = FakeAircraftClient(visible)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(100.0, _ownship())
    client._world_objects = None
    second = source.poll(100.2, _ownship())
    client._world_objects = visible
    third = source.poll(100.4, _ownship())

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


def test_more_new_candidates_than_the_cap_emits_only_the_cap_nearest_first() -> None:
    # 5 simultaneously-new infantry candidates (well within the 900 m
    # threshold), cap = NAKED_EYE_MAX_NEW_PER_POLL = 3 -- only the 3
    # nearest are emitted this poll.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=float(100 + i * 100), lon_deg=0.0)
            for i in range(1, 6)
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == NAKED_EYE_MAX_NEW_PER_POLL
    ranges = [obs.derived_world_position.x for obs in observations]  # type: ignore[union-attr]
    assert ranges == sorted(ranges)
    assert ranges == [200.0, 300.0, 400.0]


def test_candidates_dropped_by_the_cap_are_not_retried_next_poll() -> None:
    # Per the module docstring: a capped-out-but-still-visible candidate
    # counts as "previously visible" for the next poll's debounce, so it is
    # not retried unless it actually leaves and re-enters the visible set.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=float(100 + i * 100), lon_deg=0.0)
            for i in range(1, 6)
        ]
    }
    source, _client = _source(world_objects)

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_PER_POLL
    assert second == []


def test_quantise_bearing_snaps_to_nearest_clock_position() -> None:
    # 47 deg relative bearing (from heading 0) is nearer 2 o'clock (60 deg)
    # than 1 o'clock (30 deg) -- a clean, non-boundary regression anchor.
    quantised_deg, bucket_name = _quantise_bearing(0.0, 47.0)

    assert bucket_name == "OP_A2H"
    assert quantised_deg == pytest.approx(60.0)


def test_quantise_bearing_dead_ahead_is_12_oclock() -> None:
    quantised_deg, bucket_name = _quantise_bearing(0.0, 5.0)

    assert bucket_name == "OP_A12H"
    assert quantised_deg == pytest.approx(0.0)


def test_quantise_bearing_is_relative_to_heading() -> None:
    # True bearing 100 deg, ownship heading 90 deg -> 10 deg relative ->
    # nearest clock position is dead ahead (12 o'clock), expressed back as
    # true bearing 90 deg.
    quantised_deg, bucket_name = _quantise_bearing(90.0, 100.0)

    assert bucket_name == "OP_A12H"
    assert quantised_deg == pytest.approx(90.0)


def test_quantise_range_snaps_to_bucket_upper_bound() -> None:
    quantised_m, bucket_name = _quantise_range_m(1247.0)

    assert bucket_name == "OP_D1_1p5k"
    assert quantised_m == pytest.approx(1500.0)


def test_quantise_range_exact_boundary_uses_that_bucket() -> None:
    quantised_m, bucket_name = _quantise_range_m(1000.0)

    assert bucket_name == "OP_D1000M"
    assert quantised_m == pytest.approx(1000.0)
