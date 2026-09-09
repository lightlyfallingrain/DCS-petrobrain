"""`NakedEyePerceptionSource` -- the second, independent concrete
`PerceptionSource` PB-1.5 adds (`plans/pb1.5-naked-eye-detection/plan.md`).

Deliberately not a `HybridPerceptionSource` subclass/extension: the two
sources have fundamentally different gating mechanisms (a real HelperAI
detection-existence signal vs. `visibility.py`'s ED-model-grounded but
still synthetic plausibility filter) and shouldn't share a class hierarchy
that implies a common detection-existence story. See `visibility.py`'s
module docstring for the binocular-observation premise this channel models
-- the "naked_eye" name is a known misnomer, kept because the milestone,
branch, and research file all carry it (plan Decision #6).

Each `poll()`:
1. Fetches `GET /world_objects/latest` only -- no dependency on
   `/petrovich_indication/latest` (unlike `HybridPerceptionSource`, this
   channel has no real detection-existence signal to gate on at all; see
   `visibility.py`'s module docstring and the plan's Invariant Check). Runs
   the raw candidate list through `association.exclude_ownship()` before
   anything else -- `LoGetWorldObjects` is unfiltered ground truth and
   includes the player's own aircraft (see that function's docstring; a bug
   found via a live sortie, `plans/pb1.5-naked-eye-detection/debug.md`).
2. Runs every candidate through `visibility.check_visibility()`.
3. **Quantises the surviving geometry to ED's ambient-callout vocabulary**
   (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
   ambient-detection.md`, Session 5 Finding 2) before building an
   `Observation`: bearing snapped to the nearest of the 12 `OP_A1H`...
   `OP_A12H` clock positions (relative to ownship heading, then expressed
   back as a true bearing so `Observation.bearing_deg`'s existing
   true-bearing convention, per `geometry.py`'s module docstring, is
   preserved), range snapped to the nearest of the 24 `OP_D...` buckets, and
   `object_model.py`'s class bucket in place of a free-text classification
   guess in `classification_raw`. This is the plan's anti-omniscience
   mechanism at the *output* layer, distinct from and additional to
   `visibility.py`'s gate at the *input* layer.

   **Scope limit** (plan Decision #5, proceeding on the stated
   recommendation): only bearing/range/class are quantised per object here.
   Finding 2's count/formation buckets (`OP_1UNIT`...`OP_MORETHAN15UNITS`,
   `OP_SINGLE`/`OP_GROUP`) describe an *aggregate* callout across a cluster
   of objects, which this channel's per-object-id emission model doesn't
   produce without first building object clustering -- out of scope for v1.

   **`derived_world_position` is deliberately NOT quantised** -- it carries
   `candidate`'s exact ground-truth x/z, the same way `HybridPerceptionSource`
   populates it, because that field is DCS ground truth (`code owns facts`,
   never fabricated or fuzzed) reserved for future geometry/fusion work
   (e.g. BL-2's contact memory), not the crew-facing report. The
   anti-omniscience quantisation applies to the fields that represent what
   a crew member could actually have perceived and said out loud
   (`bearing_deg`, `range_m`, `classification_raw`), not to this channel's
   internal bookkeeping of where the real object actually is.
4. **Per-object debounce**: tracks the set of `object_id`s that passed the
   filter on the *previous* poll. Emits one `Observation` only for an
   `object_id` newly entering the currently-visible set (mirrors
   `HybridPerceptionSource`'s change-debounce, but keyed on object-id set
   membership rather than text-equality, since there's no text here). A
   missing `/world_objects/latest` snapshot resets this state, mirroring
   `HybridPerceptionSource.poll()`'s debounce-reset-on-gap for
   `middle_list_text` -- so the next real snapshot's candidates are treated
   as newly-appearing rather than silently already-seen.
5. **Simultaneous-detection cap** (`NAKED_EYE_MAX_NEW_PER_POLL`) -- caps how
   many *newly-appearing* objects one poll can emit, nearest-first (by
   exact, un-quantised range). Objects visible-but-not-emitted this poll
   still count as "previously visible" for the next poll's debounce
   comparison -- per the plan's Affected Modules wording ("tracks the set of
   `object_id`s that passed the filter on the *previous* poll"), this cap
   gates *emission*, not visible-set membership; a capped-out object is not
   retried on a later poll unless it actually leaves and re-enters the
   visible set. Guards against an unrealistic "instant global awareness"
   flood the moment the aircraft turns toward a dense object cluster.
"""

