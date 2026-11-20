---
name: flight-control-lua-in-band-needs-a-second-frame
description: flight_control.lua's fc_in_band_* flags start false unconditionally at the take frame and only update on the NEXT run_flight_control call -- a take-then-assert-same-frame test always reads "false"
metadata:
  type: feedback
---

In `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`, `law_init_at_take` hard-codes
`in_band_heading = false`, `in_band_altitude = false`, `in_band_speed = false` unconditionally
(the comment in `test_flight_control_lua.py` already says this for heading: "`in_band_heading`
starts `false` unconditionally at `law_init_at_take`"). The take frame itself (`run_active_
frame(t, dt, just_took=true)`) writes outputs and returns **without calling `law_update`** --
the function that actually recomputes `in_band_*` from `abs(measured - goal) <= band`. So:

**A test asserting `fc_in_band_speed`/`fc_in_band_altitude`/`fc_in_band_heading` right after the
take-resolving `run_flight_control` call will always read `"false"`, regardless of whether the
seed was seeded correctly.** You need one *more* `run_flight_control` call after that (any `dt`)
before the flag reflects reality.

**Why this matters for clamp/seed tests specifically**: when the differentiating assertion is
"does `in_band_speed` become true" (goal == measured after a clamp, vs. staying apart if
unclamped), the test is silently vacuous — always "false" — until that extra frame is added. Cost
three failed first drafts on `plans/flight-desired-state/review-s3.md`'s Required Fix 1 Lua test
(`TestUnparkTakeSeedClampsToMode1Limits`) before noticing.

**How to apply**: when writing a Lua take/seed test that reads `fc_in_band_*` right after a take
edge, either (a) follow the existing convention in `TestUnparkTakeSeedsFromMode2SetTargets`/
`TestVoiceTakeIgnoresTheHeldHeading` of running ~50 settle frames afterward, or (b) if you only
need one extra `law_update` pass (e.g. checking an immediate agree/disagree, not convergence over
time), add exactly one more `run_flight_control(t)` call before `push_flight_control_state`.
