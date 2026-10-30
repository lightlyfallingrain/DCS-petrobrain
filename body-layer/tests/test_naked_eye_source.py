"""Tests for `perception.naked_eye_source.NakedEyePerceptionSource` and its
private bearing/range quantisation helpers.

Uses a fake `AircraftLayerClient`-shaped object (duck-typed, matching
`get_world_objects_latest`) -- no network I/O, mirroring
`test_hybrid_source.py`'s fake-client pattern. `association.wgs84_to_dcs`
is monkeypatched to an identity mapping (lat/lon pass straight through as
x/z) so candidate positions are plain numbers. Gate 4 of `visibility.
check_visibility` is fail-closed as of `plans/bl11-stage4-fail-closed/
plan.md` (`BL-11` Stage 4) -- world-model's offline `line_of_sight_clear`
primitive is never consulted from the live path any more, so `FakeAircraft
Client.get_line_of_sight_latest` below synthesizes a real live-LOS join
(every object gets a `unit_name`; every present one resolves "clear" by
default) instead, which is what used to need no real world-model `.sqlite`.
The real `visibility.check_visibility` still runs, so these tests exercise
the whole poll() pipeline (visibility filtering + quantisation + debounce +
cap) with a genuine, un-mocked detectability decision underneath.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from typing import Any, Final

import pytest

from perception import association, object_model
from perception.association import SightCone
from perception.detection_trace import DetectionTraceCollector, GateOutcome
from perception.naked_eye_source import (
    NAKED_EYE_MAX_NEW_GROUPS_PER_POLL,
    PROVENANCE_EMITTER_BURNING,
    PROVENANCE_EMITTER_FIRING,
    PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    PROVENANCE_EMITTER_FIRING_VISIBLE,
    PROVENANCE_VISIBILITY_FILTER_ONLY,
    NakedEyePerceptionSource,
)
from perception.optics import SIGHT_NARROW_OPTIC
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


#: Sentinel distinguishing "not passed" from "explicitly passed `None`" for
#: `_world_object`'s `unit_name` keyword below -- `None` is itself a
#: meaningful value (omit the key entirely, simulating an object the live
#: LOS feed has no verdict for; `plans/bl11-stage4-fail-closed/plan.md`
#: step 4's "omit one to simulate no verdict for this object"), so it
#: cannot also mean "use the auto-derived default."
_AUTO_UNIT_NAME: Final[object] = object()


def _world_object(
    object_id: int,
    object_type: str,
    *,
    lat_deg: float,
    lon_deg: float,
    is_ownship: bool | None = False,
    unit_name: str | None | object = _AUTO_UNIT_NAME,
    category: int | None = None,
    subcategory: int | None = None,
) -> dict[str, Any]:
    # `unit_name` (`plans/bl11-stage4-fail-closed/plan.md` step 4, `BL-11`
    # Stage 4): the live-LOS join key (`naked_eye_source._resolve_los_by_
    # unit_name`). Every object gets one by default (`f"unit_{object_id}"`)
    # so `FakeAircraftClient.get_line_of_sight_latest` below can mark it
    # clear and the fail-closed gate admits it, same as before this plan
    # -- pass `unit_name=None` to omit the key and simulate "no live
    # verdict for this object," or an explicit string to name it for
    # `FakeAircraftClient`'s `blocked_unit_names` override.
    resolved_name = f"unit_{object_id}" if unit_name is _AUTO_UNIT_NAME else unit_name
    obj: dict[str, Any] = {
        "object_id": object_id,
        "object_type": object_type,
        "coalition": 1.0,
        "lat_deg": lat_deg,
        "lon_deg": lon_deg,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": is_ownship,
        "category": category,
        "subcategory": subcategory,
    }
    if resolved_name is not None:
        obj["unit_name"] = resolved_name
    return obj


class FakeAircraftClient:
    """`plans/bl11-stage4-fail-closed/plan.md` step 4 (`BL-11` Stage 4):
    synthesizes a working live-LOS join by default, rather than always
    returning no verdict (`get_line_of_sight_latest` used to always return
    `None`) -- fail-closed rejects a candidate with no live verdict, so a
    double that never supplies one would silently reject every candidate
    every test in this file constructs, not just the ones a test means to
    exercise the LOS gate with.

    `get_world_objects_latest`'s returned dict is given a `dcs_model_time_s`
    (defaulting to `0.0` when the caller's own `world_objects` literal
    doesn't set one, which is every call site in this file) so the skew
    check in `naked_eye_source._resolve_los_by_unit_name` has something to
    compare against; `get_line_of_sight_latest`'s own verdict snapshot
    carries the identical value, so skew is always `0.0` -- well inside
    `LOS_MAX_AGE_S` -- regardless of which `now_sim` a given poll uses.

    `blocked_unit_names` (default empty) is the per-test override hook:
    any `unit_name` in that set resolves to `terrain_clear=False` (blocked)
    instead of the default "clear." Combined with `_world_object`'s own
    `unit_name=None` escape hatch (no live verdict at all for that object),
    these two optional parameters cover all three live-LOS states a test
    might need without reviving the old, now-vacuous `clear_line_of_sight`
    autouse fixture."""

    def __init__(
        self,
        world_objects: dict[str, Any] | None,
        unit_velocity: dict[str, Any] | None = None,
        *,
        blocked_unit_names: frozenset[str] = frozenset(),
        firing: dict[str, Any] | None = None,
    ) -> None:
        self._world_objects = world_objects
        self._unit_velocity = unit_velocity
        self._blocked_unit_names = blocked_unit_names
        self._firing = firing
        self.world_objects_calls = 0

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        self.world_objects_calls += 1
        if self._world_objects is None:
            return None
        if "dcs_model_time_s" in self._world_objects:
            return self._world_objects
        return {**self._world_objects, "dcs_model_time_s": 0.0}

    def get_unit_velocity_latest(self) -> dict[str, Any] | None:
        return self._unit_velocity

    def get_line_of_sight_latest(self) -> dict[str, Any] | None:
        if self._world_objects is None:
            return None
        objects = self._world_objects.get("objects", [])
        verdicts: dict[str, Any] = {}
        for obj in objects:
            name = obj.get("unit_name")
            if not isinstance(name, str):
                continue
            blocked = name in self._blocked_unit_names
            verdicts[name] = {
                "building_clear": not blocked,
                "terrain_clear": not blocked,
            }
        return {
            "dcs_model_time_s": self._world_objects.get("dcs_model_time_s", 0.0),
            "hour_used": None,
            "fov_half_deg_used": None,
            "verdicts": verdicts,
        }

    def get_firing_latest(self) -> dict[str, Any]:
        """`plans/emitter-visibility/plan.md` Stage B -- defaults to a
        well-formed, empty-but-fresh snapshot (same `dcs_model_time_s` as
        `get_world_objects_latest`'s own, so `_resolve_firing_active`'s
        skew check always passes), same "synthesize a working default
        rather than always degrading" reasoning `get_line_of_sight_latest`
        already follows. `firing=` at construction overrides it wholesale
        for tests that need a specific `"active"` map."""
        if self._firing is not None:
            return self._firing
        t_sim = (
            self._world_objects.get("dcs_model_time_s", 0.0)
            if self._world_objects is not None
            else 0.0
        )
        return {"dcs_model_time_s": t_sim, "received_wall_clock_s": 0.0, "active": {}}


@pytest.fixture(autouse=True)
def identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


def _source(
    world_objects: dict[str, Any] | None,
    *,
    unit_velocity: dict[str, Any] | None = None,
    blocked_unit_names: frozenset[str] = frozenset(),
    firing: dict[str, Any] | None = None,
) -> tuple[NakedEyePerceptionSource, FakeAircraftClient]:
    client = FakeAircraftClient(
        world_objects,
        unit_velocity,
        blocked_unit_names=blocked_unit_names,
        firing=firing,
    )
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


# -- LiveLosCoverage (plans/bl11-stage4-fail-closed/plan.md step 4,
# `BL-11` Stage 4) -----------------------------------------------------------


def test_live_los_coverage_counts_only_gate_4_reaching_candidates() -> None:
    """`live_los_coverage.evaluated` counts candidates that reach gate 4
    (survived gates 0-3), not every candidate in the poll -- a mix of one
    in-gaze and one out-of-gaze candidate (same geometry as
    `test_default_scan_plan_narrows_to_whichever_cone_is_active` above)
    proves the gaze-rejected one never increments it. Both objects carry
    a real `unit_name` (default `_world_object` behaviour) resolving
    "clear," so `no_verdict` stays at 0 -- the companion test below covers
    the no-verdict case."""
    world_objects = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0),  # ahead
            _world_object(2, "Infantry", lat_deg=0.0, lon_deg=100.0),  # abeam
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1  # only the ahead candidate was admitted
    assert source.live_los_coverage.evaluated == 1
    assert source.live_los_coverage.no_verdict == 0


def test_live_los_coverage_no_verdict_excludes_gaze_rejected_candidates() -> None:
    """The no-verdict count only grows for a candidate that actually
    reaches gate 4 with `live_los_clear is None` -- the gaze-rejected
    abeam candidate here has no live verdict either (no `unit_name`), but
    never reaches gate 4 at all, so it must not inflate the count.
    `evaluated` and `no_verdict` both land on 1, not 2."""
    world_objects = {
        "objects": [
            # Ahead, but with no unit_name at all (`_world_object`'s
            # `unit_name=None` escape hatch) -- no live verdict for this
            # object, reaches gate 4, and is rejected by it (fail-closed).
            _world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0, unit_name=None),
            # Abeam, also no unit_name -- but this one is rejected by the
            # gaze gate (gate 0) before it ever reaches gate 4.
            _world_object(2, "Infantry", lat_deg=0.0, lon_deg=100.0, unit_name=None),
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert observations == []  # the ahead candidate is now rejected too
    assert source.live_los_coverage.evaluated == 1
    assert source.live_los_coverage.no_verdict == 1


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


def test_suppressed_until_sim_yields_no_observations() -> None:
    """`BL-B64` Stage 2, direction §6's 1 s hand movement -- `poll()`
    returns `[]` immediately while `now_sim` is still under `suppressed_
    until_sim`, for a candidate that would otherwise be admitted."""
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)
    source.suppressed_until_sim = 1.0

    assert source.poll(0.5, _ownship()) == []


def test_no_longer_suppressed_once_the_duration_elapses() -> None:
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)
    source.suppressed_until_sim = 1.0

    assert len(source.poll(1.0, _ownship())) == 1


def test_suppression_does_not_touch_dedup_state() -> None:
    """A deliberate pause is not a data gap -- unlike `world_objects is
    None`, `_previously_seen_at`/`_acquired_at` must be left exactly as
    they were."""
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)
    source.poll(0.0, _ownship())
    seen_before = dict(source._previously_seen_at)

    source.suppressed_until_sim = 10.0
    source.poll(0.5, _ownship())

    assert source._previously_seen_at == seen_before


def test_sight_cone_admits_a_candidate_beyond_the_player_bubble() -> None:
    """`BL-B64` Stage 2, direction §7 -- threaded through from `self.
    sight_cone` into `association.filter_player_bubble`, with the
    optic-aware range cap (`Optic.range_cap_m`) letting it survive
    `visibility.check_visibility`'s own gate too (plan §12a: neither
    change is sufficient alone)."""
    # T-72B, size 7 m: SIGHT_NARROW_OPTIC's own size-curve threshold is
    # 7 / 0.003 * 5.81 = 13556.67 m -- 13000 m sits inside it and inside
    # the optic's own 20 km range_cap_m, but beyond PLAYER_BUBBLE_RADIUS_M
    # (10000 m), so only the cone (not the ordinary radius test) admits
    # it. Dead ahead (lon_deg=0) so the +/-15 deg default gaze cone and
    # the narrow sight's own 3 deg FOV both clear it too.
    world_objects = {
        "objects": [_world_object(1, "T-72B", lat_deg=13_000.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)
    source.optic = SIGHT_NARROW_OPTIC
    source.sight_cone = SightCone(
        azimuth_deg=0.0, half_angle_deg=10.0, depth_m=20_000.0
    )

    assert len(source.poll(0.5, _ownship())) == 1


def test_sight_cone_none_is_unaffected_by_a_beyond_bubble_candidate() -> None:
    """The same candidate, same optic, no cone -- rejected by the ordinary
    `PLAYER_BUBBLE_RADIUS_M` test, exactly as before this entry."""
    world_objects = {
        "objects": [_world_object(1, "T-72B", lat_deg=13_000.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)
    source.optic = SIGHT_NARROW_OPTIC

    assert source.poll(0.5, _ownship()) == []


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


def test_admitted_candidate_with_clear_live_los_carries_a_relative_direction() -> None:
    """`plans/attack-run/plan.md` Decision 16, Stage 2 -- an admitted
    cluster whose live LOS resolves clear gets the ownship-relative
    observation populated, yaw-removed at the observing poll's own
    (here, zero) heading. Ownship sits at `(0, 0, 500)` facing north;
    the candidate sits 100 m north (`x=100`) at the same altitude, so
    `forward_m` is the full 100 m, `right_m`/`up_m` are both ~0."""
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.live_los_clear is True
    assert obs.relative_direction is not None
    assert obs.relative_direction.forward_m == pytest.approx(100.0)
    assert obs.relative_direction.right_m == pytest.approx(0.0, abs=1e-6)
    assert obs.relative_direction.up_m == pytest.approx(0.0, abs=1e-6)


def test_detection_trace_records_relative_direction_set_on_admission() -> None:
    """Stage 2's own stated acceptance alongside the test suite -- one
    detection-trace field, `DetectionTrace.relative_direction_set`,
    answering "was this look good enough for attack-run guidance" without
    joining against belief."""
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
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
    admitted = [
        record
        for record in trace.records
        if record.object_id == 1 and record.outcome is GateOutcome.ADMITTED
    ]
    assert len(admitted) == 1
    assert admitted[0].relative_direction_set is True


def test_aim_unit_direction_picks_the_member_nearest_the_gaze_centre() -> None:
    """`[[BL-B67]]` Stage 2, "Single unit, never a cluster" -- a two-member
    cluster (5 m lateral separation at 100 m range, well inside the
    merge boundary -- confirmed by `perception.clustering.
    cluster_candidates` directly) aims the one-member direction at
    whichever member sits nearer this poll's gaze centre, not at the
    cluster centroid, under a sight-tier optic with the gaze centre set
    (the same per-poll fields `_apply_active_gaze` assigns)."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=100.0, lon_deg=0.0),
            _world_object(2, "T-72B", lat_deg=100.0, lon_deg=5.0),
        ]
    }
    source, _client = _source(world_objects)
    source.optic = SIGHT_NARROW_OPTIC
    # Gaze centre close to member 2's own azimuth (~2.86 deg) --
    # `member 1` is at ~0 deg, so the centroid (~1.43 deg) sits between
    # both and is not itself close enough to be ambiguous.
    source.sight_cone = SightCone(azimuth_deg=2.86, half_angle_deg=10.0, depth_m=1000.0)
    source.gaze_centre_elevation_deg = 0.0

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.aim_unit_direction is not None
    assert obs.relative_direction is not None
    # Member 2's own offset (right_m ~= 5.0), not the centroid's (~2.5).
    assert obs.aim_unit_direction.right_m == pytest.approx(5.0, abs=1e-3)
    assert obs.relative_direction.right_m == pytest.approx(2.5, abs=1e-3)


