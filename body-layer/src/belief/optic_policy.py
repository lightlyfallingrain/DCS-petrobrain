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
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from itertools import pairwise
from typing import Final, Literal

import tuning
from belief.enrichment import CLOCK_BUCKET_DEG
from belief.position_belief import PositionEstimate
from perception.gaze import SCAN_CYCLE_PERIOD_S
from perception.geometry import GeoPosition, body_relative_direction, range_m
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

#: How long a contact must wait, once a sight look at it has ended without
#: advancing its classification tier, before the sight is willing to look
#: at it again -- too low and a stalled contact can still nearly
#: monopolise the sight as before, too high and one stalled for a merely
#: transient reason is abandoned for unreasonably long; the default is
#: about two laps of the search cycle (`BL-B85`). The user's own words:
#: *"we can't just indefinately look at one thing. Needs a timer value or
#: the like that forces moving on"* (`docs/acceptance/
#: 2026-10-20-sortie-feedback.md` F4). Measured empirically: a contact
#: whose classification never advances past `presence` is re-admitted by
#: `OPTIC_RETRY_INTERVAL_S` alone every retry interval regardless of
#: whether the previous look taught anything, and with several such
#: contacts in regard the sight never reaches an idle poll at all
#: (`plans/9k113-narrow-search/review.md`'s 900 s/three-contact
#: reproduction: busy 792/900 polls, `sight_search_leg` never advancing
#: past `"wide"`). **Extends `is_worth_a_look`'s existing time-based
#: re-eligibility, not a second mechanism**: when a contact's
#: classification level is unchanged since its last committed attempt
#: (`OpticState.attempted_at_level`), this cooldown applies in place of
#: the shorter `OPTIC_RETRY_INTERVAL_S` -- `RETRY_RANGE_FRACTION`'s
#: range-based escape (a contact that has genuinely closed) is untouched
#: either way, so a contact that is merely stuck at long, constant range
#: still gives way, while one actually closing on the aircraft is retried
#: as before. **Sight-only.** Only `_decide_sighting`'s own candidate
#: filter passes this; `GLASSING`'s call to `is_worth_a_look` does not, so
#: a stalled contact under binoculars keeps the pre-existing `OPTIC_
#: RETRY_INTERVAL_S` behaviour unchanged -- a mid-range contact stuck at
#: `presence` inside the binocular window could already starve `GLASSING`
#: the same way before this feature shipped (`BL-B85.md`), and extending
#: the same cooldown to it would be a `GLASSING` behaviour change beyond
#: what this fix was asked for; filed as a backlog note rather than built
#: here. Picked as roughly two of the search cycle's own full laps (`wide
#: -> narrow_near -> narrow_far`), measured at ~66 s each in the review's
#: realistic-case run -- long enough that the search cycle and other
#: contacts get real time back, short enough that a contact stalled for an
#: unrelated, transient reason is retried well inside a typical encounter.
#: A starting value to tune against a flown sortie, same footing as
#: `OPTIC_RETRY_INTERVAL_S` was when it shipped.
SIGHT_STALL_COOLDOWN_S: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_STALL_COOLDOWN_S",
    132.0,
    lo=30.0,
    hi=400.0,
    status="judgement",
)

# `is_worth_a_look`'s `stall_cooldown_s` branch only applies when it is
# actually longer than the fast path it replaces -- `OPTIC_RETRY_INTERVAL_S`
# is not itself a `tuning.real` (it is derived at import from
# `FOCUS_DWELL_S`/`SCAN_PLAN`, both independently tunable), so nothing in
# either constant's own `lo`/`hi` bounds catches a retuning that pushes
# `OPTIC_RETRY_INTERVAL_S` above `SIGHT_STALL_COOLDOWN_S`'s low end.
# `plans/9k113-narrow-search/review.md`'s "Review -- F5 boresight + BL-B85
# refinement" found this coupling was previously guarded by a bare
# `assert` here -- reachable by a single, realistic, in-bounds
# `SIGHT_STALL_COOLDOWN_S` override (e.g. 40.0, comfortably inside its own
# declared `lo=30.0, hi=400.0`) -- which crashed the whole process at
# import, violating this project's own tuning policy ("a bad value warns
# and continues on the code default -- it never refuses to start",
# `body-layer/CLAUDE.md`'s "Tuning"). Floor the effective cooldown instead
# of asserting the inversion can't happen: a stalled contact then never
# waits *less* than the ordinary retry interval, whatever either constant
# is tuned to. No startup warning on an inversion, deliberately: the only
# once-only startup-warning mechanism this module has is `tuning.py`'s
# `_check_scan_decay_coupling`, a named check wired into its own registry
# of `RejectedEntry`/`AppliedEntry` state -- there is no standalone
# print-once helper to reuse without building a second instance of that
# same machinery, which this fix was explicitly asked not to do for this
# pair. The floor also makes a warning less necessary than it would be
# for `decay.py`'s own coupling: there, a bad combination is silently
# *rejected back to defaults*, which is worth announcing; here, a bad
# combination is silently *widened to a safe value*, which is its own
# intended behaviour, not a rejection.
_EFFECTIVE_SIGHT_STALL_COOLDOWN_S: Final[float] = max(
    SIGHT_STALL_COOLDOWN_S, OPTIC_RETRY_INTERVAL_S
)

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

#: The near/mid/far band edges the sight's own search cycle sweeps --
#: `plans/9k113-narrow-search/plan.md` Stage 3, amendment 2 ("narrow
#: searches both bands, near first"). **Keep in sync with `logger.
#: _SEARCH_BAND_M`, which independently owns the same two edges for the
#: binocular search** -- the two tunable sets happen to share today's
#: defaults (`SIGHT_SEARCH_NEAR_M`/`_SEARCH_BAND_M[0]`,
#: `SIGHT_SEARCH_MID_M`/`_SEARCH_BAND_M[1]`) but are declared independently
#: on purpose, by value not by import, since one answers "where does the
#: naked eye's/binoculars' own reach end" and the other "where does the
#: sight's own wide/narrow split fall" -- two different questions that
#: happen to agree today, not one constant wearing two names.
#:
#: **Known residual coupling, not caught by per-key bounds** (the same
#: shape as `belief.decay`'s documented `OBSERVED_WINDOW_S <
#: POSITION_HALF_LIFE_S` coupling, `body-layer/CLAUDE.md` "Tuning"):
#: nothing stops `SIGHT_SEARCH_NEAR_M` being tuned above `SIGHT_SEARCH_
#: MID_M`, or `SIGHT_SEARCH_MID_M` above `SIGHT_SEARCH_FAR_M`,
#: independently within each one's own declared bounds. Single-key tuning
#: is safe; tuning more than one of these three together is not protected.
#:
#: Where the naked eye's own reach ends -- the wide leg's own near edge,
#: and (amendment 2) the near edge of narrow's own first ("near first")
#: band too.
SIGHT_SEARCH_NEAR_M: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_SEARCH_NEAR_M",
    2_333.0,
    lo=1_000.0,
    hi=4_000.0,
    status="judgement",
)

#: Where binoculars' own reach ends -- the wide/narrow-near band's own far
#: edge, and the far/near boundary between narrow's two bands (amendment
#: 2: narrow covers both the 2.3-5.6 km band and the 5.6-13.6 km band,
#: near first).
SIGHT_SEARCH_MID_M: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_SEARCH_MID_M",
    5_647.0,
    lo=4_000.0,
    hi=10_000.0,
    status="judgement",
)

