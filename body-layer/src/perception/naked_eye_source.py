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
   `plans/pb1.5-naked-eye-detection/debug.md`). Then runs the survivors
   through `association.filter_player_bubble()` (`todo/todo.md`'s "Player
   bubble" item, `association.PLAYER_BUBBLE_RADIUS_M` -- 10 km) before
   anything else sees them: group salience (1a), the gaze/visibility loop
   (2), and clustering (3) all only ever operate on what's left inside the
   bubble. A candidate the bubble drops gets one trace row (`GateOutcome.
   PLAYER_BUBBLE`) when `trace_sink` is set, rather than the per-gate row
   `check_visibility` would otherwise have produced -- it is never handed
   to `check_visibility` at all. This filters the ground/air unit pool
   only; world-model geography (landmarks, roads, settlements) is reached
   by proximity to a contact (`belief.enrichment`), not through this pool,
   and is unaffected.
1a. **Group salience is resolved once per poll, over the whole candidate
    pool, before the per-candidate gate loop** (`plans/
    group-detectability/plan.md` Stage 2) -- `perception.group_salience.
    group_salient_ids` runs on the un-gazed, un-LOS-filtered candidates
    from point 1 (a group is a property of the scene, not of what's
    currently gazed; see that module's docstring), against `UNAIDED_
    OPTIC` (this channel's only optic today). The resulting `object_id`
    set is threaded into `check_visibility`'s `group_salient` keyword,
    exactly the way `gaze_for`'s per-candidate `Gaze` resolution already
    happens one step ahead of that same call -- the caller resolves a
    per-candidate input once, `check_visibility` only ever applies
    whatever it's handed.
1b. **Movement (`plans/movement-detection/plan.md`) is resolved per candidate,
    right where `check_visibility` already runs, once per gate-admitted
    candidate.** `_resolve_velocity_by_object_id` joins this poll's
    `GET /unit_velocity/latest` snapshot onto the raw world-objects dicts by
    `unit_name` (the join key -- `LoGetWorldObjects` and mission scripting
    share no other identifier, plan Decision 1), subject to
    `perception.motion.MOTION_VELOCITY_MAX_SKEW_S` and a same-poll
    uniqueness check (a `unit_name` shared by two or more of this poll's
    candidates drops to unresolved for all of them, rather than guessing
    which one it belongs to -- the plan's own Risks note). The resolved
    `Vec3 | None` lands on `WorldObjectCandidate.velocity` via `from_dict`'s
    `velocity=` keyword, then `perception.motion.evaluate_motion_gate` runs
    for every candidate `check_visibility` admits, recording each verdict in
    `motion_by_object_id` and annotating the detection trace (module
    docstring's own trace point, mirroring `confidence_by_object_id`'s
    shape). A cluster's own `apparent_motion` (`_build_observation`) is its
    members' shared verdict when all agree (including all-`None`), else
    `None` -- the same "identical keeps, disagreement degrades" rule
    `Cluster`'s aggregate classification already follows
    (`clustering.py`'s docstring), generalised to a tri-state boolean since
    there is no presence-root equivalent to degrade *to* here.
2. Runs every candidate through `visibility.check_visibility()`.
3. **Clusters *every* gate-surviving candidate -- not yet the emission
   cap's survivors -- then estimates per cluster** (`plans/
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
   emits exactly one `Observation` per resulting cluster: bearing/range are
   an honest estimate of the cluster's *centroid* (`perception.estimation`,
   `plans/precise-position-belief/plan.md`), not any one member's own exact
   geometry and not a snap onto a reporting bucket -- the true centroid
   geometry perturbed by a per-look draw plus a never-redrawn per-cluster
   systematic bias, both deterministic (see that module's docstring), with
   the declared error ellipse riding along as `Observation.position_
   uncertainty`. `classification_raw`/`classification_level` and `count_
   bucket` come straight from the `Cluster` (identical class across every
   member keeps that class, otherwise degrades to the presence root -- see
   `clustering.py`'s docstring). ED's `OP_1UNIT`...`OP_MORETHAN15UNITS`
   count vocabulary (Session 5 Finding 2, `aircraft-layer/research/
   2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`),
   previously out of scope (plan Decision #5) for lack of a clustering
   mechanism, is exactly what `Cluster.count_bucket` now supplies.

   **`derived_world_position` is deliberately never perturbed** -- it
   carries the cluster's centroid, the mean of its members' exact
   ground-truth x/z (a documented meaning change from "one candidate's own
   position" to "a cluster's centroid," per the group-contact-model plan's
   Risks section), because that field is DCS ground truth (`code owns
   facts`, never fabricated or fuzzed) reserved for future geometry/fusion
   work, not the crew-facing report. The anti-omniscience perturbation
   applies to the fields that represent what a crew member could actually
   have perceived and said out loud (`bearing_deg`, `range_m`,
   `classification_raw`, `count_bucket`), not to this channel's internal
   bookkeeping of where the real objects actually are.
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
   plan.md`'s 2A.5 -- renamed from `NAKED_EYE_MAX_NEW_PER_POLL`; **value
   raised 3 -> 5 on 2026-09-25, user-affirmed, see that constant's own
   comment for the subitizing grounding**). The model this replaces treated
   a dense group as harder
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

import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Final, Literal

from aircraft_client import AircraftLayerClient, AircraftLayerError
from perception import object_model
from perception.association import (
    PLAYER_BUBBLE_RADIUS_M,
    WorldObjectCandidate,
    filter_ownship,
    filter_player_bubble,
)
from perception.clustering import Cluster, ClusterCandidate, cluster_candidates
from perception.detection_trace import (
    DetectionTrace,
    DetectionTraceCollector,
    GateOutcome,
)
from perception.estimation import naked_eye_sigma_m, perturbed_bearing_range
from perception.gaze import (
    FREE_SCAN_PLAN,
    SCAN_CYCLE_PERIOD_S,
    ScanPlan,
    gaze_at,
    gaze_for,
)
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.group_salience import group_salient_ids
from perception.motion import (
    MOTION_ANGULAR_THRESHOLD_RAD_S,
    MOTION_VELOCITY_MAX_SKEW_S,
    evaluate_motion_gate,
)
from perception.optics import UNAIDED_OPTIC, Optic
from perception.reporting_names import reporting_name_for
from perception.source import (
    OBSERVATION_ID_PREFIX_NAKED_EYE,
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
    PositionUncertainty,
)
from perception.visibility import VisibilityResult, check_visibility

#: Caps newly-admitted *clusters* (groups) per poll tick, nearest-first --
#: how many distinct things register in one fixation, not how many
#: individual objects (`plans/detection-cones-slice2/plan.md`'s 2A.5;
#: renamed from `NAKED_EYE_MAX_NEW_PER_POLL`, which counted objects).
#:
#: **5, raised from 3 on 2026-09-25 -- and this is the first value the user
#: has actually affirmed.** The 3 came from plan Decision #2's stated
#: recommendation, which this constant's own comment recorded as "not
#: explicitly affirmed by the user" and "cheap to change". His grounding,
#: given while diagnosing an outpost that fragmented into 18 contacts:
#:
#:   *"Human eye could detect that there's many somethings or groups of
#:   somethings easily. distinction up to 5 is trivial. 6 - 10 take a
#:   couple of seconds, 10+ is more difficult and needs more sweeps."*
#:
#: That is the subitizing boundary, and 3 sat below it -- the cap was
#: modelling a narrower glance than a human actually takes in.
#:
#: **The rest of his tiering then falls out of this one number, with no
#: extra mechanism**, because the cap is per *poll* and the live poll
#: interval is 1 s (`logger._DEFAULT_POLL_INTERVAL_S`):
#:
#: | groups present | polls to admit | elapsed | his description |
#: |---|---|---|---|
#: | up to 5 | 1 | ~1 s | "trivial" |
#: | 6-10 | 2 | ~2 s | "a couple of seconds" |
#: | 10+ | 3+ | 3 s+ | "needs more sweeps" |
#:
#: So no tiered or time-aware cap is needed: serial admission at 5 per
#: second *is* the tiering. Worth stating because the obvious reading of
#: his three tiers is three thresholds.
#:
#: **Second effect, and the reason it was raised now.** A group founded
#: across many polls is what breaks object-permanence continuity
#: (`plans/contact-fragmentation-at-range/debug.md`): continuity resolves
#: by majority object overlap between successive polls, and a dense scene
#: admitted three-at-a-time spreads one outpost's founding across ~10
#: polls, during which cluster membership churns and the vote fails --
#: dropping through to the association gate, where the ambiguity runaway
#: waits. Fewer polls to admit the same scene means fewer chances to lose
#: continuity. This attacks that trigger; it does not by itself change the
#: ambiguity rule, which remains an open question in that note.
NAKED_EYE_MAX_NEW_GROUPS_PER_POLL: Final[int] = 5

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

    #: The instrument this poll looks through (`plans/binocular-optic/
    #: plan.md` Stage 1). Assigned per poll by `logger._apply_active_gaze`
    #: alongside `scan_plan`, from the same resolution, for the same
    #: reason: the *decision* to raise binoculars reads beliefs, which
    #: `perception` may not import, so belief resolves and perception
    #: receives a frozen value -- exactly the seam `gaze.py` established.
    #:
    #: **Stage 1 always resolves to `UNAIDED_OPTIC`**, so nothing
    #: observable changes until Stage 2 supplies a policy. That is the
    #: regression gate 2B used and it is worth repeating here: the
    #: plumbing is proven before any behaviour rides on it.
    optic: Optic = UNAIDED_OPTIC
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

        raw_objects = world_objects.get("objects", [])
        # `plans/movement-detection/plan.md` Decision 2: the velocity feed
        # must be independently degradable -- an aircraft-layer instance
        # with no `autoexec.cfg` opt-in (or a deployed collector predating
        # this endpoint) has no `/unit_velocity/latest` route at all, which
        # is a transport-level `AircraftLayerError` (e.g. 404), not the
        # `None`-on-empty-cache case `get_world_objects_latest` handles on
        # its own. Falling back to `None` here reproduces exactly that
        # "no velocity -> motion unknown everywhere" degradation rather than
        # taking this whole poll (and every other candidate's visibility
        # gate) down with it.
        try:
            unit_velocity = self.aircraft_client.get_unit_velocity_latest()
        except AircraftLayerError:
            unit_velocity = None
        velocity_by_object_id, motion_skew_s = _resolve_velocity_by_object_id(
            raw_objects, world_objects.get("dcs_model_time_s"), unit_velocity
        )
        all_candidates = filter_ownship(
            [
                WorldObjectCandidate.from_dict(
                    obj,
                    theatre=self.theatre,
                    velocity=velocity_by_object_id.get(obj.get("object_id")),
                )
                for obj in raw_objects
            ]
        )

        observer = GeoPosition(
            x=ownship_state.x, z=ownship_state.z, alt_m=ownship_state.alt_m
        )
        # The player bubble (`todo/todo.md`'s "Player bubble" item,
        # `association.PLAYER_BUBBLE_RADIUS_M`) -- the earliest point a
        # candidate becomes work: dropped here, before group salience, the
        # gaze/visibility loop, and clustering ever see it. A dropped
        # candidate gets exactly one trace row (PLAYER_BUBBLE) when tracing
        # is on, instead of the per-gate row `check_visibility` would have
        # produced -- it was never handed to `check_visibility` at all.
        candidates = filter_player_bubble(all_candidates, ownship_state)
        if self.trace_sink is not None:
            in_bubble_ids = frozenset(c.object_id for c in candidates)
            for candidate in all_candidates:
                if candidate.object_id in in_bubble_ids:
                    continue
                target = GeoPosition(
                    x=candidate.x, z=candidate.z, alt_m=candidate.alt_m
                )
                self.trace_sink.record(
                    DetectionTrace(
                        object_id=candidate.object_id,
                        object_type=candidate.object_type,
                        t_sim=now_sim,
                        true_bearing_deg=bearing_deg(observer, target),
                        true_range_m=range_m(observer, target),
                        range_threshold_m=PLAYER_BUBBLE_RADIUS_M,
                        threshold_bound="player_bubble",
                        outcome=GateOutcome.PLAYER_BUBBLE,
                        optic=self.optic.name,
                    )
                )

        # 2C: the effective Gaze is a pure function of this poll's own
        # sim time and self.scan_plan (`perception.gaze.gaze_at`) -- never
        # stored, recomputed every poll.
        gaze = gaze_at(now_sim, self.scan_plan)

        # `plans/group-detectability/plan.md` Stage 2: group membership is
        # computed once per poll, over the whole un-gazed, un-LOS-filtered
        # candidate pool -- before check_visibility runs, not after (module
        # docstring's own "Where the set-ness lives" reasoning: a group is
        # a property of the scene, not of what's currently gazed).
        # UNAIDED_OPTIC -- this channel has no optic-selection mechanism yet
        # (2D's job), same reason gaze_for below is always called against it.
        salient_ids = group_salient_ids(candidates, observer, UNAIDED_OPTIC)

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
                optic=self.optic,
                gaze=candidate_gaze,
                trace=self.trace_sink,
                group_salient=candidate.object_id in salient_ids,
            )
            if result is not None:
                visible.append((candidate, result))

        currently_visible_ids = frozenset(
            candidate.object_id for candidate, _result in visible
        )
        confidence_by_object_id = {
            candidate.object_id: result.confidence for candidate, result in visible
        }

        # `plans/movement-detection/plan.md`: the movement gate runs once
        # per gate-admitted candidate, mirroring confidence_by_object_id's
        # shape immediately above (module docstring point 1b).
        motion_by_object_id: dict[int, bool | None] = {}
        for candidate, _result in visible:
            target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
            motion_result = evaluate_motion_gate(observer, target, candidate.velocity)
            motion_by_object_id[candidate.object_id] = motion_result.moving
            if self.trace_sink is not None:
                self.trace_sink.annotate_motion(
                    candidate.object_id,
                    speed_mps=motion_result.speed_mps,
                    perp_speed_mps=motion_result.perp_speed_mps,
                    angular_rate_rad_s=motion_result.angular_rate_rad_s,
                    threshold_rad_s=MOTION_ANGULAR_THRESHOLD_RAD_S,
                    skew_s=motion_skew_s,
                    apparent_motion=motion_result.moving,
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
            now_sim,
            ownship_state,
            to_emit,
            confidence_by_object_id,
            motion_by_object_id,
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
        motion_by_object_id: dict[int, bool | None],
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
                    motion_by_object_id,
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
        motion_by_object_id: dict[int, bool | None],
        continues_observation_id: str | None,
    ) -> Observation:
        """One `Observation` for `cluster` -- `plans/group-contact-model/
        plan.md` Stage 2: this is the emission unit now, not one per
        candidate. Bearing/range are an honest *estimate* of the cluster's
        centroid (`perception.estimation`, `plans/precise-position-belief/
        plan.md`), not any one member's own geometry -- the honest report a
        crew member could give for a cluster is "that group, over there,"
        not any individual member's exact bearing. `continues_observation_
        id` is resolved by `_build_observations` across the whole batch,
        not here -- see that method's docstring.

        **The per-object systematic bias is anchored to the cluster's
        lowest member `object_id`.** A cluster is position-only resolution
        (`perception.clustering`'s own docstring) and its membership can
        drift poll to poll (grow, shrink, split, merge) -- there is no
        stable per-cluster identity to hash a bias off. The lowest member
        id is deterministic and stable for the common case this milestone
        targets (a stationary or slowly-moving group whose membership does
        not change); a cluster that gains or loses members between polls
        will see its bias shift with it, a documented limitation rather
        than an attempt to solve cluster-identity tracking here.

        `apparent_motion` (`plans/movement-detection/plan.md`, module
        docstring point 1b) is the cluster's members' shared movement
        verdict when they all agree (including all-`None`), else `None` --
        `Cluster.classification_raw`'s own "identical keeps, disagreement
        degrades" rule, generalised to a tri-state boolean."""
        observer = GeoPosition(
            x=ownship_state.x, z=ownship_state.z, alt_m=ownship_state.alt_m
        )
        centroid = GeoPosition(
            x=cluster.centroid_x, z=cluster.centroid_z, alt_m=ownship_state.alt_m
        )
        true_bearing_deg = bearing_deg(observer, centroid)
        true_range_m = range_m(observer, centroid)

        self._observation_count += 1
        observation_id = f"{OBSERVATION_ID_PREFIX_NAKED_EYE}_{self._observation_count}"
        bias_object_id = min(member.object_id for member in cluster.members)
        sigma_cross_m, sigma_down_m = naked_eye_sigma_m(true_range_m)
        estimated_bearing_deg, estimated_range_m = perturbed_bearing_range(
            observation_id=observation_id,
            object_id=bias_object_id,
            true_bearing_deg=true_bearing_deg,
            true_range_m=true_range_m,
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
        )
        for member in cluster.members:
            self._object_id_to_last_observation_id[member.object_id] = observation_id

        confidence = min(
            confidence_by_object_id[member.object_id] for member in cluster.members
        )
        member_motions = {
            motion_by_object_id.get(member.object_id) for member in cluster.members
        }
        apparent_motion = (
            next(iter(member_motions)) if len(member_motions) == 1 else None
        )
        return Observation(
            id=observation_id,
            contact_id=None,
            t_sim=now_sim,
            t_wall=time.time(),
            source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
            classification_raw=cluster.classification_raw,
            bearing_deg=estimated_bearing_deg,
            range_m=estimated_range_m,
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
            position_uncertainty=PositionUncertainty(
                sigma_cross_m=sigma_cross_m, sigma_down_m=sigma_down_m
            ),
            apparent_motion=apparent_motion,
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


def _resolve_velocity_by_object_id(
    objects: list[dict[str, Any]],
    world_objects_t_sim: Any,
    unit_velocity: dict[str, Any] | None,
) -> tuple[dict[int, dict[str, float]], float | None]:
    """Join this poll's unit-velocity snapshot onto `objects` (raw
    `GET /world_objects/latest` object dicts, `unit_name` field included --
    `plans/movement-detection/plan.md` Decision 1) by `unit_name`. Returns
    `(velocity_by_object_id, skew_s)`: the first only ever contains entries
    that actually resolved, so `.get(object_id)` returning `None` covers
    every "unknown" case uniformly (no snapshot, stale skew, missing/
    non-unique `unit_name`) without the caller needing to distinguish them;
    `skew_s` is `None` on any of those same failure paths, or the actual
    `|world_objects_t - unit_velocity_t|` otherwise, for the detection trace
    (module docstring point 1b).

    **Non-unique `unit_name` collision handling** (the plan's own Risks
    note): a `unit_name` shared by two or more of *this poll's* `objects`
    drops to unresolved for every one of them, rather than guessing which
    one a matched velocity sample belongs to."""
    if unit_velocity is None:
        return {}, None
    try:
        skew_s = abs(
            float(world_objects_t_sim) - float(unit_velocity["dcs_model_time_s"])
        )
    except (KeyError, TypeError, ValueError):
        return {}, None
    if skew_s > MOTION_VELOCITY_MAX_SKEW_S:
        return {}, skew_s

    samples = unit_velocity.get("samples")
    if not isinstance(samples, dict):
        return {}, skew_s

    name_counts: Counter[str] = Counter(
        name for obj in objects if isinstance(name := obj.get("unit_name"), str)
    )

    resolved: dict[int, dict[str, float]] = {}
    for obj in objects:
        name = obj.get("unit_name")
        object_id = obj.get("object_id")
        if not isinstance(name, str) or not isinstance(object_id, int):
            continue
        if name_counts[name] > 1:
            continue
        sample = samples.get(name)
        if isinstance(sample, dict):
            resolved[object_id] = sample
    return resolved, skew_s


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
