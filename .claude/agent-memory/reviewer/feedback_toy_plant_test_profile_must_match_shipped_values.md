---
name: toy-plant-test-profile-must-match-shipped-values
description: a toy-plant test in test_flight_control_law.py can pass against the shared stale _PROFILE table while the shipped flight_profile.lua gains make the bug it claims to fix materially worse than asserted -- check which profile a new behaviour test actually ran against
metadata:
  type: feedback
---

`aircraft-layer/tests/test_flight_control_law.py`'s module-level `_PROFILE` table is a **deliberate
pre-amendment baseline** for several speed-loop fields (`omega_speed`, `speed_accel_cap_mps2`,
`k_speed_error`, `c_theta`) — slower than the shipped `flight_profile.lua["Mi-24P"]` values by a
wide margin (0.15 vs 0.5, 0.5 vs 1.9, 0.2 vs 0.3, 0.5 vs 0.90). `TestSpeedChannelIsBrisk`'s own
docstring says this outright. A new test that drives a scenario sensitive to those fields (anything
involving a commanded deceleration/acceleration, since `a_f_d`'s magnitude depends directly on them)
will under-exercise the real behaviour if it uses the shared `_PROFILE` as-is.

**This already happened once and was fixed**: `review-debug-1125.md` required fix 1 led to
`TestAmendmentProductionValuesTogether`, which overrides the specific stale fields with shipped
values inside the Lua driver (`PROFILE.c_theta = 0.85` etc.) rather than retyping the whole table.

**It happened again on BL-16 LV-1 debug-2026-11-27** (`fix/bl16-flight-epoch-bound` @ `3ae73c48`,
[[review-debug-1127]]): the new `TestDecelerationHoldsAltitude` asserted `min_dev > -15.0` and the
debug report claimed a "~4.5×" improvement, both computed against the stale `_PROFILE`. Re-running
the identical scenario with `flight_profile.PROFILES["Mi-24P"]` loaded via `dofile` (same mechanism
`TestAmendmentProductionValuesTogether` already uses) showed the real improvement is ~2× (−39.3 m →
−19.3 m), and the post-fix shipped-gains loss (−19.3 m) actually **exceeds** the committed test's own
asserted bound. The mechanism fix itself was correct (confirmed by mutation: reverting to the old
integrated-rate bias makes the committed test fail red, as expected) — only the test's own profile
was wrong.

**How to apply:** whenever a new or changed test in this file exercises a scenario whose outcome
depends on the speed/pitch channel (anything with `a_f_d` or a commanded IAS change), check which
fields of `_PROFILE` the scenario's outcome is sensitive to, and whether those fields match
`flight_profile.lua`'s shipped values. If not, either (a) the test should override them in the
driver the way `TestAmendmentProductionValuesTogether` does, or (b) independently re-run the
scenario with shipped values (via `dofile` against the real `flight_profile.lua`, not the test's
`_PROFILE` string) before trusting a debug report's own before/after numbers. A number computed on
the test's own stale baseline is not evidence about what will fly.