from __future__ import annotations

import math
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Final

from aircraft_client import AircraftLayerClient
from perception import object_model
from perception.association import WorldObjectCandidate, exclude_ownship
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
)
from perception.visibility import VisibilityResult, check_visibility

#: Caps newly-emitted detections per poll tick, nearest-first. Plan
#: Decision #2 -- proceeding on the stated recommendation (not explicitly
#: affirmed by the user), flagged as cheap to change mid-implementation.
NAKED_EYE_MAX_NEW_PER_POLL: Final[int] = 3

#: Reads differently from Hybrid's `"petrovich_indication+world_objects"` --
#: a filter pass here is structurally weaker evidence than a real HelperAI
#: detection (plan Invariant Check: "every naked-eye `Observation`'s
#: `provenance` string must read differently from Hybrid's").
PROVENANCE_VISIBILITY_FILTER_ONLY: Final[str] = "world_objects/visibility_filter_only"

#: `derived_world_position.method` for every emitted naked-eye `Observation`
#: -- distinct from Hybrid's `association.CONFIDENT_ASSOCIATION_METHOD`/
#: `AMBIGUOUS_ASSOCIATION_METHOD`, since there is no association step here.
_DERIVED_POSITION_METHOD: Final[str] = "visibility_filter"

#: The 12 ED clock-bearing fragments (`OP_A1H`...`OP_A12H`), keyed by clock
#: hour, relative to ownship heading -- `OP_A12H` is dead ahead (0 deg
#: relative), `OP_A6H` is directly astern (180 deg relative).
_CLOCK_BUCKET_DEG: Final[float] = 30.0
_CLOCK_BUCKET_NAMES: Final[dict[int, str]] = {
    1: "OP_A1H",
    2: "OP_A2H",
    3: "OP_A3H",
    4: "OP_A4H",
    5: "OP_A5H",
    6: "OP_A6H",
    7: "OP_A7H",
    8: "OP_A8H",
    9: "OP_A9H",
    10: "OP_A10H",
    11: "OP_A11H",
    12: "OP_A12H",
}

#: The 24 ED range-bucket fragments (`OP_D100M`...`OP_D10k`), as
#: `(name, upper_bound_m)` pairs in ascending order -- a range snaps to the
#: first bucket whose upper bound it does not exceed. `NAKED_EYE_RANGE_CAP_M
#: = 2500.0` (`visibility.py`) means only the first 13 buckets (up to
#: `OP_D2_2p5k`) are reachable in practice; the full 24-bucket table from
#: `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-
#: ambient-detection.md` Session 5 Finding 2 is kept intact rather than
#: truncated, so this table stays a faithful copy of ED's own vocabulary
#: independent of this channel's own range cap.
_RANGE_BUCKETS_M: Final[tuple[tuple[str, float], ...]] = (
    ("OP_D100M", 100.0),
    ("OP_D200M", 200.0),
    ("OP_D300M", 300.0),
    ("OP_D400M", 400.0),
    ("OP_D500M", 500.0),
    ("OP_D600M", 600.0),
    ("OP_D700M", 700.0),
    ("OP_D800M", 800.0),
    ("OP_D900M", 900.0),
    ("OP_D1000M", 1000.0),
    ("OP_D1_1p5k", 1500.0),
    ("OP_D1p5_2k", 2000.0),
    ("OP_D2_2p5k", 2500.0),
    ("OP_D2p5_3k", 3000.0),
    ("OP_D3_3p5k", 3500.0),
    ("OP_D3p5_4k", 4000.0),
    ("OP_D4_4p5k", 4500.0),
    ("OP_D4p5_5k", 5000.0),
    ("OP_D5_6k", 6000.0),
    ("OP_D6_7k", 7000.0),
    ("OP_D7_8k", 8000.0),
    ("OP_D8_9k", 9000.0),
    ("OP_D9_10k", 10000.0),
    ("OP_D10k", math.inf),
)


