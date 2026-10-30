---
name: fuse-depression-range-in-inverse-distance
description: Fusing a depression-angle range (h/tan δ) with a fractional range judgement must be done in 1/D, not metres — metre-domain inverse-variance fusion measured 1.67x worse than today at 50 m AGL / 500 m
metadata:
  type: feedback
---

When a plan combines a range derived from an angle (D = h / tan δ, the BL-B104 depression cue) with
another range estimate by inverse-variance weighting, **form the mean in inverse distance
(`tan δ / h` is linear in the angle error), not in metres.** Found by a 20 000-draw Monte Carlo
while planning `plans/bl-b104-ground-contacts-on-ground/plan.md` (2026-10-30):

- metres, true-geometry weights: RMS up to **1.67x today's** error and +5 % long bias at moderate
  depression (50 m AGL / 500 m, 150 m / 1 km) — `h/tan δ` is heavy-tailed long when σ_δ is a
  sizeable fraction of δ;
- metres, weights from the perceived angle: over-corrects to −12.6 % short at shallow angles;
- **1/D, true-geometry weights: ≤ 1.0x today at every grid point, bias < 1 %.**

The declared σ (first-order) is identical in all three, so a reviewer comparing the declared
sigmas sees nothing wrong — only a Monte Carlo over the envelope shows it.

**Why:** the plan's first draft used the metre-domain form; a linearised σ table looked fine. The
envelope simulation took two minutes and inverted the design.

**How to apply:** for any estimator mixing a nonlinear-in-angle range with another range, run a
quick deterministic Monte Carlo over the operating envelope (50–800 m AGL × 0.5–6 km, see
[[project_operating_altitude_envelope]]) before writing thresholds into a plan, and make that grid
a control-point test, not a prose claim.
