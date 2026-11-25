---
name: feedback_new_perpoll_read_blinds_fakes_without_the_new_field
description: wiring a new required per-poll aircraft-layer read into ConsolePerceptionRunner.run_once (especially one whose absence is treated as a fail-loud/degraded condition, not a silent no-op) silently changes the behaviour of every unrelated integration test that drives the real poll loop with a fake aircraft_client/theatre -- check which fakes need the new field, not just which raise AttributeError
metadata:
  type: feedback
---

BL-B124 Stage 4: `run_once` started unconditionally calling `self.aircraft_client.
get_firing_latest()` (guarded only on `self.theatre is not None`) to get the mission clock for
light level. Two distinct kinds of test fallout, found only by running the full targeted suite,
not by reasoning about the diff:

1. **`AttributeError`** -- fakes in `test_body.py` that construct a `ConsolePerceptionRunner`
   directly (no real `theatre`) didn't implement `get_firing_latest` at all. Fixed by guarding the
   new call on `self.theatre is not None` (no source is polled in that state anyway, so the extra
   GET was pure waste even before the fake-method gap).
2. **Silent wrong behaviour, no exception at all** -- `FakeConsoleAircraftClient` (used by
   `_run_crew_text_poll_loop`-level tests that *do* set a real theatre) already implemented
   `get_firing_latest`, but its stub carried no `"mission_clock"` key. Every naked-eye-detection
   assertion in tests using this fake silently started failing (`len(runner.store.observations) ==
   0` instead of `1`) because the new logic treats a missing mission clock as "force full dark,
   never daylight" (BL-B124's own fail-loud design) -- correct new behaviour, but invisible to a
   test written long before this feature existed and not about light level at all. No traceback,
   no AttributeError -- just a different assertion value three calls downstream.

**Why:** a new per-poll read that is allowed to degrade quietly (most of this codebase's additive
feeds) breaks nothing when a fake omits the new field. One whose absence is *fail-loud by design*
(this feature's whole point, per user Q6) breaks every unrelated test that happens to share the
fake, with a failure mode that looks like a bug in the new feature rather than a missing fixture
field -- the symptom (zero observations) gives no hint that light level is involved at all.

**How to apply:** when wiring a new required-but-can-fail per-poll read into `run_once` (or any
shared poll-loop entry point), grep every test-double class implementing the relevant client method
across the touched test files (not just the ones the plan names), and check whether each one's
default/empty response would now trip the new feature's fail-loud path. Give fakes serving
unrelated tests a value that reproduces *today's* behaviour (e.g. a fixed comfortably-daylight
mission clock here), not an absent/null one, even though the real collector's own "nothing has
happened yet" default is absent/null -- the fake's job is to keep an unrelated test testing what it
was written to test, not to exercise the new feature's own degraded path by accident.
