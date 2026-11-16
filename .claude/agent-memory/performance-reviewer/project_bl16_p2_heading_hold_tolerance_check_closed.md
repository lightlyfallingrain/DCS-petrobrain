---
name: bl16-p2-heading-hold-tolerance-check-closed
description: BL-16 Stage P2's heading hold-and-poll (5 Hz, 5-deg tolerance) checked against the plan's own P0-2 course-press-rate measurement (~2 deg/0.7s) -- worst-case per-tick step (~0.57 deg) is well inside the band, same arithmetic shape as the altitude check in project_bl16_held_press_5hz_tolerance_check.md. Closes the MONITOR item that memory named for "Stage P2's own heading/speed holds."
metadata:
  type: project
---

`plans/flight-control/perf-p2.md` performed the check `[[project_bl16_held_press_5hz_tolerance_check]]`
flagged as owed for Stage P2: is a 5 Hz readback poll fast enough to release a held heading
correction without overshoot, now that P2 reuses Stage P1's altitude hold-and-poll shape for a
second parameter (`ai_pilot_goal_tick_heading`, `aircraft-layer/dcs-export/Petrobrain/
ai_pilot_wheel.lua`).

**The numbers**: the plan's own P0-2 measurement (`plans/flight-control/plan.md` line 803) —
"0.7 s reliably reads as long ... course ±2° per hold" — gives a course press rate of
≈2.9°/s. One 5 Hz tick (0.2 s) moves the held heading ≈0.57° worst case, against a
5° (`AI_PILOT_HEADING_TOLERANCE_DEG`) tolerance band. Step well inside the band, same
"step-smaller-than-band" sufficiency argument the altitude check already used.

**Speed does not need this check**: `ai_pilot_goal_tick_speed` is a single tap per tick, not an
accumulating hold, so there is no step-vs-band question — P0-4's measured ~0.007 s readback
latency already answers it (a tap's effect is visible well within the next tick).

**Reusable point**: when a new parameter reuses an already-validated hold-and-poll shape, the
check is "does *this* parameter's own measured press rate fit inside *its own* tolerance band" —
re-derive per parameter (course rate ≠ altitude rate, 5° ≠ 20 m), don't assume the shape being
proven once elsewhere clears every reuse of it automatically. It happened to be true here, but the
arithmetic has to be re-run, not inherited.
