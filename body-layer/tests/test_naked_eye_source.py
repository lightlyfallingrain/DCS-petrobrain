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

import dataclasses
import sqlite3
from typing import Any, Final

import pytest

from perception import association, object_model, visibility
from perception.detection_trace import DetectionTraceCollector, GateOutcome
from perception.naked_eye_source import (
    NAKED_EYE_MAX_NEW_GROUPS_PER_POLL,
    PROVENANCE_VISIBILITY_FILTER_ONLY,
    NakedEyePerceptionSource,
    _quantise_bearing,
    _quantise_range_m,
)
from perception.source import SOURCE_NAKED_EYE_VISUAL_FILTERED, OwnshipState
from replay import replay

_THEATRE = "Syria"
_FAKE_CONN = sqlite3.connect(":memory:")

#: Ranges/cross-offsets for the cap/debounce tests below -- 5 candidates,
#: each carrying its own small `lon_deg` (cross-range) offset so no two are
#: exactly collinear with ownship (Stage 3b-i rev.2, `plans/
#: group-contact-model/plan.md`: two candidates on the *exact* same bearing
#: at the same altitude as ownship have zero angular separation and always
#: merge, whatever their down-range gap -- a pure down-range spread, this
#: fixture's pre-rev.2 shape, is now a degenerate case, not a safe one).
#: Every pair's true 3D angular separation was checked against
#: `perception.clustering.angular_separation_rad`/`angular_size_rad` to
#: exceed the merge threshold at every range here (Infantry, 1.8 m) --
#: computed, not guessed -- so this fixture still exercises the cap/
#: debounce mechanism in isolation from clustering, which is what it is
#: actually testing. The cross-offsets stay well inside the co-pilot
#: mask's forward allowance (`perception.cockpit_mask`'s 22 deg out to
#: 60 deg azimuth) at every one of these ranges.
#:
#: **Rescaled 2026-09-20** (`plans/detection-cones-slice1/plan.md`, final
#: scope change: `check_visibility`'s default optic moved to
#: `UNAIDED_OPTIC`, M=1.0). The naked-eye default's own `lowres` threshold
#: for Infantry is now only 600 m (`1.8 / 0.003 * 1.0`), well under the
#: old spread's 950 m top range -- every value below was rescaled to fit
#: under that ceiling and the pairwise separation re-verified (not just
#: assumed to scale): shrinking range alone *increases* each candidate's
#: apparent angular size (`size_m / range_m`), so the old cross-offsets
#: could not simply be scaled down by the same factor without risking a
#: spurious merge -- offsets were grown relative to range to compensate.
#:
#: **Rescaled again, 2C** (`plans/detection-cones-slice2/plan.md`): the
#: naked-eye channel now gazes through a +/-15 deg o'clock cone by default
#: (`perception.gaze.FOCUS_CONE_HALF_WIDTH_DEG`) rather than seeing the
#: whole cockpit envelope, so every candidate's own azimuth from boresight
#: -- not just its pairwise angular separation from its neighbours -- is
#: now a live constraint. The pre-2C offsets put candidate 2 (150 m range,
#: 40 m offset) at 14.93 deg azimuth, 0.07 deg inside the +/-15 deg gate --
#: correct, but not a margin any later retune of the gate or the fixture
#: should have to respect exactly. **Offsets were not simply scaled down**
#: (verified, not assumed): shrinking every offset by the same factor pulls
#: the whole spread toward candidate 1's own zero-offset boresight position,
#: which is exactly the degenerate same-bearing case this fixture's own
#: 2026-09-20 rescale exists to avoid -- at a 0.5x scale the nearest pair
#: (candidates 1-2) already fails to separate. `0.85x` was chosen instead
#: (computed against `perception.clustering.angular_separation_rad`/
#: `angular_size_rad`, not guessed): every candidate's azimuth drops to
#: 12.77 deg at most (2.23 deg of margin against the +/-15 deg gate) while
#: the tightest pairwise separation margin only narrows from 0.37 deg to
#: 0.30 deg -- both properties this fixture needs (inside the gate, no
#: spurious merge) hold with real margin, not a coincidence of the old
#: numbers.
_CAP_TEST_RANGES_M: Final[tuple[float, ...]] = (60.0, 150.0, 260.0, 390.0, 540.0)
_CAP_TEST_CROSS_OFFSETS_M: Final[tuple[float, ...]] = (0.0, 34.0, 55.0, 72.0, 89.0)


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
    def __init__(
        self,
        world_objects: dict[str, Any] | None,
        unit_velocity: dict[str, Any] | None = None,
    ) -> None:
        self._world_objects = world_objects
        self._unit_velocity = unit_velocity
        self.world_objects_calls = 0

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        self.world_objects_calls += 1
        return self._world_objects

    def get_unit_velocity_latest(self) -> dict[str, Any] | None:
        return self._unit_velocity


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

    assert source.poll(0.0, _ownship()) == []


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

    assert source.poll(0.0, _ownship()) == []


