---
name: project-recurring-unguarded-nonfinite-float-before-conversion
description: seven findings now, across five sessions -- three in one day (2026-10-13) in two body-layer modules, a fourth on 2026-10-30 (BL-B104, a new wire field converted with int() before any isfinite check, at the LAN-HTTP boundary into body-layer), a fifth on 2026-11-17 (BL-17, the same gap at a non-LAN boundary -- Lua-to-Python action dispatch), a sixth on 2026-11-19/20 (fix/handover-ack-seq, the first occurrence on the ENCODE side -- core.lua's fmt_num_or_null blanket-formatted int-strict schema fields as %.5f, silently dropping every flight_control telemetry line for a full day before being traced), and a seventh on 2026-11-25 (BL-B124/BL-B137, a float()-not-int() parse that does not raise on "nan"/"inf" at all, propagating through a clamp to a concrete, silently wrong daylight value -- the worst-consequence instance yet). All a non-finite or wrong-typed numeric value crossing a boundary this codebase did not fully construct, with no validation anywhere it enters or leaves. A recurring category, not isolated bugs, still being caught at Security/DoD/Debugger rather than earlier, now confirmed to generalize past "wire boundary," past "parse side," past "LAN/HTTP," and past "int() raises" to any numeric value crossing any boundary in either direction, including a float() parse that never raises at all.
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

6. `fix/handover-ack-seq` (2026-11-19/20, Debugger, `plans/flight-control/debug.md` second bug;
   also caught and classified correctly by Security as the same category, `plans/flight-control/
   security-handover-ack.md`): the first occurrence on the **encode** side rather than the parse
   side. `aircraft-layer/dcs-export/Petrobrain/core.lua`'s `fmt_num_or_null` formatted every
   number with `%.5f` with no distinction between a measurement and an `int`-strict schema field,
   so a sequence counter went out as e.g. `"-1.00000"`, which `json.loads` parses as a `float` and
   every strict `_optional_int` schema check then rejected — not a crash, a **silently dropped
   wire line**, a failure mode this memory had not yet named. `fc_last_cmd_seq` is never `null`
   (an always-set sentinel), so this dropped every `flight_control` telemetry line for a full day
   (2026-11-18 onward) before being traced past two other symptoms that looked like separate bugs
   (a take-ack seq mismatch, an ack-timeout recovery gap). Fixed with a second formatter,
   `fmt_int_or_null`, used only at schema fields actually declared `int`; `fmt_num_or_null` itself
   also gained the same `is_finite_number` guard this memory already prescribes, so a non-finite
   measurement now encodes as `null` instead of literal `nan`/`inf` text (which is not valid JSON
   either -- the same silent-whole-line-drop failure, reached from the opposite direction).

7. `BL-B124`/`[[BL-B137]]` (2026-11-25, Security deep analysis, `plans/bl-b124-light-level/
   security.md` Finding 1): **the first occurrence where the parse itself never raises at all.**
   `aircraft-layer/src/schema/firing.py`'s `MissionClockSample.from_wire` used `float(abs_str)`
   (not `int()`) for `abs_time_s`, and Python's `float()` happily parses the strings `"nan"`/
   `"inf"`/`"-inf"` without error -- so even a sibling `isinstance`+`int()` guard elsewhere in the
   same dataclass (`year`/`month`/`day`) would not have caught this one by analogy, because the
   failure mode is at the `float()` call itself, not at a later `int()` conversion. Traced
   end-to-end (not just flagged): the NaN propagated through `perception.light_level.
   sun_elevation_deg`'s own final clamp (`max(-1.0, min(1.0, sin_altitude))`, which does not hold
   NaN clean -- `min`/`max` keep their first argument on a NaN comparison) to a concrete `90.0`
   degrees, silently taking the feature's own full-daylight branch -- the one outcome its design
   explicitly forbade for a bad reading. Worst-consequence instance so far: not a crash, not a
   dropped line, a *silently wrong, in-range, plausible-looking answer* with zero logging. Fixed
   at both the wire boundary (`math.isfinite` added to the success condition) and defense-in-depth
   inside `sun_elevation_deg` itself (raises before the clamp). Notes-worthy generalisation filed
   in `notes/wire-protocol-validation.md`.

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

**How to apply.** Four things now, not three:

- **Do not assume "this field uses `float()`, not `int()`, so it's safe" — `float()` is the
  *less* safe conversion for this category, because it never raises on `"nan"`/`"inf"`/`"-inf"`
  at all, where `int()` at least raises `ValueError` on those same strings.** Finding 7 is the
  first instance where the unguarded conversion itself produced zero exception, only a silently
  wrong answer several functions downstream. A `float(x)` parse at any boundary needs its own
  explicit `math.isfinite` check regardless of whether a sibling `int()` field in the same
  structure already has one -- the two conversions fail differently and a fix for one does not
  imply the other is covered.

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
- **This is process debt, not just code debt, and it has now recurred a sixth time, the first time
  on the encode side of a boundary (Lua writing a wire line) rather than the parse side, after this
  exact memory already existed to catch the parse-side version.** The cheaper fix is a single
  finiteness/type-validating gate at both ends of each boundary -- the perception/belief boundary,
  the schema-parsing boundary, the Lua-action-dispatch boundary `rules/engine.py` owns, *and now*
  the Lua-side wire-encoding boundary (`core.lua`'s own `fmt_num_or_null`/`fmt_int_or_null`) --
  rather than re-deriving "is this operand guarded, and does its declared type match the schema on
  the other side" at every new boundary or every new field on an existing one. **DoD's own process
  signal, now sharper still**: this pattern has now been caught at Debugger, Security and DoD
  across four boundary classes and both directions of crossing (parse and encode), which is working
  as a gate but demonstrably not as prevention -- the lesson from findings 1-4 did not reach
  whoever designed BL-17's action-wrapper validator, and the lesson from finding 5 did not reach
  whoever added `fc_last_cmd_seq` to `core.lua`'s wire encoding a day later. One project-wide rule
  would catch every instance found so far: **a numeric value crossing any boundary, in either
  direction, must be both finiteness-guarded and type-matched to the schema on the other side,
  checked by grepping the other side's own validator rather than assuming an existing sibling
  helper already matches it.** Worth raising at Architect/Implementer time for any plan touching a
  wire-encoding or wire-decoding function at all, not only a new field -- this now recurs often
  enough that a mechanical check (every `fmt_*`/`_optional_*` call site cross-referenced against
  the schema it feeds, run once per touch to either side) would be cheaper than catching it by hand
  a seventh time.
