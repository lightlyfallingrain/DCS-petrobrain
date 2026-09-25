---
name: elapsed-time-inflation-quadratic-dt-composition
description: A "hold prior, inflate by elapsed_s" recovery pattern composes non-linearly across repeated polls -- recovery time scales ~1/poll_interval, not a fixed constant.
metadata:
  type: project
---

Found during the `position-belief-runaway` deep security review (`plans/position-belief-runaway/
security-review.md`), on `body-layer/src/belief/position_belief.py`'s `FUSION_SANITY_SIGMA` guard
and `clamp_to_detection_envelope` (both added by that fix, `cd768af`).

**The pattern:** a guard that, on failure, "holds the prior unchanged but still applies elapsed-time
covariance inflation" looks like it gives a bounded, poll-rate-independent recovery time (e.g. "~20s
at `GATE_GROWTH_RATE_MPS`"). It does not, if `elapsed_s` is computed as `t_sim - <the held
estimate's own as_of_sim>` and the held estimate's `as_of_sim` is bumped to the current poll's
`t_sim` on every hold (as both guards here do). Then each poll only contributes
`(rate * poll_interval)**2` to the covariance instead of `(rate * total_elapsed)**2`, and summing
`n` such small contributions over a fixed wall-clock budget gives `rate**2 * T**2 / n` --
*inversely* proportional to poll rate. A scenario that "recovers in ~20s" when tested as a single
big gap can take **minutes** at the project's actual default poll interval (`body-layer`'s
`_DEFAULT_POLL_INTERVAL_S = 1.0` gave 47s vs. the claimed 20s in direct reproduction; 0.05s poll
interval gave ~934s).

**Why this matters:** it is easy to verify a recovery-time claim with a single-gap test (looks
right, matches intuition) and never notice it does not generalize to the continuous-poll case,
which is the actual runtime shape. **Check any "holds + inflates" recovery claim against repeated
small-interval polling, not just a single re-acquisition-after-a-gap scenario**, before trusting a
"~N seconds" recovery figure in a review.

**Not exploitable / not blocked on its own** — no untrusted input, bounded and monotonic (verified
to 200,000 polls with no numerical breakdown), and reported as a Probable-risk finding with
options, not a hard block, per this project's single-user/LAN scoping. Left to user judgment in
`plans/position-belief-runaway/security-review.md`.

**Watch for this same shape elsewhere**: any future `decay.py`/confidence-half-life or
process-noise-style mechanism that resets its own "last updated" timestamp on a no-op/hold tick,
rather than tracking "last genuinely updated" separately, is a candidate for the same defect.