def test_ownship_echo_does_not_suppress_a_real_nearby_target() -> None:
    # Infantry at 100 m: within the naked-eye default's (UNAIDED_OPTIC,
    # M=1.0, `plans/detection-cones-slice1/plan.md` final scope change)
    # medres threshold (128.57 m), so it still resolves to the class-level
    # "OP_INFANTRY" this test asserts -- 500 m (the pre-2026-09-20 value)
    # now only reaches `lowres`, a different label.
    world_objects = {
        "objects": [
            _world_object(
                999, "Mi-24P", lat_deg=3.0, lon_deg=-2.0, is_ownship=True
            ),  # ownship echo
            _world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0),  # real target
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].classification_raw == "OP_INFANTRY"


# -- Gaze filtering (slice 2B; 2C's o'clock scan loop replaces the plain
# Gaze default -- plans/detection-cones-slice2/plan.md) -------------------


def test_default_scan_plan_narrows_to_whichever_cone_is_active() -> None:
    # 2C: the default is no longer "no restriction" (`None`, 2B) -- it is
    # `perception.gaze.FREE_SCAN_PLAN`, the o'clock scan loop, and a source
    # constructed with no `scan_plan` override gets it. At t_sim=0.0
    # (`SCAN_PLAN`'s index 0, clock 12 -- `perception.gaze.gaze_at`) the
    # active gaze is a +/-15 deg dead-ahead cone: a dead-ahead candidate
    # (lat_deg=100, azimuth 0) is admitted, an abeam one (lon_deg=100,
    # azimuth 90 relative to heading 0) is not -- well outside +/-15 deg
    # either way.
    ahead_world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    abeam_world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=0.0, lon_deg=100.0)]
    }
    ahead_source, _client = _source(ahead_world_objects)
    abeam_source, _client = _source(abeam_world_objects)

    assert len(ahead_source.poll(0.0, _ownship())) == 1
    assert abeam_source.poll(0.0, _ownship()) == []


def test_naked_eye_source_only_sees_a_flank_contact_when_its_cone_is_gazed() -> None:
    # The scan-loop integration case item 15 of the plan's Implementation
    # Plan asks for: a contact at a fixed bearing is detected on the cycles
    # when its o'clock is gazed and not on the others. A contact at 9
    # o'clock (lon_deg=-100, azimuth -90 relative to heading 0) sits inside
    # `SCAN_PLAN`'s active cone only during the "9" leg -- index 3, elapsed
    # in [6, 8) s of the 16 s cycle (`SCAN_PLAN = (12, 11, 10, 9, 12, 1, 2,
    # 3)` at `FOCUS_DWELL_S = 2.0` s/cone). Nothing about the contact
    # changes between the two polls -- only `now_sim`, and therefore which
    # cone `gaze_at` returns.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=0.0, lon_deg=-100.0)]
    }
    source, _client = _source(world_objects)

    ahead_leg = source.poll(0.5, _ownship())  # index 0 -> clock 12
    nine_leg = source.poll(6.5, _ownship())  # index 3 -> clock 9

    assert ahead_leg == []
    assert len(nine_leg) == 1


def test_replaying_the_same_stream_twice_yields_identical_observations() -> None:
    # Determinism (plan item 15, hard part 9): `gaze_at` is a pure function
    # of sim time, so replaying the identical frame sequence through two
    # independent, freshly-constructed sources must yield byte-identical
    # Observations -- nothing here is wall-clock- or instance-order-
    # dependent. A fixed 9 o'clock contact (lon_deg=-100) is only ever
    # admitted during the free-scan cycle's "9" leg (t in [6, 8) mod 16 s),
    # so this also exercises the scan loop actually varying poll to poll,
    # not just a trivially-static gaze.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=0.0, lon_deg=-100.0)]
    }
    frames = [
        OwnshipState(t_sim=t, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)
        for t in (0.0, 4.0, 6.0, 7.0, 8.0, 12.0, 16.0, 22.0)
    ]

    def _run() -> list[Any]:
        source = NakedEyePerceptionSource(
            aircraft_client=FakeAircraftClient(world_objects),  # type: ignore[arg-type]
            theatre=_THEATRE,
            world_model_conn=_FAKE_CONN,
            emit_mode="every_poll",
        )
        observations = []
        for _frame, obs in replay(source, frames):
            observations.extend(obs)
        return observations

    first_run = _run()
    second_run = _run()

    # A fixed contact only clears the gaze gate during the "9" leg -- both
    # runs must admit it on exactly the same subset of frames, not merely
    # produce the same *count*.
    assert len(first_run) == 3  # t=6.0, 7.0 (inside [6, 8)); t=22.0 (== 6.0 mod 16)
    assert [obs.t_sim for obs in first_run] == [6.0, 7.0, 22.0]
    assert [dataclasses.replace(obs, t_wall=0.0) for obs in first_run] == [
        dataclasses.replace(obs, t_wall=0.0) for obs in second_run
    ]


