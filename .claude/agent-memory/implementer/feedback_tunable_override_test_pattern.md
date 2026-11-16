---
name: tunable-override-test-pattern
description: to test a tunable constant's behaviour under a non-default value, monkeypatch.setattr the constant directly on its owning module (import X as X_module) in-process -- a subprocess reimport with PETROBRAIN_TUNING is only needed when testing tuning.py's own resolution machinery or a value baked in at a different module's import time.
metadata:
  type: feedback
---

BL-B118 reviewer fix (`plans/bl16-qnh-mission-start/review.md`): needed a test proving
`advance_altimeter_qnh_sync`'s calibration-step branch obeys `ALTIMETER_QNH_MAX_STEP` even when a
legal override sets `ALTIMETER_QNH_CALIBRATION_STEP > ALTIMETER_QNH_MAX_STEP` (their declared
`lo`/`hi` bounds allow this even though the defaults happen not to).

**Two different patterns exist in this codebase for "test under an overridden tunable," and they
are not interchangeable:**

1. **In-process `monkeypatch.setattr(<module>, "<CONSTANT_NAME>", <value>)`** — works whenever the
   function under test reads the constant as a plain module-global name each call (every
   `tuning.*`-declared constant in `belief.altimeter_qnh_sync.py`, `belief.groups.py`,
   `perception.estimation.py` does exactly this). `monkeypatch.setattr` mutates the module's
   `__dict__`, and global name lookup re-reads it on every call, so no reimport is needed. This is
   the common pattern (`test_groups.py::test_...cohesion_cap`,
   `test_relative_distance_scenarios.py`'s `RANGE_LOOK_SHARE` tests) and is almost always the
   right one for testing one function's behaviour at a non-default value. Needs
   `import belief.<module> as <module>_module` alongside the `from belief.<module> import
   CONSTANT` the test also wants for assertions/defaults.
2. **Subprocess reimport with `PETROBRAIN_TUNING=<path>` and a fresh `sys.executable -c` script**
   (`test_tuning.py`'s `test_a_real_constant_resolves_an_override_in_a_fresh_process`,
   `test_reviewer_repro_scan_decay_coupling_does_not_crash_the_process`) — needed only when testing
   that the *file-reading-at-import* mechanism itself works end to end, or when the value is
   captured into something that does not re-read the module global (a frozen-dataclass default
   evaluated at class-definition time, a closure formed at a different module's import). This is
   slower and heavier; reach for it only when pattern 1 cannot reach the thing under test.

**How to apply:** before writing a tunable-override test, check whether the constant is read as a
bare module-global inside the function under test (it almost always is, per `body-layer/CLAUDE.md`
"Tuning" — "constants bind by value at import" is about cross-module imports, not about the
declaring module's own later reads). If so, use pattern 1; it is simpler, faster, and is what
every existing non-`test_tuning.py` test in this codebase already does.
