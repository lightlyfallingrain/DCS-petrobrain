---
name: project-recurring-unguarded-nonfinite-float-before-conversion
description: three findings in one day (2026-10-13) in two different body-layer modules, both involving a non-finite (NaN/Inf) float reaching an integer conversion or arithmetic expression with no explicit math.isfinite guard -- a recurring category, not three unrelated bugs, and a candidate for an earlier check (Architect/plan stage) rather than catching it at Reviewer/Security each time.
metadata:
  type: project
---

Same day, two modules, three distinct findings, all the same shape -- a raw `float` that can be
`NaN`/`Inf` (almost always a ground-truth position, `x`/`z`, with no validation anywhere upstream)
reaches an operation that either raises (`math.floor` -> `ValueError`/`OverflowError`) or silently
corrupts (`NaN * 0.0 == NaN`, propagating through a clamp meant to hold a prior value clean):

1. `body-layer/src/belief/position_belief.py`'s `clamp_to_detection_envelope` holds clean on a NaN
   fused mean only *by accident* -- Python's NaN-comparison semantics (`project_nan_comparison_
   incidental_guards.md`, security memory).
2. The same file's `clamp_fold_displacement`, given an explicit `math.isfinite` guard to fix
   finding 1's sibling case, guarded `fused.x`/`fused.z` but missed a third operand
   (`max_displacement_m`) feeding the identical `dx * scale` expression -- same corruption, through
   a different unguarded float (`project_nan_guard_must_cover_every_operand.md`, reviewer memory).
3. `body-layer/src/perception/forest.py`'s `ForestOcclusion.occluded` (this feature,
   `forest-occlusion`) fed unguarded `x`/`z` straight into `math.floor` inside `_cache_cell_key`,
   one layer *upstream* of (1)/(2) -- the first point in the whole naked-eye gate chain where a
   non-finite position stops being silently tolerated (every earlier gate's comparisons are
   NaN-safe by the same incidental mechanism as finding 1) and starts raising, killing the
   perception logger's plain poll loop for the rest of the sortie
   (`project_forest_occlusion_nonfinite_position_crash.md`, security memory).

**This is now a recurring category, not three unrelated one-off findings**, and it has recurred
within a single body-layer module (position_belief.py, twice) and then immediately again in a
sibling module one gate upstream. The common root: `candidate.x`/`candidate.z` is raw
`LoGetWorldObjects` ground truth with no finiteness validation anywhere it enters this codebase,
and every function downstream has independently had to decide for itself whether to guard, rely on
incidental NaN-comparison semantics, or do neither.

**How to apply.** Two things, not one:

- **At Reviewer/Security on any new function taking a raw ground-truth float** (position, size,
  velocity -- anything derived from DCS telemetry before a validating gate), check explicitly
  whether every operand feeding an integer conversion or a multiply/divide is finite-guarded by
  design or only protected by accident (NaN-comparison semantics), per `project_nan_comparison_
  incidental_guards.md` and `project_nan_guard_must_cover_every_operand.md`. Do not assume a sibling
  function's guard pattern transfers without checking.
- **This is process debt, not just code debt, once a category hits three occurrences in one
  codebase in one day.** The cheaper fix is a single finiteness-validating gate placed where
  ground-truth floats first enter the perception/belief pipeline (e.g. at `Percept`/
  `percept_of`'s boundary, or wherever `LoGetWorldObjects`-derived candidates are first
  constructed), rather than re-deriving "is this operand guarded" at every downstream function
  that happens to do arithmetic on `x`/`z`. Worth raising at Architect for the next feature that
  touches this chain, rather than waiting for the fourth occurrence to be caught at Reviewer or
  Security again.
