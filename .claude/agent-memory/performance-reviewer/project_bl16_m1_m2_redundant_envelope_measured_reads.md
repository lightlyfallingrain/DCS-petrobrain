---
name: bl16-m1-m2-redundant-envelope-measured-reads
description: BL-16 mode 1 M1/M2's check_envelope and read_measured (flight_control.lua) independently re-read LoGetSelfData/LoGetIndicatedAirSpeed/LoGetADIPitchBankYaw every active frame -- change requested, see plans/flight-control/perf-m1-m2.md
metadata:
  type: project
---

`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`'s `run_active_frame` calls
`check_envelope(t)` then, if it passes, `read_measured()` -- both functions independently call
`LoGetSelfData`, `LoGetIndicatedAirSpeed`, and `LoGetADIPitchBankYaw`, every single active frame
(mode 1, unconditional `LuaExportBeforeNextFrame`, ~140 fps). Three native DCS-engine-boundary
calls paid twice per frame for no reason -- `check_envelope` only needed the `ias_mps`/`bank_deg`
scalars `read_measured` was about to compute anyway.

**Reusable lesson, generalizing [[project_flight_control_p1_perframe_indication_read]]**: that
earlier finding was about two *different* functions/features duplicating one expensive device
read across a 5 Hz vs. per-frame boundary. This is the same mistake shape *within one new
module*: two sibling functions called back-to-back in the same frame, each independently reading
the DCS engine rather than one reading it once and handing the result to the other. Before
approving any new per-frame function in `Export.lua` that calls `LoGet*`, check what the
function(s) it is called alongside in the same frame already read -- not just what a *different*
polling tier already reads.

**Mitigation requested**: `check_envelope` should take `read_measured`'s own output (already has
`ias_mps`/`bank_deg` as `ias_mps`/`bank_deg` fields) instead of re-reading; its `self_data`-is-a-
table liveness check ("dead" cause) is the one read worth keeping separate, or can be folded into
`read_measured` returning an extra flag.

See also [[project_export_lua_per_frame_push_functions]] -- this same batch's
`update_live_seat_tracking` (unconditional every frame, every `fc_mode`) adds up to 6 more
uncached `GetDevice(0)` lookups/frame on top of that memory's already-flagged 12, crossing its own
named "fourth such function" re-open threshold. Judged MONITOR, not NOW, consistent with that
memory's own posture (unmeasured per-call cost, no live-DCS profiler in this repo, no reported
symptom) -- but the next time this file is touched, cache one `GetDevice(0)` handle per frame and
thread it through `read_axis`/the `push_*` functions, across the whole file in one pass.
