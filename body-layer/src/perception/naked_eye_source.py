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
   the raw candidate list through `association.filter_ownship()` before
   anything else -- `LoGetWorldObjects` is unfiltered ground truth and
   includes the player's own aircraft, identified by the aircraft-layer's
   `is_ownship` flag (see that function's docstring; the flag replaced an
   earlier proximity heuristic found necessary via a live sortie,
   `plans/pb1.5-naked-eye-detection/debug.md`).
2. Runs every candidate through `visibility.check_visibility()`.
3. **Clusters the admitted candidates at the channel's own honest
   resolution limit, then quantises per cluster** (`plans/
   group-contact-model/plan.md` Stage 2 -- supersedes the per-object
   quantisation this module originally did; see that plan for why per-object
   emission was itself the defect). `_cluster_candidate` projects each
   admitted `(candidate, result)` pair into `perception.clustering.
   ClusterCandidate` (ground-truth x/z/alt, slant range, characteristic
   size, and this candidate's own individually-resolved classification
   claim); `perception.clustering.cluster_candidates` groups them by true
   3D angular separability at ownship's own position (Stage 3b-i rev.2 --
   the merge test is the angle subtended at the observer against each
   candidate's own apparent angular size, not a world-space ellipse; see
   `clustering.py`'s docstring); single-link, no chaining cap yet --
   Stage 3b-ii's job. `_build_observation` emits exactly one `Observation`
   per resulting
   cluster: bearing/range quantised from the cluster's *centroid*, not any
   one member's own geometry (bearing snapped to the nearest of the 12
   `OP_A1H`...`OP_A12H` clock positions, relative to ownship heading then
   expressed back as a true bearing per `geometry.py`'s convention; range
   snapped to the nearest of the 24 `OP_D...` buckets); `classification_raw`/
   `classification_level` and `count_bucket` come straight from the
   `Cluster` (identical class across every member keeps that class,
   otherwise degrades to the presence root -- see `clustering.py`'s
   docstring). ED's `OP_1UNIT`...`OP_MORETHAN15UNITS` count vocabulary
   (Session 5 Finding 2, `aircraft-layer/research/2026-09-08-pb1-5-
   worldobjects-filter-and-ambient-detection.md`), previously out of scope
   (plan Decision #5) for lack of a clustering mechanism, is exactly what
   `Cluster.count_bucket` now supplies.

   **`derived_world_position` is deliberately NOT quantised** -- it carries
   the cluster's centroid, the mean of its members' exact ground-truth x/z
   (a documented meaning change from "one candidate's own position" to "a
   cluster's centroid," per the plan's Risks section), because that field is
   DCS ground truth (`code owns facts`, never fabricated or fuzzed) reserved
   for future geometry/fusion work, not the crew-facing report. The
   anti-omniscience quantisation applies to the fields that represent what a
   crew member could actually have perceived and said out loud
   (`bearing_deg`, `range_m`, `classification_raw`, `count_bucket`), not to
   this channel's internal bookkeeping of where the real objects actually
   are.
4. **Per-object debounce** (`emit_mode="on_change"`, the default): tracks the
   set of `object_id`s that passed the filter on the *previous* poll. Emits
   one `Observation` only for an `object_id` newly entering the
   currently-visible set (mirrors `HybridPerceptionSource`'s change-debounce,
   but keyed on object-id set membership rather than text-equality, since
   there's no text here). A missing `/world_objects/latest` snapshot resets
   this state, mirroring `HybridPerceptionSource.poll()`'s
   debounce-reset-on-gap for `middle_list_text` -- so the next real snapshot's
   candidates are treated as newly-appearing rather than silently
   already-seen.
5. **Simultaneous-detection cap** (`NAKED_EYE_MAX_NEW_PER_POLL`) -- under
   `emit_mode="on_change"`, caps how many *newly-appearing* objects one poll
   can emit, nearest-first (by exact, un-quantised range). Objects
   visible-but-not-emitted this poll still count as "previously visible" for
   the next poll's debounce comparison -- per the plan's Affected Modules
   wording ("tracks the set of `object_id`s that passed the filter on the
   *previous* poll"), this cap gates *emission*, not visible-set membership;
   a capped-out object is not retried on a later poll unless it actually
   leaves and re-enters the visible set. Guards against an unrealistic
   "instant global awareness" flood the moment the aircraft turns toward a
   dense object cluster.

   `emit_mode="every_poll"` (`plans/pb2-contact-memory/plan.md` Stage 3, its
   Interface confirmation gap 2) re-reads this same cap as an
   *acquisition-rate* limit instead: a separate `_acquired_ids` set grows by
   at most `NAKED_EYE_MAX_NEW_PER_POLL` newly-visible objects per poll
   (nearest-first, same throttle), but every object already in that set
   keeps emitting an `Observation` on *every* subsequent poll for as long as
   it stays visible -- it is never capped out of its own repeat emission the
   way `on_change` caps it out of re-*entering* the debounce set. This is
   deliberately a second, independent piece of state from the `on_change`
   debounce set below (`_previously_visible_ids`), not a re-read of the same
   field: `on_change`'s existing behaviour (an object capped out of a
   simultaneous flood is marked "already seen" and never retried at all,
   `test_candidates_dropped_by_the_cap_are_not_retried_next_poll`) must stay
   byte-for-byte, while `every_poll`'s acquisition set must instead keep
   retrying a not-yet-acquired object every poll until the throttle admits
   it. The two sets happen to evolve identically except in that overflow
   case.

   **Stage 2 scoping decision**: this cap still throttles admission of
   individual *objects* into `to_emit`, exactly as before -- clustering
   happens strictly after, over whatever `to_emit` this poll's cap allowed
   through. `NAKED_EYE_MAX_NEW_PER_POLL` therefore does not yet cap
   *clusters* directly (a real cluster larger than the cap can still only
   have `NAKED_EYE_MAX_NEW_PER_POLL` of its members admitted in one poll,
   under-reporting that cluster's true size until acquisition catches up
   over several polls). Re-reading the cap as a true per-cluster limit is
   Stage 3's explicit job (`plans/group-contact-model/plan.md`'s
   Implementation Plan lists it under that stage's calibration work), not
   pre-tuned here.
6. **Object-permanence correlation, generalised to clusters** (`plans/
   contact-duplication-ambiguity-runaway/plan.md`, extended by `plans/
   group-contact-model/plan.md` Stage 2): a third, independent,
   **persistent** `_object_id_to_last_observation_id: dict[int, str]` map,
   keyed by DCS `object_id`, holding the most recently emitted
   `Observation.id` that object contributed to -- never cleared, including
   across a `world_objects is None` gap. `_build_observation` resolves each
   cluster's `continues_observation_id` by **majority object overlap**: every
   member with a prior map entry casts that entry as a vote, the most common
   vote wins (ties broken deterministically, lowest observation id string),
   and every member's entry is then overwritten with this poll's new cluster
   `Observation.id` regardless of whether it was the winning vote -- a
   cluster that just absorbed a neighbour, or just split off from one, still
   correlates its majority onto the contact that cluster's history actually
   belongs to. `belief.contacts.ContactStore` is the consumer that decides
   whether to trust this reference (subject to its own expiry check, `belief.
   decay.object_id_continuity_valid`) -- this module only ever reports "most
   of this report's members were previously part of this other report."
"""

from __future__ import annotations

import math
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Final, Literal

from aircraft_client import AircraftLayerClient
from perception import object_model
from perception.association import WorldObjectCandidate, filter_ownship
from perception.clustering import Cluster, ClusterCandidate, cluster_candidates
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.reporting_names import reporting_name_for
from perception.source import (
    OBSERVATION_ID_PREFIX_NAKED_EYE,
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
    #: `"on_change"` (default) preserves the original per-object debounce
    #: byte-for-byte -- every existing test constructs this class without
    #: passing `emit_mode` and must keep passing untouched
    #: (`plans/pb2-contact-memory/plan.md` Stage 3). `"every_poll"` emits one
    #: `Observation` per currently-acquired, currently-visible object on
    #: every poll -- see module docstring point 5 for how
    #: `NAKED_EYE_MAX_NEW_PER_POLL` is re-read under this mode.
    emit_mode: Literal["on_change", "every_poll"] = "on_change"

    _previously_visible_ids: frozenset[int] = field(
        default_factory=frozenset, init=False, repr=False
    )
    #: `emit_mode="every_poll"`'s own acquisition-set state -- deliberately
    #: separate from `_previously_visible_ids` above (see module docstring
    #: point 5); unused under `emit_mode="on_change"`.
    _acquired_ids: frozenset[int] = field(
        default_factory=frozenset, init=False, repr=False
    )
    #: Object-permanence correlation state (module docstring point 6) --
    #: deliberately a third, independent piece of state from
    #: `_previously_visible_ids`/`_acquired_ids` above: never cleared,
    #: including on a `world_objects is None` gap.
    _object_id_to_last_observation_id: dict[int, str] = field(
        default_factory=dict, init=False, repr=False
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
            self._acquired_ids = frozenset()
            return []

        candidates = filter_ownship(
            [
                WorldObjectCandidate.from_dict(obj, theatre=self.theatre)
                for obj in world_objects.get("objects", [])
            ]
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

        if self.emit_mode == "every_poll":
            to_emit = self._acquire_every_poll(visible, currently_visible_ids)
        else:
            to_emit = self._acquire_on_change(visible, currently_visible_ids)

        confidence_by_object_id = {
            candidate.object_id: result.confidence for candidate, result in to_emit
        }
        observer = GeoPosition(
            x=ownship_state.x, z=ownship_state.z, alt_m=ownship_state.alt_m
        )
        clusters = cluster_candidates(
            [
                self._cluster_candidate(candidate, result)
                for candidate, result in to_emit
            ],
            observer,
        )
        return self._build_observations(
            now_sim, ownship_state, clusters, confidence_by_object_id
        )

    def _build_observations(
        self,
        now_sim: float,
        ownship_state: OwnshipState,
        clusters: list[Cluster],
        confidence_by_object_id: dict[int, float],
    ) -> list[Observation]:
        """One `Observation` per `clusters` entry, resolving majority-overlap
        continuity (module docstring point 6) across the *whole* batch before
        minting any of them -- a two-pass split, not per-cluster, so a
        cluster that splits into several children never lets more than one
        of them claim the parent's continuity (the plan's "the id follows
        the majority" rule, `plans/group-contact-model/plan.md`'s Splitting
        section)."""
        cluster_votes = [
            Counter(
                self._object_id_to_last_observation_id[member.object_id]
                for member in cluster.members
                if member.object_id in self._object_id_to_last_observation_id
            )
            for cluster in clusters
        ]

        # For every historical observation id any cluster's members trace
        # back to, find the single cluster index holding the most votes for
        # it -- ties broken by lowest cluster index, deterministic and
        # arbitrary (the plan's own documented caveat: the surviving
        # identity among equally-sized children is physically meaningless,
        # only deterministic).
        best_count_for_id: dict[str, int] = {}
        winner_index_for_id: dict[str, int] = {}
        for index, votes in enumerate(cluster_votes):
            for historical_id, count in votes.items():
                if (
                    historical_id not in best_count_for_id
                    or count > best_count_for_id[historical_id]
                ):
                    best_count_for_id[historical_id] = count
                    winner_index_for_id[historical_id] = index

        observations: list[Observation] = []
        for index, cluster in enumerate(clusters):
            votes = cluster_votes[index]
            continues_observation_id: str | None = None
            if votes:
                top_id = max(
                    sorted(votes), key=lambda historical_id: votes[historical_id]
                )
                # Only the majority owner of its own top vote inherits it --
                # a minority split (this cluster's top vote is someone
                # else's majority) founds fresh instead.
                if winner_index_for_id[top_id] == index:
                    continues_observation_id = top_id
            observations.append(
                self._build_observation(
                    now_sim,
                    ownship_state,
                    cluster,
                    confidence_by_object_id,
                    continues_observation_id,
                )
            )
        return observations

    @staticmethod
    def _cluster_candidate(
        candidate: WorldObjectCandidate, result: VisibilityResult
    ) -> ClusterCandidate:
        """Project one admitted `(candidate, result)` pair into `perception.
        clustering`'s own lightweight shape -- ground-truth x/z for the
        position-only clustering decision, plus this candidate's own
        individually-derived classification claim (module docstring point 3)
        for `Cluster`'s aggregate-label logic to consume."""
        profile = object_model.profile_for(candidate.object_type)
        classification_raw, classification_level = _classification_for_tier(
            result.tier, candidate.object_type, profile.op_class
        )
        return ClusterCandidate(
            object_id=candidate.object_id,
            x=candidate.x,
            z=candidate.z,
            alt_m=candidate.alt_m,
            range_m=result.range_m,
            size_m=profile.size_m,
            classification_raw=classification_raw,
            classification_level=classification_level,
        )

    def _acquire_on_change(
        self,
        visible: list[tuple[WorldObjectCandidate, VisibilityResult]],
        currently_visible_ids: frozenset[int],
    ) -> list[tuple[WorldObjectCandidate, VisibilityResult]]:
        """Original per-object debounce: emit only newly-visible objects,
        nearest-first, capped at `NAKED_EYE_MAX_NEW_PER_POLL`. Every
        currently-visible object -- emitted or capped-out -- becomes
        "already seen" for the next poll (see module docstring point 5)."""
        newly_visible = [
            (candidate, result)
            for candidate, result in visible
            if candidate.object_id not in self._previously_visible_ids
        ]
        newly_visible.sort(key=lambda item: item[1].range_m)
        capped = newly_visible[:NAKED_EYE_MAX_NEW_PER_POLL]

        self._previously_visible_ids = currently_visible_ids
        return capped

    def _acquire_every_poll(
        self,
        visible: list[tuple[WorldObjectCandidate, VisibilityResult]],
        currently_visible_ids: frozenset[int],
    ) -> list[tuple[WorldObjectCandidate, VisibilityResult]]:
        """`emit_mode="every_poll"`'s acquisition-rate throttle: at most
        `NAKED_EYE_MAX_NEW_PER_POLL` not-yet-acquired objects (nearest-first)
        join the acquired set this poll; every acquired object still visible
        this poll is emitted, regardless of when it was acquired -- so a
        continuously-visible object emits every poll instead of aging to
        "lost" the way a blocked-cap re-entry would (module docstring
        point 5)."""
        not_yet_acquired = [
            (candidate, result)
            for candidate, result in visible
            if candidate.object_id not in self._acquired_ids
        ]
        not_yet_acquired.sort(key=lambda item: item[1].range_m)
        newly_acquired = not_yet_acquired[:NAKED_EYE_MAX_NEW_PER_POLL]
        newly_acquired_ids = frozenset(
            candidate.object_id for candidate, _result in newly_acquired
        )

        self._acquired_ids = (
            self._acquired_ids & currently_visible_ids
        ) | newly_acquired_ids

        return [
            (candidate, result)
            for candidate, result in visible
            if candidate.object_id in self._acquired_ids
        ]

    def _build_observation(
        self,
        now_sim: float,
        ownship_state: OwnshipState,
        cluster: Cluster,
        confidence_by_object_id: dict[int, float],
        continues_observation_id: str | None,
    ) -> Observation:
        """One `Observation` for `cluster` -- `plans/group-contact-model/
        plan.md` Stage 2: this is the emission unit now, not one per
        candidate. Bearing/range are quantised from the cluster's centroid
        (ground-truth mean position of its members), not from any one
        member's own geometry -- the honest report a crew member could give
        for a cluster is "that group, over there," not any individual
        member's exact bearing. `continues_observation_id` is resolved by
        `_build_observations` across the whole batch, not here -- see that
        method's docstring."""
        observer = GeoPosition(
            x=ownship_state.x, z=ownship_state.z, alt_m=ownship_state.alt_m
        )
        centroid = GeoPosition(
            x=cluster.centroid_x, z=cluster.centroid_z, alt_m=ownship_state.alt_m
        )
        true_bearing_deg = bearing_deg(observer, centroid)
        true_range_m = range_m(observer, centroid)
        quantised_bearing_deg = _quantise_bearing(
            ownship_state.heading_true_deg, true_bearing_deg
        )[0]
        quantised_range_m = _quantise_range_m(true_range_m)[0]

        self._observation_count += 1
        observation_id = f"{OBSERVATION_ID_PREFIX_NAKED_EYE}_{self._observation_count}"
        for member in cluster.members:
            self._object_id_to_last_observation_id[member.object_id] = observation_id

        confidence = min(
            confidence_by_object_id[member.object_id] for member in cluster.members
        )
        return Observation(
            id=observation_id,
            contact_id=None,
            t_sim=now_sim,
            t_wall=time.time(),
            source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
            classification_raw=cluster.classification_raw,
            bearing_deg=quantised_bearing_deg,
            range_m=quantised_range_m,
            ownship_at_observation=ownship_state,
            derived_world_position=DerivedWorldPosition(
                x=cluster.centroid_x,
                z=cluster.centroid_z,
                confidence=confidence,
                method=_DERIVED_POSITION_METHOD,
            ),
            provenance=PROVENANCE_VISIBILITY_FILTER_ONLY,
            classification_level=cluster.classification_level,
            continues_observation_id=continues_observation_id,
            count_bucket=cluster.count_bucket,
        )


#: Bare `int` mirrors of `belief.classification.SpecificityLevel`'s `CLASS`
#: (2) and `TYPE` (3) values -- `perception/` must not import `belief/`
#: (`source.py`'s module docstring), so this module states the same two
#: integers directly rather than importing the enum. `PRESENCE` (1) is not
#: named here: it is unreachable until Stage 7 moves the gating tier to
#: `lowres`, at which point `visibility.VisibilityResult.tier` can actually
#: be `"lowres"`.
_CLASSIFICATION_LEVEL_CLASS: Final[int] = 2
_CLASSIFICATION_LEVEL_TYPE: Final[int] = 3


def _classification_for_tier(
    tier: str, object_type: str, op_class: str
) -> tuple[str, int]:
    """Map `visibility.check_visibility`'s achieved `tier` to
    `(classification_raw, classification_level)`, per
    `plans/classification-refinement/plan.md` Stage 6's worked table:

    - `hires` -> `reporting_names.reporting_name_for(object_type)` at level
      3 (type) -- ground truth, exactly as the scope channel already emits
      (`hybrid_source.py`). Falls back to `op_class` at level 2 when the
      lookup misses (an `object_type` this DCS version's reporting-name
      table doesn't cover, `reporting_name_for`'s own docstring): Petrovich
      cannot speak a name he does not have, even from a close, clear look,
      so the claim degrades to class rather than emitting `None`.
    - `medres` -> `op_class` at level 2 (class) -- today's behaviour,
      unchanged.
    - `lowres` -> `object_model.DEFAULT_OP_CLASS` at level 1 (presence) --
      "something is there," ED's only catch-all
      (`belief.classification.PRESENCE_CLASS`, same value, not imported per
      the `perception`/`belief` boundary above). Unreachable until Stage 7.
    """
    if tier == "hires":
        reporting_name = reporting_name_for(object_type)
        if reporting_name is not None:
            return reporting_name, _CLASSIFICATION_LEVEL_TYPE
        return op_class, _CLASSIFICATION_LEVEL_CLASS
    if tier == "medres":
        return op_class, _CLASSIFICATION_LEVEL_CLASS
    return object_model.DEFAULT_OP_CLASS, 1


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
