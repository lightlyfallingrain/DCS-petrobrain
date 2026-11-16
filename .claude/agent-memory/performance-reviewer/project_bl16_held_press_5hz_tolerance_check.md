---
name: bl16-held-press-5hz-tolerance-check
description: How to check whether a 5 Hz readback-poll is fast enough to release a held AI-pilot-wheel press without overshoot -- compare one-tick step distance against the tolerance band width, using the measured press rate, not an assumption
metadata:
  type: project
---

BL-16's takeover revision (`plans/flight-control/plan.md`, "Revised 2026-11-16") added a
closed-loop altitude correction: hold `AI_WHEEL_UP`/`AI_WHEEL_DOWN` open, re-check the readback
only at the 5 Hz `list_indication(6)` tick (`ai_pilot_check_hold_convergence`, run from
`update_ai_pilot_wheel_overlay`), release the instant it reads within `AI_PILOT_ALT_TOLERANCE_M`
(20 m) of target. The question "is 5 Hz fast enough, or does it blow through the tolerance band
between checks" is a real performance-adjacent question for any future hold-and-poll loop in this
file (flagged explicitly for Stage P2's own heading/speed holds).

**The check, done here and reusable:** take the *measured* press rate (not an assumed one — the
rehearsal probe measured ~16 m/s for the first 2.5 s, then ~50 m/s), multiply by the tick period
(0.2 s at 5 Hz) to get the worst-case single-tick step (≤10 m here), and compare it against the
tolerance band width (20 m here). If the step is smaller than the band, the loop cannot jump over
the band in one tick when approaching from outside it — the worst-case overshoot past the boundary
is bounded by the step size itself, which still lands inside the band. **This is a one-line
arithmetic check, not a reason to speed up the poll** — do it before flagging a hold-and-poll loop
as a performance risk, and before assuming a faster tick is needed. If a future hold's measured
rate times the tick period exceeds its own tolerance band, that is the actual trigger to revisit
the tick rate, not before.

See also [[project_flight_control_p1_perframe_indication_read]] (the device-read-rate mitigation
this stage preserved) and `plans/flight-control/perf-batch-a.md`'s own MONITOR item this
calculation answers.
