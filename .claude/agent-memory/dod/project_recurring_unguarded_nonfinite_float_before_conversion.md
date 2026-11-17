---
name: project-recurring-unguarded-nonfinite-float-before-conversion
description: five findings now, across three sessions -- three in one day (2026-10-13) in two body-layer modules, a fourth on 2026-10-30 (BL-B104, a new wire field converted with int() before any isfinite check, at the LAN-HTTP boundary into body-layer), and a fifth on 2026-11-17 (BL-17, the same gap at a non-LAN boundary -- Lua-to-Python action dispatch) -- all a non-finite (NaN/Inf) float reaching an integer conversion or arithmetic expression with no explicit math.isfinite guard. A recurring category, not isolated bugs, and still being caught at Security/DoD rather than earlier, now confirmed to generalize past "wire boundary" to any boundary crossing into a value this codebase did not fully construct itself.
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
5. `BL-17` (2026-11-17, Security deep analysis, `plans/speech-rules/security-stage0-2.md` Required
   Fix 1, `.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lua_action_boundary.md`):
   **the first occurrence at a non-LAN boundary** — `body-layer/src/rules/engine.py`'s
   `_make_action_wrapper` (Lua→Python action-argument validator, `isinstance`-checked but not
   finite-checked before `int(value)`) and its `digits` Lua global (zero validation at all before
   `int(n)`, trivially reachable with an ordinary Lua string slot, not even arithmetic). Fixed and
   mutation-tested, with one extra wrinkle this category had not produced before: the first-pass fix
   degraded both sites uniformly to the existing graceful-failure shape, and Reviewer's re-review
   (`plans/speech-rules/review-security-fix.md`) found that shape *wrong* for the `digits` site
   specifically — it swallowed a rule-author's porting mistake into a silent, unlogged "Unable."
   instead of this project's own "Lua error → logged + 'Action file error.'" contract (D6). The
   right fix per-site is not always "degrade gracefully" — sometimes the correct response to an
   unguarded conversion is to make it *visibly* fail at the layer that already has a logging/rollback
   contract for exactly that.

The common root: a raw float/int entering from somewhere this codebase did not fully construct
itself — DCS telemetry, a wire payload, or (as of finding 5) a sandboxed scripting language's own
runtime values — with no finiteness validation anywhere it crosses in, and every new consumer has
independently had to decide for itself whether to guard, rely on incidental NaN-comparison
semantics, or do neither. **Four occurrences later, a fifth, brand-new feature at a *different kind
of boundary entirely* (Lua, not LAN/HTTP) still made the identical unguarded-conversion mistake on
its own new code.** This confirms the category is not "a wire-parsing habit" — it is "any boundary
where values this codebase did not construct get `int()`/`float()`-converted," and that framing
needs to reach Architect/Implementer time for *any* new boundary, not just new wire fields on
already-known boundaries.

**How to apply.** Three things now, not two:

- **At Reviewer/Security on any new function taking a raw externally-sourced float** (DCS
  telemetry, a wire payload, *or now a sandboxed scripting runtime's own values* -- not only
  ground-truth position/size/velocity), check explicitly whether every operand feeding an integer
  conversion or a multiply/divide is finite-guarded by design or only protected by accident
  (NaN-comparison semantics), per `project_nan_comparison_incidental_guards.md` and
  `project_nan_guard_must_cover_every_operand.md`. Do not assume a sibling function's guard pattern
  transfers without checking, and do not assume the category is scoped to "LAN/HTTP boundary" --
  finding 5 shows it reaches any boundary where a value this codebase did not construct itself gets
  converted.
- **The remedy is not always "degrade gracefully" at every site, even within one fix.** Finding 5's
  own re-review round is the first time this category produced that distinction: two sites with the
  same unguarded-conversion shape needed *different* failure behaviour, because one site
  (`_make_action_wrapper`) already had an established "the caller checks and handles rejection"
  contract and the other (`digits`) had none -- degrading the second the same way as the first hid a
  rule-author bug behind a legitimate-sounding "Unable." with no log. Check the surrounding contract
  per site, not just whether the guard exists.
- **This is process debt, not just code debt, and it has now recurred a fifth time, the first time
  at a boundary class (Lua, not LAN/HTTP) this memory had not yet named, after this exact memory
  already existed to catch it.** The cheaper fix is a single finiteness-validating gate placed where
  raw floats/ints first enter each pipeline (the perception/belief boundary, the schema-parsing
  boundary, *and* the Lua-action-dispatch boundary `rules/engine.py` now owns), rather than
  re-deriving "is this operand guarded" at every new boundary a future feature adds. **DoD's own
  process signal, now sharper**: this pattern is being caught reliably at Security/DoD across three
  different boundary classes, which is working as a gate but demonstrably not as prevention -- the
  lesson from findings 1-4 did not reach whoever designed BL-17's action-wrapper validator, the
  single function whose *whole job* is to be the validation boundary for every future rule-callable
  action. Worth raising at Architect/Implementer time for any plan that introduces a *new kind of
  boundary* at all (not just a new field on an existing one) -- a checklist item ("every new
  `int(raw)`/`float(raw)` conversion on a value this process did not construct itself is
  `math.isfinite`-guarded before conversion, regardless of whether the boundary is HTTP, Lua, or
  something else entirely") would catch this before Security does, rather than after.
