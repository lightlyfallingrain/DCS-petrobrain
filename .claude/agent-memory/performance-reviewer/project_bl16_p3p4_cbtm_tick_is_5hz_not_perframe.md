---
name: bl16-p3p4-cbtm-tick-is-5hz-not-perframe
description: ai_pilot_cbtm_tick (BL-16 mode 2 Stages P3+P4) runs from the 5 Hz export tick via update_ai_pilot_wheel_overlay, not per DCS frame -- confirm call graph before assuming a name like "*_tick" is on the per-frame path
metadata:
  type: project
---

Dispatching prompt for the BL-16 mode 2 Stages P3+P4 perf pass (diff `3107a662..6e0421e3`) named
`ai_pilot_cbtm_tick` alongside `run_ai_pilot_wheel` as a "DCS frame budget" hot-path concern. The
call graph says otherwise: `aircraft-layer/dcs-export/Export.lua`'s `LuaExportAfterNextFrame`
only calls `update_ai_pilot_wheel_overlay` (the sole caller of `ai_pilot_cbtm_tick`,
`ai_pilot_wheel.lua:1540`) *after* `core.tick_due(t)` gates it to the existing 5 Hz export cadence
(`Export.lua:419-442`) -- a deliberate perf fix this module's own docstring attributes to `plans/
flight-control/perf-batch-a.md` (move anything that needs a fresh `list_indication` overlay read
off the per-frame path, since the overlay itself only updates at that cadence). `run_ai_pilot_
wheel` is the actual per-frame function (`Export.lua:417`, unconditional, ~140 fps); P3+P4's only
addition to *that* function is one more O(1) pending-release deadline check.

**Reusable lesson**: a function name ending in `_tick` is not evidence of its call frequency in
this file -- this codebase already has at least two tiers of "tick" (per-frame `run_ai_pilot_
wheel`/`sight_servo_tick`/`run_flight_control`, vs. 5 Hz `update_ai_pilot_wheel_overlay`/the
various `push_*_state` functions). Before writing a frame-budget finding, grep the caller chain
back to `Export.lua`'s `LuaExportBeforeNextFrame`/`LuaExportAfterNextFrame` and check whether the
call sits before or after that function's own `core.tick_due(t)` gate (`Export.lua:419-421`), not
the name or the dispatching prompt's own framing.

See also [[project_bl16_m1_m2_redundant_envelope_measured_reads]] (the sibling M1/M2 perf finding
this same file's `check_envelope`/`read_measured` had, since fixed -- confirmed resolved by this
pass, `flight_control.lua:869`'s own comment citing `perf-m1-m2.md` finding 1).