def test_peripheral_stimulus_bypasses_the_active_gaze() -> None:
    # Same abeam, excluded-by-gaze candidate as above, but flagged as a
    # captured peripheral stimulus -- this channel always resolves
    # `gaze_for` against `UNAIDED_OPTIC` (module docstring point 7), which
    # has `peripheral=True`, so the bypass applies regardless of which
    # o'clock cone is currently active.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=0.0, lon_deg=100.0)]
    }
    source, _client = _source(world_objects)
    source.peripheral_stimulus_ids = frozenset({1})

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1


def test_hires_range_candidate_with_a_known_reporting_name_reaches_type_level() -> None:
    # T-72B: size 7 m, hires threshold at the naked-eye default
    # (UNAIDED_OPTIC, M=1.0, `plans/detection-cones-slice1/plan.md` final
    # scope change) = 7 / 0.028 * 1.0 = 250 m. "T-72B" is an exact entry
    # in the reporting-name table, so this resolves to level 3.
    world_objects = {"objects": [_world_object(1, "T-72B", lat_deg=200.0, lon_deg=0.0)]}
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "T-72B"
    assert obs.classification_level == 3


def test_medres_range_candidate_stays_at_class_level() -> None:
    # T-72B (size 7 m) at 400 m: beyond the hires threshold (250 m), still
    # inside the medres threshold (500 m) -- resolves to class.
    # **RECOMPUTED FOR THE DEFAULT-OPTIC CHANGE (2026-09-20, final scope
    # change)**: the default optic is now UNAIDED_OPTIC (M=1.0), not
    # BINOCULAR_OPTIC -- this test's range went 3000 m (binocular M=4.0
    # baseline) -> a same-session M=8.0 excursion -> 400 m now, tracking
    # the default's own magnification. Formula and angular-radius constants
    # unchanged throughout.
    world_objects = {"objects": [_world_object(1, "T-72B", lat_deg=400.0, lon_deg=0.0)]}
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "OP_ARMORED"
    assert obs.classification_level == 2


def test_hires_range_candidate_with_no_reporting_name_falls_back_to_class() -> None:
    # "Infantry" (the bare, generic type used throughout this file's other
    # fixtures) has no exact entry in the reporting-name table -- only
    # compound entries like "Infantry AK" do. A close-range look still can't
    # produce a name Petrovich doesn't have, so this stays at class level
    # even though the achieved geometric tier is `hires`. 50 m is within
    # the naked-eye default's (UNAIDED_OPTIC, M=1.0) hires threshold of
    # 64.29 m for a 1.8 m object.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=50.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "OP_INFANTRY"
    assert obs.classification_level == 2


def test_lowres_range_candidate_reaches_presence_level() -> None:
    # `plans/classification-refinement/plan.md` Stage 7: the gate moved to
    # `lowres`, making the presence tier reachable for the first time.
    #
    # **Switched from Infantry to a Ural truck, slice 2A (`plans/
    # detection-cones-slice2/plan.md` decision 3).** Infantry now carries
    # `distinctiveness=5.0`, which clamps its class threshold to its own
    # presence threshold at every optic -- infantry can no longer produce
    # a genuine presence-only observation, by design (this is exactly the
    # fix: "Infantry classifies at exactly its detection range"). A Ural
    # truck (`OP_TRUCK`, distinctiveness 1.0, "ordinary") is the object
    # this test actually needs. Ural at the naked-eye default
    # (UNAIDED_OPTIC): class threshold 6 / 0.014 * 1.0 * 1.0 = 428.57 m,
    # presence threshold 6 / 0.003 * 1.0 = 2000 m. At 1000 m the target
    # clears the gate but only achieves `lowres` -- "something is there,"
    # ED's only catch-all class, not a fabricated class guess.
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == object_model.DEFAULT_OP_CLASS
    assert obs.classification_level == 1


