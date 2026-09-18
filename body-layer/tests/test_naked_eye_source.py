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
from typing import Any, Final

import pytest

from perception import association, object_model, visibility
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

#: Ranges/cross-offsets for the cap/debounce tests below -- 5 candidates,
#: each carrying its own small `lon_deg` (cross-range) offset so no two are
#: exactly collinear with ownship (Stage 3b-i rev.2, `plans/
#: group-contact-model/plan.md`: two candidates on the *exact* same bearing
#: at the same altitude as ownship have zero angular separation and always
#: merge, whatever their down-range gap -- a pure down-range spread, this
#: fixture's pre-rev.2 shape, is now a degenerate case, not a safe one).
#: Every pair's true 3D angular separation was checked by hand against
#: `perception.clustering.angular_separation_rad`/`angular_size_rad` to
#: exceed the merge threshold at every range here (Infantry, 1.8 m) --
#: computed, not guessed -- so this fixture still exercises the cap/
#: debounce mechanism in isolation from clustering, which is what it is
#: actually testing. The cross-offsets stay well inside the co-pilot
#: mask's forward allowance (`perception.cockpit_mask`'s 22 deg out to
#: 60 deg azimuth) at every one of these ranges.
_CAP_TEST_RANGES_M: Final[tuple[float, ...]] = (100.0, 250.0, 430.0, 650.0, 950.0)
_CAP_TEST_CROSS_OFFSETS_M: Final[tuple[float, ...]] = (0.0, 60.0, 90.0, 110.0, 130.0)


