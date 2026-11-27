---
name: rate-cap-test-seed-state-not-closed-loop
description: testing a new rate/bank ceiling in flight_control.lua's heading channel through the full closed-loop toy plant can silently prove nothing, because the heading shaper's own placeholder gain (omega_heading) already caps the realized rate far below any ceiling for a 90deg step -- seed state.r_ref directly instead
metadata:
  type: feedback
---

`test_flight_control_law.py`'s closed-loop toy plant for break/turn scenarios (`_BREAK_PLANT_DRIVER`,
`TestBreakTurnChannel`) never drives the realized heading rate anywhere near 40 deg/s (the break's
own override ceiling) for a bare 90deg heading-goal step, at any speed — measured (not assumed) at
120/180/250 km/h, peak `|r_ref|` tops out around ~9.96 deg/s regardless. This is the critically-
damped shaper's own analytic step-response peak (`~omega_heading * E / e`, independent of any rate
ceiling once the ceiling exceeds that peak), already documented in `TestBreakTurnChannel`'s own
docstring for *bank*, but it applies equally to *rate* — so a new cap added to that same branch
(BL-16 LV-2's `break_max_bank_deg`-derived rate cap) cannot be exercised through the full closed
loop at all: a test asserting "bank/rate approaches the cap" there would pass or fail for reasons
unrelated to the cap.

**How to apply:** when adding a test for a new ceiling/clamp inside `law_update`'s heading-rate
step (or any shaper-gated channel with a similarly slow placeholder gain), seed `state.r_ref`
directly above the new ceiling via `law_init_at_take`'s own `seed.heading_deg` + `measured.r_deg_s`
path (the technique `TestUnparkMidTurnRateNeverSlammedToTheOrdinaryCeiling` already established for
the *old* ceiling) and check the very next `law_update` frame's `r_ref` against
`law_turn_rate_at_bank(new_cap, v_t)` directly. The hard `law_clamp` in that branch dominates a
one-frame overshoot this large regardless of the heading-error term's own sign, so the result is
deterministic and isolated from the shaper's own unrelated slowness — confirmed by mutation (removing
the cap's `math.min` made the seeded test fail red for the stated reason, restored it to green).
Always probe the full closed-loop scenario with a throwaway Lua script first, printing the peak
rate/bank actually reached, before assuming a card-style numeric assertion ("approaches 60 deg") is
writable against it — it frequently is not, at this project's current placeholder gains.