#: The sight narrow setting's own presence reach (`2333 * 5.81`,
#: `plans/9k113-sight/plan.md` §17) -- the far band's own far edge, and the
#: whole search cycle's outer limit.
SIGHT_SEARCH_FAR_M: Final[float] = tuning.real(
    "belief.optic_policy.SIGHT_SEARCH_FAR_M",
    13_556.0,
    lo=8_000.0,
    hi=20_000.0,
    status="judgement",
)

#: BL-B71's de-escalation-only hysteresis band (plan §7's "a ladder that
#: thrashes at the boundary would be worse than one that never
#: de-escalates at all") -- a *fraction* of the lower rung's own presence
#: threshold, not a fixed metre band, because the ladder's rungs are
#: 2.42x apart (`presence_range_mult`), so a fixed band would be enormous
#: at the naked-eye rung and negligible at the sight's, and
#: `GUIDANCE_OPTIC_MIN_INTERVAL_S` must exceed the time this band buys
#: (~10 s of closing at 0.25) or a fly-past re-crosses it early, so the two
#: are retuned together. Escalation has no
#: band at all (plan: "Escalate when range_m > threshold(current)") --
#: only stepping *down* to a less capable optic waits for this margin.
#: Sized against the sorties' own measured closing rate (median 60 m/s):
#: 0.25 gives a ~583 m band at the naked-eye rung, about 10 s of closing,
#: which is what `GUIDANCE_OPTIC_MIN_INTERVAL_S` below must then exceed
#: against the worst observed *reversal* rate (+130 m/s) to stop a
#: fly-past re-crossing it before the minimum interval has elapsed. An
#: `agreed-guess` like every uncalibrated perception constant before its
#: first sortie.
GUIDANCE_OPTIC_HYSTERESIS_FRACTION: Final[float] = tuning.real(
    "belief.optic_policy.GUIDANCE_OPTIC_HYSTERESIS_FRACTION",
    0.25,
    lo=0.05,
    hi=0.9,
    status="agreed-guess",
)

#: BL-B71 guard 3: the shortest time between two guidance-optic grants,
#: clocked by `OpticState.guidance_optic_since_sim` -- must stay above
#: `HANDS_BUSY_DURATION_S` (tuning it below that makes a grant
#: re-chargeable before the previous charge even finishes) and must
#: also exceed the ~4.5 s a fly-past needs to re-cross `GUIDANCE_OPTIC_
#: HYSTERESIS_FRACTION`'s own band at the worst observed reversal rate
#: (+130 m/s) -- 10.0 s bounds the worst case to one 1 s blind interval
#: per 10 s (10% duty). Not derived from `HANDS_BUSY_DURATION_S` directly
#: (that bound must stay an AST-literal for `tools/generate_defaults.py`
#: to read it, and the two are independently tunable regardless), so the
#: coupling above is a tuning caution, not an enforced invariant -- the
#: declared bounds (this constant's `lo=1.0`, `HANDS_BUSY_DURATION_S`'s
#: `hi=5.0`) do permit violating it at the extremes; no cross-key check
#: guards it, same posture as `belief.decay.py`'s own residual coupling
#: note in `body-layer/CLAUDE.md`'s "Tuning" section. An `agreed-guess`
#: like `GUIDANCE_OPTIC_HYSTERESIS_FRACTION` above.
GUIDANCE_OPTIC_MIN_INTERVAL_S: Final[float] = tuning.real(
    "belief.optic_policy.GUIDANCE_OPTIC_MIN_INTERVAL_S",
    10.0,
    lo=1.0,
    hi=60.0,
    status="agreed-guess",
)


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