def _ownship() -> OwnshipState:
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _world_object(
    object_id: int,
    object_type: str,
    *,
    lat_deg: float,
    lon_deg: float,
    is_ownship: bool | None = False,
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": object_type,
        "coalition": 1.0,
        "lat_deg": lat_deg,
        "lon_deg": lon_deg,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": is_ownship,
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


def test_ownship_echo_in_world_objects_is_not_emitted() -> None:
    # Reproduces the PB-1.5 live-sortie bug: LoGetWorldObjects is unfiltered
    # ground truth and includes the player's own aircraft, identified here
    # by the aircraft-layer's is_ownship flag rather than proximity. Before
    # the original fix this produced a phantom OP_GROUPSOMETHING contact
    # pinned at the smallest range bucket with a meaningless (near-zero-
    # baseline) bearing.
    world_objects = {
        "objects": [
            _world_object(999, "Mi-24P", lat_deg=3.0, lon_deg=-2.0, is_ownship=True)
        ]
    }
    source, _client = _source(world_objects)

    assert source.poll(100.0, _ownship()) == []


def test_ownship_echo_does_not_suppress_a_real_nearby_target() -> None:
    world_objects = {
        "objects": [
            _world_object(
                999, "Mi-24P", lat_deg=3.0, lon_deg=-2.0, is_ownship=True
            ),  # ownship echo
            _world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0),  # real target
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    assert observations[0].classification_raw == "OP_INFANTRY"


def test_hires_range_candidate_with_a_known_reporting_name_reaches_type_level() -> None:
    # T-72B: size 7 m, hires threshold = 7 / 0.02 * 4.0 = 1400 m
    # (`plans/classification-refinement/plan.md` Stage 6). "T-72B" is an
    # exact entry in the reporting-name table, so this resolves to level 3.
    world_objects = {
        "objects": [_world_object(1, "T-72B", lat_deg=1000.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "T-72B"
    assert obs.classification_level == 3


def test_medres_range_candidate_stays_at_class_level() -> None:
    # T-72B at 1500 m: beyond the 1000 m hires threshold, still inside the
    # 2000 m medres threshold -- resolves to class. Both thresholds moved in
    # the 2026-09-17 screenshot calibration (hires 1400 -> 1000 m, medres
    # 3500 -> 2000 m for a 7 m object), which is why this range is 1500 and
    # not the 3000 it was: 3000 m is now presence-only, matching what the
    # ladder shows through binoculars at 2.99 km.
    world_objects = {
        "objects": [_world_object(1, "T-72B", lat_deg=1500.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "OP_ARMORED"
    assert obs.classification_level == 2


def test_hires_range_candidate_with_no_reporting_name_falls_back_to_class() -> None:
    # "Infantry" (the bare, generic type used throughout this file's other
    # fixtures) has no exact entry in the reporting-name table -- only
    # compound entries like "Infantry AK" do. A close-range look still can't
    # produce a name Petrovich doesn't have, so this stays at class level
    # even though the achieved geometric tier is `hires`.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=300.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "OP_INFANTRY"
    assert obs.classification_level == 2


def test_lowres_range_candidate_reaches_presence_level() -> None:
    # `plans/classification-refinement/plan.md` Stage 7: the gate moved to
    # `lowres`, making the presence tier reachable for the first time.
    # Infantry: medres threshold = 900 m, lowres threshold = 1674.42 m. At
    # 1600 m the target clears the (now wider) gate but only achieves
    # `lowres` -- "something is there," ED's only catch-all class, not a
    # fabricated class guess.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=1600.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == object_model.DEFAULT_OP_CLASS
    assert obs.classification_level == 1


def test_no_visible_candidates_returns_empty() -> None:
    # A 6 m truck gates out past 8000 m (6 / 0.003 * 4.0) since the
    # 2026-09-17 calibration; 6000 m, which used to be beyond the gate, is
    # now comfortably inside it.
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=8500.0, lon_deg=0.0)]
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


def test_continuity_resolves_across_a_multi_poll_gap_including_a_missing_snapshot() -> (
    None
):
    """`plans/contact-duplication-ambiguity-runaway/plan.md`'s object-
    permanence mechanism: the same `object_id`, re-emitted after several
    polls of *not* being in the visible set at all -- including a poll with
    no `world_objects` snapshot whatsoever -- must still resolve
    `continues_observation_id` to the last observation emitted before the
    gap, not `None`. This is what distinguishes the persistent map from the
    zero-gap design the plan explicitly superseded."""
    visible = {"objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]}
    empty: dict[str, Any] = {"objects": []}
    client = FakeAircraftClient(visible)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(100.0, _ownship())
    assert len(first) == 1
    assert first[0].continues_observation_id is None

    client._world_objects = empty
    assert source.poll(100.2, _ownship()) == []
    client._world_objects = None
    assert source.poll(100.4, _ownship()) == []
    client._world_objects = empty
    assert source.poll(100.6, _ownship()) == []

    client._world_objects = visible
    reacquired = source.poll(100.8, _ownship())

    assert len(reacquired) == 1
    assert reacquired[0].continues_observation_id == first[0].id


def test_continuity_never_cross_tags_two_different_objects() -> None:
    """Two distinct, simultaneously-visible objects must never have their
    `continues_observation_id`s cross -- each `object_id`'s map entry is
    independent."""
    world_objects = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0),
            _world_object(2, "Ural-4320", lat_deg=400.0, lon_deg=200.0),
        ]
    }
    empty: dict[str, Any] = {"objects": []}
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(100.0, _ownship())
    assert len(first) == 2
    assert all(obs.continues_observation_id is None for obs in first)

    # Force both back through the debounce cycle (leave, then re-enter).
    client._world_objects = empty
    assert source.poll(100.2, _ownship()) == []
    client._world_objects = world_objects
    second = source.poll(100.4, _ownship())

    assert len(second) == 2
    infantry_first = next(
        obs for obs in first if obs.classification_raw == "OP_INFANTRY"
    )
    truck_first = next(obs for obs in first if obs.classification_raw != "OP_INFANTRY")
    infantry_second = next(
        obs for obs in second if obs.classification_raw == "OP_INFANTRY"
    )
    truck_second = next(
        obs for obs in second if obs.classification_raw != "OP_INFANTRY"
    )

    # Each object's re-emission continues its own earlier observation, and
    # never the other object's.
    assert infantry_second.continues_observation_id == infantry_first.id
    assert truck_second.continues_observation_id == truck_first.id
    assert infantry_second.continues_observation_id != truck_first.id
    assert truck_second.continues_observation_id != infantry_first.id


def test_more_new_candidates_than_the_cap_emits_only_the_cap_nearest_first() -> None:
    # 5 simultaneously-new infantry candidates (well within the 900 m
    # threshold), cap = NAKED_EYE_MAX_NEW_PER_POLL = 3 -- only the 3
    # nearest are emitted this poll. Spacing (`_CAP_TEST_RANGES_M`) is wide
    # enough that no two of these candidates fall within `perception.
    # clustering.naked_eye_down_range_radius_m` of each other -- computed by
    # hand, not guessed (see `_CAP_TEST_RANGES_M`'s own docstring) -- so this test
    # still exercises the cap/debounce mechanism in isolation from Stage 2's
    # clustering (`plans/group-contact-model/plan.md`), which is what it is
    # actually testing.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=lat_deg, lon_deg=lon_deg)
            for i, (lat_deg, lon_deg) in enumerate(
                zip(_CAP_TEST_RANGES_M, _CAP_TEST_CROSS_OFFSETS_M), start=1
            )
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == NAKED_EYE_MAX_NEW_PER_POLL
    ranges = [obs.derived_world_position.x for obs in observations]  # type: ignore[union-attr]
    assert ranges == sorted(ranges)
    assert ranges == list(_CAP_TEST_RANGES_M[:NAKED_EYE_MAX_NEW_PER_POLL])


def test_candidates_dropped_by_the_cap_are_not_retried_next_poll() -> None:
    # Per the module docstring: a capped-out-but-still-visible candidate
    # counts as "previously visible" for the next poll's debounce, so it is
    # not retried unless it actually leaves and re-enters the visible set.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=lat_deg, lon_deg=lon_deg)
            for i, (lat_deg, lon_deg) in enumerate(
                zip(_CAP_TEST_RANGES_M, _CAP_TEST_CROSS_OFFSETS_M), start=1
            )
        ]
    }
    source, _client = _source(world_objects)

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_PER_POLL
    assert second == []


def test_every_poll_mode_re_emits_a_continuously_visible_candidate() -> None:
    # Stage 3 (plans/pb2-contact-memory/plan.md Interface confirmation gap
    # 2): under emit_mode="every_poll", a continuously-visible object must
    # keep emitting an Observation on every poll instead of being debounced
    # away after acquisition.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())
    third = source.poll(100.4, _ownship())

    assert len(first) == 1
    assert len(second) == 1
    assert len(third) == 1


def test_every_poll_mode_stops_emitting_once_the_candidate_leaves() -> None:
    visible = {"objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]}
    empty: dict[str, Any] = {"objects": []}
    client = FakeAircraftClient(visible)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _ownship())
    client._world_objects = empty
    second = source.poll(100.2, _ownship())

    assert len(first) == 1
    assert second == []


def test_every_poll_mode_still_throttles_first_time_acquisition() -> None:
    # 5 simultaneously-new infantry candidates, cap = 3 -- the acquisition
    # throttle still applies to *first-time* acquisition even under
    # every_poll, guarding against instant global awareness.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=lat_deg, lon_deg=lon_deg)
            for i, (lat_deg, lon_deg) in enumerate(
                zip(_CAP_TEST_RANGES_M, _CAP_TEST_CROSS_OFFSETS_M), start=1
            )
        ]
    }
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_PER_POLL


