---
name: project_bl_b80_v2_t_sim_unbounded_in_stated_bounds
description: BL-B80 v2's sight_target bounds sentence names az/el/rate as finite+bounded but omits t_sim, which feeds a clamp()'s subtraction directly -- required addition at plan review, same shape as the corrected extract_json_number_field finding
metadata:
  type: project
---

`plans/9k113-sight-pointing/plan.md` (v2, 2026-10-22 re-plan) reshapes the `sight_target` wire
payload to `{goal_az, goal_el, goal_rate_az, goal_rate_el, t_sim}` and states: *"Bounds: az ∈
[−360, 360], el ∈ [−90, 90], |rate| ≤ 30 °/s, all finite; enforced in the API and in Lua"* —
naming three of the five fields. `t_sim` is used two lines later directly in
`goal(t) = goal + rate·clamp(t − t_sim, 0, cap)`, evaluated every Export.lua frame.

**Why this matters despite the `clamp`:** `clamp(·, 0, cap)` bounds the extrapolation term for any
*finite* `t_sim`, however stale or future-dated. It does not bound it for a non-finite one — `t −
t_sim` with `t_sim = NaN` yields `NaN`, and Lua's `<` comparisons (which any hand-rolled `clamp`
uses) are all false against `NaN`, so the result depends on the exact `clamp` implementation
rather than being structurally guaranteed. A `NaN`/`Inf` `goal(t)` would then reach the
rate-limited setpoint step, with the gimbal clamp as the only remaining backstop.

**Same shape as [[project_export_lua_json_extractor_cannot_yield_nonfinite]]**: "the parser can't
produce X so a downstream guard is dead code" was wrong there because it was a claim about the
parser's accepted grammar, not the inputs anyone had tried. Here the analogous unstated assumption
would be "`t_sim` is only ever a sane value because that's what a correct sender sends" — not a
property the wire format enforces by itself.

**Flagged in `plans/9k113-sight-pointing/security-plan-review.md` (v2) as a required, narrow
addition** (not a plan rejection): add `t_sim` to the bounds/finite-check sentence, and give it the
same missing/non-finite → reject-the-command treatment `az_cmd`/`elev_cmd` already have in v1's
`handle_sight_target_command`. Since `extract_json_number_field` already guarantees
absent/non-numeric/non-finite → `nil` (the corrected memory above), the fix is a presence check on
the Lua side plus a matching `isfinite` check on the API side — small, but needs writing into the
Implementation Plan explicitly.

**How to apply:** when a plan's stated "bounds" sentence lists some fields of a new wire payload
and not others, check every field actually used in Lua/Python arithmetic downstream — not just the
ones the sentence names — especially a timestamp/time-delta field feeding a `clamp` or similar
bound, where "the bound protects me" is only true given finiteness upstream of it.
