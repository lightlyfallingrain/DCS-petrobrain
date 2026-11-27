---
name: bl16-lv3-hover-blend-bounded-scalar-cost
description: BL-16 LV-3 (hover/low-speed regime, lambda blend, yaw damper, hover pedal band, goal slew) adds only bounded scalar arithmetic to law_update (30 Hz) and law_outputs (140 Hz), no new per-frame allocation or LoGet* call -- confirmed by reading call sites, not the plan's prose
metadata:
  type: project
---

LV-3 (`plans/flight-lift-vector/plan.md`, "LV-3 amendment (2026-11-27)") added the hover/forward
blend (`λ`), an all-speed yaw damper, a hover yaw-rate integral, a hover pedal band, and a
low-speed goal-acceleration slew to `flight_control.lua`'s `law_update`/`law_outputs`. Reviewed at
tip `3fdc7bae`. Every addition is scalar arithmetic over existing locals/state fields — no new
table, string or closure allocation anywhere in the diff; `law_lambda` is a pure function; the
`next_state` `pairs`-copy table in `law_update` already existed pre-LV-3, not a new allocation this
batch adds.

**Frequency, confirmed by reading call sites rather than trusting the plan's own wording:**
`law_outputs` and the output write are still every DCS frame (~140 Hz, `flight_control.lua:3265/
3279/3378`); `law_update` is still gated to `law_hz` (~30 Hz, unchanged `run_active_frame` gating);
`reseed_from_measured` (and its two new getters `get_lambda`/`get_take_speed_kmh`) runs only on a
take/mode-transition edge (`flight_desired.lua`'s `tick`, the `new_mode ~= fd_mode` branch) —
**not** per frame, despite being described in the plan as "mirrors the take rule."

**Lua budget measured independently with `luac5.1 -l`, matched the implementer's report exactly**:
`law_update` 8/60 upvalues, `run_active_frame` 34/60, `run_flight_control` 38/60 (the implementer's
combined "38/60" note is the higher of the two — verify both separately next time, they differ),
module-level locals 124/200 (`main` chunk). `run_flight_control` at 63% of its own ceiling is the
one to re-measure first at the next BL-16 stage (SAU), not assume stable.

**Reusable lesson for this role:** when a plan describes a getter as "mirroring the take rule" or
similar, grep the actual call site before rating its frequency — the two new `flight_control`
getters this stage added (`get_lambda`, `get_take_speed_kmh`) sound like they could be per-frame
telemetry reads from the plan's prose alone, but are edge-triggered (take only). Don't infer hot-
path membership from a function's *name* or its *module* — check who calls it and how often.

See [[project_bl16_lv_estimator_ring_buffers_confirmed_fixed]],
[[project_lv_plan_estimator_every_mode_and_dual_velocity_source]] — this is the LV-3 sequel to
those LV-0/LV-1/LV-2 findings; the estimator's own `v_g`/`v_g_f`/`v_g_r` fields LV-3 reads for the
blend were already computed at law rate by LV-0/LV-1, not newly added reads.
