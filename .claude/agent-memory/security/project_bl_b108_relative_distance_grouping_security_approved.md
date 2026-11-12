---
name: bl-b108-relative-distance-grouping-security-approved
description: BL-B108's correlated-noise/belief math (estimation.py, position_belief.py) has no network/dependency/eval surface; division-by-range-ratio and matrix-inverse sites are explicitly floor-guarded against zero/degenerate inputs
metadata:
  type: project
---

Security deep analysis (2026-11-01) on `feature/relative-distance-grouping` (BL-B108, six-stage
plan plus a cross-optic amendment) found no security findings. Full report:
`plans/relative-distance-grouping/security-review.md`.

**Why this is a clean pattern worth remembering for future body-layer numerical/belief features:**
the whole feature is in-process arithmetic over already-trusted perception/belief data — new
random-Fourier-feature noise fields, a tiered-optic correlation ladder, Bar-Shalom-Campo fusion —
with zero new dependencies, zero new sockets/HTTP routes, zero new file writes, and no
`eval`/`exec`/`pickle`/`yaml.load`. That is the expected shape for this kind of change in
body-layer: the no-omniscience/belief layer does math, not I/O.

**The one class of risk worth actually checking on this kind of feature — divide-by-range-ratio
and matrix-inverse sites — and how this one got it right:**
- `position_belief.py`'s `lo = max(1.0, min(correlation_range_m, anchor.range_m))` floors the
  divisor before `hi / lo` (feeds a `log()` downstream), so a near-zero or zero range can never
  produce `log(0)`/`inf`.
- `association_over_time.py`'s hypothesis-range scaling guards `percept.range_m > 0.0` explicitly
  before dividing by it.
- `_Matrix2D.inverse`'s `determinant = max(determinant, floor)` before `1/determinant` divisions
  guards near-singular/degenerate covariance.
- `optic_range_correlation`'s `max(k_a, k_b)` denominator is safe because every optic's range-
  sigma-scale tunable has a `lo` bound strictly `> 0` in `config/defaults.toml`, and the tuning
  loader (`src/tuning.py`) rejects an out-of-range override rather than clamping it to 0.

**How to apply:** for a future body-layer feature that adds a new ratio/correlation/inverse over
tunable constants, check these same four shapes (floored divisor, explicit zero-guard, floored
determinant, strictly-positive `lo` bound on anything used as a denominator) rather than assuming
the tuning loader's reject-not-crash posture alone is enough — the loader stops a *bad override*
from reaching the constant, but does not by itself stop the *code* from dividing by a legitimate
small value unless the code also floors/guards it. All four were explicitly guarded here; that is
what let this pass with no findings rather than an assumption.