def test_no_visible_candidates_returns_empty() -> None:
    # **STALE-FIGURE UPDATE (2026-09-20)**: at the old M=4.0 a 6 m truck's
    # lowres threshold was 8000 m, so 8500 m gated it out. At the new
    # M=8.0 that same threshold computes 16000 m, capped by
    # `NAKED_EYE_RANGE_CAP_M` (10000 m) -- 8500 m is now comfortably
    # inside it (see `test_ural_truck_gate_is_now_bound_by_the_range_cap_
    # again` in `test_visibility.py` for the same finding at the gate
    # level). 10500 m clears the hard range cap regardless of object size
    # or magnification, so it stays a reliable "gates out" candidate.
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=10_500.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    assert source.poll(0.0, _ownship()) == []


def test_a_newly_visible_candidate_emits_one_observation() -> None:
    # 100 m -- within the naked-eye default's (UNAIDED_OPTIC, M=1.0,
    # `plans/detection-cones-slice1/plan.md` final scope change) medres
    # threshold (128.57 m), so this still resolves to "OP_INFANTRY"; 500 m
    # (the pre-2026-09-20 value) now only reaches `lowres`.
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.source == SOURCE_NAKED_EYE_VISUAL_FILTERED
    assert obs.classification_raw == "OP_INFANTRY"
    assert obs.provenance == PROVENANCE_VISIBILITY_FILTER_ONLY
    assert obs.derived_world_position is not None
    assert obs.derived_world_position.x == 100.0
    assert obs.derived_world_position.z == 0.0


def test_still_visible_candidate_is_not_re_emitted_on_the_next_poll() -> None:
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    first = source.poll(0.0, _ownship())
    second = source.poll(0.2, _ownship())

    assert len(first) == 1
    assert second == []


def test_candidate_leaving_and_re_entering_the_visible_set_re_emits() -> None:
    # 2C: acquisition state is time-based, not poll-indexed (module
    # docstring point 4a) -- an object stays "known" for
    # `_ACQUISITION_RETENTION_WINDOW_S` (== `perception.gaze.
    # SCAN_CYCLE_PERIOD_S`, 16.0 s) after it was last actually seen, not
    # just the one poll it was last visible on. A brief absence (under one
    # scan cycle) is exactly what the fix is *for* -- a cone sweeping off a
    # sector and back must not read as "gone" -- so re-emission on
    # reappearance now needs a gap wider than one cycle to be a genuine
    # re-emission rather than the tolerated-brief-gap case. Poll 2 sits
    # 16.5 s after poll 1 (> `SCAN_CYCLE_PERIOD_S`, evicting the object),
    # and poll 3, 0.2 s later, still lands in the same "12 o'clock" free-
    # scan leg as poll 1 (16.1 % 16.0 == 0.1, inside `SCAN_PLAN`'s index-0
    # dwell) so the gaze gate is not itself the reason for re-emission.
    visible = {"objects": [_world_object(1, "Infantry", lat_deg=500.0, lon_deg=0.0)]}
    empty: dict[str, Any] = {"objects": []}
    client = FakeAircraftClient(visible)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(0.0, _ownship())
    client._world_objects = empty
    second = source.poll(16.1, _ownship())
    client._world_objects = visible
    third = source.poll(16.3, _ownship())

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

    first = source.poll(0.0, _ownship())
    client._world_objects = None
    second = source.poll(0.2, _ownship())
    client._world_objects = visible
    third = source.poll(0.4, _ownship())

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

    first = source.poll(0.0, _ownship())
    assert len(first) == 1
    assert first[0].continues_observation_id is None

    client._world_objects = empty
    assert source.poll(0.2, _ownship()) == []
    client._world_objects = None
    assert source.poll(0.4, _ownship()) == []
    client._world_objects = empty
    assert source.poll(0.6, _ownship()) == []

    client._world_objects = visible
    reacquired = source.poll(0.8, _ownship())

    assert len(reacquired) == 1
    assert reacquired[0].continues_observation_id == first[0].id