def test_aim_unit_direction_tracks_the_gaze_centre_across_polls() -> None:
    """ "sticky across polls as the head moves" -- the same two-member
    cluster, polled once with the gaze centre near member 1 and once
    near member 2, picks each member in turn."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=100.0, lon_deg=0.0),
            _world_object(2, "T-72B", lat_deg=100.0, lon_deg=5.0),
        ]
    }
    source, _client = _source(world_objects)
    source.optic = SIGHT_NARROW_OPTIC
    source.sight_cone = SightCone(azimuth_deg=0.0, half_angle_deg=10.0, depth_m=1000.0)
    source.gaze_centre_elevation_deg = 0.0
    # The unchanged cluster must still re-emit on poll 2, for this test's
    # own comparison -- `"every_poll"`, not the default debounce.
    source.emit_mode = "every_poll"

    near_member_1 = source.poll(0.0, _ownship())
    assert len(near_member_1) == 1
    assert near_member_1[0].aim_unit_direction is not None
    assert near_member_1[0].aim_unit_direction.right_m == pytest.approx(0.0, abs=1e-3)

    source.sight_cone = SightCone(azimuth_deg=2.86, half_angle_deg=10.0, depth_m=1000.0)
    near_member_2 = source.poll(1.0, _ownship())
    assert len(near_member_2) == 1
    assert near_member_2[0].aim_unit_direction is not None
    assert near_member_2[0].aim_unit_direction.right_m == pytest.approx(5.0, abs=1e-3)


def test_aim_unit_direction_equals_the_centroid_for_a_single_member_cluster() -> None:
    """A single-member cluster needs no "nearest member" search -- the
    one candidate trivially wins, so `aim_unit_direction` equals
    `relative_direction`."""
    world_objects = {"objects": [_world_object(1, "T-72B", lat_deg=100.0, lon_deg=0.0)]}
    source, _client = _source(world_objects)
    source.optic = SIGHT_NARROW_OPTIC
    source.sight_cone = SightCone(azimuth_deg=0.0, half_angle_deg=10.0, depth_m=1000.0)
    source.gaze_centre_elevation_deg = 0.0

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.aim_unit_direction is not None
    assert obs.relative_direction is not None
    assert obs.aim_unit_direction == obs.relative_direction


def test_aim_unit_direction_none_without_a_sight_tier_optic() -> None:
    """`single_unit=False` is every pre-existing caller's unchanged
    behaviour: with the default `UNAIDED_OPTIC` (no gaze centre, no
    sight tier), `aim_unit_direction` stays `None` even though `live_
    los_clear` is `True` and `relative_direction` is populated."""
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.live_los_clear is True
    assert obs.relative_direction is not None
    assert obs.aim_unit_direction is None


def test_a_candidate_whose_live_los_is_blocked_never_reaches_emission() -> None:
    """The bound, restated at the field level (`perception.source.
    RelativeDirection`'s own docstring): gate 4 is fail-closed (`BL-11`
    Stage 4), so a candidate whose live LOS is not confirmed clear is
    rejected before clustering ever runs -- there is no reachable
    "admitted but unclear" case for `relative_direction` to guess at."""
    world_objects = {
        "objects": [_world_object(1, "Infantry", lat_deg=100.0, lon_deg=0.0)]
    }
    source, _client = _source(world_objects, blocked_unit_names=frozenset({"unit_1"}))

    assert source.poll(0.0, _ownship()) == []


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


# Bearing/range quantisation (`_quantise_bearing`/`_quantise_range_m`) was
# deleted from this channel's emission path by `plans/
# precise-position-belief/plan.md` Stage 2, replaced by `perception.
# estimation`'s error model + perturbation -- see `test_estimation.py` for
# that module's own coverage, and the tests below for this source's use of
# it (`test_emitted_bearing_range_are_perturbed_not_quantised`,
# `test_position_uncertainty_is_declared_on_every_observation`).


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


def test_mixed_domain_candidates_never_share_a_cluster() -> None:
    # A ground vehicle and a helicopter at the same angular position --
    # close enough to merge under ordinary (same-domain) clustering --
    # must still end up as two separate Observations, never one mixed
    # cluster, because `plans/bl-b104-ground-contacts-on-ground/plan.md`
    # Stage 1 clusters each domain separately and concatenates.
    world_objects = {
        "objects": [
            _world_object(
                1,
                "BMP-2",
                lat_deg=500.0,
                lon_deg=0.0,
                category=2,  # wsType_Ground
            ),
            _world_object(
                2,
                "Mi-8",
                lat_deg=500.0,
                lon_deg=0.0,
                category=1,  # wsType_Air
                subcategory=1,  # wsType_Airplane (not helicopter -> stays air)
            ),
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 2
    surface_flags = {o.surface_alt_m is not None for o in observations}
    assert surface_flags == {True, False}  # one surface, one air -- never merged


def test_air_only_poll_is_unchanged_by_domain_split() -> None:
    # An air-only (no category at all, today's un-redeployed Export.lua
    # shape) poll must produce exactly the observations it would have
    # before the domain split existed -- one clustered Observation for
    # two close candidates, same as `test_two_close_candidates_emit_one_
    # clustered_observation` above.
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
    assert observations[0].surface_alt_m is None


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


def test_merging_previously_separate_contacts_abandons_the_minority_identities() -> (
    None
):
    # Reproduces the mechanism behind a real sortie's "near constant stream
    # of contact reports... many of those reports were about the same
    # units" complaint (`plans/contact-report-flood/debug.md`), traced from
    # a live `--detection-trace`/`--belief-truth-log` capture: a tight
    # scatter of T-55s at ~4.4 km repeatedly re-clustered as the o'clock
    # scan cone swept across it, and at t_sim=751.247 a 4-member supercluster
    # formed from 3 *already separately tracked* clusters (2+1+1 members)
    # inherited only the 2-member one's identity -- the other two (1 member
    # each) got no vote at all in the result and simply stopped being
    # updated, left to decay in `ContactStore` while their real objects kept
    # being seen under the surviving id.
    #
    # Three already-independent clusters are established over two polls
    # (objects 1+2 paired at lon 0.0/3.0 -- gap 3, confirmed merging; object
    # 3 alone at lon 12.0 -- gap 9 from object 2, confirmed separate; object
    # 4 alone at lon 24.0 -- gap 12 from object 3, confirmed separate; see
    # this module's own empirical sweep in `plans/contact-report-flood/
    # debug.md` for where the merge/no-merge boundary actually sits for this
    # object type/range, 7-8 m of lon at 600 m). A third poll then adds two
    # new objects (5, 6) at the midpoints (lon 7.5, 18.0) that single-link
    # chain the whole scatter into one six-member cluster -- exactly what a
    # scan sweep admitting one more real vehicle into view does, with no
    # need for anything to have physically moved.
    #
    # `_build_observations`' majority-overlap rule (module docstring point
    # 6) is working exactly as designed here -- objects 1+2's identity has
    # 2 votes against 1 each for objects 3 and 4, a clean majority, no tie
    # to break. **That is the point**: this is not an edge case that a
    # better tie-break would fix. Discarding 2 of 3 live, already-identified
    # contacts the instant their members get folded into one supercluster
    # is the documented behaviour (`_build_observations`'s own docstring:
    # "a minority split... founds fresh instead" -- merging is the same
    # code path as splitting, and the plan this rule came from
    # (`plans/group-contact-model/plan.md`'s Splitting section) only ever
    # analysed splitting a single parent, not several independent parents
    # colliding). The two abandoned contacts receive no further
    # observations and no signal that their object is still present; they
    # simply decay toward `lost` while the surviving contact (and,
    # eventually, a freshly-founded one for any object a later re-split
    # does not reunite with it) keeps the conversation going as if this
    # were new ground.
    #
    # **Not fixed here.** Changing which identity should survive a merge
    # (or whether the belief layer should be told about the discarded ones
    # at all) is the same class of decision `plans/
    # contact-duplication-ambiguity-runaway/debug.md` and `plans/
    # contact-fragmentation-at-range/debug.md` already escalated to the
    # Architect rather than patching `ContactStore`'s/`naked_eye_source`'s
    # continuity policy directly -- see `plans/contact-report-flood/
    # debug.md`.
    rng = 600.0
    client = FakeAircraftClient({"objects": []})
    trace = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
        trace_sink=trace,
    )

    separate = {
        "objects": [
            _world_object(1, "BTR-80", lat_deg=rng, lon_deg=0.0),
            _world_object(2, "BTR-80", lat_deg=rng, lon_deg=3.0),
            _world_object(3, "BTR-80", lat_deg=rng, lon_deg=12.0),
            _world_object(4, "BTR-80", lat_deg=rng, lon_deg=24.0),
        ]
    }
    merged = {
        "objects": [
            *separate["objects"],
            _world_object(5, "BTR-80", lat_deg=rng, lon_deg=7.5),
            _world_object(6, "BTR-80", lat_deg=rng, lon_deg=18.0),
        ]
    }

    def _members_by_observation_id() -> dict[str, frozenset[int]]:
        by_id: dict[str, set[int]] = {}
        for entry in trace.records:
            if entry.observation_id is not None:
                by_id.setdefault(entry.observation_id, set()).add(entry.object_id)
        return {obs_id: frozenset(members) for obs_id, members in by_id.items()}

    client._world_objects = separate
    trace.records.clear()
    first = source.poll(0.0, _ownship())
    assert len(first) == 3

    # Re-poll once at the same geometry so each of the three identities has
    # a `_object_id_to_last_observation_id` entry that is one poll old, not
    # brand new -- matching the real trace, where every one of the three
    # pre-merge contacts had already survived at least one prior poll.
    trace.records.clear()
    second = source.poll(0.1, _ownship())
    assert len(second) == 3
    members_of = _members_by_observation_id()
    majority_id = next(
        obs.id for obs in second if members_of[obs.id] == frozenset({1, 2})
    )
    minority_ids = {obs.id for obs in second if members_of[obs.id] != frozenset({1, 2})}
    assert len(minority_ids) == 2

    client._world_objects = merged
    trace.records.clear()
    third = source.poll(0.2, _ownship())

    assert len(third) == 1
    merged_observation = third[0]
    # The majority identity (objects 1+2, 2 votes against 1 each) survives
    # the merge...
    assert merged_observation.continues_observation_id == majority_id
    # ...and the two minority identities (objects 3 and 4, 1 vote each) are
    # simply absent from the result -- nothing links back to them, and
    # nothing tells `ContactStore` their objects moved into the surviving
    # contact rather than vanishing. A real `ContactStore` leaves both of
    # those contacts to decay toward `lost` while the pilot keeps hearing
    # about this same patch of ground under the surviving id (and, if a
    # later poll re-splits the scatter, possibly a freshly founded one for
    # whichever object does not reunite with it).
    assert merged_observation.continues_observation_id not in minority_ids


# -- Emitter visibility (plans/emitter-visibility/plan.md, BL-B72 Stage A) --


def test_a_burning_unit_beyond_naked_eye_range_becomes_visible() -> None:
    """End-to-end demonstration: a T-72B at 9 km is far beyond its own
    2333.33 m `lowres` presence threshold (`test_armored_vehicle_just_
    inside_lowres_tier_range_is_visible` in `test_visibility.py` has the
    derivation) -- only the emitter bypass can admit it."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 0.5, "life0": 1.0},
        }
    }
    source, _client = _source(world_objects, unit_velocity=unit_velocity)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].classification_raw == object_model.DEFAULT_OP_CLASS
    assert observations[0].provenance == PROVENANCE_EMITTER_BURNING


