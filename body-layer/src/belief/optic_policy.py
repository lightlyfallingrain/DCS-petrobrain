"""When Petrovich raises binoculars, and when he puts them down.

`plans/binocular-optic/plan.md` Stage 2. The optical model already existed
and was unreachable; this is the decision that reaches it.

**It is a phase cycle, not an interrupt** (user direction, 2026-09-23:
*"when scan detects target, do not immediately raise binoculars. First
complete the current sector naked eye scan to get as many naked eye
detections as possible, then raise binoculars to take a closer look"*):

- **Scan phase** -- the naked-eye plan runs to completion. Detections
  accumulate; nothing is glassed.
- **Glass phase** -- entered only at a phase boundary, and only when there
  is something worth looking at. Ends on its own conditions, hands back.

**That structure is what enforces the cost.** The user's rule was *"at
least one naked eye scan before next binocular usage"*, and rather than a
timer that could be got wrong, a glass phase is simply unreachable except
from the end of a scan phase -- the illegal state cannot be expressed. Its
length then follows whatever plan is active, which is exactly the
*"depends on scan mode"* the user asked for: a free scan cycles in 16 s, a
commanded o'clock sector far faster, and **nothing here computes that** --
it is the plan's own period.

**Why this lives in `belief`.** The decision reads beliefs -- what is
detected, at what class, at what range -- and `perception` may not import
`belief` (`perception/source.py`'s module docstring). `gaze.py` resolved
this exact tension already and its resolution is reused verbatim: belief
decides, `logger` hands perception a frozen value per poll, perception
owns the act. `decide` is a pure function of its inputs, so replay stays
deterministic for the same reason `gaze_at` does.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import pairwise
from typing import Final

import tuning
from belief.enrichment import CLOCK_BUCKET_DEG
from belief.position_belief import PositionEstimate
from perception.gaze import SCAN_CYCLE_PERIOD_S
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.object_model import apparent_extent_m, distinctiveness_of, profile_for

#: How many sigma of a contact's own `PositionEstimate.bearing_uncertainty_
#: deg` the look sweep must cover -- `plans/precise-position-belief/plan.md`
#: Stage 5. Declared independently of `belief.association_over_time.
#: GATE_SIGMA_THRESHOLD` (which happens to share this value) rather than
#: importing it: that constant answers a different question (does an
#: incoming percept plausibly refer to this contact) from this one (how
#: wide must a sweep be to actually cover the belief), and the two
#: modules' own history (`association_over_time.py`'s docstring, Stage
#: 3b-i) is exactly about not letting two different questions share a
#: number by accident. At 3 km with `perception.estimation.
#: BEARING_SIGMA_DEG=3.0`, a single fresh look's own 1-sigma cross-range
#: angle is ~3 degrees, so a 3-sigma sweep is +/-9 degrees -- narrower than
#: the pre-Stage-5 fixed +/-15 (`CLOCK_BUCKET_DEG / 2.0`), and a
#: well-refined contact (several looks fused, tight covariance) narrows
#: further still, collapsing to a single-step stare once the sweep fits in
#: one binocular field of view.
LOOK_SWEEP_SIGMA: Final[float] = 3.0
from perception.optics import (
    BINOCULAR_OPTIC,
    SIGHT_NARROW_OPTIC,
    SIGHT_WIDE_OPTIC,
    UNAIDED_OPTIC,
    Optic,
    within_field_of_regard,
)
from perception.visibility import tier_ranges

#: The longest one look can last. The user's number, and a ceiling rather
#: than a duration: `look_is_finished` normally ends a look sooner, when
#: there is nothing left to learn from it. This fires only when recognition
#: simply is not happening, which is exactly the case where continuing to
#: stare buys nothing and costs the scan.
MAX_LOOK_S: Final[float] = 6.0

#: Above this rate of attitude change, binoculars come down (user:
#: *"jittery flying and hard manouvering lowers binoculars, they are
#: useless unless the flight is fairly smooth"*).
#:
#: **This gate sees manoeuvring, not vibration, and does not need to see
#: vibration.** Body-layer samples attitude about once a second, which
#: aliases anything faster -- but `BINOCULAR_OPTIC`'s own stabilisation
#: penalty already prices the fact that a helicopter cockpit is never
#: still. Modelling the shake twice would double-count it. What this
#: catches is the aircraft being thrown around, which is both observable at
#: this rate and the thing that actually makes an instrument unusable.
#:
#: Uncalibrated, like every perception constant before its first sortie.
STEADY_RATE_LIMIT_DEG_S: Final[float] = 12.0

#: How long the 1 s hand movement of switching the sight on/off, or
#: between its settings, suppresses observation entirely -- direction §6
#: (`docs/acceptance/2026-10-15-9k113-sight-direction.md`), `plans/
#: 9k113-sight/plan.md` Stage 2. Any cockpit action that touches the
#: sight sets `OpticState.hands_busy_until_sim` to `now_sim + this`; while
#: it is set, no optic yields observations at all -- Petrovich's eyes are
#: on the switch, not through any instrument. Not sourced from the
#: manual; a project modelling choice, same footing as `MAX_LOOK_S`
#: above. Raising it makes the switch cost more attention per toggle;
#: lowering it toward 0 makes OBSERV effectively free to flip.
HANDS_BUSY_DURATION_S: Final[float] = tuning.real(
    "belief.optic_policy.HANDS_BUSY_DURATION_S",
    1.0,
    lo=0.1,
    hi=5.0,
    status="judgement",
)

#: The 9K113's own manoeuvre-tolerance threshold, mirroring
#: `STEADY_RATE_LIMIT_DEG_S`'s role but for a gyro-stabilised sight rather
#: than a pair of hands holding binoculars steady -- direction §8
#: (*"Gyros are sensitive to violent manouvres and OBSERV must be
#: swithced OFF is pilot manouvres violently"*), plan §13.
#: **Deliberately a separate constant, not a reuse** -- a stabilised
#: sight tolerates far more attitude-rate than an arm does, so the same
#: number here would force OBSERV off during perfectly flyable
#: manoeuvring. Higher than `STEADY_RATE_LIMIT_DEG_S` is the only
#: direction that makes sense; lowering it below that sibling would make
#: the sight *less* tolerant than binoculars, which the user's own
#: framing rules out. Uncalibrated, like `STEADY_RATE_LIMIT_DEG_S` before
#: its first sortie.
SIGHT_STEADY_RATE_LIMIT_DEG_S: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_STEADY_RATE_LIMIT_DEG_S",
    30.0,
    lo=12.0,
    hi=90.0,
    status="judgement",
)

#: The sight's own dwell ceiling, mirroring `MAX_LOOK_S`'s role but much
#: longer -- direction §9 (*"When using 9K113 we typically use it for a
#: longer period of time"*), plan §13. Unlike `MAX_LOOK_S` (which only
#: fires when recognition genuinely is not happening), this is also the
#: *scheduled* break trigger: dwelling at the sight this long, regardless
#: of whether something is still worth looking at, forces a brief
#: naked-eye glance away (`SIGHT_GLANCE_AWAY_S`) before resuming --
#: direction §9's *"Maybe take eyes off it for a quick glance around and
#: then continue with the sight."* A project modelling choice, tuned from
#: flying like every dwell/scan constant before it.
SIGHT_MAX_DWELL_S: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_MAX_DWELL_S",
    30.0,
    lo=5.0,
    hi=120.0,
    status="judgement",
)

#: How long the brief naked-eye glance away from the sight lasts, mirroring
#: `SCAN_CYCLE_PERIOD_S`'s role as the home phase's own dwell boundary --
#: but here the *interruption's* duration, not the home phase's: direction
#: §9's "inverted dwell shape" (plan §13) swaps which phase is home and
#: which is the bounded break, so the breaks' own timescale inverts with
#: it -- brief here, where `MAX_LOOK_S` (the old break, now unused while
#: OBSERV is on) was the long one.
SIGHT_GLANCE_AWAY_S: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_GLANCE_AWAY_S",
    3.0,
    lo=1.0,
    hi=15.0,
    status="judgement",
)

#: How much closer a contact must get before a failed identification is
#: worth retrying (user: *"if ID failed, try again when we get closer"*).
#:
#: **A range test rather than a timer, deliberately.** A contact at
#: constant range has not become more identifiable, so a retry there
#: re-asks a question already answered and spends the look that another
#: contact could have used.
RETRY_RANGE_FRACTION: Final[float] = 0.8

#: `plans/sortie-2026-09-26-fixes/decisions.md` Decision 2/2a -- alongside
#: `RETRY_RANGE_FRACTION` above (which stays, for the *closing-on* case),
#: a time-based re-eligibility for the *watched-or-orbited* case: a contact
#: held at roughly constant range (a stand-off, an orbit) can never satisfy
#: `RETRY_RANGE_FRACTION` and would otherwise be locked out of binoculars
#: for the rest of the encounter after a single attempt. **This is a
#: starting value to tune against a flown sortie, not a measurement** --
#: proposed as `4 * SCAN_CYCLE_PERIOD_S`, long enough that re-looks don't
#: dominate "identification takes priority over search" every completed
#: scan cycle, short enough that a stalled contact gets retried well inside
#: a typical encounter rather than after hundreds of seconds.
OPTIC_RETRY_INTERVAL_S: Final[float] = 4.0 * SCAN_CYCLE_PERIOD_S

#: The widest sector a binocular *search* will sweep (user: *"cap binocular
#: scan at 30 deg azimuth, there's no wide area binocular scan"*). A wider
#: commanded scan simply gets no search phase -- see `plans/binocular-optic/
#: plan.md` D6 for the arithmetic that makes a 180-degree sweep absurd
#: (~60 steps) where a 30-degree one is about twelve.
MAX_SEARCH_SECTOR_HALF_WIDTH_DEG: Final[float] = 15.0

#: How long the look rests on each step of a search sweep. Short, because
#: the act is *detection* -- the user's own framing: *"this should be fast,
#: not dwelling on any spot, but rather trying to detect targets. Detected
#: targets then get the dwell behaviour."* Dwelling is what the
#: identification look is for, and it happens on a later cycle.
SEARCH_STEP_S: Final[float] = 0.8


class OpticPhase(str, Enum):
    """Which part of the cycle is running.

    `SEARCHING` is a glass phase too -- binoculars are up -- but a
    different *act*: it sweeps to detect rather than resting to resolve,
    so it has its own step timing and its own end condition. Keeping them
    apart is what stops a search inheriting the identification look's
    "stop when nothing can improve", which would end a sweep on its first
    step every time.
    """

    SCANNING = "scanning"
    GLASSING = "glassing"
    SEARCHING = "searching"
    #: Dwelling at the 9K113 sight (`BL-B64` Stage 2, direction §6/§9) --
    #: reachable only as the *home* phase (`OpticState.home_phase`), never
    #: entered the way `GLASSING`/`SEARCHING` are. While OBSERV is on this
    #: plays the role `SCANNING` plays today: the resting phase `decide`
    #: returns to at every phase boundary. See `OpticState.home_phase`'s
    #: own docstring for the full inversion.
    SIGHTING = "sighting"


@dataclass(frozen=True)
class LookTarget:
    """One contact worth a closer look, with what the decision needs about
    it. Built by the caller from live beliefs; this module never touches a
    `Contact` directly, so the policy stays testable without a store."""

    contact_id: str
    azimuth_deg: float
    elevation_deg: float
    range_m: float
    object_type: str
    #: The specificity the contact is already believed at -- `"presence"`,
    #: `"class"`, `"type"`, or `"unknown"` (`belief.classification.
    #: SpecificityLevel`'s own vocabulary, lowercased). It selects *which*
    #: tier a look would gain, which is what makes the trigger "raise to
    #: classify" rather than "raise to identify".
    current_level: str
    #: How far the *believed* bearing may be from the true one, degrees.
    #:
    #: **This is why a look is a sweep and not a stare.** Originally, a
    #: contact's position was reconstructed from a quantised percept -- the
    #: reporting vocabulary's 30-degree clock bucket -- so the belief could
    #: be up to 15 degrees off in azimuth, against a binocular field of view
    #: of 4.25. Aiming a single stare at the believed position would miss
    #: the target most of the time, and a mock-flight test caught exactly
    #: that as four vanished observations. He knows it is "around two
    #: o'clock"; he sweeps around two o'clock.
    #:
    #: **As of `plans/precise-position-belief/plan.md` Stage 5, this is a
    #: real measured number, not the fixed bucket half-width.**
    #: `look_target_for`'s `bearing_uncertainty_deg` parameter passes
    #: `LOOK_SWEEP_SIGMA * contact.position.bearing_uncertainty_deg(observer)`
    #: when the caller has a real `PositionEstimate` to hand -- see that
    #: function's own docstring. The `CLOCK_BUCKET_DEG / 2.0` default below
    #: is kept as the fallback for any caller (present or future) that does
    #: not yet have one, not because it is still the honest figure.
    bearing_uncertainty_deg: float = CLOCK_BUCKET_DEG / 2.0

    #: Whether the pilot asked for this contact to be watched (user,
    #: 2026-09-25: identify by glass *"for all contacts, but even more so
    #: watched contacts"*). Read from `belief.attention.
    #: effective_attention`'s derived level, the same definition the
    #: watched-only callouts and the eyesight view's orange both use --
    #: keeping the three in step matters, because "why is he glassing
    #: that one" and "why is that one reporting to me" should have the
    #: same answer.
    #:
    #: Only `choose_look` reads it. It deliberately does **not** affect
    #: `is_worth_a_look`/`can_still_improve`: an unwatched contact inside
    #: its improvement window is still worth identifying, so this changes
    #: the *order* looks happen in, never whether they happen at all.
    watched: bool = False


@dataclass(frozen=True)
class OpticState:
    """The cycle's own state, carried across polls by the runner.

    Frozen and replaced rather than mutated, so a poll that decides nothing
    returns the identical object and a replay produces the identical
    sequence."""

    phase: OpticPhase = OpticPhase.SCANNING
    #: When the current phase began. **`None` until the first poll**, not
    #: `0.0`: a mission's sim clock does not start at zero, so a default of
    #: zero means the very first poll sees a scan that "completed" long ago
    #: and raises binoculars before ever having scanned. A test caught
    #: exactly that. `decide` adopts the first `now_sim` it is given and
    #: starts the cycle there.
    phase_started_sim: float | None = None
    #: Where the current look points, body-relative. `None` while scanning.
    look_azimuth_deg: float | None = None
    look_elevation_deg: float | None = None
    #: The sweep being worked through, and how far into it. Used by both
    #: glass phases: a search sweeps a sector, and a look sweeps the
    #: uncertainty around one believed contact. Empty while scanning.
    search_pattern_steps: tuple[tuple[float, float], ...] = ()
    search_step_index: int = 0
    #: The look's own sweep centre and half-width, fixed for the whole
    #: `GLASSING` phase -- unlike `look_azimuth_deg`, which moves to the
    #: current step every poll. `look_is_finished` and the attempted-range
    #: marking test against *this* envelope, not the current step, because
    #: a contact deliberately outside today's step may still be inside the
    #: sweep the look as a whole covers (`plans/binocular-optic/
    #: stage3b.md` D4). `None` outside `GLASSING` (and while `SEARCHING`,
    #: which has its own end condition and never reads these).
    look_envelope_azimuth_deg: float | None = None
    look_envelope_half_width_deg: float | None = None
    #: Range at the last *committed* attempt, per contact --
    #: `RETRY_RANGE_FRACTION`'s input. Contacts are never removed: the map
    #: is bounded by how many distinct contacts one sortie produces, and
    #: forgetting an attempt would let a contact be re-glassed forever at
    #: the same range. **Committed** means the look that covered this
    #: contact reached its own natural end (`look_is_finished`) -- see
    #: `pending_attempted_at_range_m` below for the look-in-progress twin
    #: this is merged from.
    attempted_at_range_m: dict[str, float] = field(default_factory=dict)
    #: `plans/sortie-2026-09-26-fixes/plan.md` Stage 2 (Fix B1) -- the
    #: attempt marks a look-in-progress has covered but not yet delivered.
    #: Populated at the SCANNING -> GLASSING transition exactly where
    #: `attempted_at_range_m` used to be populated directly; merged into
    #: `attempted_at_range_m`/`attempted_at_time_sim` only when the current
    #: look reaches its own natural end (`look_is_finished` true while
    #: still steady) -- an interruption (`not steady`, or `lower_binoculars`
    #: called from outside) drops this map instead, via `_back_to_home`,
    #: without ever committing it. This is the fix for the diagnosed
    #: defect: a look cut short by a player command delivered less than a
    #: full look's worth of dwell and must not burn the same retry budget
    #: as a completed one. Empty outside `GLASSING`.
    pending_attempted_at_range_m: dict[str, float] = field(default_factory=dict)
    #: `plans/sortie-2026-09-26-fixes/plan.md` Stage 3 (Fix B2) --
    #: `attempted_at_range_m`'s time-of-attempt twin, committed at the same
    #: point (value: `now_sim` at commit). Drives `is_worth_a_look`'s
    #: time-based re-eligibility branch (`belief.optic_policy.
    #: OPTIC_RETRY_INTERVAL_S`) alongside the existing range-based one --
    #: see that constant's own docstring for why a watched-or-orbited
    #: contact held at roughly constant range needs a time basis, not only
    #: a range one.
    attempted_at_time_sim: dict[str, float] = field(default_factory=dict)
    #: `plans/sortie-2026-09-26-fixes/plan.md` Stage 4 (Fix C) -- the
    #: `contact_id` of the *primary* (chosen/centred) target of the current
    #: look, set at the same SCANNING -> GLASSING transition site as
    #: `pending_attempted_at_range_m`/`attempted_at_time_sim` above, cleared
    #: by `_back_to_home`. Names only the look's chosen centre, not
    #: every contact its field of view happens to also cover -- a look
    #: centred on contact A that incidentally covers contact B still counts
    #: as "not on B" for `follow <target>`'s continuation check
    #: (`decisions.md` Decision 2: "if binoculars were in use AND looking at
    #: <target> continue"), matching the user's own fallback ("if...NOT
    #: looking at target, lower...re-point at the target") rather than
    #: requiring full envelope-overlap testing. `None` while `SCANNING` or
    #: `SEARCHING`.
    look_contact_id: str | None = None
    #: Where the sight head *actually* points, as distinct from
    #: `look_azimuth_deg`/`look_elevation_deg` above (belief's *desired*
    #: aim) -- `plans/9k113-sight/plan.md` §15a, direction §12. `None`
    #: exactly when no fixed look is commanded, mirroring `look_azimuth_
    #: deg`'s own contract. Advanced by `advance_sight_aim` at the one
    #: place `OpticDecision`'s desired aim becomes a `Gaze`
    #: (`logger._apply_active_gaze`) -- carried here, not computed inside
    #: `gaze_at`, because `gaze_at` must stay a pure function of `t_sim`
    #: alone for replay determinism, which is exactly what this class's own
    #: "frozen and replaced rather than mutated" rule protects. Today
    #: `actual := desired` unconditionally (`advance_sight_aim`'s own
    #: docstring) -- permanently correct for the naked eye and binoculars,
    #: a stated placeholder for a sighted optic until `[[BL-B66]]` inserts
    #: a real controller between these two fields without moving this one.
    #:
    #: **Every branch of `decide` below that constructs a fresh `OpticState`
    #: (rather than `replace`-ing one) must carry these two fields forward
    #: explicitly** -- they are not part of this cycle's own phase
    #: bookkeeping, so there is no phase-transition reason to reset them,
    #: and a future controller needs continuity across polls to converge at
    #: all.
    actual_aim_azimuth_deg: float | None = None
    actual_aim_elevation_deg: float | None = None

    #: Which phase `decide` treats as *home* -- `SCANNING` (default) or
    #: `SIGHTING` -- `BL-B64` Stage 2, plan §13, direction §6/§9/§13a.
    #: Set to `SIGHTING` only by the pilot's own "Observ on" command
    #: (`logger.py`'s poll loop, mirroring `lower_binoculars`'s own
    #: external-caller shape) and back to `SCANNING` by "Observ off" **or**
    #: by a violent manoeuvre (`SIGHT_STEADY_RATE_LIMIT_DEG_S`) -- never by
    #: `lower_binoculars` itself, which must leave this field alone (§13a's
    #: first named trap: *"the pilot asking for something is itself
    #: evidence that what Petrovich is doing matters less than what was
    #: just asked for"* governs the current *dwell*, not the standing
    #: OBSERV mode).
    #:
    #: **`SCANNING` default means every OBSERV-off poll is bit-identical to
    #: before this field existed** -- `decide`'s dispatch below only takes
    #: a different path when this is `SIGHTING`, so a caller that never
    #: sets it exercises exactly the code this entry found already
    #: working.
    #:
    #: **The inversion, direction §9:** with `home_phase=SCANNING` (today),
    #: `SCANNING` rests and `GLASSING`/`SEARCHING` are the phase entered at
    #: a scan boundary to look closer. With `home_phase=SIGHTING`,
    #: `SIGHTING` itself rests (long dwell, picking and sweeping a look
    #: target exactly as `GLASSING` does today, just without a gating scan
    #: to complete first) and `SCANNING` becomes the bounded interruption
    #: -- a brief naked-eye glance away, entered at a *dwell* boundary
    #: (`SIGHT_MAX_DWELL_S`) precisely as `GLASSING` is entered at a scan
    #: boundary today, and left again after `SIGHT_GLANCE_AWAY_S`. Reusing
    #: `OpticPhase.SCANNING` for both roles (home, and the glance-away) is
    #: deliberate, not a conflation: distinguishing them only ever needs
    #: `state.phase == state.home_phase`, exactly how `lower_binoculars`
    #: already asks "am I home".
    home_phase: OpticPhase = OpticPhase.SCANNING
    #: Set by any cockpit action that touches the sight (the pilot's
    #: "Observ on"/"Observ off" command, `logger.py`'s poll loop) to
    #: `now_sim + HANDS_BUSY_DURATION_S` -- while `now_sim` is still below
    #: this, `decide` suppresses every optic's observations (`OpticDecision.
    #: suppressed`) rather than advancing any phase logic, direction §6's
    #: "1 s hand movement" (plan Stage 2). `None` (the default, and the
    #: value whenever no such action has ever run) is a true no-op.
    hands_busy_until_sim: float | None = None
    #: When the *current* look-within-`SIGHTING` started -- distinct from
    #: `phase_started_sim`, which for `SIGHTING` tracks the *whole dwell*
    #: since entering the sight (the clock `SIGHT_MAX_DWELL_S` reads),
    #: not any one look's own envelope-sweep timing the way it does for
    #: `GLASSING` (where entering the phase and starting the look are the
    #: same event). `None` while idle (nothing chosen) or outside
    #: `SIGHTING` entirely.
    look_started_sim: float | None = None


@dataclass(frozen=True)
class OpticDecision:
    """What perception should do this poll."""

    optic: Optic
    #: Where to point, when glassing. `None` means "leave the scan plan
    #: alone" -- the scan phase does not override the gaze at all.
    look_azimuth_deg: float | None = None
    look_elevation_deg: float | None = None
    #: `True` while `OpticState.hands_busy_until_sim` is active -- `BL-B64`
    #: Stage 2, direction §6. `_apply_active_gaze` (`logger.py`) reads this
    #: to suppress `NakedEyePerceptionSource` entirely for the poll, rather
    #: than assigning any particular optic -- `optic` is still populated on
    #: this branch (as `UNAIDED_OPTIC`) only because the field is not
    #: optional; it is never acted on while this is `True`.
    suppressed: bool = False


def advance_sight_aim(
    actual_azimuth_deg: float | None,
    actual_elevation_deg: float | None,
    desired_azimuth_deg: float | None,
    desired_elevation_deg: float | None,
    *,
    dt_s: float,
) -> tuple[float | None, float | None]:
    """Converge the sight's *actual* pointing direction toward belief's
    *desired* one, one poll at a time -- `plans/9k113-sight/plan.md` §15a,
    direction §12/§12a. Called from the one conversion point where
    `OpticDecision`'s desired aim becomes the `Gaze`/cone perception
    actually uses (`logger._apply_active_gaze`), so a future controller
    replaces this function's body without moving that call site.

    **Perception-stage body: a pure pass-through.** The sight is slewed by
    a rate-commanded control loop in reality -- read where it is, command
    a deflection, repeat (direction §12) -- but that loop belongs to the
    effector stage (`[[BL-B66]]`), which has not landed. Until it does,
    `actual := desired` instantly: *permanently* correct for the naked eye
    and binoculars (a head turn is instant against a 1 Hz poll), a stated
    placeholder for a sighted optic.

    `dt_s` is accepted and unused here -- reserved for the rate-limited
    controller `[[BL-B66]]` adds, which needs it to bound how far `actual`
    may move in one poll. Keeping it in the signature now, even though
    this body ignores it, is what lets that controller drop in without
    changing the call site or its callers."""
    return desired_azimuth_deg, desired_elevation_deg


def _step_centres_deg(half_width_deg: float, fov_full_width_deg: float) -> list[float]:
    """Evenly-spread step centres covering `[-half_width_deg,
    +half_width_deg]`, so the first and last steps cover the edges.

    Shared by `search_pattern` (sweeping a sector of *unknown* ground) and
    `look_sweep` (sweeping the *known* angular uncertainty around one
    believed direction) -- both need the same "how many steps of this
    width does it take to cover this span, evenly centred" arithmetic, and
    only the number of steps and what each represents differ
    (`plans/binocular-optic/stage3b.md` D2).
    """
    steps_across = max(1, math.ceil((2.0 * half_width_deg) / fov_full_width_deg))
    if steps_across == 1:
        return [0.0]
    stride = (2.0 * half_width_deg) / steps_across
    return [-half_width_deg + stride * (index + 0.5) for index in range(steps_across)]


def search_pattern(
    *,
    sector_half_width_deg: float,
    near_m: float,
    far_m: float,
    altitude_agl_m: float,
    fov_full_width_deg: float,
) -> list[tuple[float, float]]:
    """The boustrophedon sweep for a binocular search of one sector:
    `(azimuth, elevation)` steps in the order they should be looked at.

    **Range is the vertical axis, so "close to far" and "as high as there
    is ground ahead" are the same instruction** (user's own worded
    example). A patch of ground at range `R` sits `atan(h / R)` below the
    horizon, so sweeping outward *is* sweeping upward, and the far limit is
    the horizon rather than a distance anyone has to choose. Elevation is
    therefore never positive: "do not scan at sky" is a property of the
    geometry here, not a clamp bolted on afterwards.

    **The number of range bands is derived, and at helicopter altitude it
    is one.** The whole 2.3-5.6 km band spans under 2 degrees of depression
    at 120 m AGL -- far inside a binocular's own ~8.5-degree field -- so the
    S-shape degenerates to a single left-right sweep, and only becomes a
    real raster above roughly 700 m. Computing the bands rather than fixing
    their count is what makes that fall out instead of producing a
    pointlessly slow vertical crawl at low level.

    `sector_half_width_deg` is capped at `MAX_SEARCH_SECTOR_HALF_WIDTH_DEG`
    (user: *"cap binocular scan at 30 deg azimuth, there's no wide area
    binocular scan"*) -- a wider commanded scan is swept only across its
    middle, rather than taking a minute to cover.
    """
    half_width = min(sector_half_width_deg, MAX_SEARCH_SECTOR_HALF_WIDTH_DEG)
    azimuths = _step_centres_deg(half_width, fov_full_width_deg)

    near_depression = math.degrees(math.atan2(altitude_agl_m, max(near_m, 1.0)))
    far_depression = math.degrees(math.atan2(altitude_agl_m, max(far_m, 1.0)))
    spread = abs(near_depression - far_depression)
    bands = max(1, math.ceil(spread / fov_full_width_deg))
    if bands == 1:
        elevations = [-(near_depression + far_depression) / 2.0]
    else:
        step = (near_depression - far_depression) / (bands - 1)
        elevations = [-(near_depression - step * index) for index in range(bands)]

    pattern: list[tuple[float, float]] = []
    for band_index, elevation in enumerate(elevations):
        sweep = azimuths if band_index % 2 == 0 else list(reversed(azimuths))
        pattern.extend((azimuth, elevation) for azimuth in sweep)
    return pattern


def look_sweep(
    *,
    centre_azimuth_deg: float,
    centre_elevation_deg: float,
    bearing_uncertainty_deg: float,
    fov_full_width_deg: float,
    regard_optic: Optic | None = None,
) -> list[tuple[float, float]]:
    """The steps one binocular identification look works through, sweeping
    the believed bearing's own angular uncertainty instead of staring at
    its centre (`plans/binocular-optic/stage3b.md`).

    **A sibling of `search_pattern`, not a reuse of it.** `search_pattern`
    covers unknown ground between two ranges and derives elevation from a
    range->depression mapping; a look covers the *known* angular error
    around one believed direction, at the elevation the belief already
    supplies. Forcing this through `search_pattern` would mean passing
    `near_m = far_m` to recover an angle already in hand, and inheriting a
    search-policy cap (`MAX_SEARCH_SECTOR_HALF_WIDTH_DEG`) and a
    ground-only sky clamp that both answer the wrong question here.

    **Elevation is held constant at `centre_elevation_deg`.** The down-range
    bucket that widens a naked-eye report also perturbs elevation, but at
    helicopter geometry that is well under a degree against a binocular's
    ~4-degree half-angle -- a second swept axis would buy nothing and only
    cost steps that azimuth needs more.

    **Ordered centre-outward**: the believed bearing is the most likely
    one, so looking there first maximises the chance of ending the sweep on
    step 0 (`look_is_finished`), and guarantees the single most likely
    direction is sampled even if the poll rate under-samples the rest of
    the sweep.

    **`N == 1` reproduces today's stare exactly** -- when the uncertainty
    fits inside one field of view, the sweep is a single step at the
    believed direction for the whole look. The stare is this function's
    degenerate case, not a branch elsewhere.

    **`regard_optic` truncates the sweep at the mount's own field of regard
    (`BL-B64` security follow-up, `plans/9k113-sight/security.md`'s
    "Notable Discoveries").** `_decide_sighting` already rejects a *chosen*
    target outside the sight's field of regard before this function ever
    runs -- but the sweep this function builds *around* that validated
    target still reaches `bearing_uncertainty_deg` past it on either side,
    and a fresh contact's 15-degree default uncertainty is wider than the
    narrow sight's own 3-degree half-angle, so a target only a few degrees
    inside the boundary swept steps well past it. Every such step was
    committed as `look_azimuth_deg` exactly as the chosen target itself
    would have been, feeding the player-bubble cone from a direction the
    9K113 cannot physically point -- the same leak the required fix closed,
    one level downstream.

    **Truncated, not narrowed.** Dropping the out-of-regard steps (rather
    than shrinking `bearing_uncertainty_deg` before sweeping) keeps every
    step on the reachable side at its full width, so the half of the
    uncertainty that is *not* adjacent to the boundary is swept exactly as
    before. Narrowing the envelope instead would have reduced coverage on
    the unconstrained side too, for no benefit -- the contact may just as
    well have drifted away from the boundary as into it, and nothing about
    the boundary makes that direction less likely. A mount that cannot
    swing past its limit does not search less on the side it *can* reach
    either; it searches that side in full and simply does not visit the
    side it cannot. This is the same "reject, not clamp" choice
    `within_field_of_regard`'s own docstring makes at the selection point,
    carried through to this sweep: a step outside the envelope is dropped,
    never pulled back to the boundary and attributed to a bearing it was
    not generated for.

    **A true no-op when `regard_optic` is `None`** (the default, and the
    only value `GLASSING`'s binocular call ever passes -- `BINOCULAR_OPTIC.
    regard_azimuth_half_deg` is `None`, so filtering by it would have been
    a no-op there regardless; passing `None` through this parameter
    instead keeps that unconditional, not merely incidental). Also a
    no-op, field by field, for any `regard_optic` whose own `regard_*`
    attributes are `None` -- `within_field_of_regard` already treats an
    unset bound as unrestricted, and this function relies on that rather
    than re-deriving it.

    **The centre step (offset zero) always survives the filter.** It is
    exactly `(centre_azimuth_deg, centre_elevation_deg)` -- the chosen
    target's own validated direction, by every caller's construction -- so
    this function never returns an empty list for a `regard_optic` whose
    bound that direction already satisfies. It does not re-validate that
    precondition itself; a caller that swept around an already-rejected
    centre would be a bug upstream of this function, not one this filter
    can repair.
    """
    half_width = max(bearing_uncertainty_deg, 0.0)
    azimuths = sorted(
        _step_centres_deg(half_width, fov_full_width_deg), key=lambda a: (abs(a), a)
    )
    steps = [(centre_azimuth_deg + offset, centre_elevation_deg) for offset in azimuths]
    if regard_optic is not None:
        steps = [
            step
            for step in steps
            if within_field_of_regard(regard_optic, step[0], step[1])
        ]
    return steps


def is_steady(
    attitude_samples: Sequence[tuple[float, float, float, float]],
    *,
    rate_limit_deg_s: float = STEADY_RATE_LIMIT_DEG_S,
) -> bool:
    """Whether the aircraft is flying smoothly enough to use binoculars.

    `attitude_samples` is `(t_sim, pitch_deg, bank_deg, heading_deg)`,
    oldest first -- whatever recent history the caller has. Fewer than two
    samples is treated as steady: at startup there is no evidence of
    manoeuvring, and refusing to look until proven calm would make the
    instrument unusable for the first seconds of every mission.

    Heading is wrapped before differencing, so crossing north is not a
    360-degree-per-second manoeuvre.

    `rate_limit_deg_s` defaults to `STEADY_RATE_LIMIT_DEG_S` (binoculars'
    own threshold), kept as a parameter rather than a second copy of this
    function so `[[BL-B64]]` Stage 2 can reuse it for the sight's own,
    higher `SIGHT_STEADY_RATE_LIMIT_DEG_S` (`logger.py`'s poll loop calls
    this twice per poll, once per threshold)."""
    if len(attitude_samples) < 2:
        return True

    for (t0, pitch0, bank0, hdg0), (t1, pitch1, bank1, hdg1) in pairwise(
        attitude_samples
    ):
        dt = t1 - t0
        if dt <= 0.0:
            continue  # duplicate or out-of-order sample; no rate to read
        heading_delta = (hdg1 - hdg0 + 180.0) % 360.0 - 180.0
        rate = (
            max(
                abs(pitch1 - pitch0),
                abs(bank1 - bank0),
                abs(heading_delta),
            )
            / dt
        )
        if rate > rate_limit_deg_s:
            return False
    return True


def improvement_window_m(
    object_type: str, *, current_level: str
) -> tuple[float, float]:
    """The range band in which binoculars would move this contact up a
    tier: `(unaided_range, binocular_range)` for whichever tier is next.

    **Whatever tier is next, not always type.** The user's brief said both
    *"raise to classify"* and *"at distance where binoculars would identify
    type"*, and the first is the general rule the second is an instance of:
    a contact known only to exist is worth glassing to learn what *kind* of
    thing it is, and one already classed is worth glassing to learn what it
    *is*. Reading it as type-only made the feature nearly unusable, and the
    numbers say why -- for a 7 m vehicle:

        presence -> class:   500 m unaided,  1750 m glassed
        class    -> type:    250 m unaided,   750 m glassed

    Classification is both the commoner want and the far wider band. A
    type-only trigger would have confined binoculars to inside 750 m, where
    the interesting question is usually *"what is that"* at three times
    that range.

    **Computed from the existing calibration rather than tuned.** Closer
    than the lower bound, the naked eye reaches that tier on the next dwell
    anyway, so glassing there spends the look to learn nothing; beyond the
    upper bound the binoculars cannot reach it either. The window is
    exactly the band where the instrument is the difference, and it comes
    out of `tier_ranges` -- the same code the eye itself uses -- not from a
    threshold invented here.

    A contact already at `type` has no next tier: `(0.0, 0.0)`, a window
    nothing falls inside.
    """
    profile = profile_for(object_type)
    # Aspect is unknown for a belief (the contact may have turned since it
    # was last seen), so the profile's own extent is used. A wrong guess
    # costs at most one wasted look, which `RETRY_RANGE_FRACTION` then
    # stops from repeating.
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)

    def ranges(optic: Optic) -> tuple[float, float, float]:
        return tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=optic,
            distinctiveness=distinctiveness,
        )

    _, unaided_class_m, unaided_type_m = ranges(UNAIDED_OPTIC)
    _, binocular_class_m, binocular_type_m = ranges(BINOCULAR_OPTIC)

    if current_level == "type":
        return 0.0, 0.0
    if current_level == "class":
        return unaided_type_m, binocular_type_m
    # presence, unknown, or anything else a belief can hold: the next thing
    # worth learning is what kind of thing it is.
    return unaided_class_m, binocular_class_m


def can_still_improve(target: LookTarget) -> bool:
    """Whether a look at this contact could raise its tier at all, ignoring
    whether one has been tried before.

    **Separate from `is_worth_a_look`, and the separation is load-bearing.**
    A look marks every contact it covers as attempted the moment it starts
    (they all get its benefit, so they all bear the retry rule) -- so if the
    stop condition asked "is this still *worth* a look", every look would
    end on the poll after it began, because the contact it was aimed at had
    just been marked. The retry rule governs *starting* a look; this governs
    *continuing* one. A test caught the conflation.
    """
    if target.current_level == "type":
        return False
    lower_m, upper_m = improvement_window_m(
        target.object_type, current_level=target.current_level
    )
    return lower_m < target.range_m <= upper_m


def is_worth_a_look(
    target: LookTarget, state: OpticState, now_sim: float = 0.0
) -> bool:
    """Whether this contact would gain anything from a *new* look now.

    `now_sim` defaults to `0.0` so every pre-existing call site that never
    supplied one keeps compiling and behaving identically -- `state.
    attempted_at_time_sim` is empty for those (no committed attempt has a
    time recorded), so the time-based branch below never fires for them
    regardless of the default's value."""
    if not can_still_improve(target):
        return False
    if target.contact_id in state.pending_attempted_at_range_m:
        # A look already in progress is covering this contact right now --
        # not yet committed, but plainly not worth *starting a second* look
        # over. `decide` never actually reaches this branch mid-`GLASSING`
        # (its own stop condition is `look_is_finished`, not this
        # function), but this keeps the invariant true regardless of
        # caller: starting a look and continuing one are different
        # questions about the same contact, in both directions.
        return False
    attempted_at = state.attempted_at_range_m.get(target.contact_id)
    if attempted_at is None:
        return True
    # Tried before: worth repeating once it has genuinely closed
    # (`RETRY_RANGE_FRACTION`, the closing-on case) -- **or** once enough
    # time has passed regardless of range (`OPTIC_RETRY_INTERVAL_S`, the
    # watched-or-orbited case D5 didn't cover: a contact held at roughly
    # constant range can never satisfy the range test alone). Either
    # condition suffices.
    closed_enough = target.range_m <= attempted_at * RETRY_RANGE_FRACTION
    attempted_at_time = state.attempted_at_time_sim.get(target.contact_id)
    time_elapsed_enough = (
        attempted_at_time is not None
        and now_sim - attempted_at_time >= OPTIC_RETRY_INTERVAL_S
    )
    return closed_enough or time_elapsed_enough


def choose_look(targets: Sequence[LookTarget]) -> LookTarget | None:
    """Which direction to point, given everything worth looking at.

    **Picks the direction holding the most targets, not the nearest one**
    (user: *"if binocular FOV sees multiple units at once, they all get the
    benefit"*). The optic is a property of the look rather than of a
    target, so a look that covers three unresolved contacts resolves three;
    choosing the nearest instead would spend the same look on one.

    **Directions covering a watched contact are preferred outright** (user,
    2026-09-25: identify by glass *"for all contacts, but even more so
    watched contacts"*). Ordered: how many watched contacts the direction
    covers, then how many contacts in total, then nearest. So a look at one
    watched contact beats a look at three unwatched ones, and among looks
    covering the same number of watched contacts the old coverage rule
    still applies unchanged.

    This orders looks; it does not gate them. An unwatched contact inside
    its improvement window is still worth identifying and still gets its
    turn -- see `LookTarget.watched`.
    """
    if not targets:
        return None
    half_angle = BINOCULAR_OPTIC.fov_half_angle_deg
    if half_angle is None:  # pragma: no cover -- binoculars always have one
        return min(targets, key=lambda t: t.range_m)

    def covered(centre: LookTarget) -> tuple[int, int, float]:
        in_view = [
            other
            for other in targets
            if _angular_separation_deg(centre, other) <= half_angle
        ]
        watched_count = sum(1 for other in in_view if other.watched)
        return watched_count, len(in_view), -centre.range_m

    return max(targets, key=covered)


def _angular_separation_deg(a: LookTarget, b: LookTarget) -> float:
    """True angular separation between two look directions -- not an
    azimuth difference, for the same reason `within_optic_fov` is not a
    box: a circular eyepiece does not admit a target because azimuth and
    elevation each pass independently."""
    az_delta = math.radians(a.azimuth_deg - b.azimuth_deg)
    el_a = math.radians(a.elevation_deg)
    el_b = math.radians(b.elevation_deg)
    cos_sep = math.sin(el_a) * math.sin(el_b) + math.cos(el_a) * math.cos(
        el_b
    ) * math.cos(az_delta)
    return math.degrees(math.acos(max(-1.0, min(1.0, cos_sep))))


def look_is_finished(
    state: OpticState,
    now_sim: float,
    targets: Sequence[LookTarget],
    *,
    started_sim: float | None = None,
    max_dwell_s: float = MAX_LOOK_S,
) -> bool:
    """Whether the current look has nothing left to give.

    The user's stop condition, which is sharper than the timer beside it:

    > unit(s) looked at gained more detailed identification / no other
    > units in FOV at distance where more detailed identification can be
    > expected

    Both halves are one predicate -- **no contact inside the look's sweep
    envelope is still within the improvement window** -- since a contact
    that has been identified has left the window by definition, and one
    that never could be was never in it. `max_dwell_s` then only fires
    when recognition is not happening at all.

    **The test is against the sweep's envelope, not the field of view**
    (`plans/binocular-optic/stage3b.md` D4). As written against the field
    of view, this would end every sweep on its first poll: step 0 may
    deliberately point away from a target that is still inside the
    believed bearing's own uncertainty, and that is the entire premise of
    sweeping. Today's stare is the `N = 1` case where the envelope *is*
    the field of view, so this widening is a strict generalisation, not a
    new rule -- the predicate keeps its old meaning exactly where it
    currently applies.

    `started_sim`/`max_dwell_s` default to `None` (meaning "use `state.
    phase_started_sim`") and `MAX_LOOK_S` -- `GLASSING`'s own shape,
    unchanged. `[[BL-B64]]` Stage 2's `SIGHTING` branch passes `state.
    look_started_sim`/`SIGHT_MAX_DWELL_S` instead, because for `SIGHTING`
    `phase_started_sim` tracks the *whole dwell* since entering the sight,
    not this one look's own clock (`OpticState.look_started_sim`'s own
    docstring).
    """
    look_started_sim = (
        started_sim if started_sim is not None else state.phase_started_sim
    )
    if look_started_sim is None or now_sim - look_started_sim >= max_dwell_s:
        return True
    return not any(
        _target_in_current_look(state, target) and can_still_improve(target)
        for target in targets
    )


def _target_in_current_look(state: OpticState, target: LookTarget) -> bool:
    """Whether `target` is inside the current look's sweep envelope --
    within `state.look_envelope_half_width_deg` of
    `state.look_envelope_azimuth_deg`, at the current look elevation
    (constant across a sweep, see `look_sweep`'s docstring). Falls back to
    the binocular field of view when no envelope is recorded (a search
    phase, or a state built without one), which reproduces the pre-sweep
    behaviour exactly."""
    if state.look_elevation_deg is None:
        return False
    centre_azimuth = state.look_envelope_azimuth_deg
    if centre_azimuth is None:
        centre_azimuth = state.look_azimuth_deg
    if centre_azimuth is None:
        return False
    half_angle = state.look_envelope_half_width_deg
    if half_angle is None:
        half_angle = BINOCULAR_OPTIC.fov_half_angle_deg
    if half_angle is None:  # pragma: no cover -- binoculars always have one
        return True
    centre = LookTarget(
        contact_id="",
        azimuth_deg=centre_azimuth,
        elevation_deg=state.look_elevation_deg,
        range_m=0.0,
        object_type="",
        current_level="unknown",
    )
    return _angular_separation_deg(centre, target) <= half_angle


#: `home_phase -> the optic it rests on` -- `SCANNING` rests naked-eye,
#: `SIGHTING` rests wide-sight (direction §8's wide/narrow axis mirrors
#: naked-eye/binocular: wide is the broad, idle-dwell setting; narrow is
#: reserved for an active look, same role `BINOCULAR_OPTIC` plays for
#: `GLASSING`). Keyed by the enum rather than an `if`/`elif` chain so a
#: third home phase (none planned) could not silently fall through to the
#: wrong optic.
_HOME_OPTIC: Final[dict[OpticPhase, Optic]] = {
    OpticPhase.SCANNING: UNAIDED_OPTIC,
    OpticPhase.SIGHTING: SIGHT_WIDE_OPTIC,
}


def _back_to_home(
    state: OpticState, now_sim: float
) -> tuple[OpticState, OpticDecision]:
    """End whatever glass/sight phase was running and hand back to
    `state.home_phase` -- `SCANNING` unless OBSERV is on (`BL-B64` Stage 2,
    plan §13), in which case `SIGHTING`.

    **Also drops `pending_attempted_at_range_m`** (Stage 2, Fix B1): any
    attempt marks a look-in-progress had not yet committed are discarded
    here, never carried into the next look -- this is what makes an
    interruption (`not steady`, or `lower_binoculars`, both of which reach
    this function without ever committing the pending map first) leave the
    interrupted contact immediately eligible again, instead of burning the
    retry budget for dwell it never delivered. `attempted_at_range_m`/
    `attempted_at_time_sim` (the *committed* marks) are untouched -- not
    named in `replace` below, so they carry through from `state` exactly as
    a natural look-end's caller already merged them in before calling this
    function.

    **Renamed from `_back_to_home`** (`BL-B64` Stage 2) -- the
    destination is no longer always `SCANNING`, so the old name would
    silently lie the day `home_phase` differs. Every pre-existing call
    site reached only `SCANNING` before this change and still does
    whenever `home_phase` holds its default; this is the generalisation
    that makes the OBSERV-off path provably unchanged (§13's own claim)."""
    return (
        replace(
            state,
            phase=state.home_phase,
            phase_started_sim=now_sim,
            look_azimuth_deg=None,
            look_elevation_deg=None,
            search_pattern_steps=(),
            search_step_index=0,
            look_envelope_azimuth_deg=None,
            look_envelope_half_width_deg=None,
            pending_attempted_at_range_m={},
            look_contact_id=None,
            look_started_sim=None,
        ),
        OpticDecision(optic=_HOME_OPTIC[state.home_phase]),
    )


def _start_glance_away(
    state: OpticState, now_sim: float
) -> tuple[OpticState, OpticDecision]:
    """Force the brief naked-eye glance away from the sight -- direction
    §9's inverted dwell shape (plan §13): entered from `SIGHTING` at its
    own dwell boundary (`SIGHT_MAX_DWELL_S`), exactly as `GLASSING` is
    entered from `SCANNING` at a scan boundary today, with the roles of
    "home" and "the bounded interruption" swapped (`OpticState.
    home_phase`). `home_phase` itself is left at `SIGHTING` -- this is a
    scheduled break *within* OBSERV staying on, not OBSERV turning off
    (that is `_force_observ_off`, a manoeuvre-only path).

    Drops any in-progress pending look the same way `_back_to_home` does
    on an interruption -- the look did not reach its own natural end."""
    return (
        replace(
            state,
            phase=OpticPhase.SCANNING,
            phase_started_sim=now_sim,
            look_azimuth_deg=None,
            look_elevation_deg=None,
            look_envelope_azimuth_deg=None,
            look_envelope_half_width_deg=None,
            pending_attempted_at_range_m={},
            look_contact_id=None,
            look_started_sim=None,
        ),
        OpticDecision(optic=UNAIDED_OPTIC),
    )


def _force_observ_off(
    state: OpticState, now_sim: float
) -> tuple[OpticState, OpticDecision]:
    """Violent manoeuvre forces OBSERV off entirely -- direction §8
    (*"Gyros are sensitive to violent manouvres and OBSERV must be
    swithced OFF is pilot manouvres violently"*), plan §13. Unlike
    `_start_glance_away` (a scheduled break, OBSERV stays on), this drops
    `home_phase` back to `SCANNING` -- the standing mode itself ends, not
    just the current dwell, same as the pilot commanding "Observ off"
    (`logger.py`'s poll loop sets `home_phase` the same way; this is the
    one path that does it from inside `decide` itself, because a violated
    rate limit is read every poll, not dispatched as a command)."""
    state_with_mode_off = replace(state, home_phase=OpticPhase.SCANNING)
    return _back_to_home(state_with_mode_off, now_sim)


def lower_binoculars(state: OpticState, now_sim: float) -> OpticState:
    """Put them down now, whatever the cycle was doing.

    Called when the player issues any command (user: *"new command from
    player lowers binoculars"*) -- not per command type: the pilot asking
    for something is itself evidence that what Petrovich is doing matters
    less than what was just asked for.

    **Must not drop OBSERV** (`BL-B64` Stage 2, plan §13a's first named
    trap). §6 makes OBSERV a *pilot-commanded standing mode*, distinct from
    the current dwell this function ends -- so this generalises to "am I
    already home" (`state.phase is state.home_phase`) rather than hardcoding
    `SCANNING`, and `_back_to_home` (which this calls) returns to `state.
    home_phase` unchanged, never to `SCANNING` unconditionally. Lowering
    binoculars while OBSERV is on and the sight is already resting idle
    (`phase is SIGHTING is home_phase`, no look chosen) is correctly a
    no-op, exactly as lowering binoculars while naked-eye scanning
    already is today.

    **One case `SCANNING`-at-home never has to handle, that `SIGHTING`-at-
    home does: an active look *within* the home phase itself.** `SCANNING`
    never sets `look_contact_id` while it is the current phase -- only
    `GLASSING`/`SEARCHING` do, and those are handled by the `else` branch
    below. `SIGHTING` is its own "closer look" (`_decide_sighting`'s own
    docstring), so a look can be in progress while `phase is home_phase`
    both hold. Lowering then drops that look back to idle, same phase,
    `home_phase` untouched -- OBSERV stays on, only the current dwell's
    look ends, same distinction §13a draws for the standing mode.
    """
    if state.phase is state.home_phase:
        if state.look_contact_id is None:
            return state
        return replace(
            state,
            look_azimuth_deg=None,
            look_elevation_deg=None,
            look_envelope_azimuth_deg=None,
            look_envelope_half_width_deg=None,
            pending_attempted_at_range_m={},
            look_contact_id=None,
            look_started_sim=None,
        )
    return _back_to_home(state, now_sim)[0]


def _decide_sighting(
    state: OpticState,
    now_sim: float,
    targets: Sequence[LookTarget],
    sight_steady: bool,
) -> tuple[OpticState, OpticDecision]:
    """`SIGHTING`'s own body -- `BL-B64` Stage 2, plan §13, direction
    §8/§9. Only ever called from `decide` while `state.phase is OpticPhase.
    SIGHTING` **and** `state.home_phase is OpticPhase.SIGHTING` -- `decide`'s
    own dispatch checks both explicitly immediately before calling this
    (`BL-B64` Stage 2 review, Pass 2 required fix), rather than assuming the
    two fields stay in agreement once `phase` has entered `SIGHTING`. Before
    that fix, a pilot's "Observ off" changed `home_phase` alone and this
    function had no way to notice, so the two could diverge and this
    docstring's claim did not hold; it is enforced now, not merely assumed.

    **Plays the role `GLASSING` plays today** -- pick a target via
    `choose_look`, sweep its believed-bearing envelope via `look_sweep`,
    using the narrow sight (the role `BINOCULAR_OPTIC` plays for
    `GLASSING`) -- **but as the home phase**: no scan boundary to wait
    for, so a target is picked the instant one is worth looking at, and
    picking the *next* target (once the current one's look reaches its
    own natural end, `look_is_finished`) does not itself end the dwell --
    only `SIGHT_MAX_DWELL_S`, the whole-dwell clock on `phase_started_sim`,
    does that (direction §9's scheduled break, `_start_glance_away`).
    `state.look_started_sim` is the separate, *per-look* clock `look_is_
    finished` needs for the natural-end check -- see that field's own
    docstring for why it must not be `phase_started_sim` here.

    Builds every return value with `replace(state, ...)`, never a fresh
    `OpticState(...)` -- unlike `GLASSING`'s entry point, which has to
    reconstruct a state from inside `decide`'s `SCANNING`-at-home body.
    That is what makes `home_phase`/`hands_busy_until_sim`/`actual_aim_*`
    carry forward automatically rather than needing the explicit
    carry-forward `decide`'s other two fresh-construction sites require."""
    if not sight_steady:
        return _force_observ_off(state, now_sim)

    dwell_started_sim = (
        state.phase_started_sim if state.phase_started_sim is not None else now_sim
    )
    if now_sim - dwell_started_sim >= SIGHT_MAX_DWELL_S:
        return _start_glance_away(state, now_sim)

    if state.look_contact_id is not None and look_is_finished(
        state,
        now_sim,
        targets,
        started_sim=state.look_started_sim,
        max_dwell_s=SIGHT_MAX_DWELL_S,
    ):
        # The current look's own natural end (recognition succeeded,
        # nothing left to learn in its envelope) -- commit its pending
        # marks, same shape as GLASSING's natural end, then fall through
        # below to pick the next target immediately. Only the scheduled
        # break above ends the dwell itself.
        committed_range = dict(state.attempted_at_range_m)
        committed_time = dict(state.attempted_at_time_sim)
        for contact_id, attempted_range_m in state.pending_attempted_at_range_m.items():
            committed_range[contact_id] = attempted_range_m
            committed_time[contact_id] = now_sim
        state = replace(
            state,
            attempted_at_range_m=committed_range,
            attempted_at_time_sim=committed_time,
            pending_attempted_at_range_m={},
            look_contact_id=None,
            look_envelope_azimuth_deg=None,
            look_envelope_half_width_deg=None,
            look_azimuth_deg=None,
            look_elevation_deg=None,
            look_started_sim=None,
        )

    if state.look_contact_id is not None and state.look_started_sim is not None:
        # Still mid-look (not finished -- the block above would have
        # cleared `look_contact_id` otherwise): continue the existing
        # sweep without re-selecting. **Must not re-run `is_worth_a_look`
        # on this contact first** -- it is already in `pending_attempted_
        # at_range_m` (it was marked the moment this look started, exactly
        # as `GLASSING`'s own look does), so `is_worth_a_look` would read
        # that as "a look already in progress... not worth *starting a
        # second* one" (that function's own docstring) and exclude it,
        # which would make every look vanish after its first poll. Step-
        # indexed exactly as `decide`'s own `GLASSING` branch, against
        # `SIGHT_MAX_DWELL_S` in place of `MAX_LOOK_S` and `look_started_
        # sim` in place of `phase_started_sim` (this look's own clock, not
        # the whole dwell's).
        step_count = len(state.search_pattern_steps)
        if step_count > 0:
            step_s = SIGHT_MAX_DWELL_S / step_count
            elapsed = now_sim - state.look_started_sim
            index = min(int(elapsed // step_s), step_count - 1)
            azimuth, elevation = state.search_pattern_steps[index]
        else:  # pragma: no cover -- a look always has at least one step
            index = state.search_step_index
            azimuth = state.look_azimuth_deg or 0.0
            elevation = state.look_elevation_deg or 0.0
        return (
            replace(
                state,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
                search_step_index=index,
            ),
            OpticDecision(
                optic=SIGHT_NARROW_OPTIC,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
            ),
        )

    # `BL-B64` security finding (`plans/9k113-sight/security.md`, required
    # fix 1): a target outside the sight's own field of regard is excluded
    # from the candidate list before `choose_look` ever sees it -- rejected,
    # not clamped (`within_field_of_regard`'s own docstring has the
    # attribution argument against clamping). `SIGHT_WIDE_OPTIC`'s
    # `regard_*` fields are read rather than `SIGHT_NARROW_OPTIC`'s only
    # because one has to be named and the two are identical (`optics.py`'s
    # own docstring: "both settings share one sight head, so what angles it
    # can be pointed to does not depend on which magnification is
    # selected").
    worth_looking = [
        target
        for target in targets
        if is_worth_a_look(target, state, now_sim)
        and within_field_of_regard(
            SIGHT_WIDE_OPTIC, target.azimuth_deg, target.elevation_deg
        )
    ]
    chosen = choose_look(worth_looking)
    if chosen is None:
        # Nothing worth a closer look: rest wide, pointed ahead -- the
        # sight's own idle state, the role `UNAIDED_OPTIC` plays for
        # `SCANNING`-at-home.
        return (
            replace(
                state,
                look_azimuth_deg=None,
                look_elevation_deg=None,
                look_envelope_azimuth_deg=None,
                look_envelope_half_width_deg=None,
                look_contact_id=None,
                look_started_sim=None,
            ),
            OpticDecision(optic=SIGHT_WIDE_OPTIC),
        )

    # Starting a new look at the chosen target -- same shape as `decide`'s
    # own SCANNING-at-home body entering `GLASSING`, swept against the
    # narrow sight's own field of view rather than the binoculars'.
    #
    # `regard_optic=SIGHT_WIDE_OPTIC` truncates the sweep at the mount's
    # own field of regard (`look_sweep`'s own docstring has the full
    # reasoning) -- `chosen` already passed `within_field_of_regard` above,
    # but the sweep built *around* it can still reach past the boundary on
    # a wide-uncertainty contact close to the edge. `SIGHT_WIDE_OPTIC` is
    # read for the same reason the candidate filter above reads it: one
    # optic has to be named and the two sight optics' `regard_*` fields are
    # identical.
    fov_full_width_deg = (SIGHT_NARROW_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    sweep = look_sweep(
        centre_azimuth_deg=chosen.azimuth_deg,
        centre_elevation_deg=chosen.elevation_deg,
        bearing_uncertainty_deg=chosen.bearing_uncertainty_deg,
        fov_full_width_deg=fov_full_width_deg,
        regard_optic=SIGHT_WIDE_OPTIC,
    )
    envelope_half_width = max(chosen.bearing_uncertainty_deg, 0.0)

    pending = dict(state.pending_attempted_at_range_m)
    for target in worth_looking:
        if _angular_separation_deg(chosen, target) <= envelope_half_width:
            pending[target.contact_id] = target.range_m

    first_azimuth, first_elevation = sweep[0]
    new_state = replace(
        state,
        look_azimuth_deg=first_azimuth,
        look_elevation_deg=first_elevation,
        search_pattern_steps=tuple(sweep),
        search_step_index=0,
        look_envelope_azimuth_deg=chosen.azimuth_deg,
        look_envelope_half_width_deg=envelope_half_width,
        pending_attempted_at_range_m=pending,
        look_contact_id=chosen.contact_id,
        look_started_sim=now_sim,
    )
    return (
        new_state,
        OpticDecision(
            optic=SIGHT_NARROW_OPTIC,
            look_azimuth_deg=first_azimuth,
            look_elevation_deg=first_elevation,
        ),
    )


def decide(
    state: OpticState,
    *,
    now_sim: float,
    scan_cycle_period_s: float,
    targets: Sequence[LookTarget],
    steady: bool,
    search: Sequence[tuple[float, float]] = (),
    sight_steady: bool = True,
) -> tuple[OpticState, OpticDecision]:
    """Advance the cycle one poll and say what to look through.

    `search` is the sweep to run when there is nothing worth a closer look
    -- empty when the active scan is free or its sector is too wide to
    sweep (Stage 3). **Identification takes priority over search**: a
    contact already detected and resolvable is worth more than looking for
    another one, and the user's own sequencing says so (*"detected targets
    then get the dwell behaviour"*).

    Pure: same inputs, same outputs, no clock read and no store access --
    which is what keeps a replay identical, the property `gaze_at` was
    built around and this has to preserve.

    `sight_steady` (`BL-B64` Stage 2, direction §8) defaults to `True` --
    a true no-op for every pre-existing caller, exactly like `group_
    salient`/`forest` elsewhere in this codebase. It is `steady`'s sibling
    at the sight's own, higher rate limit (`SIGHT_STEADY_RATE_LIMIT_DEG_S`)
    -- `logger.py`'s poll loop calls `is_steady` twice per poll, once per
    threshold, and only the `SIGHTING` branch below ever reads this one.
    `steady` itself is unaffected: `GLASSING`/`SEARCHING` still gate on the
    binocular threshold exactly as before, since neither is reachable
    while `home_phase is SIGHTING` (the trigger that would enter them --
    `choose_look` succeeding inside the `SCANNING`-at-home body -- only
    runs when `home_phase is SCANNING`).

    **OBSERV-off is bit-identical by construction**: every branch below
    that is new (the hands-busy check, the `SIGHTING` phase, the
    glance-away sub-state of `SCANNING`) is reached only when `state.
    home_phase is OpticPhase.SIGHTING` or `state.hands_busy_until_sim` is
    set -- neither of which any pre-existing caller, or the dataclass
    default, ever produces."""
    if state.phase_started_sim is None:
        # First poll: start the cycle from this mission's own clock rather
        # than from zero, and scan before deciding anything. Home-aware
        # (`_HOME_OPTIC`) rather than hardcoding `UNAIDED_OPTIC` --
        # resolves to the same value as before whenever `home_phase` holds
        # its default (`SCANNING`), which is every pre-existing caller.
        return (
            replace(state, phase_started_sim=now_sim),
            OpticDecision(optic=_HOME_OPTIC[state.home_phase]),
        )

    if state.hands_busy_until_sim is not None and now_sim < state.hands_busy_until_sim:
        # The 1 s hand movement (`BL-B64` Stage 2, direction §6) -- no
        # phase advances, no look is picked, and the caller
        # (`logger._apply_active_gaze`) suppresses every optic's
        # observations for this poll. `None` on every pre-existing
        # `OpticState`, so this branch is unreachable before this entry.
        return state, OpticDecision(optic=UNAIDED_OPTIC, suppressed=True)

    if state.phase is OpticPhase.SEARCHING:
        if not steady:
            return _back_to_home(state, now_sim)
        elapsed = now_sim - state.phase_started_sim
        index = int(elapsed // SEARCH_STEP_S)
        if index >= len(state.search_pattern_steps):
            return _back_to_home(state, now_sim)
        azimuth, elevation = state.search_pattern_steps[index]
        return (
            replace(state, search_step_index=index),
            OpticDecision(
                optic=BINOCULAR_OPTIC,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
            ),
        )
    if state.phase is OpticPhase.GLASSING:
        if not steady:
            # Interrupted (manoeuvring, or `lower_binoculars` reaching here
            # from outside `decide` entirely): the look did not run to its
            # own natural end, so it never delivered the benefit the
            # attempted-marking rule presupposes. `_back_to_home` drops
            # `pending_attempted_at_range_m` without ever merging it into
            # the committed map (Stage 2, Fix B1) -- the interrupted
            # contact is immediately eligible for a new look again.
            return _back_to_home(state, now_sim)
        if look_is_finished(state, now_sim, targets):
            # Natural end (recognition succeeded, nothing left to learn, or
            # MAX_LOOK_S expired): the look ran and delivered its benefit,
            # so its pending marks are committed -- merged into the
            # *committed* maps first, then handed to `_back_to_home`,
            # which only ever drops the *pending* one.
            committed_range = dict(state.attempted_at_range_m)
            committed_time = dict(state.attempted_at_time_sim)
            for (
                contact_id,
                attempted_range_m,
            ) in state.pending_attempted_at_range_m.items():
                committed_range[contact_id] = attempted_range_m
                committed_time[contact_id] = now_sim
            return _back_to_home(
                replace(
                    state,
                    attempted_at_range_m=committed_range,
                    attempted_at_time_sim=committed_time,
                ),
                now_sim,
            )
        # Step-indexed exactly as `SEARCHING` above: `step_s` is derived
        # from the sweep's own step count rather than a new constant
        # (`plans/binocular-optic/stage3b.md` D3), so a sweep running out
        # of steps and `MAX_LOOK_S` expiring are the same event -- `N = 1`
        # (today's stare) gives `step_s == MAX_LOOK_S`, unchanged.
        step_count = len(state.search_pattern_steps)
        if step_count > 0:
            step_s = MAX_LOOK_S / step_count
            elapsed = now_sim - state.phase_started_sim
            index = min(int(elapsed // step_s), step_count - 1)
            azimuth, elevation = state.search_pattern_steps[index]
        else:  # pragma: no cover -- a look always has at least one step
            index = state.search_step_index
            azimuth = state.look_azimuth_deg or 0.0
            elevation = state.look_elevation_deg or 0.0
        return (
            replace(
                state,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
                search_step_index=index,
            ),
            OpticDecision(
                optic=BINOCULAR_OPTIC,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
            ),
        )

    if state.phase is OpticPhase.SIGHTING:
        if state.home_phase is not OpticPhase.SIGHTING:
            # A pilot's "Observ off" (`logger.py`'s poll loop) drains into
            # `home_phase` alone, one poll lagged, the same shape `_force_
            # observ_off` already uses in the other direction (a violated
            # `sight_steady`). Nothing inside `_decide_sighting` ever reads
            # `home_phase`, so without this check a command-driven change
            # would be invisible until the sight's own internal stop
            # conditions fired (`SIGHT_MAX_DWELL_S`, or an unsteady poll) --
            # up to `SIGHT_MAX_DWELL_S` of the sight, the cone, and any
            # look in progress continuing to run under a readback that
            # already said "Observ off" (`BL-B64` Stage 2 review, Pass 2
            # required fix). `_back_to_home` both ends the dwell at the
            # very next poll and drops any pending look the same way every
            # other interruption on this phase already does (`not steady`,
            # `lower_binoculars`) -- this is not a new mechanism, it is the
            # existing interruption path reached from a third trigger.
            return _back_to_home(state, now_sim)
        return _decide_sighting(state, now_sim, targets, sight_steady)

    # state.phase must be SCANNING here (the only phase not already
    # dispatched above). Whether this is the *home* phase or the sight's
    # own bounded glance-away interruption (direction §9, plan §13)
    # depends entirely on `home_phase` -- `SCANNING is state.home_phase`
    # for every pre-existing caller, which is exactly the branch
    # unchanged below.
    if state.home_phase is OpticPhase.SIGHTING:
        # The brief naked-eye glance away from the sight -- entered by
        # `_start_glance_away`, left again after `SIGHT_GLANCE_AWAY_S`
        # (or sooner, nothing here checks `steady`: a manoeuvre violent
        # enough to matter is caught by `sight_steady` inside `_decide_
        # sighting`, which this glance will return to).
        elapsed = now_sim - state.phase_started_sim
        if elapsed >= SIGHT_GLANCE_AWAY_S:
            return _back_to_home(state, now_sim)
        return state, OpticDecision(optic=UNAIDED_OPTIC)

    # Scanning-at-home (`home_phase is SCANNING`). A look can only start
    # at a completed scan cycle -- this is the lockout, and it is a
    # structural property rather than a rule.
    scan_complete = now_sim - state.phase_started_sim >= scan_cycle_period_s
    if not scan_complete or not steady:
        return state, OpticDecision(optic=UNAIDED_OPTIC)

    worth_looking = [
        target for target in targets if is_worth_a_look(target, state, now_sim)
    ]
    chosen = choose_look(worth_looking)
    if chosen is None:
        if search:
            # Nothing to resolve, but a narrow sector was commanded: sweep
            # it for things the naked eye could not pick up.
            azimuth, elevation = search[0]
            return (
                OpticState(
                    phase=OpticPhase.SEARCHING,
                    phase_started_sim=now_sim,
                    search_pattern_steps=tuple(search),
                    attempted_at_range_m=dict(state.attempted_at_range_m),
                    attempted_at_time_sim=dict(state.attempted_at_time_sim),
                    # Not part of this phase's own bookkeeping -- carried
                    # forward explicitly (`OpticState.actual_aim_azimuth_
                    # deg`'s own docstring) rather than reset, since a
                    # fresh `OpticState(...)` here (not `replace`) would
                    # otherwise drop them. `home_phase`/`hands_busy_until_
                    # sim` too, same reason -- this branch is only ever
                    # reached with `home_phase is SCANNING` (`decide`'s own
                    # dispatch above), so this is a no-op in value, but the
                    # *rule* ("every fresh `OpticState(...)` construction
                    # must carry these forward explicitly") is what `BL-B64`
                    # Stage 1's own review flagged as the real trap here.
                    actual_aim_azimuth_deg=state.actual_aim_azimuth_deg,
                    actual_aim_elevation_deg=state.actual_aim_elevation_deg,
                    home_phase=state.home_phase,
                    hands_busy_until_sim=state.hands_busy_until_sim,
                ),
                OpticDecision(
                    optic=BINOCULAR_OPTIC,
                    look_azimuth_deg=azimuth,
                    look_elevation_deg=elevation,
                ),
            )
        # Nothing to look at: the scan cycle restarts rather than the
        # aircraft waiting in a completed phase forever.
        return (
            replace(state, phase_started_sim=now_sim),
            OpticDecision(optic=UNAIDED_OPTIC),
        )

    # The look sweeps the believed bearing's own angular uncertainty
    # rather than staring at its centre (`plans/binocular-optic/
    # stage3b.md`). The attempted-range marking widens to match: the
    # sweep will visit the whole envelope, so every target in it gets the
    # look's benefit and must bear the retry rule, or a contact the sweep
    # only reaches on a later step would never be marked and would
    # re-trigger a look immediately.
    fov_full_width_deg = (BINOCULAR_OPTIC.fov_half_angle_deg or 0.0) * 2.0
    sweep = look_sweep(
        centre_azimuth_deg=chosen.azimuth_deg,
        centre_elevation_deg=chosen.elevation_deg,
        bearing_uncertainty_deg=chosen.bearing_uncertainty_deg,
        fov_full_width_deg=fov_full_width_deg,
    )
    envelope_half_width = max(chosen.bearing_uncertainty_deg, 0.0)

    # Stage 2 (Fix B1): every contact this look covers goes into the
    # *pending* map, not the committed one -- the look has not yet
    # delivered any benefit, only started. `decide`'s own GLASSING branch
    # above is what commits (on `look_is_finished`) or drops (on `not
    # steady`) these marks; `lower_binoculars` reaches the same drop path.
    pending = dict(state.pending_attempted_at_range_m)
    for target in worth_looking:
        if _angular_separation_deg(chosen, target) <= envelope_half_width:
            # Every contact this look covers counts as attempted, not just
            # the one it was centred on -- they all get the benefit, so
            # they all bear the retry rule.
            pending[target.contact_id] = target.range_m

    first_azimuth, first_elevation = sweep[0]
    return (
        OpticState(
            phase=OpticPhase.GLASSING,
            phase_started_sim=now_sim,
            look_azimuth_deg=first_azimuth,
            look_elevation_deg=first_elevation,
            search_pattern_steps=tuple(sweep),
            search_step_index=0,
            look_envelope_azimuth_deg=chosen.azimuth_deg,
            look_envelope_half_width_deg=envelope_half_width,
            attempted_at_range_m=dict(state.attempted_at_range_m),
            pending_attempted_at_range_m=pending,
            attempted_at_time_sim=dict(state.attempted_at_time_sim),
            look_contact_id=chosen.contact_id,
            # Carried forward explicitly, same reason as the SEARCHING
            # branch above.
            actual_aim_azimuth_deg=state.actual_aim_azimuth_deg,
            actual_aim_elevation_deg=state.actual_aim_elevation_deg,
            home_phase=state.home_phase,
            hands_busy_until_sim=state.hands_busy_until_sim,
        ),
        OpticDecision(
            optic=BINOCULAR_OPTIC,
            look_azimuth_deg=first_azimuth,
            look_elevation_deg=first_elevation,
        ),
    )


def look_target_for(
    contact_id: str,
    *,
    observer: GeoPosition,
    target_position: GeoPosition,
    heading_true_deg: float,
    object_type: str,
    current_level: str,
    position: PositionEstimate | None = None,
    watched: bool = False,
) -> LookTarget:
    """Build a `LookTarget` from a contact's believed position.

    Lives here rather than in the caller so the azimuth/elevation
    convention is stated once: body-relative azimuth (0 dead ahead,
    positive clockwise) and elevation positive up, the same frame
    `within_optic_fov` tests in.

    `position` (`plans/precise-position-belief/plan.md` Stage 5, `Contact.
    position` -- the fused `belief.position_belief.PositionEstimate`) is
    optional and keyword-only, kept separate from `target_position` rather
    than replacing it: `target_position` is *always* needed (it is what the
    azimuth/elevation/range below are computed from -- `Contact.
    last_position`, which already reads `position`'s mean under the hood),
    while `position`'s own covariance is only needed for the sweep width.
    When supplied, `LookTarget.bearing_uncertainty_deg` becomes
    `LOOK_SWEEP_SIGMA * position.bearing_uncertainty_deg(observer)` -- a
    real, measured sweep width instead of the fixed clock-bucket half-width
    default (see that field's own docstring). `None` (the default) leaves
    `LookTarget`'s own default untouched, for any caller with no
    `PositionEstimate` to hand.
    """
    true_bearing = bearing_deg(observer, target_position)
    slant_m = range_m(observer, target_position)
    azimuth = (true_bearing - heading_true_deg + 540.0) % 360.0 - 180.0
    height_delta = target_position.alt_m - observer.alt_m
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, height_delta / slant_m))))
    kwargs: dict[str, float] = {}
    if position is not None:
        kwargs["bearing_uncertainty_deg"] = (
            LOOK_SWEEP_SIGMA * position.bearing_uncertainty_deg(observer)
        )
    return LookTarget(
        contact_id=contact_id,
        azimuth_deg=azimuth,
        elevation_deg=elevation,
        range_m=slant_m,
        object_type=object_type,
        current_level=current_level,
        watched=watched,
        **kwargs,
    )