def test_every_poll_mode_progressively_acquires_capped_overflow() -> None:
    # Unlike on_change (where a capped-out object is never retried), every_
    # poll's acquisition set must keep retrying a not-yet-acquired object on
    # later polls until the throttle admits it -- the whole point of
    # re-reading NAKED_EYE_MAX_NEW_PER_POLL as an acquisition-rate limit
    # rather than an emission cap.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=lat_deg, lon_deg=lon_deg)
            for i, (lat_deg, lon_deg) in enumerate(
                zip(_CAP_TEST_RANGES_M, _CAP_TEST_CROSS_OFFSETS_M), start=1
            )
        ]
    }
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_PER_POLL
    # first poll's 3 acquired objects re-emit, plus the 2 remaining
    # overflow objects are now acquired and emitted for the first time.
    assert len(second) == 5


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


# --- Stage 2 clustering (plans/group-contact-model/plan.md) -----------------


def test_two_close_candidates_emit_one_clustered_observation() -> None:
    # Two Infantry candidates 20 m apart *along the line of sight* from
    # ownship at the origin (both differ only in lat, i.e. down-range) --
    # well within the 100 m down-range radius at range ~500 m
    # (`perception.clustering.naked_eye_down_range_radius_m(500.0)`) -- must
    # emit one Observation, not two. The count is genuinely `OP_1UNIT`, not
    # plural -- a *direct* (non-chained) pair can only ever land in one
    # cross-range bin (see `perception.clustering._count_cross_range_
    # subclusters`'s own docstring: the full-ellipse merge test already
    # requires any two directly-connected members to be within one
    # cross-range radius of each other). A cross-range separation this size
    # would not even *merge* post-3b-i (the cross-range radius at this
    # range is ~0.4 m) -- that distinction, and a real plural count via
    # single-link chaining, are exercised by `test_calibration_cluster_
    # merge_undercount.py` and `test_clustering.py`'s own chained-cluster
    # test, not here -- this test only pins the wiring (one cluster in,
    # one Observation out).
    world_objects = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=520.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    assert observations[0].count_bucket == "OP_1UNIT"