def test_the_same_unit_not_burning_is_not_visible() -> None:
    """The other half of the regression gate: the identical T-72B at
    9 km, healthy, is not seen at all."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 1.0, "life0": 1.0},
        }
    }
    source, _client = _source(world_objects, unit_velocity=unit_velocity)

    observations = source.poll(0.0, _ownship())

    assert observations == []


def test_a_burning_unit_behind_terrain_stays_invisible() -> None:
    """*"Terrain does block, of course... Terrain just blocks LOS."* --
    the emitter bypass does not reach gate 4."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 0.5, "life0": 1.0},
        }
    }
    source, client = _source(
        world_objects,
        unit_velocity=unit_velocity,
        blocked_unit_names=frozenset({"unit_1"}),
    )

    observations = source.poll(0.0, _ownship())

    assert observations == []
    assert client.world_objects_calls == 1


def test_emitter_does_not_widen_group_salience_for_a_non_emitting_neighbour() -> None:
    """The plan's own pin (Implementation Plan step 11, Risks &
    Unknowns): `group_salient_ids` runs on the whole candidate pool
    *before* visibility is resolved and has no `emitter` parameter at
    all, so an emitter bypass structurally cannot widen it for a
    neighbour.

    **Range chosen to make that claim falsifiable** (review of this plan,
    `BL-B72` Stage A, 2026-10-15): the original fixture placed both T-72Bs
    at 9 km, beyond even `group_salience.py`'s relaxed `RESOLUTION_
    ANGULAR_RADIUS_RAD` threshold (5468.75 m for a 7 m vehicle under
    `UNAIDED_OPTIC`), so group-salience membership could not have changed
    either candidate's outcome whether or not the leak this test exists to
    catch were present -- mutation testing confirmed the old fixture
    passed unchanged under both shapes of that leak. The healthy
    neighbour here instead sits at 4 km: beyond `LOWRES_ANGULAR_RADIUS_
    RAD`'s own lone-presence threshold (2333.33 m, so a correctly-
    unflagged candidate is rejected) but inside the relaxed `RESOLUTION_
    ANGULAR_RADIUS_RAD` one (5468.75 m, so a candidate *wrongly* marked
    `group_salient` -- the plan's own "one AAA gun makes a whole convoy
    visible" risk -- would be admitted instead). The burning unit stays
    at 9 km, still beyond the relaxed threshold either way, so its own
    visibility still comes entirely from the emitter bypass, unaffected
    by this change; only 2 candidates total, still well under `GROUP_
    MIN_MEMBERS` (3), so there is no legitimate group-salience mechanism
    for the neighbour to ride on regardless."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
            _world_object(2, "T-72B", lat_deg=4000.0, lon_deg=200.0),
        ]
    }
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 0.5, "life0": 1.0},
            "unit_2": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 1.0, "life0": 1.0},
        }
    }
    source, _client = _source(world_objects, unit_velocity=unit_velocity)

    observations = source.poll(0.0, _ownship())

    # Only the burning unit (9 km, emitter-bypass-admitted) is reported --
    # the healthy neighbour at 4 km is beyond its own lone-presence
    # threshold and must stay rejected, not ride along on a borrowed
    # group-salience flag.
    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_EMITTER_BURNING


def test_emitter_present_but_cleared_unaided_keeps_ordinary_provenance() -> None:
    """*"an emitter must never lower what Petrovich can see"* -- a
    burning unit well inside its own ordinary presence range keeps the
    ordinary provenance, not `PROVENANCE_EMITTER_BURNING` (the tier was
    never clamped, since no bypass fired)."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=100.0, lon_deg=0.0),
        ]
    }
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 0.5, "life0": 1.0},
        }
    }
    source, _client = _source(world_objects, unit_velocity=unit_velocity)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_VISIBILITY_FILTER_ONLY


