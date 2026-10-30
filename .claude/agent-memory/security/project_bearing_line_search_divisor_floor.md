---
name: bearing-line-search-divisor-floor
description: optic_policy._bearing_line_search_offsets clamps step_deg to a 0.01 floor, so SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION reaching its hi bound (0.8, capped below 1.0) cannot produce a zero-step infinite loop or divide-by-zero index
metadata:
  type: project
---

`belief/optic_policy.py`'s `_bearing_line_search_offsets` (added `plans/atgm-run-sight-tracking/plan.md`,
reviewed at commit `cc6dafac`) computes a per-step depression offset from
`SIGHT_LOCK_SEARCH_STEP_OVERLAP_FRACTION` and an optic's own FOV: `step_deg = fov_full_width_deg *
(1.0 - overlap_fraction)`. This feeds both a `while n * step <= band_half_width_deg` growth loop and,
separately, `_decide_sighting_locked`'s `(now_sim - search_since_sim) // SIGHT_LOCK_SEARCH_STEP_S %
len(offsets)` index calc.

**Why this didn't need a fix**: `step = max(step_deg, 0.01)` floors the offsets-loop's step before use,
so even a zero-FOV optic or an overlap fraction near 1.0 cannot zero it out — tunable's own `hi=0.8`
bound keeps overlap_fraction from reaching 1.0 anyway, belt-and-suspenders. The *other* divisor,
`SIGHT_LOCK_SEARCH_STEP_S`, is a `tuning.real(...)` with a hard `lo=0.3` bound, so it can never reach
`0.0` through the tunable path at all — no runtime floor needed there.

**General lesson for this project**: when a Security deep-analysis finds a tunable feeding a divisor
or a loop-advance, check both (a) whether the *code* floors/clamps it at the use site, and (b) whether
the *tunable's own `lo`/`hi` bounds* already exclude the dangerous value — either alone is sufficient,
and this feature had both. Reviewer's `review.md` for this feature independently verified the same
floor under its own "Cross-key coupling check" heading — a useful cross-check pattern: Reviewer and
Security converging on the same floor from different angles (correctness vs. exploitability) is a
good sign, not redundant work.

See [[tunable-bounds-behaviour-not-safety]] if written later — the broader point that `X-T26`-style
`lo`/`hi` bounds in this codebase are generally chosen for *behavioural* sanity (wasted dwell time,
not a crash), and a Security pass should separately verify the *code* doesn't assume the bound also
rules out zero/negative at a use site, since the tunable mechanism itself doesn't guarantee that.
