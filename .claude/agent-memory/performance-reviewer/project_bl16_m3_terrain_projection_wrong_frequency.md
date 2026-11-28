---
name: bl16-m3-terrain-projection-wrong-frequency
description: M3's terrain projection in run_active_frame allocates N+1 fresh tables every DCS frame (~140 Hz) but only law_update (~30 Hz, gated) ever reads measured.terrain -- the first per-frame allocation scaling with N this file has ever added, measured and judged MONITOR not NOW
metadata:
  type: project
---

BL-16 M3 (`plans/flight-lift-vector/plan.md`, section E) added a terrain-grid projection to
`run_active_frame` (`flight_control.lua:3453-3467`) that runs unconditionally every DCS frame
(~140 Hz, `run_flight_control`'s own "Every frame" comment) and allocates a fresh outer table
plus one `{d, T}` table per grid point (up to `MAX_TERRAIN_POINTS`, 32) whenever a fresh/in-age/
valid grid exists — the common case for the whole sortie once the LOS Hook is up. The only
consumer, `law_update`'s `law_terrain_w_floor` call, runs gated at `profile.law_hz` (~30 Hz,
`law_due()`), so roughly 4.5 out of 5 projections are computed and discarded the same frame,
unread. Through LV-3, this role's own prior review (`project_bl16_lv3_hover_blend_bounded_
scalar_cost`) had confirmed "no new table, string or closure allocation anywhere" in this file —
M3 is the first stage to add a per-frame allocation that scales with N (grid size), not just more
scalar arithmetic or more closures of the same shape.

**Measured before judging severity** (`luajit -joff` and vanilla `lua 5.5`, closer to DCS's
un-JITted Lua 5.1 than JIT-compiled LuaJIT): at N=16, the allocating shape costs ~0.9-1.5 µs/call
vs. ~0.25-0.4 µs/call for an equivalent that reuses two preallocated parallel arrays instead of
fresh tables — a real ~3-4x difference in isolation, but at 140 Hz the allocating version's total
overhead is only ~0.13-0.21 ms of CPU per second against a ~7.14 ms per-frame budget (~0.02-0.03%
of real time), and the garbage volume (~100 KB/s) is well within what any Lua GC absorbs without
a visible pause. **Judged MONITOR, not NOW** — this is the "measure n before scaling anything by
n" lesson applied to a qualitative GC-pressure worry rather than a raw count: the shape is real
and the pattern is worth fixing opportunistically (reuse fixed-capacity parallel arrays, the same
shape this file's own estimator ring buffers already use — `est_ring_*`), but the measured
absolute cost does not clear this role's own "credible risk at realistic scale" bar today. Would
re-open if `MAX_TERRAIN_POINTS` (currently 32, protocol constant) grows, or if a future stage
stacks another per-frame N-scaling allocation onto the same function — the pattern compounds even
though any one instance measured small.

**Reusable lesson for this role**: "function X only runs every frame" is not the same claim as
"the data X is building is only *needed* every frame" — check who actually *reads* a per-frame
computation's result and at what rate, the same way `project_bl16_p3p4_cbtm_tick_is_5hz_not_
perframe` already established for call-rate claims generally. Here the write side (`run_active_
frame`) is unconditionally per-frame but the read side (`law_update`) is rate-gated, so most of
the work is thrown away — a "work at the wrong frequency" finding that would be invisible from
reading `law_update`/`law_terrain_w_floor` alone, only visible by tracing `measured.terrain`'s
producer and consumer separately.

See [[project_bl16_lv3_hover_blend_bounded_scalar_cost]] (the prior "no new allocation" baseline
this stage breaks), [[project_bl16_p3p4_cbtm_tick_is_5hz_not_perframe]] (the call-graph-over-name
lesson this finding reused), [[feedback_measure_claimed_anchor_regressions]] (measure before
accepting a magnitude claim — here the magnitude ended up smaller than the qualitative shape
suggested, the same direction-right-magnitude-wrong pattern).
