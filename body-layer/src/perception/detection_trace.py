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
    code-level distinction `visibility.py` doesn't have.

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