# -- Emitter visibility, Stage B (plans/emitter-visibility/plan.md, BL-B73) --


def _firing_active_map(
    unit_name: str, *, targets_ownship: bool = False
) -> dict[str, Any]:
    return {
        "dcs_model_time_s": 0.0,
        "received_wall_clock_s": 0.0,
        "active": {
            unit_name: {
                "kind": "firing",
                "since_sim": 0.0,
                "targets_ownship": targets_ownship,
            }
        },
    }


def test_a_unit_firing_beyond_naked_eye_range_becomes_visible() -> None:
    """End-to-end demonstration, `BL-B73`'s own version of the Stage A
    regression gate above: a T-72B at 9 km, not burning, firing -- only
    the emitter bypass can admit it."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(world_objects, firing=_firing_active_map("unit_1"))

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].classification_raw == object_model.DEFAULT_OP_CLASS
    assert observations[0].provenance == PROVENANCE_EMITTER_FIRING


def test_the_same_unit_not_firing_is_not_visible() -> None:
    """The other half of the regression gate: the identical T-72B at
    9 km, not firing, not burning, is not seen at all."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(world_objects)

    observations = source.poll(0.0, _ownship())

    assert observations == []


def test_a_unit_firing_behind_terrain_stays_invisible() -> None:
    """Gate 4 is unreached by either bypass -- firing included."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(
        world_objects,
        firing=_firing_active_map("unit_1"),
        blocked_unit_names=frozenset({"unit_1"}),
    )

    observations = source.poll(0.0, _ownship())

    assert observations == []


def test_a_unit_firing_at_ownship_sets_the_targets_ownship_provenance() -> None:
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(
        world_objects,
        firing=_firing_active_map("unit_1", targets_ownship=True),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP


def test_a_visible_unit_firing_at_ownship_sets_the_targets_ownship_provenance() -> None:
    """`docs/acceptance/2026-10-20-sortie-feedback.md` F6 follow-up: a
    shooter at 1,073 m (well inside the naked-eye `T-72B` hires threshold
    of 250 m used by `test_a_unit_at_hires_threshold...` above, so no
    bypass is needed at all) must still produce the `targets_ownship`
    provenance once it is admitted and the collector says it targets
    ownship -- the defect was that `targets_ownship_by_object_id` only
    ever looked at `VisibilityResult.emitter_kind`, which stays `None` for
    an ordinary, unaided admission. `classification_raw` is asserted at
    its exact hires value (`"T-72B"`, not `object_model.DEFAULT_OP_CLASS`)
    to prove the tier clamp the emitter *bypass* applies (`visibility.py`'s
    "Emitter bypass" section) was correctly never reached -- this fix must
    not raise or lower classification, only the provenance bit."""
    world_objects = {"objects": [_world_object(1, "T-72B", lat_deg=200.0, lon_deg=0.0)]}
    source, _client = _source(
        world_objects,
        firing=_firing_active_map("unit_1", targets_ownship=True),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP
    assert observations[0].classification_raw == "T-72B"


def test_a_visible_unit_firing_at_others_gets_the_firing_visible_provenance() -> None:
    """**Changed by `plans/taking-fire-visible-shooter/debug.md`'s second
    half** (F6 follow-up "visible unit firing at others", `docs/acceptance/
    2026-10-20-sortie-feedback.md`): this test used to pin the opposite
    behaviour (ordinary provenance, no firing report at all for a visible
    shooter aimed at anything but ownship) as the deliberate scope boundary
    of the targets-ownship fix above. The user's own words settled it the
    other way: *"someone shooting is important, especially if they are
    close -> report"*. A visible (no-bypass-needed) unit firing at
    something *other* than ownship now gets `PROVENANCE_EMITTER_FIRING_
    VISIBLE`, not the bypass-needed `PROVENANCE_EMITTER_FIRING` ("something
    firing... far" stays reserved for a unit that would otherwise have been
    invisible) and not the ordinary `PROVENANCE_VISIBILITY_FILTER_ONLY`.
    `classification_raw` is still asserted at its exact hires value
    (`"T-72B"`) -- the emitter fact must never raise *or* lower
    classification, only add the firing report."""
    world_objects = {"objects": [_world_object(1, "T-72B", lat_deg=200.0, lon_deg=0.0)]}
    source, _client = _source(
        world_objects,
        firing=_firing_active_map("unit_1", targets_ownship=False),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_EMITTER_FIRING_VISIBLE
    assert observations[0].classification_raw == "T-72B"


def test_a_visible_burning_unit_keeps_ordinary_provenance() -> None:
    """The other emitter kind, same scope boundary: a burning unit well
    inside its own ordinary presence range (no bypass needed) keeps the
    ordinary provenance, not `PROVENANCE_EMITTER_BURNING` -- unaffected by
    the `targets_ownship` fix above, since `BURNING` never carries a
    `targets_ownship` bit (`Emitter.targets_ownship`'s own docstring)."""
    world_objects = {"objects": [_world_object(1, "T-72B", lat_deg=200.0, lon_deg=0.0)]}
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 0.5, "life0": 1.0},
        }
    }
    source, _client = _source(world_objects, unit_velocity=unit_velocity)

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_VISIBILITY_FILTER_ONLY
    assert observations[0].classification_raw == "T-72B"