def test_continuity_never_cross_tags_two_different_objects() -> None:
    """Two distinct, simultaneously-visible objects must never have their
    `continues_observation_id`s cross -- each `object_id`'s map entry is
    independent."""
    # **Rescaled 2026-09-20** (`plans/detection-cones-slice1/plan.md`,
    # final scope change): both candidates need to resolve to a real
    # class-level label (not the shared presence-level default) for the
    # `classification_raw == "OP_INFANTRY"` lookups below to disambiguate
    # them at all -- 100 m keeps Infantry inside its medres threshold
    # (128.57 m at the naked-eye default, M=1.0); Ural-4320 at (90, 90)
    # (range ~127.3 m) stays inside its own hires threshold (214.29 m for
    # a 6 m object). Confirmed by actually running this scenario, not
    # assumed.
    #
    # **Rescaled again, 2C** (`plans/detection-cones-slice2/plan.md`): the
    # original 90-deg cross-offset put the Ural dead abeam, well outside
    # the default +/-15 deg gaze cone this slice adds -- moved to (125, 22)
    # (range 126.9 m, azimuth 9.98 deg, comfortably inside the gate and
    # still inside the 214.29 m hires threshold) while confirming (not
    # assuming) the two candidates stay angularly separable at the new,
    # tighter geometry (`perception.clustering.angular_separation_rad`
    # margin 9.98 deg against a 1.87 deg merge threshold).
    world_objects = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0),
            _world_object(2, "Ural-4320", lat_deg=125.0, lon_deg=22.0),
        ]
    }
    empty: dict[str, Any] = {"objects": []}
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(0.0, _ownship())
    assert len(first) == 2
    assert all(obs.continues_observation_id is None for obs in first)

    # Force both back through the debounce cycle (leave, then re-enter).
    # 2C: acquisition is time-based (`_ACQUISITION_RETENTION_WINDOW_S` ==
    # `perception.gaze.SCAN_CYCLE_PERIOD_S`, 16.0 s), so the gap has to
    # exceed one full scan cycle for a genuine re-emission -- see
    # `test_candidate_leaving_and_re_entering_the_visible_set_re_emits`'s
    # own docstring for the same derivation. 16.1/16.3 both still land in
    # the same "12 o'clock" free-scan leg as t=0.0 (16.1 % 16.0 == 0.1).
    client._world_objects = empty
    assert source.poll(16.1, _ownship()) == []
    client._world_objects = world_objects
    second = source.poll(16.3, _ownship())

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
    # 5 simultaneously-new infantry candidates (well within the naked-eye
    # default's 600 m threshold), cap = NAKED_EYE_MAX_NEW_GROUPS_PER_POLL = 3 --
    # only the 3 nearest are emitted this poll. Spacing (`_CAP_TEST_RANGES_M`)
    # is wide enough in true angular separation that no two of these
    # candidates merge under `perception.clustering`'s predicate -- computed,
    # not guessed (see `_CAP_TEST_RANGES_M`'s own docstring) -- so this test
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

    observations = source.poll(0.0, _ownship())

    assert len(observations) == NAKED_EYE_MAX_NEW_GROUPS_PER_POLL
    ranges = [obs.derived_world_position.x for obs in observations]  # type: ignore[union-attr]
    assert ranges == sorted(ranges)
    assert ranges == list(_CAP_TEST_RANGES_M[:NAKED_EYE_MAX_NEW_GROUPS_PER_POLL])


