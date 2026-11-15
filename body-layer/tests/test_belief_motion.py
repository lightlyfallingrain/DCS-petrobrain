"""Tests for `belief.motion.fold_motion` -- `plans/movement-detection/
plan.md` Stage 3. Unit tests of the pure fold rule, mirroring
`test_cardinality.py`'s per-outcome coverage of `fold_cardinality`."""

from __future__ import annotations

from belief.decay import MOTION_STOP_CONFIRM_S
from belief.motion import MotionBelief, fold_motion


def _moving(established_sim: float, confidence: float = 0.5) -> MotionBelief:
    return MotionBelief(
        state="moving", confidence=confidence, established_sim=established_sim
    )


def _stopped(established_sim: float, confidence: float = 0.5) -> MotionBelief:
    return MotionBelief(
        state="stopped", confidence=confidence, established_sim=established_sim
    )


def test_founding_true_adopts_moving_outright() -> None:
    outcome = fold_motion(None, True, 10.0, None)
    assert outcome.motion is not None
    assert outcome.motion.state == "moving"
    assert outcome.motion.established_sim == 10.0
    assert outcome.pending_stop_since_sim is None


def test_founding_false_starts_a_watch_rather_than_adopting_stopped_outright() -> None:
    """`[[BL-B112]]`: at Mi-24 ranges a single glance cannot tell a unit
    driving straight at the helicopter from one parked, so a founding
    `False` reading no longer adopts "stopped" immediately -- it starts
    the same `MOTION_STOP_CONFIRM_S` watch the demotion branch uses.
    `motion` stays honestly `None` ("never observed for movement") until
    the watch completes."""
    outcome = fold_motion(None, False, 10.0, None)
    assert outcome.motion is None
    assert outcome.pending_stop_since_sim == 10.0


def test_founding_false_confirms_stopped_once_the_watch_completes() -> None:
    """The counterpart: once `MOTION_STOP_CONFIRM_S` of continuous
    sub-threshold evidence has elapsed since the founding reading, the
    watch completes and `"stopped"` is adopted -- the same confirmation
    the demotion branch (`test_demotion_requires_the_full_confirm_window`)
    already requires, now also required at founding."""
    started = fold_motion(None, False, 10.0, None)
    since = started.pending_stop_since_sim
    assert since is not None

    # Just short of the window -- still unobserved-for-movement.
    almost = fold_motion(None, False, since + MOTION_STOP_CONFIRM_S - 0.01, since)
    assert almost.motion is None
    assert almost.pending_stop_since_sim == since

    # At (or past) the window -- confirms "stopped".
    confirmed = fold_motion(None, False, since + MOTION_STOP_CONFIRM_S, since)
    assert confirmed.motion is not None
    assert confirmed.motion.state == "stopped"
    assert confirmed.pending_stop_since_sim is None


def test_founding_false_watch_is_cancelled_by_a_true_reading() -> None:
    """A `True` reading mid-watch promotes to `"moving"` immediately, same
    as mid-demotion (`test_a_true_reading_mid_countdown_cancels_the_
    demotion`) -- the watch is not a separate mechanism from the
    demotion countdown, it is the same one."""
    started = fold_motion(None, False, 10.0, None)
    since = started.pending_stop_since_sim
    assert since is not None

    resumed = fold_motion(None, True, since + 1.0, since)
    assert resumed.motion is not None
    assert resumed.motion.state == "moving"
    assert resumed.pending_stop_since_sim is None


def test_founding_none_stays_none() -> None:
    outcome = fold_motion(None, None, 10.0, None)
    assert outcome.motion is None
    assert outcome.pending_stop_since_sim is None


def test_one_true_promotes_to_moving_immediately_from_stopped() -> None:
    """Promotion is instant on a single above-threshold observation --
    module docstring's central asymmetry."""
    held = _stopped(0.0)
    outcome = fold_motion(held, True, 10.0, None)
    assert outcome.motion is not None
    assert outcome.motion.state == "moving"
    assert outcome.motion.established_sim == 10.0


def test_one_false_does_not_demote_moving_immediately() -> None:
    """A single sub-threshold reading is not enough to demote -- the
    confirm window must actually elapse."""
    held = _moving(0.0)
    outcome = fold_motion(held, False, 1.0, None)
    assert outcome.motion is held  # unchanged -- still "moving"
    assert outcome.pending_stop_since_sim == 1.0


def test_demotion_requires_the_full_confirm_window() -> None:
    held = _moving(0.0)
    # Countdown starts at t=1.0.
    outcome = fold_motion(held, False, 1.0, None)
    since = outcome.pending_stop_since_sim
    assert since == 1.0

    # Just short of the window -- still holds at "moving".
    almost = fold_motion(held, False, since + MOTION_STOP_CONFIRM_S - 0.01, since)
    assert almost.motion is held
    assert almost.pending_stop_since_sim == since

    # At (or past) the window -- demotes.
    confirmed = fold_motion(held, False, since + MOTION_STOP_CONFIRM_S, since)
    assert confirmed.motion is not None
    assert confirmed.motion.state == "stopped"
    assert confirmed.pending_stop_since_sim is None


def test_a_true_reading_mid_countdown_cancels_the_demotion() -> None:
    held = _moving(0.0)
    started = fold_motion(held, False, 1.0, None)
    since = started.pending_stop_since_sim
    assert since is not None

    resumed = fold_motion(held, True, since + 1.0, since)
    assert resumed.motion is not None
    assert resumed.motion.state == "moving"
    assert resumed.pending_stop_since_sim is None


def test_none_holds_the_belief_and_the_countdown() -> None:
    """A gap in observation is neither evidence of motion nor a break in an
    in-progress demotion countdown -- both are preserved untouched."""
    held = _moving(0.0)
    started = fold_motion(held, False, 1.0, None)
    since = started.pending_stop_since_sim

    gap = fold_motion(held, None, since + 1.0, since)
    assert gap.motion is held
    assert gap.pending_stop_since_sim == since


def test_none_never_demotes_and_never_promotes_with_no_prior_belief() -> None:
    outcome = fold_motion(None, None, 5.0, None)
    assert outcome.motion is None


def test_reinforcing_moving_refreshes_established_sim_and_raises_confidence() -> None:
    held = _moving(0.0, confidence=0.5)
    outcome = fold_motion(held, True, 5.0, None)
    assert outcome.motion is not None
    assert outcome.motion.state == "moving"
    assert outcome.motion.established_sim == 5.0
    assert outcome.motion.confidence > 0.5


def test_reinforcing_stopped_does_not_touch_pending_countdown() -> None:
    held = _stopped(0.0, confidence=0.5)
    outcome = fold_motion(held, False, 5.0, None)
    assert outcome.motion is not None
    assert outcome.motion.state == "stopped"
    assert outcome.motion.confidence > 0.5
    assert outcome.pending_stop_since_sim is None
