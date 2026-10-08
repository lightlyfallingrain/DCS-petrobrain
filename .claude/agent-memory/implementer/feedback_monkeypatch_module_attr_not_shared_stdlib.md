---
name: monkeypatch-module-attr-not-shared-stdlib
description: monkeypatch.setattr(mod.time, "sleep", fake) mutates the real process-wide time module -- rebind the name in the module-under-test's own namespace instead.
metadata:
  type: feedback
---

`monkeypatch.setattr(some_module.time, "sleep", fake_fn)` does not scope the patch to
`some_module` -- `some_module.time` is the *same* `time` module object every other `import time`
in the process sees, so every thread calling `time.sleep` during the test gets the fake, not just
`some_module`'s own calls.

**Why this matters:** on BL-11 Stage 4 round 3 (`plans/bl11-stage4-fail-closed/implementation.md`),
patching `logger_module.time.sleep` to raise `KeyboardInterrupt` after N calls (to break a
`while True:` loop inside `main()`) also raised inside an unrelated leftover
`belief.brain_client.BrainLayerClient` daemon poll thread from an earlier test in the same pytest
session (never stopped, because nothing joins a `daemon=True` thread) -- a
`PytestUnhandledThreadExceptionWarning`, tests still green but real cross-test pollution that
would bite the next time such a thread does something less inert than an HTTP retry sleep.

**How to apply:** when faking `time.sleep`/`time.monotonic`/etc. to drive a loop in module X,
rebind the *name* in X's own namespace instead: `monkeypatch.setattr(X, "time", fake_time_obj)`,
where `fake_time_obj` implements only the attributes the code path under test actually calls and
delegates everything else to the real module via `__getattr__`. This only changes what X's own
`time.sleep(...)` resolves to; every other module's `import time` is untouched. Applies to any
shared stdlib module (`time`, `random`, etc.), not just `time`.