@dataclass
class NakedEyePerceptionSource:
    """See module docstring. `world_model_conn` is a read-only world-model
    `.sqlite` connection (`perception.geometry.open_world_model`), needed
    for `visibility.py`'s terrain-LOS gate -- the first concrete consumer of
    `geometry.line_of_sight_clear`, which `HybridPerceptionSource` never
    exercised."""

    aircraft_client: AircraftLayerClient
    theatre: str
    world_model_conn: sqlite3.Connection

    _previously_visible_ids: frozenset[int] = field(
        default_factory=frozenset, init=False, repr=False
    )
    _observation_count: int = field(default=0, init=False, repr=False)

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        world_objects = self.aircraft_client.get_world_objects_latest()
        if world_objects is None:
            # No snapshot -- reset visible-set state so the next real
            # snapshot's candidates are treated as newly-appearing, mirroring
            # HybridPerceptionSource's debounce-reset-on-gap for
            # middle_list_text (see that module's poll() docstring).
            self._previously_visible_ids = frozenset()
            return []

        candidates = exclude_ownship(
            [
                WorldObjectCandidate.from_dict(obj, theatre=self.theatre)
                for obj in world_objects.get("objects", [])
            ],
            ownship_state,
        )

        visible: list[tuple[WorldObjectCandidate, VisibilityResult]] = []
        for candidate in candidates:
            result = check_visibility(
                ownship_state, candidate, self.world_model_conn, self.theatre
            )
            if result is not None:
                visible.append((candidate, result))

        currently_visible_ids = frozenset(
            candidate.object_id for candidate, _result in visible
        )
        newly_visible = [
            (candidate, result)
            for candidate, result in visible
            if candidate.object_id not in self._previously_visible_ids
        ]
        newly_visible.sort(key=lambda item: item[1].range_m)
        capped = newly_visible[:NAKED_EYE_MAX_NEW_PER_POLL]

        self._previously_visible_ids = currently_visible_ids

        return [
            self._build_observation(now_sim, ownship_state, candidate, result)
            for candidate, result in capped
        ]

    def _build_observation(
        self,
        now_sim: float,
        ownship_state: OwnshipState,
        candidate: WorldObjectCandidate,
        result: VisibilityResult,
    ) -> Observation:
        quantised_bearing_deg = _quantise_bearing(
            ownship_state.heading_true_deg, result.bearing_deg
        )[0]
        quantised_range_m = _quantise_range_m(result.range_m)[0]
        profile = object_model.profile_for(candidate.object_type)

        self._observation_count += 1
        return Observation(
            id=f"OBS_{self._observation_count}",
            contact_id=None,
            t_sim=now_sim,
            t_wall=time.time(),
            source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
            classification_raw=profile.op_class,
            bearing_deg=quantised_bearing_deg,
            range_m=quantised_range_m,
            ownship_at_observation=ownship_state,
            derived_world_position=DerivedWorldPosition(
                x=candidate.x,
                z=candidate.z,
                confidence=result.confidence,
                method=_DERIVED_POSITION_METHOD,
            ),
            provenance=PROVENANCE_VISIBILITY_FILTER_ONLY,
        )


def _quantise_bearing(
    heading_true_deg: float, true_bearing_deg: float
) -> tuple[float, str]:
    """Snap `true_bearing_deg` to the nearest of the 12 `OP_A1H`...`OP_A12H`
    clock positions, relative to `heading_true_deg`. Returns
    `(quantised_true_bearing_deg, bucket_name)` -- the quantised value is
    converted back to a true bearing (not left as a heading-relative clock
    angle) so it stays consistent with `Observation.bearing_deg`'s existing
    true-bearing convention (`geometry.py`'s module docstring)."""
    relative_deg = (true_bearing_deg - heading_true_deg) % 360.0
    clock_hour = round(relative_deg / _CLOCK_BUCKET_DEG) % 12
    if clock_hour == 0:
        clock_hour = 12
    quantised_relative_deg = 0.0 if clock_hour == 12 else clock_hour * _CLOCK_BUCKET_DEG
    quantised_true_deg = (heading_true_deg + quantised_relative_deg) % 360.0
    return quantised_true_deg, _CLOCK_BUCKET_NAMES[clock_hour]


def _quantise_range_m(range_m: float) -> tuple[float, str]:
    """Snap `range_m` to the nearest of the 24 `OP_D...` range buckets.
    Returns `(bucket_upper_bound_m, bucket_name)` -- the first bucket whose
    upper bound `range_m` does not exceed."""
    for name, upper_bound_m in _RANGE_BUCKETS_M:
        if range_m <= upper_bound_m:
            return upper_bound_m, name
    return math.inf, _RANGE_BUCKETS_M[-1][0]  # unreachable: last bound is inf
