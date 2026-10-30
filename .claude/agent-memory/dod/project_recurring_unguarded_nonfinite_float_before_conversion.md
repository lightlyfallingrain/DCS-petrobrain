---
name: project-recurring-unguarded-nonfinite-float-before-conversion
description: four findings now, across two sessions -- three in one day (2026-10-13) in two body-layer modules, plus a fourth on 2026-10-30 (BL-B104, a new wire field converted with int() before any isfinite check, at the LAN-HTTP boundary into body-layer) -- all a non-finite (NaN/Inf) float reaching an integer conversion or arithmetic expression with no explicit math.isfinite guard. A recurring category, not isolated bugs, and still being caught at Security/DoD rather than earlier.
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

**This is now a recurring category, not isolated findings**, and it has recurred within a single
body-layer module (position_belief.py, twice), then immediately again in a sibling module one gate
upstream, and now a fourth time in a different feature entirely:

4. `BL-B104` (2026-10-30, Security deep analysis, `plans/bl-b104-ground-contacts-on-ground/
   security-review.md` Finding 1): the feature's own new wire fields (`category`/`subcategory`,
   `Type.level1`/`level2` forwarded from `Export.lua`) were converted with `int(raw)` after only an
   `isinstance` type check, at **two** sites — `aircraft-layer/src/schema/world_objects.py`'s
   `_optional_int` (type-checked but not finite-checked) and, worse, `body-layer/src/perception/
   association.py`'s `WorldObjectCandidate.from_dict` (no type guard at all) — the latter reachable
   at the LAN-HTTP boundary (`GET /world_objects/latest`) without a live DCS session, since
   `json.loads` accepts the non-standard `NaN`/`Infinity` literals by default. Both fixed with the
   same `math.isfinite` guard this memory already prescribes, closed and mutation-tested.

The common root: a raw float/int straight off DCS telemetry or a wire payload, with no finiteness
validation anywhere it enters this codebase, and every new consumer has independently had to decide
for itself whether to guard, rely on incidental NaN-comparison semantics, or do neither — and three
occurrences later, a fourth, brand-new feature still made the same unguarded-conversion mistake on
its *own* new field, not an old one.

**How to apply.** Two things, not one:

- **At Reviewer/Security on any new function taking a raw ground-truth float** (position, size,
  velocity -- anything derived from DCS telemetry before a validating gate), check explicitly
  whether every operand feeding an integer conversion or a multiply/divide is finite-guarded by
  design or only protected by accident (NaN-comparison semantics), per `project_nan_comparison_
  incidental_guards.md` and `project_nan_guard_must_cover_every_operand.md`. Do not assume a sibling
  function's guard pattern transfers without checking.
- **This is process debt, not just code debt, and it has now recurred a fourth time, in a
  different feature, after this exact memory already existed to catch it.** The cheaper fix is a
  single finiteness-validating gate placed where raw floats/ints first enter the perception/belief
  pipeline (e.g. at the schema-parsing boundary itself, or `Percept`/`percept_of`'s boundary),
  rather than re-deriving "is this operand guarded" at every new wire field a future feature adds.
  **DoD's own process signal**: this pattern is being caught reliably at Security/DoD, which is
  working as a gate but not as prevention — a new feature (`BL-B104`) added a new wire field and
  made the identical mistake on it, meaning the lesson from findings 1-3 did not reach whoever
  wrote the Stage 1 wire parsing for finding 4. Worth raising at Architect/Implementer time for any
  plan that adds a new numeric field crossing a LAN/wire boundary — a checklist item ("every new
  `int(raw)`/`float(raw)` conversion on externally-sourced data is `math.isfinite`-guarded before
  conversion") would catch this before Security does, rather than after.
