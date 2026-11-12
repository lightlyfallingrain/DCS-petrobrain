---
name: harness-resampling-fix-can-falsify-an-existing-guarantee
description: Fixing a test harness's frozen-draw bug (unique ids/time base per trial) can move an existing "always"/100% fence measured under that same bug -- treat it as a stop finding, revert the harness edit, don't patch the fence yourself.
metadata:
  type: feedback
---

**When a plan tells you to fix a cross-time ensemble harness's draw-freezing bug (same
`observation_id`/`t_sim` reused across every trial instead of resampled), run the *other* tests
in that file too, not just the ones the plan is targeting. A fence calibrated under the frozen
draw can be wrong in either direction, and "always folds" / exact-100% assertions are exactly
where it shows up.**

**Why:** `BL-B110` Stage 1b (2026-11-09) instructed a narrow fix — unique `observation_id` and a
per-trial `t_sim`/`poll_key` base (`t0 = trial * 1e-3`) in `test_relative_distance_sweep.py`'s two
cross-time helpers (`_e3_fold_rate`, `_fuse_two_looks`) — to measure a *different* trigger's
false-split rate. Applying only that fix and re-running the whole file (not just the cells the
plan cared about) showed two pre-existing `BL-B108` fences had moved: a same-optic "always folds"
guarantee (asserted at exactly `1.0`) measured 83–86% once the frozen `z_look`/bearing draw was
actually resampled, and a zero-tolerance `assert len(store.contacts) == 1` inside a shared helper
hit an already-known-elsewhere (fenced at ≥90% in a sibling test) non-fold rate once resampling
could reach it. Both fences were calibrated against one lucky frozen draw, not against the
model's real behaviour.

**The mechanism to check for, by name, before trusting a fix is scoped correctly:** grep the
module for every helper that builds an `Observation` via `perturbed_bearing_range`/
`surface_range_estimate` with a **fixed** `observation_id` string and a **fixed** `t_sim` across
a trial loop. The field (`_FIELD_REALISATION_SALT`) being resampled per trial does not resample
`z_look` (keyed by `(optic, poll_key=t_sim)`) or the per-look bearing draw (keyed by
`observation_id` alone) — those two are independent of the salt, so any helper that doesn't also
vary id/time per trial is still giving every trial the same draw for those two terms, no matter
how carefully the salt loop is written.

**How to apply:** when a plan names a narrow scope for this exact fix (specific lines/helpers),
do the narrow fix, but then run the *whole file's* suite, not a `-k` subset, before reporting
done — this is how the two unrelated fences were caught, and the plan's own stop-gate language
("if any fence moves, stop and report both outputs, do not edit the fence") only protects you if
you actually ran the tests that could move. If a fence does move: **revert the harness-fix edit**
(`git checkout -- <file>`) so the committed tree stays green, record both pytest outputs (before/
after) and the measured numbers in the plan and implementation log, and stop — do not widen the
assertion yourself even in a "documented, monitored" form (the pattern this project otherwise uses
for a reported-but-not-fixed defect, [[project_bl_b110...]] Stage 0's `>= 0.15` test). That pattern
is for a defect inside *this* entry's own new work (`BL-B110` Stage 0's own
`test_false_trigger_rate_for_long_gap_stationary_same_group_exceeds_the_gate`, `>= 0.15`); a fence
that belongs to an *already-merged* entry (`BL-B108` here) needs that entry's own sign-off before
its stated guarantee changes, which only the user can give.