def test_a_capped_out_group_is_retried_and_the_backlog_drains_over_polls() -> None:
    # REPLACES test_candidates_dropped_by_the_cap_are_not_retried_next_poll
    # (2026-09-21, `plans/detection-cones-slice2/plan.md`'s 2A.5, user-
    # approved rewrite -- "Behaviour changes, test needs to reflect that").
    # The old test pinned a defect: a candidate that lost a simultaneous-
    # admission cap roll was marked "already seen" and silently never
    # retried, permanently under-reporting a scene the pilot never actually
    # stopped being able to see. 2A.5 fixes this at group granularity --
    # a capped-out cluster's members are deliberately kept OUT of
    # `_previously_visible_ids` (`_acquire_on_change`'s new steady_ids/
    # admitted_ids split), so they are still "new" on the next poll and
    # compete for a cap slot again.
    #
    # Derivation of the expected counts (not observed and back-fit): 5
    # candidates, no two of which merge into a shared cluster (see
    # `_CAP_TEST_RANGES_M`'s own docstring), so each is its own singleton
    # group -- 5 eligible groups, cap = NAKED_EYE_MAX_NEW_GROUPS_PER_POLL =
    # 3. Poll 1: all 5 groups are eligible (nothing previously visible
    # yet); the 3 nearest are admitted and their members become previously
    # visible, leaving the 2 furthest groups' members out of that set.
    # Poll 2 (identical snapshot, nothing left or re-entered): only those 2
    # groups are still eligible (their members are still absent from
    # `_previously_visible_ids`) -- both fit under the cap of 3, so both
    # are admitted this poll, and the backlog is now fully drained. Poll 3
    # (same snapshot again): every group's members are now previously
    # visible, so nothing is eligible and no observation is emitted --
    # true steady state, not a further backlog.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=lat_deg, lon_deg=lon_deg)
            for i, (lat_deg, lon_deg) in enumerate(
                zip(_CAP_TEST_RANGES_M, _CAP_TEST_CROSS_OFFSETS_M), start=1
            )
        ]
    }
    source, _client = _source(world_objects)

    first = source.poll(0.0, _ownship())
    second = source.poll(0.2, _ownship())
    third = source.poll(0.4, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_GROUPS_PER_POLL
    assert len(second) == len(_CAP_TEST_RANGES_M) - NAKED_EYE_MAX_NEW_GROUPS_PER_POLL
    assert third == []


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

    first = source.poll(0.0, _ownship())
    second = source.poll(0.2, _ownship())
    third = source.poll(0.4, _ownship())

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

    first = source.poll(0.0, _ownship())
    client._world_objects = empty
    second = source.poll(0.2, _ownship())

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

    first = source.poll(0.0, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_GROUPS_PER_POLL


def test_every_poll_mode_progressively_acquires_capped_overflow() -> None:
    # Unlike on_change (where a capped-out object is never retried), every_
    # poll's acquisition set must keep retrying a not-yet-acquired object on
    # later polls until the throttle admits it -- the whole point of
    # re-reading NAKED_EYE_MAX_NEW_GROUPS_PER_POLL as an acquisition-rate limit
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

    first = source.poll(0.0, _ownship())
    second = source.poll(0.2, _ownship())

    assert len(first) == NAKED_EYE_MAX_NEW_GROUPS_PER_POLL
    # first poll's 3 acquired objects re-emit, plus the 2 remaining
    # overflow objects are now acquired and emitted for the first time.
    assert len(second) == 5


def test_a_dense_group_larger_than_the_cap_admits_whole_in_one_poll() -> None:
    # The headline 2A.5 case (`plans/detection-cones-slice2/plan.md`): ten
    # co-located vehicles must produce one Observation of ten, not three
    # observations growing over three polls -- because the cap now counts
    # *groups*, and admitting a group admits every one of its members at
    # once, however many that is.
    #
    # Ten Infantry, 10 m apart down-range (well inside the down-range
    # merge distance `test_two_close_candidates_emit_one_clustered_
    # observation` above already establishes at 20 m), single-link chains
    # the whole run into one cluster -- confirmed by actually running this
    # scenario (not assumed to chain just because pairwise merge holds):
    # `trace.records` below shows all ten `object_id`s sharing one
    # `cluster_member_object_ids` tuple and one `observation_id`.
    world_objects = {
        "objects": [
            _world_object(i, "Infantry", lat_deg=500.0 + (i - 1) * 10.0, lon_deg=0.0)
            for i in range(1, 11)
        ]
    }
    trace = DetectionTraceCollector()
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        trace_sink=trace,
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1

    # No-omniscience leak check: every one of the ten members that ended up
    # in the emitted cluster must have individually cleared
    # `check_visibility`'s own gate -- clustering/capping never admits a
    # candidate the gate itself rejected.
    admitted_ids = {
        record.object_id
        for record in trace.records
        if record.outcome == GateOutcome.ADMITTED
    }
    assert admitted_ids == set(range(1, 11))
    for record in trace.records:
        assert record.cluster_member_object_ids == tuple(range(1, 11))
        assert record.observation_id == observations[0].id


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

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].count_bucket == "OP_1UNIT"


#: Three T-72B (`size_m=7.0`, `OP_ARMORED`) at 3000 m -- beyond `LOWRES_
#: ANGULAR_RADIUS_RAD`'s own 2333.33 m threshold (so a lone one is
#: rejected), well inside `RESOLUTION_ANGULAR_RADIUS_RAD`'s 5384.6 m
#: threshold. Cross-range spacing of ~18.18 m matches the ladder's own
#: "200 m / 12 units" figure: well past `clustering.py`'s own merge
#: boundary at this range (~7 m, so these stay three separate resolution
#: clusters, not one), well inside `group_salience.py`'s own ~70 m
#: cohesion boundary at this range (`GROUP_COHESION_GAP_UNIT_WIDTHS=10.0`)
#: -- exactly the "separable but still reads as one structure" case the
#: two modules' docstrings both describe. Each candidate's azimuth
#: (`atan(18.18 / 3000) ~= 0.35 deg`) is comfortably inside the default
#: scan plan's +/-15 deg gaze cone.
_GROUP_SALIENCE_RANGE_M: Final[float] = 3000.0
_GROUP_SALIENCE_SPACING_M: Final[float] = 18.18


def test_group_salience_wiring_admits_beyond_lowres_via_the_full_poll_pipeline() -> (
    None
):
    """`plans/group-detectability/plan.md` Stage 2's wiring, exercised
    through the real `poll()` pipeline (not `visibility.py` directly, as
    `test_vision_calibration.py`'s own group-detectability tests do) --
    `NakedEyePerceptionSource.poll` resolves `group_salient_ids` once per
    poll and threads it into every `check_visibility` call. None of these
    three candidates would individually clear `LOWRES_ANGULAR_RADIUS_RAD`
    at 3000 m (see `test_group_salience_wiring_does_not_admit_a_lone_
    candidate_at_the_same_range` below); together, they do."""
    world_objects = {
        "objects": [
            _world_object(
                1,
                "T-72B",
                lat_deg=_GROUP_SALIENCE_RANGE_M,
                lon_deg=-_GROUP_SALIENCE_SPACING_M,
            ),
            _world_object(2, "T-72B", lat_deg=_GROUP_SALIENCE_RANGE_M, lon_deg=0.0),
            _world_object(
                3,
                "T-72B",
                lat_deg=_GROUP_SALIENCE_RANGE_M,
                lon_deg=_GROUP_SALIENCE_SPACING_M,
            ),
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) > 0
    for observation in observations:
        assert observation.range_m >= _GROUP_SALIENCE_RANGE_M - 1000.0


def test_group_salience_wiring_does_not_admit_a_lone_candidate_at_the_same_range() -> (
    None
):
    """The regression this wiring must not introduce: with no group
    around it, the same candidate at the same range stays rejected --
    group salience never applies to a unit the group pass hasn't
    separately found to be a member of a cohesive, resolvable group of
    at least `GROUP_MIN_MEMBERS`."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=_GROUP_SALIENCE_RANGE_M, lon_deg=0.0)
        ]
    }
    source, _client = _source(world_objects)

    assert source.poll(0.0, _ownship()) == []


def _high_ownship() -> OwnshipState:
    """An 85 m AGL variant of `_ownship()` (500 m target altitude + 85 m)
    -- needed by `test_a_cluster_splitting_gives_the_majority_child_
    continuity` below, where a down-range-only split must actually
    separate two candidates angularly: at the same altitude as its
    targets, ownship's own line of sight to any two same-bearing
    candidates is collinear regardless of their down-range gap (Stage
    3b-i rev.2), so the split in that test needs a real depression-angle
    axis to work at all.

    **Rescaled 2026-09-20** (`plans/detection-cones-slice1/plan.md`, final
    scope change -- see `_CAP_TEST_RANGES_M`'s own note): was 200 m AGL
    (`plans/group-contact-model/plan.md`'s own worked case) against a
    1300+ m range spread that no longer fits under the naked-eye default's
    600 m threshold. The AGL offset was rescaled down with the range
    spread it accompanies, by the same factor, so the depression-angle
    relationship the sibling test depends on is preserved rather than
    guessed -- confirmed by actually running the scenario, not assumed."""
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=585.0, heading_true_deg=0.0)


def test_a_cluster_splitting_gives_the_majority_child_continuity() -> None:
    # Two Infantry candidates close enough to merge at long range, then far
    # enough apart to split once ownship has closed in -- the majority
    # child (more of the parent cluster's own members) must inherit
    # `continues_observation_id`; the minority child must get `None` and be
    # offered fresh to the belief-layer gate (`plans/group-contact-model/
    # plan.md`'s Splitting section -- "the id follows the majority").
    #
    # **Rescaled 2026-09-20** (`plans/detection-cones-slice1/plan.md`,
    # final scope change: `check_visibility`'s default optic moved to
    # `UNAIDED_OPTIC`, M=1.0). The naked-eye default's own gate for
    # Infantry now tops out at 600 m, well under this fixture's original
    # 1300+ m spread -- every range/offset/altitude value below was
    # rescaled down by the same factor (~2.4x) and the whole scenario
    # re-run against the real pipeline to confirm the merge/split counts
    # still hold (not assumed to survive scaling: apparent angular size
    # grows as range shrinks, which could have collapsed the split this
    # test depends on -- see `_high_ownship`'s own docstring for why its
    # AGL offset was rescaled too, not left at its old value).
    #
    # object_id=1 stays at lat 540, lon 0 -- close enough (down-range) to
    # the other three to merge with them on the first poll. object_id=2, 3,
    # 4 (three of them, so they form the cluster's own majority once it
    # splits) sit at lat 545, spread in *lon* (cross-range) instead of lat
    # this time: 0.0/0.4/0.75, chaining together single-link under Stage
    # 3b-i rev.2's angular predicate the same way `test_clustering.
    # test_chained_cluster_reports_a_plural_count` demonstrates in
    # isolation. On the second poll object_id=1 alone moves to lat 250 --
    # from `_high_ownship()`'s 85 m AGL, that down-range move genuinely
    # separates it angularly from the group (confirmed by running this
    # test, not assumed -- a down-range-only move at ownship's own altitude
    # would not separate anything at all, see `_high_ownship`'s docstring).
    # It splits off on its own -- a 1-vs-3 split, the 3-strong group the
    # majority child.
    merged = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=540.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=545.0, lon_deg=0.0),
            _world_object(3, "Infantry", lat_deg=545.0, lon_deg=0.4),
            _world_object(4, "Infantry", lat_deg=545.0, lon_deg=0.75),
        ]
    }
    split = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=250.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=545.0, lon_deg=0.0),
            _world_object(3, "Infantry", lat_deg=545.0, lon_deg=0.4),
            _world_object(4, "Infantry", lat_deg=545.0, lon_deg=0.75),
        ]
    }
    client = FakeAircraftClient(merged)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
    )

    first = source.poll(0.0, _high_ownship())
    assert len(first) == 1
    # All 4 are acquired together this first poll: they are all one cluster
    # (module docstring point 5, 2A.5) -- `NAKED_EYE_MAX_NEW_GROUPS_PER_
    # POLL` (3) caps how many *groups* are admitted per poll, and one
    # cluster is one group regardless of its member count, so the cap
    # never binds here at all.

    client._world_objects = split
    second = source.poll(0.2, _high_ownship())

    assert len(second) == 2
    # Identified by position, not `count_bucket` -- both the majority
    # (3-member) and minority (1-member) clusters land on `OP_1UNIT` here
    # (confirmed by running this test), so the count no longer distinguishes
    # them the way it did before Stage 3b-i rev.2. The minority child is the
    # one that moved to lat 250; the majority child is still near lat 545.
    majority = next(
        obs
        for obs in second
        if obs.derived_world_position is not None
        and obs.derived_world_position.x > 400.0
    )
    minority = next(
        obs
        for obs in second
        if obs.derived_world_position is not None
        and obs.derived_world_position.x <= 400.0
    )
    assert majority.continues_observation_id == first[0].id
    assert minority.continues_observation_id is None


def test_continuity_survives_a_cluster_whose_membership_grows_between_polls() -> None:
    # Acquisition state stays object-keyed even though the cap now operates
    # on clusters (module docstring point 4/5, 2A.5): a cluster has no
    # stable identity across polls, so continuity has to be resolved from
    # its *members'* own history, not from "the same cluster as last time."
    # Three Infantry (lat 545, lon 0.0/0.4/0.75 -- the same chained-single-
    # link spacing `test_a_cluster_splitting_gives_the_majority_child_
    # continuity` above already establishes merges into one cluster) form
    # one cluster and emit one Observation. A fourth (lon 1.1, chaining on
    # to object 3) then joins on the next poll -- confirmed by actually
    # running this scenario, not assumed to chain just because the first
    # three do: the whole group is still one cluster, now with different
    # membership. Because object_ids 1-3 each carry a vote for the first
    # poll's Observation and that is the whole (and therefore majority)
    # vote, `_build_observations`' majority-overlap rule must resolve the
    # grown cluster's continuity onto that same Observation, not found
    # fresh -- the thing a per-cluster-id scheme could not have done, since
    # no cluster id survives poll to poll at all.
    three_members = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=545.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=545.0, lon_deg=0.4),
            _world_object(3, "Infantry", lat_deg=545.0, lon_deg=0.75),
        ]
    }
    four_members = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=545.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=545.0, lon_deg=0.4),
            _world_object(3, "Infantry", lat_deg=545.0, lon_deg=0.75),
            _world_object(4, "Infantry", lat_deg=545.0, lon_deg=1.1),
        ]
    }
    client = FakeAircraftClient(three_members)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
    )

    first = source.poll(0.0, _high_ownship())
    assert len(first) == 1

    client._world_objects = four_members
    second = source.poll(0.2, _high_ownship())

    assert len(second) == 1
    assert second[0].continues_observation_id == first[0].id
