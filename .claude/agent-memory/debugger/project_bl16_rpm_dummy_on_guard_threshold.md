---
name: bl16-rpm-dummy-on-guard-threshold
description: a stand-in sensor value (BL-16's 90% rotor-RPM dummy) sat exactly on its guard's `<=` threshold, silently locking mode-1 collective against rising for days; check shipped dummies against every guard that reads them
metadata:
  type: project
---

BL-16 mode 1 shipped `ROTOR_RPM_SOURCE = "dummy"` (90 %, the user's own number) and a guard
`rpm <= floor + margin` = 85 + 5. 90 ≤ 90: the guard tripped every frame, and its cap was 0, so the
law could lower the collective but never raise it. Found 2026-11-24 when a re-fly trace showed
`u_c_rate` exactly 0 for 7 s with `a_u_d` = +3 m/s² and the aircraft sinking 6 m/s
(`plans/flight-lift-vector/debug-2026-11-24b.md`). Fixed by making the guard strict.

**Why it survived:** every test set `rotor_rpm_pct` explicitly (100 or 88); none fed the real
module's dummy through the law. The DoD note even said the reading was "entirely synthetic" without
checking what the synthetic value did.

**How to apply:** when a value is a placeholder (dummy sensor, default limit, fallback reading),
grep every comparison that reads it and evaluate it at the placeholder — boundaries included. Add one
test that pulls the placeholder from the real module rather than restating a number. In a trace,
a rate stuck at *exactly* zero while its error is large is a cap, not a slow loop.
