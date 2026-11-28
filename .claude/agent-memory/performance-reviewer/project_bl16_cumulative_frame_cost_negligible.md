---
name: bl16-cumulative-frame-cost-negligible
description: BL-16's whole Lua-side per-frame compute addition (read_measured, law_outputs, law_update, terrain projection), summed across every stage, measures ~130 us of CPU/sec against a multi-ms frame budget -- never the real risk in this module; disk I/O and call-rate multipliers are.
metadata:
  type: project
---

Did a cumulative (all-stages) BL-16 performance pass (`plans/flight-lift-vector/performance-bl16-full.md`,
2026-11-28, diff `1561d370..cf03d63e`) after ~15 per-stage passes already existed. Microbenchmarked
the real operation mix with interpreted `lua`/`luajit -joff` as Lua-5.1 stand-ins, counting actual
`math.*` call counts in the real `law_update` (46 calls over 850 lines, mostly `max`/`min`/`abs`,
no `sin`/`cos`/`atan` at all -- cheaper than the line count suggests) rather than assuming a shape.

**Result: `read_measured` (~0.4 us/call @140Hz), `law_outputs` (~0.04 us/call @140Hz), `law_update`
(~0.3 us/call @30Hz gated), terrain projection (~1.9 us/call, 16 small tables, @30Hz gated) sum to
roughly ~130 us of CPU per second.** A DCS frame budget is multiple *milliseconds* (7.1ms @140fps,
16.7ms @60fps) -- three to four orders of magnitude of headroom. **Table allocation (one 22-field
table/frame, ~16 small 2-field tables/law_hz-tick) is fixed-size and bounded regardless of contact
count or session length, so GC pressure stays flat, not growing.**

**Lesson for next pass on this module**: don't re-derive this from scratch -- the Lua-side compute
cost in `Export.lua`/`flight_control.lua` is settled as negligible. What actually matters here,
confirmed across every pass to date, is (1) call-rate multipliers on expensive DCS-engine calls
(`list_indication`, any `LoGet*`) -- unmeasured-from-here engine cost times a frame-rate multiplier
is the real risk class (`perf-batch-a.md`'s `list_indication` finding), and (2) blocking I/O on the
render thread (`flight_trace_log`'s `write()+flush()` at ~30/s when `FLIGHT_TRACE_ENABLED` --
MONITOR, debug-flag-gated, not NOW). Don't spend a pass re-benchmarking scalar Lua arithmetic in
this file again absent a new heavy transcendental-math addition (sin/cos/atan in a per-frame loop
would be the thing to re-measure).