def test_firing_wins_over_burning_for_the_same_unit() -> None:
    """The plan's "Co-moving Fields" precedence, exercised end to end:
    a unit both burning and firing resolves to the `FIRING` provenance."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ]
    }
    unit_velocity = {
        "samples": {
            "unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0, "life": 0.5, "life0": 1.0},
        }
    }
    source, _client = _source(
        world_objects,
        unit_velocity=unit_velocity,
        firing=_firing_active_map("unit_1"),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].provenance == PROVENANCE_EMITTER_FIRING


# -- Cluster-level fold, genuine multi-member clusters (`plans/
# taking-fire-visible-shooter/debug.md` review: every fold test above --
# `member_emitter_kinds` and `member_targets_ownship` alike -- used a
# single-member cluster, which only trivially satisfies `len({x}) == 1`
# unanimity. These use the same down-range clustering recipe as
# `test_two_close_candidates_emit_one_clustered_observation` above (two
# candidates 20 m apart along the line of sight at ~500 m range, well
# inside the down-range merge radius there) to exercise the real,
# 2+-member aggregation. --


def _two_unit_firing_active_map(
    **targets_ownship_by_unit_name: bool,
) -> dict[str, Any]:
    return {
        "dcs_model_time_s": 0.0,
        "received_wall_clock_s": 0.0,
        "active": {
            unit_name: {
                "kind": "firing",
                "since_sim": 0.0,
                "targets_ownship": targets_ownship,
            }
            for unit_name, targets_ownship in targets_ownship_by_unit_name.items()
        },
    }


def test_two_clustered_visible_units_both_firing_at_others_get_the_firing_visible_provenance() -> (
    None
):
    """The positive half of the genuine-cluster gap: two clustered,
    unaided (no-bypass-needed) members both firing at something other than
    ownship fold to `PROVENANCE_EMITTER_FIRING_VISIBLE` -- unanimous
    `True`, nothing less, same "identical keeps" rule `member_emitter_
    kinds`/`member_targets_ownship` already follow."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=500.0, lon_deg=0.0),
            _world_object(2, "T-72B", lat_deg=520.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(
        world_objects,
        firing=_two_unit_firing_active_map(unit_1=False, unit_2=False),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].count_bucket == "OP_1UNIT"
    assert observations[0].provenance == PROVENANCE_EMITTER_FIRING_VISIBLE


def test_a_mixed_firing_cluster_degrades_to_ordinary_provenance() -> None:
    """The "disagreement degrades" half: one clustered member firing at
    others (visible, no bypass needed) alongside one member not firing at
    all must not inherit the firing-visible provenance -- the exact gap
    the plan review flagged (every existing fold test, firing or burning,
    only ever used a single-member cluster)."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=500.0, lon_deg=0.0),
            _world_object(2, "T-72B", lat_deg=520.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(
        world_objects,
        firing=_firing_active_map("unit_1", targets_ownship=False),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].count_bucket == "OP_1UNIT"
    assert observations[0].provenance == PROVENANCE_VISIBILITY_FILTER_ONLY


def test_a_cluster_mixing_targets_ownship_and_firing_at_others_degrades() -> None:
    """A narrower disagreement than the one above: both members are
    visible and firing, but one targets ownship and the other does not.
    Neither `member_targets_ownship` nor the new `member_firing_visible`
    set is unanimous (the targeting member's own `firing_visible` flag is
    `False` by construction -- `_build_observation`'s own docstring, check
    2's condition (c) -- so it cannot smuggle the cluster into
    `PROVENANCE_EMITTER_FIRING_VISIBLE` either), so this degrades to the
    ordinary provenance rather than picking either firing wording."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=500.0, lon_deg=0.0),
            _world_object(2, "T-72B", lat_deg=520.0, lon_deg=0.0),
        ]
    }
    source, _client = _source(
        world_objects,
        firing=_two_unit_firing_active_map(unit_1=True, unit_2=False),
    )

    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    assert observations[0].count_bucket == "OP_1UNIT"
    assert observations[0].provenance == PROVENANCE_VISIBILITY_FILTER_ONLY


