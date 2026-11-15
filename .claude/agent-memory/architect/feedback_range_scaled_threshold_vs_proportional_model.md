---
name: feedback_range_scaled_threshold_vs_proportional_model
description: Before designing a range-scaled "good enough" threshold that would trigger a look, check how the error model scales -- body-layer's naked-eye range sigma is exactly 0.17*R (only smaller with altitude), so a proportional allowance is all-or-nothing, never selective (BL-B110 fifth pass, 2026-11-02)
metadata:
  type: feedback
---

A threshold of the form "act when belief error > allowance(R)" only selects *some* contacts if the
error and the allowance scale differently with R. body-layer's naked-eye down-range sigma is
`RANGE_FRACTIONAL_SIGMA * R` = 0.17 R (a plain constant), cross-range 3 deg, and the depression cue
only ever tightens it. So any allowance k*R either fires on every contact (k < 0.17) or none
(k >= 0.17); an absolute floor (e.g. 250 m, half the spoken 0.5 km step) changes nothing above it.
For BL-B110 that meant "priority 1, rough location" needed no binocular look at all -- the scan
was the whole answer -- and the planned look machinery shrank to watched contacts only.

**Why:** the fourth pass had designed per-group location looks for every contact beyond ~2 km;
measuring the model's scaling (one short script over `look_sigma_m` / the cue fusion) showed
the premise was empty.

**How to apply:** when a plan proposes "look again if the position is worse than X at this range",
tabulate the shipped sigma over the operating envelope (0.5-6 km, 0-800 m AGL) first, and check
which tuning keys could move it. If no shipped key can break the conclusion, fence it with a test
rather than adding a tunable nothing reads. Related: [[feedback_run_the_belief_forward_after_the_benefit]].
