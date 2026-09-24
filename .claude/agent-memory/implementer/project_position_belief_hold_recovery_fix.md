---
name: position-belief-hold-recovery-fix
description: fix/position-belief-runaway security-followup — hold-recovery timing bug and the general pattern that caused it
metadata:
  type: project
---

`body-layer/src/belief/position_belief.py`'s two "hold the prior" branches
(`fold_position`'s `FUSION_SANITY_SIGMA` guard, `clamp_to_detection_envelope`) used to reset
`PositionEstimate.as_of_sim` on every hold and inflate elapsed time against that reset stamp.
Under continuous polling this composes `(rate * dt) ** 2` once per poll instead of `(rate * T) **
2` once per `T`-second gap — summing `n` squared pieces of a fixed budget is always less than
squaring the whole budget — so recovery time scaled as ~`1 / poll_interval_s` (measured ~47s at
the real 1.0s default, ~934s at 0.05s) even though the merged review's approval rested on a
single-gap ~20s figure.

**The general pattern, worth recognizing elsewhere in this codebase**: any "hold the last value,
inflate for elapsed time" branch that recomputes its own timestamp on every hold is a quadratic
under-inflation bug waiting to happen under tight polling, *not* just under this one guard. The
fix is always the same shape — track two timestamps with different meanings (last-updated-for-
display vs. last-genuinely-changed-by-evidence) and always inflate the *evidence* timestamp's own
un-inflated base fresh, never an already-inflated value from the previous poll. Here that's
`PositionEstimate.fused_at_sim`/`fused_covariance` alongside `as_of_sim`/`covariance`, and a
single `_inflated_since_last_fuse` helper every hold/fuse site goes through — worth grepping for
this shape (`.inflated(elapsed_s)` where `elapsed_s` is computed from a timestamp the same
function might have just reset) before adding a new hold-and-decay mechanism.

Regression test for this class of bug: don't just check "recovers eventually" — chain the same
scenario through many polls at two very different intervals and assert both land within one
shared bound of each other. A single-poll-gap test cannot see this bug at all; it only shows up
under repeated holds.

See `plans/position-belief-runaway/debug.md`'s 2026-09-25 addendum for the full fix.