def test_a_stale_firing_snapshot_is_discarded() -> None:
    """`FIRING_MAX_AGE_S` -- a firing snapshot whose own `dcs_model_time_s`
    is far older than this poll's world-objects snapshot is treated the
    same as no firing at all, mirroring the LOS feed's own skew discipline."""
    world_objects = {
        "objects": [
            _world_object(1, "T-72B", lat_deg=9000.0, lon_deg=0.0),
        ],
        "dcs_model_time_s": 100.0,
    }
    stale_firing = {
        "dcs_model_time_s": 0.0,  # 100 s stale, far past FIRING_MAX_AGE_S
        "received_wall_clock_s": 0.0,
        "active": {
            "unit_1": {"kind": "firing", "since_sim": 0.0, "targets_ownship": False}
        },
    }
    source, _client = _source(world_objects, firing=stale_firing)

    observations = source.poll(0.0, _ownship())

    assert observations == []


def test_reset_for_new_mission_clears_dedup_and_counter_state() -> None:
    """`BL-15` Stage 1 (`plans/bl15-mission-start/plan.md`) -- pokes the
    private dedup/acquisition/counter attributes directly rather than
    driving a real `poll()` through the visibility pipeline, which is
    already covered by every other test in this file; this test is only
    about the reset mechanism itself. `live_los_coverage` (Stage 1
    Decision 5) is poked the same way, since `check_visibility` is the
    only other writer and this test deliberately avoids driving the real
    pipeline."""
    source, _client = _source(None)
    source._previously_seen_at[7] = 10.0
    source._acquired_at[7] = 10.0
    source._object_id_to_last_observation_id[7] = "obs_1"
    source._observation_count = 3
    source.live_los_coverage.evaluated = 5
    source.live_los_coverage.no_verdict = 2

    source.reset_for_new_mission()

    assert source._previously_seen_at == {}
    assert source._acquired_at == {}
    assert source._object_id_to_last_observation_id == {}
    assert source._observation_count == 0
    assert source.live_los_coverage.evaluated == 0
    assert source.live_los_coverage.no_verdict == 0


