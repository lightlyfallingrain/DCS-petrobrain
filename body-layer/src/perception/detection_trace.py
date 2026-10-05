"""Detection trace types -- `plans/bl9-debug-visualization/plan.md` ("BL-9,
the detection trace").

`visibility.check_visibility` already evaluates, in order, cockpit mask ->
angular-size/range-cap -> terrain LOS, and returns `None` on the first
failing gate. The first-failing-gate *is* the answer to "why did Petrovich
not see that" -- this module exists to record what that control flow
already decided, not to recompute anything. `GateOutcome`/`DetectionTrace`
are pure perception-layer types (ground truth by construction, same footing
as `WorldObjectCandidate`/`VisibilityResult`) -- no `belief/` import here,
matching `source.py`'s own perception/belief boundary rule.

**`DetectionTraceCollector` is a true no-op when unused.** Every caller
(`check_visibility`, `NakedEyePerceptionSource.poll`) takes an optional
`trace`/`trace_sink` parameter defaulting to `None`, the same additive
pattern `overlay_client`/`speech_client` already use elsewhere in this
codebase (`body-layer/CLAUDE.md`).

`DetectionTrace` is deliberately mutable (not `frozen`): `check_visibility`
records one entry per candidate per poll at whichever gate decided its
fate, and `NakedEyePerceptionSource.poll` later annotates that *same*
entry in place with cluster/observation detail once clustering and
emission have happened -- two separate call sites writing to one record
over the lifetime of a single poll, not two records."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GateOutcome(str, Enum):
    """Which of `check_visibility`'s three gates decided a candidate's
    fate this poll, or that it cleared all three. A plain `str` subclass
    so `.value` serializes directly to JSON without a custom encoder."""

    #: `perception.gaze.within_gaze` rejected it -- the first gate
    #: `check_visibility` evaluates, ahead of `COCKPIT_MASK`
    #: (`plans/detection-cones-slice2/plan.md`'s 2B, hard part 3: attention
    #: direction *is* the optimisation, so it has to be the cheapest,
    #: most-selective test and run first). **This reorders what
    #: `COCKPIT_MASK`'s own trace count means once a real gaze restriction
    #: is active**: a rear-hemisphere candidate that both a narrow gaze and
    #: the cockpit mask would reject now records `GAZE`, not
    #: `COCKPIT_MASK` -- the mask's own rejection rate stops being directly
    #: observable from a live trace at that point. Deliberate, not a defect
    #: to "fix" by reordering back: the mask is a static, already-measured
    #: envelope (`cockpit_mask.py`) that can be characterised offline,
    #: while the gaze rejection count is the number 2C's scan loop will
    #: actually be tuned against. 2B's own default gaze (`None`, no
    #: restriction -- `perception.gaze`'s module docstring) never fires
    #: this outcome, so the attribution shift only becomes observable once
    #: a real gaze restriction lands (a commanded scan sector here, the
    #: free-scan loop in 2C).
    GAZE = "gaze"
    COCKPIT_MASK = "cockpit_mask"
    #: The optic's own field of view rejected it -- a narrower cone on top
    #: of the cockpit mask (`perception.optics`, cones slice 1). Never fires
    #: for `UNAIDED_OPTIC`, whose `fov_half_angle_deg` is `None`, so it is
    #: dormant on every path that exists today; added at the BL-9/cones
    #: merge so that the gate cannot silently return without a trace entry
    #: once slice 2 makes a non-default optic selectable.
    OPTIC_FOV = "optic_fov"
    RANGE_OR_SIZE = "range_or_size"
    TERRAIN_LOS = "terrain_los"
    ADMITTED = "admitted"
    #: Dropped by the player bubble (`perception.association.
    #: filter_player_bubble`, `todo/todo.md`'s "Player bubble" item) before
    #: `check_visibility` was ever called -- unlike every outcome above,
    #: this one is recorded by `NakedEyePerceptionSource.poll` directly,
    #: not inside `check_visibility`'s own gate chain, because the whole
    #: point of the bubble is that a candidate past it is never handed to
    #: that chain at all. Always the *first* and *only* row for an
    #: object_id this poll when it fires, since nothing downstream ever
    #: sees that candidate.
    PLAYER_BUBBLE = "player_bubble"


@dataclass
class DetectionTrace:
    """One candidate's gate outcome for one poll. `range_threshold_m`/
    `threshold_bound` are always populated (even on a `COCKPIT_MASK`
    failure) -- the angular-size/range-cap threshold is cheap to compute
    from `object_type` alone and doesn't depend on which gate actually
    ran, so recording it unconditionally gives a uniform row shape and
    answers "how close would it have had to get" even for a candidate that
    never got that far. `threshold_bound` is `"range_cap"` when
    `NAKED_EYE_RANGE_CAP_M` is the binding term of the `min()` in
    `visibility.py`, `"group_resolution"` when the size-curve term bound
    instead *and* the relaxed group-salience threshold
    (`RESOLUTION_ANGULAR_RADIUS_RAD`, `plans/group-detectability/plan.md`)
    was the one applied, else `"size_curve"` (the ordinary,
    salience-threshold admission) -- the angular-size and range-cap
    checks are one arithmetic expression there, not two separable gates,
    so this field recovers the distinct *reasons* ("outside the range
    cap" vs "angular size too small for this tier" vs "admitted only
    because a salient group relaxed the threshold") without inventing a
    code-level distinction `visibility.py` doesn't have. A fourth value,
    `"player_bubble"`, is set only on a `GateOutcome.PLAYER_BUBBLE` row --
    recorded before `check_visibility` ever ran, so `range_threshold_m` on
    that row is `association.PLAYER_BUBBLE_RADIUS_M`, not anything derived
    from the object's own size curve.

    `achieved_tier`/`cluster_member_object_ids`/`observation_id` are
    `None` until the candidate is admitted (the first) or, further, until
    `NakedEyePerceptionSource.poll` has clustered and emitted it (the
    latter two) -- an `ADMITTED` outcome does not by itself guarantee
    `cluster_member_object_ids`/`observation_id` are set, since
    `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL` can still throttle a gate-admitted
    candidate out of this poll's emission (see `naked_eye_source.py`'s own
    module docstring, point 5) -- that candidate's trace stays `ADMITTED`
    with no cluster/observation detail, which is itself useful debrief
    information ("visible, but throttled")."""

    object_id: int
    object_type: str
    t_sim: float
    true_bearing_deg: float
    true_range_m: float
    range_threshold_m: float
    threshold_bound: str
    outcome: GateOutcome
    achieved_tier: str | None = None
    cluster_member_object_ids: tuple[int, ...] | None = None
    observation_id: str | None = None
    #: The movement gate's own inputs/verdict (`perception.motion`, `plans/
    #: movement-detection/plan.md`), annotated by `NakedEyePerceptionSource.
    #: poll` via `annotate_motion` below, independently of
    #: `annotate_admission` -- the motion gate runs (or doesn't, when
    #: `velocity is None`) for every admitted candidate regardless of
    #: whether it later makes it into an emitted cluster, so this is set
    #: whenever a velocity sample was available to test, not only on
    #: `ADMITTED` entries. `None` on every field when the candidate had no
    #: velocity sample this poll (unknown, not "not moving" -- see
    #: `motion.py`'s own module docstring) or the trace sink never got the
    #: chance to see it (e.g. a candidate rejected before the movement gate
    #: runs). `speed_mps`/`perp_speed_mps` are `|v|`/`|v_perp|`;
    #: `angular_rate_rad_s` is the computed rate (`None` when the cheap
    #: early-out alone decided the verdict, since the full vector projection
    #: was never computed); `skew_s` is the velocity sample's time offset
    #: from the world-objects poll it was joined against.
    motion_speed_mps: float | None = None
    motion_perp_speed_mps: float | None = None
    motion_angular_rate_rad_s: float | None = None
    motion_threshold_rad_s: float | None = None
    motion_skew_s: float | None = None
    apparent_motion: bool | None = None

    #: DCS-driven LOS (`plans/dcs-driven-los/plan.md`, X-B29), annotated by
    #: `NakedEyePerceptionSource.poll` via `annotate_los` below, mirroring
    #: `annotate_motion`'s own call-site shape and timing (same poll step).
    #: `building_clear`/`terrain_clear` are the two independently-computed
    #: fields the Hook script publishes; `live_los_clear` is the joined
    #: verdict `visibility.check_visibility`'s gate 4 actually used
    #: (`building_clear and terrain_clear`, or `None` if the join never
    #: resolved); `los_skew_s` is the join's own time offset, mirroring
    #: `motion_skew_s`. `hour_used`/`fov_half_deg_used` are the query wedge
    #: the Hook script actually used that poll -- recording them lets a
    #: debrief tell "outside the queried wedge" from "queried and no
    #: verdict" (plan SS12). All `None` when no live LOS feed was joined
    #: this poll (feed absent, unit outside the queried wedge, too stale,
    #: or the trace sink never got the chance to see it) -- never a
    #: guessed boolean, same tri-state discipline as every other joined
    #: field in this module.
    building_clear: bool | None = None
    terrain_clear: bool | None = None
    live_los_clear: bool | None = None
    los_skew_s: float | None = None
    hour_used: int | None = None
    fov_half_deg_used: int | None = None

    #: The instrument this candidate was evaluated through (`plans/
    #: binocular-optic/plan.md` Stage 1) -- `optics.Optic.name`.
    #:
    #: Recorded per row rather than per poll even though the optic is a
    #: property of the *look*, because a debrief's question is always about
    #: one contact ("why was that never identified?"), and an answer that
    #: requires joining against a separate per-poll table is an answer
    #: nobody computes. The `range_threshold_m` beside it is already the
    #: optic-scaled figure, so without this field that number is
    #: unexplainable: the same contact at the same range yields two
    #: different thresholds depending on an instrument the row does not
    #: name.
    optic: str = "unaided"


@dataclass
class DetectionTraceCollector:
    """A small mutable accumulator `check_visibility`/
    `NakedEyePerceptionSource` append/annotate. `records` holds every entry
    ever recorded, in recording order, across every poll -- callers that
    write it out per-poll (`detection_trace_writer.py`) are responsible
    for clearing it once a poll's records have been persisted."""

    records: list[DetectionTrace] = field(default_factory=list)
    #: The most recently recorded entry per `object_id`, for
    #: `annotate_admission` to mutate -- `check_visibility` records at most
    #: once per `object_id` per poll (one call per candidate per poll), so
    #: "most recent" is unambiguous within a single poll.
    _last_by_object_id: dict[int, DetectionTrace] = field(
        default_factory=dict, init=False, repr=False
    )

    def record(self, entry: DetectionTrace) -> None:
        self.records.append(entry)
        self._last_by_object_id[entry.object_id] = entry

    def annotate_admission(
        self,
        object_id: int,
        cluster_member_object_ids: tuple[int, ...],
        observation_id: str,
    ) -> None:
        """Fill in the cluster/observation detail on `object_id`'s most
        recently recorded entry -- a no-op if that entry doesn't exist or
        wasn't `ADMITTED` (defensive; every real caller only calls this for
        an object it just admitted and clustered)."""
        entry = self._last_by_object_id.get(object_id)
        if entry is None or entry.outcome is not GateOutcome.ADMITTED:
            return
        entry.cluster_member_object_ids = cluster_member_object_ids
        entry.observation_id = observation_id

    def annotate_motion(
        self,
        object_id: int,
        *,
        speed_mps: float | None,
        perp_speed_mps: float | None,
        angular_rate_rad_s: float | None,
        threshold_rad_s: float,
        skew_s: float | None,
        apparent_motion: bool | None,
    ) -> None:
        """Fill in the movement gate's inputs/verdict on `object_id`'s most
        recently recorded entry (`perception.motion`, `plans/
        movement-detection/plan.md`) -- a no-op if that entry doesn't exist.
        Unlike `annotate_admission`, not restricted to `ADMITTED` entries:
        the movement gate only ever runs on already-admitted (`visible`)
        candidates in `NakedEyePerceptionSource.poll`, so the outcome is
        always `ADMITTED` in practice, but this method itself does not
        assume that."""
        entry = self._last_by_object_id.get(object_id)
        if entry is None:
            return
        entry.motion_speed_mps = speed_mps
        entry.motion_perp_speed_mps = perp_speed_mps
        entry.motion_angular_rate_rad_s = angular_rate_rad_s
        entry.motion_threshold_rad_s = threshold_rad_s
        entry.motion_skew_s = skew_s
        entry.apparent_motion = apparent_motion

    def annotate_los(
        self,
        object_id: int,
        *,
        building_clear: bool | None,
        terrain_clear: bool | None,
        live_los_clear: bool | None,
        skew_s: float | None,
        hour_used: int | None,
        fov_half_deg_used: int | None,
    ) -> None:
        """Fill in the DCS-driven LOS fields on `object_id`'s most recently
        recorded entry (`plans/dcs-driven-los/plan.md`, X-B29) -- mirrors
        `annotate_motion`'s own shape exactly: a no-op if that entry
        doesn't exist, not restricted to `ADMITTED` entries (the join
        happens upstream of the gate chain, in `naked_eye_source.py`'s
        candidate construction, so it is meaningful for a candidate at any
        gate outcome, including `TERRAIN_LOS` itself)."""
        entry = self._last_by_object_id.get(object_id)
        if entry is None:
            return
        entry.building_clear = building_clear
        entry.terrain_clear = terrain_clear
        entry.live_los_clear = live_los_clear
        entry.los_skew_s = skew_s
        entry.hour_used = hour_used
        entry.fov_half_deg_used = fov_half_deg_used
