---
name: shared-profile-fixture-outlives-the-values-it-tests
description: aircraft-layer flight_control_law toy-plant tests keep a deliberately stale shared PROFILE fixture; a tuning pass that raises production constants again (not just once) recreates a gap a prior review already caught and fixed
metadata:
  type: feedback
---

On BL-16 LV-1 (`feature/bl16-lift-vector-law`), `test_flight_control_law.py`/`test_flight_control_lua.py`
keep a shared `_PROFILE`/`PROFILE` fixture deliberately pinned to **pre-amendment** values
(`omega_speed = 0.15`, `k_speed_error = 0.2`, `c_theta = 0.5`) so most scenarios test the stable
baseline rather than chasing every tuning pass. A handful of tests override locally to exercise a
specific amendment's production numbers — `TestAmendmentProductionValuesTogether` exists *because*
`review-lv1-amendment.md`'s "required fix 1" caught "no test runs `c_theta=0.85`,
`speed_accel_cap_mps2=1.9` and `k_pedal_from_collective_rate=0.6` together."

**The gap recurred one iteration later.** The 2026-11-25 debug pass raised `c_theta` 0.85→0.90,
`k_speed_error` 0.2→0.30, and introduced `omega_speed` 0.15→0.5 plus a new anti-windup ceiling meant
to make that raise safe — but left every committed test's local overrides frozen at the *old*
`c_theta=0.85` and never touched `omega_speed`/`k_speed_error` at all. Confirmed by mutation:
deleting the new anti-windup ceiling, and separately deleting a new combined-output clamp added in
the same pass, left all 124 tests in both files green. Neither of the two central mechanisms this
debug pass shipped had any committed regression coverage — only a throwaway, uncommitted toy-plant
harness (mentioned in the debug report, never checked in) ever exercised them.

**Why:** a test built to close one profile-constant gap pins the numbers it was built against; it
does not automatically track the next time those same constants move. Nothing re-opens the question
"does any committed test still run the *current* shipped values together" after the fix review that
created it closes.

**How to apply:** whenever a review touches `flight_profile.lua` (or any per-aircraft tunable
profile with this "stable shared fixture + local override" test shape), diff the production values
the commit just changed against every test's local override of the same names — not just whether a
test with that class name exists. If the override is stale, mutation-test the new mechanism before
trusting "tests still pass" as coverage: delete the new guard/clamp/ceiling and re-run; if nothing
fails, the fix is unverified by the suite regardless of green CI. This is the same "verify by
mutation, per entry" discipline `reviewer.md` already states, applied to a profile-constant class of
change specifically, because this is the second time it has caught exactly this shape of gap on the
same branch.