#: Every `NakedEyePerceptionSource` field, bucketed -- `review.md`'s Optional
#: Refinement 1. Three buckets, matching the class's own three shapes of
#: field (see `reset_for_new_mission`'s own docstring for the per-poll-
#: overwritten reasoning, and `peripheral_stimulus_ids`'s own field
#: docstring for why it sits there too despite nothing writing it yet).
_PRESERVED_FIELDS: frozenset[str] = frozenset(
    {
        "aircraft_client",
        "theatre",
        "world_model_conn",
        "forest",
        "emit_mode",
        "trace_sink",
    }
)
_PER_POLL_OVERWRITTEN_FIELDS: frozenset[str] = frozenset(
    {
        "scan_plan",
        "optic",
        "sight_cone",
        "gaze_centre_elevation_deg",
        "suppressed_until_sim",
        "peripheral_stimulus_ids",
    }
)
_RESET_FIELDS: frozenset[str] = frozenset(
    {
        "_previously_seen_at",
        "_acquired_at",
        "_object_id_to_last_observation_id",
        "_observation_count",
        "live_los_coverage",
    }
)


def test_reset_for_new_mission_field_coverage_is_complete() -> None:
    """Enumerates `dataclasses.fields(NakedEyePerceptionSource)` at test
    time and asserts every one is accounted for by exactly one of the
    three buckets above -- a field added later and placed in none of them
    fails this test immediately, rather than silently leaking across a
    mission restart with no test ever noticing (the gap `review.md`
    named)."""
    field_names = {f.name for f in dataclasses.fields(NakedEyePerceptionSource)}
    all_buckets = _PRESERVED_FIELDS | _PER_POLL_OVERWRITTEN_FIELDS | _RESET_FIELDS
    assert field_names == all_buckets
    assert _PRESERVED_FIELDS.isdisjoint(_PER_POLL_OVERWRITTEN_FIELDS)
    assert _PRESERVED_FIELDS.isdisjoint(_RESET_FIELDS)
    assert _PER_POLL_OVERWRITTEN_FIELDS.isdisjoint(_RESET_FIELDS)
