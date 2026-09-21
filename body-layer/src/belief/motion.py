"""The motion belief -- `plans/movement-detection/plan.md` Stage 3.

`classification.py`/`cardinality.py`'s sibling in shape (a small fold rule
`belief.contacts.Contact.record` calls instead of overwriting), but a
two-state flag rather than a lattice/interval: `MotionBelief.state` is
`"moving"` or `"stopped"`, there is no specificity level or containment
relation to reason about, only which state is currently held and how
confident that claim still is.

**Unlike `classification`/`cardinality`, `Contact.motion` is `None`-able
even after founding.** Those two are always seeded at founding (a real
claim, however coarse) because every source supplies *some* classification
evidence. Motion is different: only the naked-eye channel supplies a
velocity-derived verdict at all (the plan's Stage 2 join lives entirely in
`naked_eye_source.py`), so a contact seen only through the scope/hybrid
channel never receives a motion percept and should stay honestly
`None` -- "never observed for movement," not silently "stopped."

**The fold is deliberately asymmetric** (`body-layer/ROADMAP.md`'s
2026-09-20 design, restated in `plans/movement-detection/plan.md`'s
Decision 4): one above-threshold (`True`) percept promotes to `"moving"`
immediately -- motion is positive evidence, noticed at once. Demoting to
`"stopped"` from an already-`"moving"` claim requires
`belief.decay.MOTION_STOP_CONFIRM_S` of **continuous** sub-threshold
(`False`) evidence -- concluding something has stopped takes watching it a
while. This is also what stops a unit hovering right at the threshold from
flapping the event every `belief.events.EVENT_COOLDOWN_S`.

`None` (unobserved this poll, or no velocity match) always **holds** --
neither promotes nor demotes, and does not interrupt an in-progress
demotion countdown either (a gap in observation is not evidence the unit
started moving again, so `pending_stop_since_sim` survives a `None` poll
unchanged; only a `True` reading resets it).

A contact's *founding* motion percept (no `held` claim yet) is adopted
outright regardless of direction -- there is no prior "moving" claim to
demote away from, so a first `False` reading becomes `"stopped"`
immediately, the same "adopt the founding claim as-is" rule
`classification.py`/`cardinality.py` both already follow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from belief.decay import MOTION_STOP_CONFIRM_S

MotionState = Literal["moving", "stopped"]

#: Placeholder starting confidence for a freshly-established motion claim --
#: same posture as `classification._DEFAULT_CONFIDENCE_BY_LEVEL`/
#: `cardinality._DEFAULT_CONFIDENCE`, not calibrated.
_DEFAULT_CONFIDENCE: Final[float] = 0.5

#: Reinforcement ceiling/step, identical values to `classification.py`'s/
#: `cardinality.py`'s own -- the same "residual uncertainty never fully
#: resolves" judgment call, reused rather than re-derived.
_CONFIDENCE_CEILING: Final[float] = 0.95
_REINFORCE_CONFIDENCE_STEP: Final[float] = 0.05


@dataclass(frozen=True, slots=True)
class MotionBelief:
    """One contact's held motion claim. `established_sim` is when this
    exact `state` was last confirmed -- refreshed on reinforcement, reset
    to the fold's `now_sim` on a promotion or a confirmed demotion, mirroring
    `ClassificationBelief.established_sim`'s own convention."""

    state: MotionState
    confidence: float
    established_sim: float


@dataclass(frozen=True, slots=True)
class FoldMotionOutcome:
    """`fold_motion`'s result. `motion` is `None` only when `held` was
    already `None` and `incoming` was `None` too (nothing to hold, nothing
    to adopt). `pending_stop_since_sim` is the demotion-countdown state --
    the sim time the *first* contradicting `False` reading arrived since
    `motion` was last confirmed `"moving"`, or `None` when no demotion is in
    progress (module docstring)."""

    motion: MotionBelief | None
    pending_stop_since_sim: float | None


def fold_motion(
    held: MotionBelief | None,
    incoming: bool | None,
    now_sim: float,
    pending_stop_since_sim: float | None,
) -> FoldMotionOutcome:
    """The fusion rule `belief.contacts.Contact.record` calls instead of
    overwriting. `incoming` is `Percept.apparent_motion` -- `perception.
    motion.is_apparently_moving`'s tri-state verdict, already crossed the
    `perception`/`belief` boundary as a bare `bool | None` (module
    docstring's central invariant). See the module docstring for the full
    promote-fast/demote-slow rule."""
    if incoming is None:
        # Unobserved this poll -- pure hold, on both the belief and the
        # demotion countdown (module docstring).
        return FoldMotionOutcome(
            motion=held, pending_stop_since_sim=pending_stop_since_sim
        )

    if incoming:
        # Real positive evidence -- promote immediately, whatever the prior
        # state (or lack of one) was. Any in-progress demotion countdown is
        # cancelled: the unit is moving again.
        if held is not None and held.state == "moving":
            motion = _reinforce(held, now_sim)
        else:
            motion = MotionBelief(
                state="moving", confidence=_DEFAULT_CONFIDENCE, established_sim=now_sim
            )
        return FoldMotionOutcome(motion=motion, pending_stop_since_sim=None)

    # incoming is False.
    if held is None:
        # Founding claim -- no prior "moving" belief to demote away from
        # (module docstring's "adopt the founding claim as-is" rule).
        motion = MotionBelief(
            state="stopped", confidence=_DEFAULT_CONFIDENCE, established_sim=now_sim
        )
        return FoldMotionOutcome(motion=motion, pending_stop_since_sim=None)

    if held.state == "stopped":
        # Already stopped -- reinforce, no countdown needed (only a
        # moving -> stopped transition is gated by MOTION_STOP_CONFIRM_S).
        return FoldMotionOutcome(
            motion=_reinforce(held, now_sim), pending_stop_since_sim=None
        )

    # held.state == "moving" and incoming is False -- a demotion candidate.
    # `pending_stop_since_sim` marks the first contradicting reading in this
    # (possibly still ongoing) run; a fresh run starts it at `now_sim`.
    since = pending_stop_since_sim if pending_stop_since_sim is not None else now_sim
    if now_sim - since >= MOTION_STOP_CONFIRM_S:
        motion = MotionBelief(
            state="stopped", confidence=_DEFAULT_CONFIDENCE, established_sim=now_sim
        )
        return FoldMotionOutcome(motion=motion, pending_stop_since_sim=None)
    return FoldMotionOutcome(motion=held, pending_stop_since_sim=since)


def _reinforce(held: MotionBelief, now_sim: float) -> MotionBelief:
    return MotionBelief(
        state=held.state,
        confidence=min(
            _CONFIDENCE_CEILING, held.confidence + _REINFORCE_CONFIDENCE_STEP
        ),
        established_sim=now_sim,
    )