#: Which leg of the idle sight's search cycle is current --
#: `plans/9k113-narrow-search/plan.md` Stage 3, amendment 2. A brief
#: `"wide"` orientation pass, then `"narrow_near"`/`"narrow_far"`
#: (*"narrow sweeps both bands, near first, wide only to orient"*), then a
#: `"binocular"` excursion for any out-of-regard remainder a commanded
#: sector left over (Stage 2's split). Four names, not two, because
#: amendment 2 gave narrow its own near/far split -- the original design's
#: `"narrow"` single leg no longer names one thing.
SightSearchLeg = Literal["wide", "narrow_near", "narrow_far", "binocular"]


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
    #: `BL-B85` -- `attempted_at_range_m`'s classification-level twin: the
    #: contact's `LookTarget.current_level` at the moment of the last
    #: *committed* attempt (merged from `pending_attempted_at_level` the
    #: same way, and at the same commit sites, as `attempted_at_range_m`
    #: is merged from `pending_attempted_at_range_m`). Drives `is_worth_a_
    #: look`'s `stall_cooldown_s` branch: if a fresh candidate's level
    #: still matches what is recorded here, the look that covered it last
    #: time taught nothing, and the longer `SIGHT_STALL_COOLDOWN_S`
    #: applies in place of `OPTIC_RETRY_INTERVAL_S`. Populated alongside
    #: `attempted_at_range_m` for both `GLASSING` and `SIGHTING` so the two
    #: dicts never fall out of step with each other regardless of which
    #: phase last attempted a given contact, even though only `_decide_
    #: sighting`'s candidate filter currently reads it as a cooldown.
    attempted_at_level: dict[str, str] = field(default_factory=dict)
    #: `pending_attempted_at_range_m`'s level twin, same reason
    #: `attempted_at_level` is `attempted_at_range_m`'s -- the level
    #: recorded here is the one at *look start*, so what is compared at
    #: the next candidacy check is "has this contact's level moved since
    #: the look that attempted it began", not since it ended.
    pending_attempted_at_level: dict[str, str] = field(default_factory=dict)
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
    #: Which sight setting the current look is using -- `plans/
    #: 9k113-narrow-search/plan.md` Stage 4 Part A. Set once, at look-start,
    #: to `sight_look_optic(chosen)`; read, not recomputed, at look-
    #: continuation (the look's own envelope/field of view are fixed for
    #: its whole run, same reason `look_envelope_azimuth_deg` is). **Not**
    #: `sight_search_leg` below -- a different question asked of a
    #: different activity (which sight setting resolves a specific chosen
    #: target, vs. which *search* leg is currently running); `LOOK_SWEEP_
    #: SIGMA`'s own docstring is this module's standing reminder against
    #: letting two different questions share one number. Default
    #: `SIGHT_NARROW_OPTIC` is harmless -- never read outside an active
    #: look, so a pre-existing `OpticState()` construction carries an unread
    #: value, not a wrong one.
    look_optic: Optic = SIGHT_NARROW_OPTIC
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
    #: `SIGHTING` entirely. **Doubles as the active search leg's own per-leg
    #: clock** (`plans/9k113-narrow-search/plan.md` Stage 3) -- the same
    #: field, not a second one, because a look and a search leg are never
    #: both running at once (`sight_search_leg` only advances while `chosen
    #: is None`, i.e. no look is in progress), so there is no ambiguity
    #: about whose clock this is at any given poll.
    look_started_sim: float | None = None
    #: Which leg of the idle search cycle is current -- `SightSearchLeg`'s
    #: own docstring has the cycle. Default `"wide"` is a true no-op for
    #: every pre-existing caller/test: read only inside `_decide_sighting`'s
    #: idle branch, never by `SCANNING`/`GLASSING`/`SEARCHING`-at-home,
    #: which have their own, unrelated, single-optic sweeps.
    sight_search_leg: SightSearchLeg = "wide"

    #: `BL-B71`'s standing guidance grant -- the optic `attack_run`'s
    #: request is currently overriding every other optic decision with,
    #: or `None` when no attack run is engaged (or `decide` has never
    #: granted one). **Set only by `decide`'s own `_apply_guidance` step**
    #: -- never by any of the phase-dispatch branches above, which is what
    #: makes "the 9K113 is never reached for autonomously" (`BL-B71.md`'s
    #: hard gate) checkable by reading `_apply_guidance` alone rather than
    #: auditing every call site. `None` on every pre-existing `OpticState`,
    #: so a caller that never passes `guidance_request` to `decide` never
    #: sets this -- a true no-op, same posture as `hands_busy_until_sim`.
    guidance_optic: Optic | None = None
    #: When `guidance_optic` was last (re)granted -- `BL-B71` guard 3's own
    #: clock (`GUIDANCE_OPTIC_MIN_INTERVAL_S`). `None` exactly when
    #: `guidance_optic` is `None` -- the two are set and cleared together,
    #: never independently (`_apply_guidance`'s own contract).
    guidance_optic_since_sim: float | None = None


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
    center_azimuth_deg: float = 0.0,
    max_half_width_deg: float = MAX_SEARCH_SECTOR_HALF_WIDTH_DEG,
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

    `sector_half_width_deg` is capped at `max_half_width_deg`, which
    defaults to `MAX_SEARCH_SECTOR_HALF_WIDTH_DEG` (user: *"cap binocular
    scan at 30 deg azimuth, there's no wide area binocular scan"*) -- a
    wider commanded scan is swept only across its middle, rather than
    taking a minute to cover. **`plans/9k113-narrow-search/plan.md` Stage 3
    passes the sight's own, much wider field of regard here instead** --
    the binocular cap is a UX choice about how long a sweep is worth
    taking, not a property of this function, which the sight's own search
    legs have no reason to inherit.

    `center_azimuth_deg` (Stage 2 of the same plan) shifts every generated
    azimuth by this amount -- `0.0` (the default) is a true no-op for every
    caller that predates it, including `logger._search_sweep`'s own
    unsplit, free-scan-excluded sweep. Needed once a caller sweeps a
    sub-span with a genuinely non-zero centre (the in-regard/out-of-regard
    halves a commanded sector splits into), where sweeping symmetrically
    about `0.0` regardless of the sector actually asked for would be wrong.
    """
    half_width = min(sector_half_width_deg, max_half_width_deg)
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
        pattern.extend((center_azimuth_deg + azimuth, elevation) for azimuth in sweep)
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


def sight_look_optic(target: LookTarget) -> Optic:
    """Which of the sight's two settings a look at `target` should use --
    `plans/9k113-narrow-search/plan.md` Stage 4 Part A, direction §8
    (*"wide<->narrow should use similar logic to naked eye and binocular
    usage"*) and the settled "least capable optic that suffices"
    (`docs/acceptance/2026-10-20-sortie-feedback.md`, F4/F5).

    **Not a reuse of `least_capable_sufficient_optic`/`_LADDER`** -- that
    function answers "can this instrument *see* the target at all" (a
    presence-tier threshold), a weaker bar than "does this instrument
    deliver the *specific* recognition gain this look exists for".
    Instead, this generalises `improvement_window_m`'s own pattern
    (`profile_for`/`apparent_extent_m`/`distinctiveness_of`/`tier_ranges`),
    substituting the two sight optics for `UNAIDED_OPTIC`/`BINOCULAR_OPTIC`.

    Stops at wide/narrow by design -- a caller needing the full
    eye->binocular->wide->narrow ladder still wants `least_capable_
    sufficient_optic`, not this."""
    profile = profile_for(target.object_type)
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)

    def next_tier_threshold_m(optic: Optic) -> float:
        _, class_m, type_m = tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=optic,
            distinctiveness=distinctiveness,
        )
        return type_m if target.current_level == "class" else class_m

    if target.range_m <= next_tier_threshold_m(SIGHT_WIDE_OPTIC):
        return SIGHT_WIDE_OPTIC
    return SIGHT_NARROW_OPTIC


def sight_can_still_improve(target: LookTarget) -> bool:
    """Whether the sight -- wide or narrow, whichever `sight_look_optic`
    would pick -- could still raise `target`'s tier. The `SIGHTING`
    counterpart of `can_still_improve`, which asks the same question of
    the naked eye/binoculars pair; required fix from `plans/
    9k113-narrow-search/review.md` ("the worth-a-look gate... is bound by
    the naked-eye/binocular pair, not the sight's own reach").

    **An upper-bound check against `SIGHT_NARROW_OPTIC`'s own class/type
    threshold, with no lower bound -- deliberately not `improvement_
    window_m`'s two-sided shape.** That function's lower bound exists
    because the naked eye reaches the same tier "for free" on its next
    dwell, making a binocular look below it wasted; while `SIGHTING`
    nothing dwells in parallel to resolve a close contact for free (the
    sight *is* the active instrument), so there is no equivalent
    exclusion here. Using `SIGHT_WIDE_OPTIC`'s own threshold as a lower
    bound would incorrectly exclude close targets that `sight_look_optic`
    itself still resolves with wide.
    """
    if target.current_level == "type":
        return False
    profile = profile_for(target.object_type)
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)
    _, class_m, type_m = tier_ranges(
        presence_size_m=profile.size_m,
        recognition_extent_m=extent,
        optic=SIGHT_NARROW_OPTIC,
        distinctiveness=distinctiveness,
    )
    threshold_m = type_m if target.current_level == "class" else class_m
    return target.range_m <= threshold_m


#: The ladder `BL-B71`'s guidance override walks, ascending capability --
#: `Optic.presence_range_mult` ascending *is* `fov_half_angle_deg`
#: descending across the whole shipped table (`BL-B71.md`'s own
#: derivation), so this is the existing four-optic table in presence
#: order, not a new ranking invented for this feature. A future optic
#: joins the ladder by being added here, in its own presence-ascending
#: place.
_LADDER: Final[tuple[Optic, ...]] = (
    UNAIDED_OPTIC,
    BINOCULAR_OPTIC,
    SIGHT_WIDE_OPTIC,
    SIGHT_NARROW_OPTIC,
)


def least_capable_sufficient_optic(
    range_m: float, object_type: str, *, floor: Optic, ceiling: Optic
) -> Optic:
    """The least capable optic, between `floor` and `ceiling` inclusive on
    `_LADDER`, whose own presence threshold still reaches `range_m` --
    `BL-B71`'s naive ladder lookup (`plans/attack-run-sortie-fixes/plan.md`
    §6/§7 Stage 1).

    **A sibling of `improvement_window_m` above, deliberately not a
    generalisation of it** (the plan's own framing): that function asks
    whether binoculars would raise a contact's *recognition tier*, over
    two hardcoded optics; this one asks whether the instrument in
    Petrovich's hands can *see* the thing he is guiding on at all, over
    the whole ladder -- two different questions, kept as two functions
    (`LOOK_SWEEP_SIGMA`'s own docstring is this module's standing
    reminder against letting two different questions share one number).

    **No memory of a previous grant** -- this is the naive per-tick
    answer; `guidance_request_for` below applies the de-escalation
    hysteresis on top of it, and is what callers with state should use
    instead. Returns `ceiling` (the most capable optic allowed) if even
    that cannot resolve the target, rather than raising -- the caller's
    own `TOO_FAR`/remembered-sighting fallback is what speaks in that
    case, not this function."""
    profile = profile_for(object_type)
    # Aspect is unknown for a belief the same way `improvement_window_m`
    # treats it -- the profile's own extent, not a guess from a stale
    # heading.
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)
    floor_rank = _LADDER.index(floor)
    ceiling_rank = _LADDER.index(ceiling)
    for optic in _LADDER[floor_rank : ceiling_rank + 1]:
        presence_threshold_m, _class_threshold_m, _type_threshold_m = tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=optic,
            distinctiveness=distinctiveness,
        )
        if presence_threshold_m >= range_m:
            return optic
    return ceiling


def guidance_request_for(
    range_m: float,
    object_type: str,
    previous: Optic | None,
    *,
    floor: Optic,
    ceiling: Optic,
) -> Optic:
    """`BL-B71` Stage 3's hysteresis wrapper around `least_capable_
    sufficient_optic` above -- escalation is immediate (the plan's own
    "Escalate when range_m > threshold(current)"); de-escalation steps
    down one rung at a time and only once `range_m` is past that rung's
    own presence threshold by `GUIDANCE_OPTIC_HYSTERESIS_FRACTION`'s
    margin (guard 2). **Guard 1 ("do not re-evaluate while `MASKED`") and
    guard 3 (the minimum interval between grants) are both the caller's
    job, not this function's** -- `belief.attack_run.decide` simply never
    calls this on a masked tick, and `optic_policy.decide`'s own `_apply_
    guidance` clocks guard 3 against `OpticState.guidance_optic_since_sim`
    -- neither input exists for this pure range/profile function to read.

    `previous` is the *caller's own* last request (`AttackRunState.
    requested_optic`), **never** `OpticState.guidance_optic` -- the two
    can legitimately differ (the sight ceiling may have clamped what was
    actually granted), and this function's whole job is tracking what the
    target's geometry alone would ask for, independent of whether `optic_
    policy` chose to grant it. `None` (no previous request -- a fresh run,
    or a re-point onto a different contact) means "start from `floor`,
    nothing to de-escalate from yet."
    """
    profile = profile_for(object_type)
    extent = apparent_extent_m(profile, None)
    distinctiveness = distinctiveness_of(profile)

    def presence_threshold_m(optic: Optic) -> float:
        value, _class_m, _type_m = tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=optic,
            distinctiveness=distinctiveness,
        )
        return value

    floor_rank = _LADDER.index(floor)
    baseline = previous if previous is not None else floor
    baseline_rank = _LADDER.index(baseline)
    if baseline_rank < floor_rank:
        # The floor itself was raised since the last request (e.g. an
        # ATGM run's own floor/ceiling parameters) -- never hold a request
        # below the current floor.
        baseline = floor
        baseline_rank = floor_rank

    if range_m > presence_threshold_m(baseline):
        # Guard 2 does not gate escalation (the plan's own wording) --
        # walk straight up to whichever rung resolves the target.
        return least_capable_sufficient_optic(
            range_m, object_type, floor=baseline, ceiling=ceiling
        )

    if baseline_rank <= floor_rank:
        return baseline
    lower = _LADDER[baseline_rank - 1]
    if range_m < presence_threshold_m(lower) * (
        1.0 - GUIDANCE_OPTIC_HYSTERESIS_FRACTION
    ):
        return lower
    return baseline


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
    target: LookTarget,
    state: OpticState,
    now_sim: float = 0.0,
    *,
    can_improve: Callable[[LookTarget], bool] = can_still_improve,
    stall_cooldown_s: float | None = None,
) -> bool:
    """Whether this contact would gain anything from a *new* look now.

    `now_sim` defaults to `0.0` so every pre-existing call site that never
    supplied one keeps compiling and behaving identically -- `state.
    attempted_at_time_sim` is empty for those (no committed attempt has a
    time recorded), so the time-based branch below never fires for them
    regardless of the default's value.

    `can_improve` defaults to `can_still_improve` (the naked-eye/binocular
    window) -- a true no-op for every pre-existing caller. `_decide_
    sighting`'s candidate filter passes `sight_can_still_improve` instead,
    so a contact beyond binocular's own reach but still within the
    sight's is admitted as a candidate (`plans/9k113-narrow-search/
    review.md` required fix).

    `stall_cooldown_s` (`BL-B85`) defaults to `None`, a true no-op for
    every pre-existing caller -- `GLASSING`'s own call never passes it, so
    its re-eligibility stays exactly `OPTIC_RETRY_INTERVAL_S` regardless of
    whether a contact's classification ever moves. `_decide_sighting`'s
    candidate filter passes `SIGHT_STALL_COOLDOWN_S`: when a contact's
    level has not changed since its last committed attempt (`state.
    attempted_at_level`), that longer cooldown governs the time-based
    branch below in place of `OPTIC_RETRY_INTERVAL_S` -- the sight has had
    its look and taught nothing, so the search cycle and other contacts
    get the time back instead. The range-based escape (`RETRY_RANGE_
    FRACTION`) is unaffected either way: a contact that has genuinely
    closed is worth retrying regardless of whether its level has moved."""
    if not can_improve(target):
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
    attempted_at_level = state.attempted_at_level.get(target.contact_id)
    retry_interval_s = OPTIC_RETRY_INTERVAL_S
    if (
        stall_cooldown_s is not None
        and attempted_at_level is not None
        and attempted_at_level == target.current_level
    ):
        retry_interval_s = stall_cooldown_s
    time_elapsed_enough = (
        attempted_at_time is not None
        and now_sim - attempted_at_time >= retry_interval_s
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
    can_improve: Callable[[LookTarget], bool] = can_still_improve,
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

    `can_improve` defaults to `can_still_improve`, a true no-op for every
    pre-existing caller. `_decide_sighting` passes `sight_can_still_
    improve` instead -- it must, and not only at the candidate-admission
    step (`is_worth_a_look`): if this function kept judging an in-progress
    sight look against the eye/binocular window, a contact admitted only
    because the sight can still reach it would read as already outside
    that narrower window on the very next poll, ending the look one poll
    after it started and committing `attempted_at_range_m` as if it had
    actually resolved something -- silently reintroducing the gate defect
    one poll later (`plans/9k113-narrow-search/review.md` required fix).
    """
    look_started_sim = (
        started_sim if started_sim is not None else state.phase_started_sim
    )
    if look_started_sim is None or now_sim - look_started_sim >= max_dwell_s:
        return True
    return not any(
        _target_in_current_look(state, target) and can_improve(target)
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
    that makes the OBSERV-off path provably unchanged (§13's own claim).

    **`home_phase is SIGHTING`: the aim is carried through, never nulled**
    (`plans/9k113-narrow-search/plan.md` Stage 1, closing F5's "idle sight
    has no aim" defect for every path that reaches here -- an interrupted
    glance-away, a finished binocular excursion, `lower_binoculars` called
    mid-interruption). This *is* "the sight stays at last position," for
    free, once this function stops erasing it -- defaulting to `(0.0, 0.0)`
    (dead ahead) only if an aim was never set at all (the very first poll
    after "Observ on"). `home_phase is SCANNING`: byte-for-byte unchanged,
    aim nulled exactly as before -- `UNAIDED_OPTIC` is unrestricted and
    free-scans, so it has no "last position" to preserve."""
    if state.home_phase is OpticPhase.SIGHTING:
        azimuth = state.look_azimuth_deg if state.look_azimuth_deg is not None else 0.0
        elevation = (
            state.look_elevation_deg if state.look_elevation_deg is not None else 0.0
        )
        return (
            replace(
                state,
                phase=state.home_phase,
                phase_started_sim=now_sim,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
                search_pattern_steps=(),
                search_step_index=0,
                look_envelope_azimuth_deg=None,
                look_envelope_half_width_deg=None,
                pending_attempted_at_range_m={},
                pending_attempted_at_level={},
                look_contact_id=None,
                look_started_sim=None,
            ),
            OpticDecision(
                optic=SIGHT_WIDE_OPTIC,
                look_azimuth_deg=azimuth,
                look_elevation_deg=elevation,
            ),
        )
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
            pending_attempted_at_level={},
            look_contact_id=None,
            look_started_sim=None,
        ),
        OpticDecision(optic=_HOME_OPTIC[state.home_phase]),
    )


def _start_glance_away(
    state: OpticState, now_sim: float, targets: Sequence[LookTarget]
) -> tuple[OpticState, OpticDecision]:
    """Force the brief naked-eye glance away from the sight -- direction
    §9's inverted dwell shape (plan §13): entered from `SIGHTING` at its
    own dwell boundary (`SIGHT_MAX_DWELL_S`), exactly as `GLASSING` is
    entered from `SCANNING` at a scan boundary today, with the roles of
    "home" and "the bounded interruption" swapped (`OpticState.
    home_phase`). `home_phase` itself is left at `SIGHTING` -- this is a
    scheduled break *within* OBSERV staying on, not OBSERV turning off
    (that is `_force_observ_off`, a manoeuvre-only path).

    **Commits a pending contact's mark only if that look made no progress
    on it** (`BL-B85` required fix, `plans/9k113-narrow-search/review.md`
    "Review -- BL-B85": Part 2 of the original fix committed every pending
    mark unconditionally, which also throttled a contact whose
    classification was genuinely advancing -- measured at a re-look
    cadence of ~94 s instead of the pre-`BL-B85` ~33 s). "Made no
    progress" means `pending_attempted_at_level[contact_id]` (the level
    recorded at *this look's start*, same convention `pending_attempted_
    at_level`'s own docstring describes) still matches the contact's
    *current* level in `targets` at the moment the dwell boundary fires.
    If it does not match, the mark is dropped instead -- the same
    treatment a genuine interruption already gives it (`_back_to_home`'s
    Fix B1, `plans/sortie-2026-09-26-fixes/plan.md` Stage 2: "an
    interrupted look does not mark the target attempted"), because a look
    that taught something is not the stalled case `SIGHT_STALL_COOLDOWN_S`
    exists to throttle.

    The whole-dwell clock this fires from and the per-look natural-end
    timeout (`look_is_finished`'s `max_dwell_s`) share the same constant,
    `SIGHT_MAX_DWELL_S`, and `_decide_sighting` checks this boundary
    *before* the natural-end check -- so a contact that never resolves
    (`can_still_improve`/`sight_can_still_improve` stays true the whole
    dwell) has its look cut off here on every single cycle, never reaching
    the natural-end commit at all. A contact stuck like that now gets
    committed here (this function's original `BL-B85` fix), which is what
    lets `SIGHT_STALL_COOLDOWN_S` engage for it at all."""
    current_level_by_id = {
        target.contact_id: target.current_level for target in targets
    }
    committed_range = dict(state.attempted_at_range_m)
    committed_time = dict(state.attempted_at_time_sim)
    committed_level = dict(state.attempted_at_level)
    for contact_id, attempted_range_m in state.pending_attempted_at_range_m.items():
        look_start_level = state.pending_attempted_at_level[contact_id]
        # Not found in `targets` (the contact dropped out of candidacy
        # mid-look, e.g. lost): nothing to compare against, so there is no
        # evidence of progress -- commit, same as the stalled case.
        current_level = current_level_by_id.get(contact_id, look_start_level)
        if current_level != look_start_level:
            continue
        committed_range[contact_id] = attempted_range_m
        committed_time[contact_id] = now_sim
        committed_level[contact_id] = look_start_level
    return (
        replace(
            state,
            phase=OpticPhase.SCANNING,
            phase_started_sim=now_sim,
            look_azimuth_deg=None,
            look_elevation_deg=None,
            look_envelope_azimuth_deg=None,
            look_envelope_half_width_deg=None,
            attempted_at_range_m=committed_range,
            attempted_at_time_sim=committed_time,
            attempted_at_level=committed_level,
            pending_attempted_at_range_m={},
            pending_attempted_at_level={},
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
            pending_attempted_at_level={},
            look_contact_id=None,
            look_started_sim=None,
        )
    return _back_to_home(state, now_sim)[0]


#: The search cycle's fixed order -- `plans/9k113-narrow-search/plan.md`
#: Stage 3, amendment 2. `_next_search_leg` walks it; never read directly
#: outside this module.
_SEARCH_LEG_ORDER: Final[tuple[SightSearchLeg, ...]] = (
    "wide",
    "narrow_near",
    "narrow_far",
    "binocular",
)

#: Which optic each non-binocular leg looks through -- `"binocular"` is
#: deliberately absent: that leg hands off to `OpticPhase.SEARCHING`
#: entirely (`_enter_binocular_search`), which already hardcodes
#: `BINOCULAR_OPTIC` for every one of its callers.
_SEARCH_LEG_OPTIC: Final[dict[Literal["wide", "narrow_near", "narrow_far"], Optic]] = {
    "wide": SIGHT_WIDE_OPTIC,
    "narrow_near": SIGHT_NARROW_OPTIC,
    "narrow_far": SIGHT_NARROW_OPTIC,
}


def _next_search_leg(leg: SightSearchLeg, *, has_out_of_regard: bool) -> SightSearchLeg:
    """The next leg after `leg` in the fixed cycle `wide -> narrow_near ->
    narrow_far -> binocular -> wide`, skipping `binocular` whenever there is
    no out-of-regard remainder to search (the default-sector and `ahead`
    cases, where the cycle is `wide -> narrow_near -> narrow_far` only)."""
    index = _SEARCH_LEG_ORDER.index(leg)
    candidate = _SEARCH_LEG_ORDER[(index + 1) % len(_SEARCH_LEG_ORDER)]
    if candidate == "binocular" and not has_out_of_regard:
        return _SEARCH_LEG_ORDER[(index + 2) % len(_SEARCH_LEG_ORDER)]
    return candidate


def _enter_binocular_search(
    state: OpticState,
    now_sim: float,
    sight_out_of_regard_search: Sequence[tuple[float, float]],
) -> tuple[OpticState, OpticDecision]:
    """The `binocular` leg: a commanded sector's out-of-regard remainder,
    searched via the ordinary `OpticPhase.SEARCHING` dispatch (unchanged --
    it already hardcodes `BINOCULAR_OPTIC`, correct for this new caller
    too), not through `_decide_sighting` again.

    **Deliberately omits `look_azimuth_deg`/`look_elevation_deg` from the
    `replace()` below** -- leaving them exactly as they were is "the sight
    stays at its last position" (`docs/acceptance/2026-10-20-sortie-
    feedback.md`, F4/F5 "settled": *"Leave 9K113 at last position"*), for
    free, simply by never touching them.

    **Sets `sight_search_leg` back to `"wide"` immediately at entry**,
    not on exit, so that whenever this excursion ends (pattern exhausted,
    or `not steady`) and `_back_to_home` resumes `SIGHTING`, the very next
    idle-branch evaluation starts a fresh `wide` pass without needing to
    distinguish "just returned from binoculars" from any other resume."""
    first_azimuth, first_elevation = sight_out_of_regard_search[0]
    return (
        replace(
            state,
            phase=OpticPhase.SEARCHING,
            phase_started_sim=now_sim,
            search_pattern_steps=tuple(sight_out_of_regard_search),
            search_step_index=0,
            look_contact_id=None,
            look_started_sim=None,
            pending_attempted_at_range_m={},
            pending_attempted_at_level={},
            look_envelope_azimuth_deg=None,
            look_envelope_half_width_deg=None,
            sight_search_leg="wide",
        ),
        OpticDecision(
            optic=BINOCULAR_OPTIC,
            look_azimuth_deg=first_azimuth,
            look_elevation_deg=first_elevation,
        ),
    )


def _idle_sight_rest(state: OpticState) -> tuple[OpticState, OpticDecision]:
    """The defensive fallback for when no search leg has anything to step
    through at all. **Never reached in production**: `logger._commanded_
    or_default_sector` always yields a non-empty in-regard span (Stage 2's
    own geometry argument -- every named `RelativeSector`, and the
    synthesized default, straddles or contains azimuth 0), so `_idle_
    sight_search` below always finds a non-empty leg to step. It is
    reached by a direct `decide()`/`_decide_sighting()` call that supplies
    none of the four `sight_*_search` sequences -- most of this module's
    own tests -- and must still never leave the aim unset (closes F5):
    hold the last position, or dead ahead if there never was one, exactly
    `_back_to_home`'s own convention for the same question."""
    azimuth = state.look_azimuth_deg if state.look_azimuth_deg is not None else 0.0
    elevation = (
        state.look_elevation_deg if state.look_elevation_deg is not None else 0.0
    )
    return (
        replace(
            state,
            look_azimuth_deg=azimuth,
            look_elevation_deg=elevation,
            look_contact_id=None,
            look_started_sim=None,
        ),
        OpticDecision(
            optic=SIGHT_WIDE_OPTIC,
            look_azimuth_deg=azimuth,
            look_elevation_deg=elevation,
        ),
    )


def _idle_sight_search(
    state: OpticState,
    now_sim: float,
    *,
    sight_wide_search: Sequence[tuple[float, float]],
    sight_narrow_near_search: Sequence[tuple[float, float]],
    sight_narrow_far_search: Sequence[tuple[float, float]],
    sight_out_of_regard_search: Sequence[tuple[float, float]],
) -> tuple[OpticState, OpticDecision]:
    """`_decide_sighting`'s idle branch (nothing worth a closer look):
    step through whichever leg of the search cycle is current (`state.
    sight_search_leg`) -- a brief `wide` orientation pass, then `narrow_
    near`/`narrow_far` (amendment 2's "narrow sweeps both bands, near
    first"), then a `binocular` excursion for any out-of-regard remainder
    -- advancing to the next leg once the current one's steps run out.
    `SEARCH_STEP_S` per step, `look_started_sim` reused as the per-leg
    clock (its own docstring), exactly the mechanism `GLASSING`/
    `SEARCHING` already use for their own step timing, generalised to
    whichever leg is current.

    **Skips an empty leg defensively rather than stalling on it**
    (`_next_search_leg`'s own skip of `binocular` is the one case this is
    known to hit in production; see `_idle_sight_rest` for what happens
    if every leg is empty)."""
    sequences: dict[
        Literal["wide", "narrow_near", "narrow_far"], Sequence[tuple[float, float]]
    ] = {
        "wide": sight_wide_search,
        "narrow_near": sight_narrow_near_search,
        "narrow_far": sight_narrow_far_search,
    }
    has_out_of_regard = bool(sight_out_of_regard_search)

    def first_nonempty_leg(starting: SightSearchLeg) -> SightSearchLeg | None:
        leg = starting
        for _ in range(len(_SEARCH_LEG_ORDER)):
            if leg == "binocular":
                if has_out_of_regard:
                    return leg
            elif sequences[leg]:
                return leg
            leg = _next_search_leg(leg, has_out_of_regard=has_out_of_regard)
        return None

    leg = first_nonempty_leg(state.sight_search_leg)
    if leg is None:
        return _idle_sight_rest(state)
    if leg == "binocular":
        return _enter_binocular_search(state, now_sim, sight_out_of_regard_search)

    steps = sequences[leg]
    leg_started_sim = (
        state.look_started_sim
        if state.sight_search_leg == leg and state.look_started_sim is not None
        else now_sim
    )
    index = int((now_sim - leg_started_sim) // SEARCH_STEP_S)
    if index >= len(steps):
        next_leg = first_nonempty_leg(
            _next_search_leg(leg, has_out_of_regard=has_out_of_regard)
        )
        if next_leg is None:
            return _idle_sight_rest(state)
        if next_leg == "binocular":
            return _enter_binocular_search(state, now_sim, sight_out_of_regard_search)
        leg = next_leg
        steps = sequences[leg]
        leg_started_sim = now_sim
        index = 0

    azimuth, elevation = steps[index]
    return (
        replace(
            state,
            look_azimuth_deg=azimuth,
            look_elevation_deg=elevation,
            search_step_index=index,
            look_started_sim=leg_started_sim,
            sight_search_leg=leg,
        ),
        OpticDecision(
            optic=_SEARCH_LEG_OPTIC[leg],
            look_azimuth_deg=azimuth,
            look_elevation_deg=elevation,
        ),
    )


def _decide_sighting(
    state: OpticState,
    now_sim: float,
    targets: Sequence[LookTarget],
    sight_steady: bool,
    *,
    sight_wide_search: Sequence[tuple[float, float]] = (),
    sight_narrow_near_search: Sequence[tuple[float, float]] = (),
    sight_narrow_far_search: Sequence[tuple[float, float]] = (),
    sight_out_of_regard_search: Sequence[tuple[float, float]] = (),
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

    The four `sight_*_search` sequences (`plans/9k113-narrow-search/
    plan.md` Stage 3) are the idle branch's own active search cycle --
    `logger.py` computes them fresh every poll from the commanded-or-
    default sector (the same way `search` is computed for `SCANNING`-at-
    home) and threads them through `decide`/`_decide_without_guidance`
    unchanged; all four default to empty, a true no-op for every
    pre-existing caller/test, none of which pass them.

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
        return _start_glance_away(state, now_sim, targets)

    if state.look_contact_id is not None and look_is_finished(
        state,
        now_sim,
        targets,
        started_sim=state.look_started_sim,
        max_dwell_s=SIGHT_MAX_DWELL_S,
        can_improve=sight_can_still_improve,
    ):
        # The current look's own natural end (recognition succeeded,
        # nothing left to learn in its envelope) -- commit its pending
        # marks, same shape as GLASSING's natural end, then fall through
        # below to pick the next target immediately. Only the scheduled
        # break above ends the dwell itself.
        committed_range = dict(state.attempted_at_range_m)
        committed_time = dict(state.attempted_at_time_sim)
        committed_level = dict(state.attempted_at_level)
        for contact_id, attempted_range_m in state.pending_attempted_at_range_m.items():
            committed_range[contact_id] = attempted_range_m
            committed_time[contact_id] = now_sim
            committed_level[contact_id] = state.pending_attempted_at_level[contact_id]
        state = replace(
            state,
            attempted_at_range_m=committed_range,
            attempted_at_time_sim=committed_time,
            attempted_at_level=committed_level,
            pending_attempted_at_range_m={},
            pending_attempted_at_level={},
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
                optic=state.look_optic,
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
        if is_worth_a_look(
            target,
            state,
            now_sim,
            can_improve=sight_can_still_improve,
            stall_cooldown_s=_EFFECTIVE_SIGHT_STALL_COOLDOWN_S,
        )
        and within_field_of_regard(
            SIGHT_WIDE_OPTIC, target.azimuth_deg, target.elevation_deg
        )
    ]
    chosen = choose_look(worth_looking)
    if chosen is None:
        # Nothing worth a closer look: step through the idle search cycle
        # instead of resting with no aim (`plans/9k113-narrow-search/
        # plan.md` Stage 3, closing F5's defect).
        return _idle_sight_search(
            state,
            now_sim,
            sight_wide_search=sight_wide_search,
            sight_narrow_near_search=sight_narrow_near_search,
            sight_narrow_far_search=sight_narrow_far_search,
            sight_out_of_regard_search=sight_out_of_regard_search,
        )

    # Starting a new look at the chosen target -- same shape as `decide`'s
    # own SCANNING-at-home body entering `GLASSING`, swept against
    # whichever sight setting suffices (`sight_look_optic`, `plans/
    # 9k113-narrow-search/plan.md` Stage 4 Part A) rather than always
    # narrow.
    #
    # `regard_optic=SIGHT_WIDE_OPTIC` truncates the sweep at the mount's
    # own field of regard (`look_sweep`'s own docstring has the full
    # reasoning) -- `chosen` already passed `within_field_of_regard` above,
    # but the sweep built *around* it can still reach past the boundary on
    # a wide-uncertainty contact close to the edge. `SIGHT_WIDE_OPTIC` is
    # read for the same reason the candidate filter above reads it: one
    # optic has to be named and the two sight optics' `regard_*` fields are
    # identical.
    look_optic = sight_look_optic(chosen)
    fov_full_width_deg = (look_optic.fov_half_angle_deg or 0.0) * 2.0
    sweep = look_sweep(
        centre_azimuth_deg=chosen.azimuth_deg,
        centre_elevation_deg=chosen.elevation_deg,
        bearing_uncertainty_deg=chosen.bearing_uncertainty_deg,
        fov_full_width_deg=fov_full_width_deg,
        regard_optic=SIGHT_WIDE_OPTIC,
    )
    envelope_half_width = max(chosen.bearing_uncertainty_deg, 0.0)

    pending = dict(state.pending_attempted_at_range_m)
    pending_level = dict(state.pending_attempted_at_level)
    for target in worth_looking:
        if _angular_separation_deg(chosen, target) <= envelope_half_width:
            pending[target.contact_id] = target.range_m
            pending_level[target.contact_id] = target.current_level

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
        pending_attempted_at_level=pending_level,
        look_contact_id=chosen.contact_id,
        look_optic=look_optic,
        look_started_sim=now_sim,
    )
    return (
        new_state,
        OpticDecision(
            optic=look_optic,
            look_azimuth_deg=first_azimuth,
            look_elevation_deg=first_elevation,
        ),
    )


def _decide_without_guidance(
    state: OpticState,
    *,
    now_sim: float,
    scan_cycle_period_s: float,
    targets: Sequence[LookTarget],
    steady: bool,
    search: Sequence[tuple[float, float]] = (),
    sight_steady: bool = True,
    sight_wide_search: Sequence[tuple[float, float]] = (),
    sight_narrow_near_search: Sequence[tuple[float, float]] = (),
    sight_narrow_far_search: Sequence[tuple[float, float]] = (),
    sight_out_of_regard_search: Sequence[tuple[float, float]] = (),
) -> tuple[OpticState, OpticDecision]:
    """The ordinary phase-cycle dispatch -- `decide`'s whole body before
    `BL-B71`, renamed and kept otherwise unchanged so that the public
    `decide` below can post-process its result through `_apply_guidance`
    without touching any of the dispatch logic itself (the plan's own
    "leaves the phase machine otherwise untouched"). Advance the cycle one
    poll and say what to look through.

    `search` is the sweep to run when there is nothing worth a closer look
    -- empty when the active scan is free or its sector is too wide to
    sweep (Stage 3). **Identification takes priority over search**: a
    contact already detected and resolvable is worth more than looking for
    another one, and the user's own sequencing says so (*"detected targets
    then get the dwell behaviour"*).

    The four `sight_*_search` sequences are `search`'s own sibling for the
    `SIGHTING` branch below (`plans/9k113-narrow-search/plan.md` Stage 3)
    -- threaded straight through to `_decide_sighting`, read only there.
    All default to empty, a true no-op for every pre-existing caller.

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
            committed_level = dict(state.attempted_at_level)
            for (
                contact_id,
                attempted_range_m,
            ) in state.pending_attempted_at_range_m.items():
                committed_range[contact_id] = attempted_range_m
                committed_time[contact_id] = now_sim
                committed_level[contact_id] = state.pending_attempted_at_level[
                    contact_id
                ]
            return _back_to_home(
                replace(
                    state,
                    attempted_at_range_m=committed_range,
                    attempted_at_time_sim=committed_time,
                    attempted_at_level=committed_level,
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
        return _decide_sighting(
            state,
            now_sim,
            targets,
            sight_steady,
            sight_wide_search=sight_wide_search,
            sight_narrow_near_search=sight_narrow_near_search,
            sight_narrow_far_search=sight_narrow_far_search,
            sight_out_of_regard_search=sight_out_of_regard_search,
        )

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
                    attempted_at_level=dict(state.attempted_at_level),
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
                    # `BL-B71`: also not part of this phase's own
                    # bookkeeping -- a search-sweep entry unrelated to any
                    # standing guidance grant must not reset it (`_apply_
                    # guidance`, which runs after this dispatch, would
                    # otherwise read a freshly-`None`d `guidance_optic_
                    # since_sim` as "never granted" and recharge the
                    # hands-busy cost for a grant that was already
                    # standing).
                    guidance_optic=state.guidance_optic,
                    guidance_optic_since_sim=state.guidance_optic_since_sim,
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
    pending_level = dict(state.pending_attempted_at_level)
    for target in worth_looking:
        if _angular_separation_deg(chosen, target) <= envelope_half_width:
            # Every contact this look covers counts as attempted, not just
            # the one it was centred on -- they all get the benefit, so
            # they all bear the retry rule.
            pending[target.contact_id] = target.range_m
            pending_level[target.contact_id] = target.current_level

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
            attempted_at_level=dict(state.attempted_at_level),
            pending_attempted_at_level=pending_level,
            look_contact_id=chosen.contact_id,
            # Carried forward explicitly, same reason as the SEARCHING
            # branch above.
            actual_aim_azimuth_deg=state.actual_aim_azimuth_deg,
            actual_aim_elevation_deg=state.actual_aim_elevation_deg,
            home_phase=state.home_phase,
            hands_busy_until_sim=state.hands_busy_until_sim,
            # `BL-B71`: same reason as the SEARCHING branch's own comment
            # above -- an ordinary glass-phase entry must not reset a
            # standing guidance grant's bookkeeping.
            guidance_optic=state.guidance_optic,
            guidance_optic_since_sim=state.guidance_optic_since_sim,
        ),
        OpticDecision(
            optic=BINOCULAR_OPTIC,
            look_azimuth_deg=first_azimuth,
            look_elevation_deg=first_elevation,
        ),
    )


def _apply_guidance(
    state: OpticState,
    decision: OpticDecision,
    now_sim: float,
    guidance_request: Optic | None,
) -> tuple[OpticState, OpticDecision]:
    """`BL-B71`'s override step -- runs after `_decide_without_guidance`
    has already produced `(state, decision)` from the ordinary phase
    dispatch, and only ever changes `decision.optic` plus the two
    `guidance_*` fields on `state`; `phase`, `look_azimuth_deg`, and the
    whole SCANNING/GLASSING/SEARCHING/SIGHTING cycle are left exactly as
    the dispatch decided (the plan's own "leaves the phase machine
    otherwise untouched"). `decide` never calls this while `decision.
    suppressed` -- the hands-busy window already means no optic yields
    observations this poll, so there is nothing to override and no grant
    to charge.

    **The sight ceiling is re-derived from `state.home_phase` on every
    call, never cached or latched** -- this is what makes "the 9K113 is
    never reached for autonomously" (`BL-B71.md`'s hard gate) structural
    rather than a check a caller could forget: a sight-ranked request is
    silently capped to `BINOCULAR_OPTIC` whenever `home_phase` is not
    `SIGHTING`, so a pilot's "Observ off" (which only ever changes `home_
    phase`, read fresh here every poll) demotes any standing sight grant
    to binoculars on the very next poll, and a violated `sight_steady`
    (`_force_observ_off`, which also only ever changes `home_phase`)
    demotes it the same way -- neither transition needs its own special
    case here, because this function never trusts a cached answer to "is
    a sight optic currently allowed."

    `guidance_request is None` means the run is not engaged (or `attack_
    run.decide` has nothing to request this tick, which in practice only
    happens for a `MASKED` tick -- see that module) -- revokes any
    standing grant (the Co-moving Fields table's `disengage`/`drop_target`/
    run-ends row): `guidance_optic`/`guidance_optic_since_sim` both go to
    `None` together, never independently, and `decision` is returned
    unchanged (whatever the ordinary phase dispatch already picked)."""
    if guidance_request is None:
        if state.guidance_optic is None:
            return state, decision
        return (
            replace(state, guidance_optic=None, guidance_optic_since_sim=None),
            decision,
        )

    effective_request = guidance_request
    if _LADDER.index(guidance_request) > _LADDER.index(BINOCULAR_OPTIC) and (
        state.home_phase is not OpticPhase.SIGHTING or decision.look_azimuth_deg is None
    ):
        # `plans/9k113-narrow-search/plan.md` Stage 1's fourth path:
        # `home_phase is SIGHTING` is not by itself proof that a sight tier
        # has an aim to grant onto -- the glance-away sub-phase's own
        # decision is bare `OpticDecision(optic=UNAIDED_OPTIC)` (no aim,
        # because the naked eye never needs one), and a guidance request
        # arriving during exactly that poll must still be capped, or it
        # would hand back a sight optic with the glance's own `look_
        # azimuth_deg=None` untouched -- the same defect F5 found, through
        # a fourth path.
        effective_request = BINOCULAR_OPTIC

    if effective_request == state.guidance_optic:
        # Already granted -- re-affirm the override (the ordinary
        # dispatch's own `decision.optic` may disagree, e.g. a GLASSING
        # phase busy with an unrelated contact) without touching the
        # clock or charging hands again.
        return state, replace(decision, optic=effective_request)

    if (
        state.guidance_optic_since_sim is not None
        and now_sim - state.guidance_optic_since_sim < GUIDANCE_OPTIC_MIN_INTERVAL_S
    ):
        # Guard 3: too soon since the last grant -- refused. Hold the
        # standing grant, if any; a refused request must not advance
        # `hands_busy_until_sim` (refusing costs no hands).
        if state.guidance_optic is not None:
            return state, replace(decision, optic=state.guidance_optic)
        return state, decision

    # A real change: grant `effective_request`, re-stamp the clock, and
    # charge the 1 s hands-busy cost iff the optic actually in use is
    # changing -- compared against the standing grant if there is one,
    # or against the phase's own home optic otherwise (the first grant
    # of a run, where nothing has been granted yet to compare against).
    # Known narrow gap, left as-is (review's optional refinement, `plans/
    # attack-run-sortie-fixes/review-bl-b71.md`): this first-grant
    # comparison uses `_HOME_OPTIC[state.home_phase]` rather than
    # `decision.optic`, so a first grant can overcharge hands-busy when
    # the ordinary phase dispatch already happened to be using the same
    # optic the request resolves to (e.g. a GLASSING phase already up on
    # binoculars for an unrelated contact). Not safety-relevant -- it
    # only ever charges a cost that was not strictly owed, never skips a
    # real one -- so left uncorrected rather than widened beyond the
    # required fix this task was scoped to.
    previous_optic = (
        state.guidance_optic
        if state.guidance_optic is not None
        else _HOME_OPTIC[state.home_phase]
    )
    new_state = replace(
        state,
        guidance_optic=effective_request,
        guidance_optic_since_sim=now_sim,
        hands_busy_until_sim=(
            now_sim + HANDS_BUSY_DURATION_S
            if effective_request != previous_optic
            else state.hands_busy_until_sim
        ),
    )
    return new_state, replace(decision, optic=effective_request)


def decide(
    state: OpticState,
    *,
    now_sim: float,
    scan_cycle_period_s: float,
    targets: Sequence[LookTarget],
    steady: bool,
    search: Sequence[tuple[float, float]] = (),
    sight_steady: bool = True,
    sight_wide_search: Sequence[tuple[float, float]] = (),
    sight_narrow_near_search: Sequence[tuple[float, float]] = (),
    sight_narrow_far_search: Sequence[tuple[float, float]] = (),
    sight_out_of_regard_search: Sequence[tuple[float, float]] = (),
    guidance_request: Optic | None = None,
) -> tuple[OpticState, OpticDecision]:
    """Advance the cycle one poll and say what to look through --
    `_decide_without_guidance`'s ordinary phase dispatch, then `BL-B71`'s
    `_apply_guidance` override on top of it.

    `guidance_request` (`plans/attack-run-sortie-fixes/plan.md` §6/§7)
    defaults to `None` -- a true no-op for every pre-existing caller,
    exactly like `sight_steady`/`group_salient`/`forest` elsewhere in this
    module. `logger.py`'s poll loop sets it from `AttackRunState.
    requested_optic` whenever an attack run is engaged; `belief.attack_
    run.decide` is the only producer of that value.

    The four `sight_*_search` sequences (`plans/9k113-narrow-search/
    plan.md` Stage 3) are `_decide_without_guidance`'s own parameters of
    the same name, passed straight through; see that function's docstring.

    **Never applied while `decision.suppressed`** -- the hands-busy
    window already means nothing is observed through any optic this
    poll, so there is nothing for `_apply_guidance` to override and no
    new grant for it to charge."""
    new_state, decision = _decide_without_guidance(
        state,
        now_sim=now_sim,
        scan_cycle_period_s=scan_cycle_period_s,
        targets=targets,
        steady=steady,
        search=search,
        sight_steady=sight_steady,
        sight_wide_search=sight_wide_search,
        sight_narrow_near_search=sight_narrow_near_search,
        sight_narrow_far_search=sight_narrow_far_search,
        sight_out_of_regard_search=sight_out_of_regard_search,
    )
    if decision.suppressed:
        return new_state, decision
    return _apply_guidance(new_state, decision, now_sim, guidance_request)


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
    pitch_deg: float = 0.0,
    bank_deg: float = 0.0,
) -> LookTarget:
    """Build a `LookTarget` from a contact's believed position.

    Lives here rather than in the caller so the azimuth/elevation
    convention is stated once: body-relative azimuth (0 dead ahead,
    positive clockwise) and elevation positive up, the same frame
    `within_optic_fov` tests in -- via `body_relative_direction`, the same
    conversion `perception.visibility.check_visibility` uses, rather than a
    second derivation of it (F5, `docs/acceptance/
    2026-10-20-sortie-feedback.md`: a look target's azimuth/elevation must
    rotate with pitch and bank exactly as a live detection's does, or the
    sight's field-of-regard check it is tested against means two different
    things depending on which path produced the number it is testing).

    `pitch_deg`/`bank_deg` both default to `0.0` -- a true no-op for every
    pre-existing call site, mirroring `perception.source.OwnshipState`'s
    own default convention. `logger._look_targets` is the one caller with
    a real ownship to hand, and passes `ownship.pitch_deg`/`ownship.
    bank_deg`.

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
    slant_m = range_m(observer, target_position)
    body_direction = body_relative_direction(
        observer,
        target_position,
        heading_true_deg=heading_true_deg,
        pitch_deg=pitch_deg,
        bank_deg=bank_deg,
    )
    azimuth = body_direction.azimuth_deg
    elevation = body_direction.elevation_deg
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