def _high_ownship() -> OwnshipState:
    """A 200 m AGL variant of `_ownship()` (500 m target altitude + 200 m,
    matching `plans/group-contact-model/plan.md`'s own worked case) --
    needed by `test_a_cluster_splitting_gives_the_majority_child_continuity`
    below, where a down-range-only split must actually separate two
    candidates angularly: at the same altitude as its targets, ownship's
    own line of sight to any two same-bearing candidates is collinear
    regardless of their down-range gap (Stage 3b-i rev.2), so the split in
    that test needs a real depression-angle axis to work at all."""
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=700.0, heading_true_deg=0.0)


def test_a_cluster_splitting_gives_the_majority_child_continuity() -> None:
    # Two Infantry candidates close enough to merge at long range, then far
    # enough apart to split once ownship has closed in -- the majority
    # child (more of the parent cluster's own members) must inherit
    # `continues_observation_id`; the minority child must get `None` and be
    # offered fresh to the belief-layer gate (`plans/group-contact-model/
    # plan.md`'s Splitting section -- "the id follows the majority").
    #
    # object_id=1 stays at lat 1300, lon 0 -- close enough (down-range) to
    # the other three to merge with them on the first poll. object_id=2, 3,
    # 4 (three of them, so they form the cluster's own majority once it
    # splits) sit at lat 1310, spread in *lon* (cross-range) instead of lat
    # this time: 0.0/0.9/1.8, chaining together single-link under Stage
    # 3b-i rev.2's angular predicate the same way `test_clustering.
    # test_chained_cluster_reports_a_plural_count` demonstrates in
    # isolation. On the second poll object_id=1 alone moves to lat 100 --
    # from `_high_ownship()`'s 200 m AGL, that down-range move genuinely
    # separates it angularly from the group (confirmed by running this
    # test, not assumed -- a down-range-only move at ownship's own altitude
    # would not separate anything at all, see `_high_ownship`'s docstring).
    # lat 600, not closer, so object_id=1 stays within the co-pilot mask's
    # 22 deg forward depression allowance at 200 m AGL (`perception.
    # cockpit_mask`) rather than dropping out of visibility entirely -- a
    # real constraint this fixture ran into, not tuned around blindly.
    # It splits off on its own -- a 1-vs-3 split, the 3-strong group the
    # majority child.
    merged = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=1300.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=1310.0, lon_deg=0.0),
            _world_object(3, "Infantry", lat_deg=1310.0, lon_deg=0.9),
            _world_object(4, "Infantry", lat_deg=1310.0, lon_deg=1.8),
        ]
    }
    split = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=600.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=1310.0, lon_deg=0.0),
            _world_object(3, "Infantry", lat_deg=1310.0, lon_deg=0.9),
            _world_object(4, "Infantry", lat_deg=1310.0, lon_deg=1.8),
        ]
    }
    client = FakeAircraftClient(merged)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _high_ownship())
    assert len(first) == 1
    # Only 3 of the 4 are acquired this first poll -- `NAKED_EYE_MAX_NEW_
    # PER_POLL` (3) still throttles first-time acquisition per-object, even
    # under `emit_mode="every_poll"` (module docstring point 5's "Stage 2
    # scoping decision"); the 4th joins on the next poll.

    client._world_objects = split
    second = source.poll(100.2, _high_ownship())

    assert len(second) == 2
    # Identified by position, not `count_bucket` -- both the majority
    # (3-member) and minority (1-member) clusters land on `OP_1UNIT` here
    # (confirmed by running this test), so the count no longer distinguishes
    # them the way it did before Stage 3b-i rev.2. The minority child is the
    # one that moved to lat 100; the majority child is still near lat 1310.
    majority = next(
        obs
        for obs in second
        if obs.derived_world_position is not None
        and obs.derived_world_position.x > 1000.0
    )
    minority = next(
        obs
        for obs in second
        if obs.derived_world_position is not None
        and obs.derived_world_position.x <= 1000.0
    )
    assert majority.continues_observation_id == first[0].id
    assert minority.continues_observation_id is None
