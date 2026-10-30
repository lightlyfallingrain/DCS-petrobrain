---
name: mock-flight-scenario-detection-gating
description: Designing a mock-flight scenario that drives naked-eye detection end to end must respect the real angular-size gate (~2.3km for a 7m object) and cockpit-mask thresholds, not just "ownship closes toward a target"
type: feedback
---

When building a `body-layer` scenario that exercises the **real**
naked-eye perception pipeline end to end (not a bare `ContactStore`/
`Observation` drive), two real-geometry constraints bite that a
bare-belief-layer test never has to think about:

1. **The naked-eye angular-size gate is a true-range threshold
   independent of AGL**: `size_m / LOWRES_ANGULAR_RADIUS_RAD` (default
   0.003 rad), e.g. ~2333 m for a 7 m (T-72-sized) object at the default
   `UNAIDED_OPTIC`. A scenario starting much farther than this (e.g. a
   "5 km approach") simply produces zero naked-eye observations until
   true range crosses that threshold — design the scenario's assertions
   around the window *after* that point, not from t=0.

2. **The cockpit mask (`perception.cockpit_mask`) is a *belief-position*
   check, not a pure-geometry one** (`belief.contacts._callout_may_speak`
   reads `contact.last_position`, the believed position, not ground
   truth) — so the observed masked/visible transition happens near, but
   not exactly at, the geometrically-computed threshold
   (`AGL / tan(22°)` forward, `AGL / tan(10°)` abeam). Don't assert on
   the exact computed threshold; measure the actual transition by running
   the scenario once and place test legs generously either side.

**The genuinely tricky one — two same-bearing groups at different
ranges, closing**: a closing run that starts far enough to see the near
group and ends by overflying it will mask the near group (cockpit mask)
*before* the far group (farther away) ever crosses the angular-size gate.
The only poll where exactly one candidate is briefly admitted (the far
group's first look) then gets folded by the belief-side spatial gate into
the near group's own now-stale, decay-widened contact — collapsing two
real contacts into one. This is a geometry artifact of exercising the
real detection gate on a closing approach to *both* groups at once, not a
finding about `association_over_time`'s gate (Stage 4's own
`ContactStore`-only version of this scenario never exercises the
detection gate, so it never hits this). **Fix: hold ownship stationary at
a point where both groups are simultaneously admissible and neither is
masked**, rather than closing on both. Compute the window:
`far_group_range < angular_size_threshold` and
`near_group_range > AGL / tan(22°)` must both hold at the chosen point.

Also: naked-eye's own "ahead" scan task still cycles 11->12->1 o'clock
(`FOCUS_DWELL_S` legs) even with a persistent `scan_area` task registered
— it does **not** give a static 12-o'clock stare. A scenario needing
continuous per-poll looks (not statistically likely-eventually) should
hold position for many polls rather than assume every poll looks forward.
