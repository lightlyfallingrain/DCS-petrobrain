---
name: bl16-lv1-decel-blade-stall-threshold-approved
description: BL-16 LV-1 decel-altitude fix round 3 approved -- blade-stall threshold was the real defect (250->335 km/h), not just the rate-vs-value mechanism; debugger's own named target speeds (150->60) are worth independently probing even when not in the committed tests.
metadata:
  type: project
---

Round 3 of the BL-16 deceleration-altitude fix (`plans/flight-lift-vector/debug-2026-11-27.md`)
corrected `RETREATING_BLADE_STALL_IAS_KMH` from 250 to 335 km/h, re-based on the DCS V_NE table,
after round 2 traced the residual -19.3 m altitude dip (under shipped gains) to the guard's own
threshold rather than the rate-vs-value mechanism round 1 fixed. Reviewed and approved
(`review-debug-1127-r3.md`).

**What this round taught, worth repeating:** the debugger's own committed scenario used
273->108 km/h (the sixth re-fly's actual trace). The user's sortie feedback separately named
"command to speed 60" as the scenario where a *different*, deferred issue (late pedal near 60)
showed up. When a debug report names one scenario and the user's feedback names another nearby
one, independently running the untested one (150->60 here) is cheap with the same toy-plant
harness already in the test file, and is exactly the kind of gap a reviewer should close rather
than assume is covered by extrapolation from a harder operating point. In this case it confirmed
coverage (same order-of-magnitude improvement, well inside bounds) rather than finding a gap, but
that confirmation is itself the value -- "the mechanism is general enough" is a claim worth
checking once per review, not assuming.

**Mutation note:** reverting *either* the mechanism (rate-bias vs. bounded value-level nudge) or
*just* the threshold (335 -> 250 in the test's own `_LIMITS`) independently turns the same two
shipped-gain tests red. Both are load-bearing on the committed assertions, not just one.

See also [[feedback_toy_plant_test_profile_must_match_shipped_values]] (round 1/2's own lesson,
restated in this fix's commit messages) and the standing finite-float rule
(`.claude/agents/reviewer.md`, 2026-11-25) -- checked here and found not applicable: a changed
value at an *existing* tuning-boundary field (not newly introduced) whose `tuning.real()` range
check already rejects NaN/Infinity by construction, and a new local Lua profile literal that never
crosses a process boundary, are both outside the rule's own scope (wire/HTTP JSON/Hook
payload/`tuning.toml` parse only). Worth stating explicitly in the review rather than silently
skipping the checklist item, so a reader can tell it was checked and ruled out, not missed.
