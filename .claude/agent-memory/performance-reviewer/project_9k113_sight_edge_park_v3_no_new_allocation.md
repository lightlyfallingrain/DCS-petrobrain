---
name: 9k113-sight-edge-park-v3-no-new-allocation
description: BL-B80 v3 Stage 6 (field_target clip + mark_is_clipped, run_sight_servo) added per-frame arithmetic only, no new allocation or device reads — confirms the per-frame closure baseline held
metadata:
  type: project
---

Reviewed `feature/9k113-sight-edge-park` (tip `e1d9f985b7`), Stage 6 of
`plans/9k113-sight-pointing/plan.md` v3 — replaced the wrong-magnitude `setpoint_inside_field` gate
(checked the setpoint against the 60° gimbal limit, not the ASP-17's real ~4.3° field) with
`sight_mark_is_clipped` (mark's own raw reading vs. the field) and a new `sight_clip_to_field_body_
deg` ray-to-box clip feeding `field_target`, always closed-loop now (`open` mode deleted, replaced
by capped `homing`).

**Result: no new allocation, no new per-frame device reads in the always-on path.** Both new
functions (`sight_clip_to_field_body_deg`, `sight_mark_is_clipped`) are top-level named functions
over scalars, called from `run_sight_servo` — not closures, return multiple scalars not a table.
The `m566`/`m555` `GetDevice(0)` reads they consume were already being made every frame by the
code they replaced (`mark_valid`'s own check) — reused, not duplicated. `push_slew_trace` (the
`SLEW_DEBUG`-gated per-frame probe) did gain two more `GetDevice(0)` calls (raw 566/555 for
calibration), but it's a no-op unless the debug flag is set, consistent with
[[project_export_lua_per_frame_push_functions]]'s MONITOR disposition for debug-only additions.

**Why worth keeping**: confirms [[project_export_lua_per_frame_closures_are_established_pattern]]'s
prediction held for a stage that removed a whole branch and added two new per-frame pure
functions — a plan-stated reason for its own dedicated perf pass (`implementation.md` line ~805-809)
that turned out to cost nothing new. Re-affirms: judge new `run_sight_servo` per-frame additions
against allocation/device-read count, not against "more functions were added."
