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
3. **Clusters *every* gate-surviving candidate -- not yet the emission
   cap's survivors -- then quantises per cluster** (`plans/
   group-contact-model/plan.md` Stage 2, reordered ahead of the cap by
   `plans/detection-cones-slice2/plan.md`'s 2A.5: see point 5 below for why
   the cap now has to run *after* clustering rather than before it).
   `_cluster_candidate` projects each gate-admitted `(candidate, result)`
   pair into `perception.clustering.ClusterCandidate` (ground-truth x/z/alt,
   slant range, characteristic size, and this candidate's own
   individually-resolved classification claim); `perception.clustering.
   cluster_candidates` groups them by true 3D angular separability at
   ownship's own position (Stage 3b-i rev.2 -- the merge test is the angle
   subtended at the observer against each candidate's own apparent angular
   size, not a world-space ellipse; see `clustering.py`'s docstring);
   single-link, no chaining cap yet -- Stage 3b-ii's job. `_build_observation`
   emits exactly one `Observation` per resulting
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
4. **Per-object acquisition state, resolved at cluster granularity**
   (`emit_mode="on_change"`, the default): tracks the `object_id`s that
   were admitted into an *emitted* cluster on a previous poll
   (`_previously_seen_at`) -- state stays keyed on `object_id`, never on
   a cluster identity, because a cluster has no stable identity across polls
   (its membership can grow, shrink, split, or merge poll to poll; see
   point 6). A missing `/world_objects/latest` snapshot resets this state,
   mirroring `HybridPerceptionSource.poll()`'s debounce-reset-on-gap for
   `middle_list_text` -- so the next real snapshot's candidates are treated
   as newly-appearing rather than silently already-seen.
4a. **Time-based, not poll-indexed** (`plans/detection-cones-slice2/
    plan.md`'s 2C -- hard part 6). Both acquisition sets are
    `dict[int, float]` of `object_id -> last-seen t_sim`, not a per-poll
    `frozenset`: with the gaze filter now an *active, moving* o'clock cone
    (point 7 below) rather than always-on, a per-poll frozenset would treat
    every object the cone has swept off of as "gone" the instant it leaves
    this poll's `currently_visible_ids`, and "newly visible" again the
    moment the cone sweeps back -- defeating `_acquire_on_change`'s
    debounce every single scan cycle. "Still known" instead means "seen
    within `_ACQUISITION_RETENTION_WINDOW_S`" (== `perception.gaze.
    SCAN_CYCLE_PERIOD_S`, not an invented constant -- the eviction window
    has to span at least one full scan cycle or a flank object ages out
    before the cone sweeps back to it), evaluated fresh each poll via
    `_live_ids`/`_prune_stale`, never by dict membership alone.
5. **Simultaneous-detection cap counts groups, not objects**
   (`NAKED_EYE_MAX_NEW_GROUPS_PER_POLL`, `plans/detection-cones-slice2/
   plan.md`'s 2A.5 -- renamed from `NAKED_EYE_MAX_NEW_PER_POLL`, value
   unchanged at 3). The model this replaces treated a dense group as harder
   to take in than a sparse one, purely because it had more members to
   throttle one at a time -- backwards: a human looking straight at ten
   co-located trucks sees ten trucks at once, and it is a *spread-out* ten
   that trickles in gradually. Point 3's clustering now runs over every
   gate-surviving candidate *before* this cap is applied, so the cap can
   operate on clusters -- how many distinct things get registered in one
   fixation -- rather than on individual candidates ahead of the grouping
   that would have told it they were one thing.

   `_select_capped_clusters` (shared by both acquisition modes below) finds
   every cluster holding at least one `object_id` not yet in the acquisition
   set passed to it, sorts those *eligible* clusters nearest-first (by their
   nearest member's own exact, un-quantised range), and takes the first
   `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` of them. **Admitting a cluster admits
   all of its members at once** -- a ten-member cluster with even one
   never-before-seen member is one admitted group, not up to three
   individually-admitted members with the rest deferred; this is the
   mechanism that lets a dense group be reported whole in a single poll.

   Under `emit_mode="on_change"`: a cluster's members are stamped into
   `_previously_seen_at` only when that cluster is one of the polled
   admitted clusters. A currently-visible cluster that was *not* admitted
   this poll (steady-state, or capped-out) leaves its not-yet-seen members
   out of `_previously_seen_at` -- unlike the pre-2A.5
   behaviour, where every currently-visible object became "previously
   visible" regardless of whether the cap let it emit. **This is the
   `on_change` fix**: a capped-out group is retried on a later poll instead
   of being dropped forever, because its members never got marked seen in
   the first place (`test_a_capped_out_group_is_retried_and_the_backlog_
   drains_over_polls`, which replaces the old permanently-dropped pin --
   see that test's own docstring).

   `emit_mode="every_poll"` (`plans/pb2-contact-memory/plan.md` Stage 3, its
   Interface confirmation gap 2) re-reads the same cap as a group
   *acquisition-rate* limit instead: `_acquired_at` grows by the members of
   at most `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` newly-eligible clusters per
   poll (same `_select_capped_clusters` helper, same nearest-first order),
   but every object already in that set keeps emitting on *every* subsequent
   poll for as long as it stays visible, as part of whichever cluster it
   currently belongs to -- unaffected by whether that cluster is itself
   "new" this poll. This stays a second, independent piece of state from the
   `on_change` set above, not a re-read of the same field.

   **Not yet re-read for 2B/2C/2D**: this remains purely an intake-bandwidth
   limiter on cluster admission, with no gaze/scan/dwell awareness -- those
   are separate, later mechanisms (`plans/detection-cones-slice2/plan.md`)
   that this cap composes with rather than duplicates.
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
7. **Gaze filters every candidate before it reaches `check_visibility`**
   (`plans/detection-cones-slice2/plan.md`'s 2B; generalised from a plain
   `Gaze` to a `ScanPlan` by 2C's scan loop). Each poll resolves
   `perception.gaze.gaze_at(now_sim, self.scan_plan)` once, then threads
   that `Gaze` through `perception.gaze.gaze_for` per candidate alongside
   `self.peripheral_stimulus_ids` -- see those fields' own docstrings.
   `self.scan_plan` defaults to `perception.gaze.FREE_SCAN_PLAN` (the
   o'clock scan loop, not "no restriction" -- 2C has no unrestricted
   `ScanPlan` any more), `peripheral_stimulus_ids` to a true no-op (empty).
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
from perception.detection_trace import DetectionTraceCollector
from perception.gaze import (
    FREE_SCAN_PLAN,
    SCAN_CYCLE_PERIOD_S,
    ScanPlan,
    gaze_at,
    gaze_for,
)
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.optics import UNAIDED_OPTIC
from perception.reporting_names import reporting_name_for
from perception.source import (
    OBSERVATION_ID_PREFIX_NAKED_EYE,
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
)
from perception.visibility import VisibilityResult, check_visibility

#: Caps newly-admitted *clusters* (groups) per poll tick, nearest-first --
#: how many distinct things register in one fixation, not how many
#: individual objects (`plans/detection-cones-slice2/plan.md`'s 2A.5;
#: renamed from `NAKED_EYE_MAX_NEW_PER_POLL`, which counted objects; value
#: unchanged at 3, deliberately, so the 2C sortie can attribute a later
#: change in behaviour to the scan loop rather than to a value that moved
#: at the same time as its unit). Originally plan Decision #2 -- proceeding
#: on the stated recommendation (not explicitly affirmed by the user),
#: flagged as cheap to change mid-implementation.
NAKED_EYE_MAX_NEW_GROUPS_PER_POLL: Final[int] = 3

#: How long an object_id stays "known" (previously visible/acquired) after
#: it was last actually seen, before the acquisition dicts evict it (2C,
#: module docstring point 4a; `plans/detection-cones-slice2/plan.md` hard
#: part 6) -- reused directly from `perception.gaze.SCAN_CYCLE_PERIOD_S`,
#: not an invented constant: "still known" has to span at least one full
#: scan cycle, or a flank object the cone has swept off of ages out before
#: the cone sweeps back to it.
_ACQUISITION_RETENTION_WINDOW_S: Final[float] = SCAN_CYCLE_PERIOD_S

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
    #: `"on_change"` (default) is the per-object debounce, resolved at
    #: cluster granularity as of 2A.5 (module docstring point 5) --
    #: `plans/pb2-contact-memory/plan.md` Stage 3 established this as the
    #: default every existing test constructs without passing `emit_mode`.
    #: `"every_poll"` emits one `Observation` per currently-acquired,
    #: currently-visible cluster on every poll -- see module docstring
    #: point 5 for how `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` governs both
    #: modes.
    emit_mode: Literal["on_change", "every_poll"] = "on_change"
    #: BL-9's detection trace (`plans/bl9-debug-visualization/plan.md`) --
    #: additive, defaults to `None` (a true no-op, same pattern as every
    #: other optional-sink field in this codebase). When set, every
    #: `check_visibility` call this poll records into it, and this class
    #: annotates each admitted candidate's entry with its cluster's member
    #: object_ids and the emitted `Observation.id` once clustering and
    #: emission are done (see `poll()`).
    trace_sink: DetectionTraceCollector | None = None
    #: The gaze/scan filter (`plans/detection-cones-slice2/plan.md`,
    #: `perception.gaze`) -- a frozen `ScanPlan`, not a `Gaze` (2C: gaze
    #: needs no state at all, module docstring point 1 of the plan's "hard
    #: parts"). `FREE_SCAN_PLAN` (the default) is the o'clock scan loop,
    #: not "no restriction" -- there is no unrestricted `ScanPlan` any more
    #: (2C's whole point). `logger.py`'s poll loop is the only writer,
    #: assigning a new `ScanPlan` each tick from whatever ownship-relative
    #: scan sector is currently commanded (`FREE_SCAN_PLAN` again when
    #: nothing is commanded) -- the same single-assignment,
    #: write-thread/read-thread pattern `last_t_sim` already uses safely.
    #: `poll()` resolves the effective `Gaze` for this poll via
    #: `perception.gaze.gaze_at(now_sim, self.scan_plan)`.
    scan_plan: ScanPlan = field(default_factory=lambda: FREE_SCAN_PLAN)
    #: The peripheral channel's output (hard parts 2a/4 of the plan) --
    #: always empty until the attention-capture channel exists (out of
    #: scope this slice); resolved per candidate through `perception.gaze.
    #: gaze_for` before each `check_visibility` call below, so a member of
    #: this set clears the gaze gate at any azimuth *only* when the active
    #: optic still has peripheral vision (`UNAIDED_OPTIC` -- this channel
    #: has no optic-selection mechanism yet, so `gaze_for` is always called
    #: with `UNAIDED_OPTIC`).
    peripheral_stimulus_ids: frozenset[int] = field(
        default_factory=frozenset, repr=False
    )

    #: `object_id -> last-seen t_sim`, not a per-poll frozenset (2C, module
    #: docstring point 4a) -- a moving cone makes poll-indexing wrong (a
    #: sector the cone has swept off of would otherwise look "not visible"
    #: every poll it isn't gazed, defeating the debounce this state exists
    #: to provide the instant it swept back). "Still known" means "seen
    #: within `_ACQUISITION_RETENTION_WINDOW_S`", evaluated at each poll's
    #: own `now_sim` via `_live_ids` below, not "present in this poll's
    #: `currently_visible_ids`".
    _previously_seen_at: dict[int, float] = field(
        default_factory=dict, init=False, repr=False
    )
    #: `emit_mode="every_poll"`'s own acquisition-set state -- deliberately
    #: separate from `_previously_seen_at` above (see module docstring
    #: point 5); unused under `emit_mode="on_change"`. Same `object_id ->
    #: last-seen t_sim` shape and eviction rule as `_previously_seen_at`.
    _acquired_at: dict[int, float] = field(default_factory=dict, init=False, repr=False)
    #: Object-permanence correlation state (module docstring point 6) --
    #: deliberately a third, independent piece of state from
    #: `_previously_seen_at`/`_acquired_at` above: never cleared,
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
            self._previously_seen_at = {}
            self._acquired_at = {}
            return []

        candidates = filter_ownship(
            [
                WorldObjectCandidate.from_dict(obj, theatre=self.theatre)
                for obj in world_objects.get("objects", [])
            ]
        )

        # 2C: the effective Gaze is a pure function of this poll's own
        # sim time and self.scan_plan (`perception.gaze.gaze_at`) -- never
        # stored, recomputed every poll.
        gaze = gaze_at(now_sim, self.scan_plan)

        visible: list[tuple[WorldObjectCandidate, VisibilityResult]] = []
        for candidate in candidates:
            # UNAIDED_OPTIC -- this channel has no optic-selection mechanism
            # yet (2D's job), so `gaze_for`'s peripheral-bypass rule is
            # always evaluated against the naked eye's own peripheral
            # vision (module docstring on `peripheral_stimulus_ids`).
            candidate_gaze = gaze_for(
                candidate.object_id,
                gaze,
                self.peripheral_stimulus_ids,
                UNAIDED_OPTIC,
            )
            result = check_visibility(
                ownship_state,
                candidate,
                self.world_model_conn,
                self.theatre,
                gaze=candidate_gaze,
                trace=self.trace_sink,
            )
            if result is not None:
                visible.append((candidate, result))

        currently_visible_ids = frozenset(
            candidate.object_id for candidate, _result in visible
        )
        confidence_by_object_id = {
            candidate.object_id: result.confidence for candidate, result in visible
        }

        observer = GeoPosition(
            x=ownship_state.x, z=ownship_state.z, alt_m=ownship_state.alt_m
        )
        # Cluster *every* gate-surviving candidate first -- the cap below
        # operates on the resulting groups, not on individual candidates
        # ahead of the grouping that would have told it they were one thing
        # (module docstring point 5, 2A.5).
        clusters = cluster_candidates(
            [
                self._cluster_candidate(candidate, result)
                for candidate, result in visible
            ],
            observer,
            # UNAIDED_OPTIC.presence_range_mult -- the only optic
            # `check_visibility` is called with today (no optic-selection
            # mechanism exists until slice 2B, `plans/detection-cones-
            # slice2/plan.md`). Threading the active optic's own presence
            # multiplier is what keeps `clustering._separable`'s floor (A)
            # slack for whichever optic actually admitted these
            # candidates -- see that module's docstring.
            UNAIDED_OPTIC.presence_range_mult,
        )

        if self.emit_mode == "every_poll":
            to_emit = self._acquire_every_poll(now_sim, clusters, currently_visible_ids)
        else:
            to_emit = self._acquire_on_change(now_sim, clusters, currently_visible_ids)

        observations = self._build_observations(
            now_sim, ownship_state, to_emit, confidence_by_object_id
        )
        if self.trace_sink is not None:
            for cluster, observation in zip(to_emit, observations):
                member_ids = tuple(member.object_id for member in cluster.members)
                for member in cluster.members:
                    self.trace_sink.annotate_admission(
                        member.object_id, member_ids, observation.id
                    )
        return observations

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

    @staticmethod
    def _select_capped_clusters(
        clusters: list[Cluster], known_ids: frozenset[int]
    ) -> list[Cluster]:
        """Shared by both acquisition modes (module docstring point 5, 2A.5):
        a cluster is *eligible* when at least one of its members is not yet
        in `known_ids`; eligible clusters are sorted nearest-first (by their
        nearest member's own exact, un-quantised range -- computed before
        clustering, in `_cluster_candidate`) and the first
        `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` are admitted whole. A cluster
        already fully covered by `known_ids` never competes for a cap slot
        at all, which is what lets a steady-state scene stay silent under
        `on_change` and what lets `every_poll` keep re-emitting an
        already-acquired cluster with no further cap cost."""
        eligible = [
            cluster
            for cluster in clusters
            if any(member.object_id not in known_ids for member in cluster.members)
        ]
        eligible.sort(key=lambda cluster: min(m.range_m for m in cluster.members))
        return eligible[:NAKED_EYE_MAX_NEW_GROUPS_PER_POLL]

    @staticmethod
    def _live_ids(seen_at: dict[int, float], now_sim: float) -> frozenset[int]:
        """The `object_id`s in `seen_at` still within
        `_ACQUISITION_RETENTION_WINDOW_S` of `now_sim` -- 2C's time-based
        replacement for a per-poll frozenset (module docstring point 4a):
        "still known" means "seen within the current scan cycle," not
        "present in this exact poll's visible set", so an object the cone
        has swept off of stays known for the rest of the cycle rather than
        immediately reading as gone."""
        return frozenset(
            object_id
            for object_id, last_seen_sim in seen_at.items()
            if now_sim - last_seen_sim <= _ACQUISITION_RETENTION_WINDOW_S
        )

    @staticmethod
    def _prune_stale(seen_at: dict[int, float], now_sim: float) -> dict[int, float]:
        """Drops entries past `_ACQUISITION_RETENTION_WINDOW_S` -- called
        once per poll after `seen_at` has been updated, so the dict itself
        never grows without bound."""
        return {
            object_id: last_seen_sim
            for object_id, last_seen_sim in seen_at.items()
            if now_sim - last_seen_sim <= _ACQUISITION_RETENTION_WINDOW_S
        }

    def _acquire_on_change(
        self,
        now_sim: float,
        clusters: list[Cluster],
        currently_visible_ids: frozenset[int],
    ) -> list[Cluster]:
        """Per-object debounce resolved at cluster granularity: a cluster is
        emitted only if it is among this poll's cap-admitted groups (module
        docstring point 5). `_previously_seen_at` only gains a fresh
        timestamp for the members of *emitted* clusters and for members
        that were already known and are still currently visible
        (`steady_ids`) -- a currently-visible-but-not-emitted member
        (capped-out) is deliberately left un-refreshed, so a capped-out
        group is retried on a later poll instead of being marked
        "already seen" forever (the `on_change` fix 2A.5 makes). Eviction
        is time-based, not poll-based (module docstring point 4a): an
        object the cone has swept off of stays "known" for
        `_ACQUISITION_RETENTION_WINDOW_S`, not just the one poll it was
        last actually visible on."""
        known_ids = self._live_ids(self._previously_seen_at, now_sim)
        admitted = self._select_capped_clusters(clusters, known_ids)
        admitted_ids = frozenset(
            member.object_id for cluster in admitted for member in cluster.members
        )

        steady_ids = currently_visible_ids & known_ids
        for object_id in steady_ids | admitted_ids:
            self._previously_seen_at[object_id] = now_sim
        self._previously_seen_at = self._prune_stale(self._previously_seen_at, now_sim)
        return admitted

    def _acquire_every_poll(
        self,
        now_sim: float,
        clusters: list[Cluster],
        currently_visible_ids: frozenset[int],
    ) -> list[Cluster]:
        """`emit_mode="every_poll"`'s acquisition-rate throttle, resolved at
        cluster granularity: at most `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL`
        clusters holding a not-yet-known member join the acquired set this
        poll (whole cluster, all members); every cluster whose members are
        all currently visible *and* known is emitted this poll, regardless
        of when each member joined -- so a continuously-visible cluster
        emits every poll instead of aging out, and a known-but-not-
        currently-visible cluster (cone pointed elsewhere) emits nothing
        this poll without losing its acquired status (module docstring
        point 5; time-based eviction per point 4a, mirroring
        `_acquire_on_change` above)."""
        known_ids = self._live_ids(self._acquired_at, now_sim)
        newly_admitted = self._select_capped_clusters(clusters, known_ids)
        newly_acquired_ids = frozenset(
            member.object_id for cluster in newly_admitted for member in cluster.members
        )

        steady_ids = currently_visible_ids & known_ids
        for object_id in steady_ids | newly_acquired_ids:
            self._acquired_at[object_id] = now_sim
        self._acquired_at = self._prune_stale(self._acquired_at, now_sim)

        acquired_ids = frozenset(self._acquired_at)
        return [
            cluster
            for cluster in clusters
            if all(member.object_id in acquired_ids for member in cluster.members)
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
