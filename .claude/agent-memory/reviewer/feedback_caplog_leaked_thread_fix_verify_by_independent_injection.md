---
name: caplog-leaked-thread-fix-verify-by-independent-injection
description: when reviewing a caplog-filter fix for a leaked-daemon-thread flake (BL-B92), live --randomly-seed reruns are unreliable evidence -- write your own injection harness instead of trusting the debugger's
metadata:
  type: feedback
---

`caplog.at_level(level, logger=name)` only scopes the *level* of the named logger, not which
records land in `caplog.records` (pytest attaches its capture handler to root unconditionally).
`body-layer` has at least one known, accepted leak that exploits this:
`belief.brain_client.BrainLayerClient._poll_loop`, a never-stopped `daemon=True` thread started by
unrelated tests against unreachable URLs, logging via its own logger every ~1s for the rest of the
session. See the debugger's own memory file, `project_caplog_cross_logger_pollution.md`, for the
full mechanism and the sibling fix pattern (`record.thread == worker.ident` when two leaked
instances share one logger name).

**Why live seed-sweeping is not good verification here, and what to do instead (`BL-B92`
review).** The pollution's timing is wall-clock-coincidental, not seed-deterministic — reruns of
the identical `--randomly-seed` reproduced a *different* failing test on the debugger's own
machine, and on this reviewer's run across ~20 seeds (including the two the debugger's own
investigation used, 36 and 56) the connection-reporter flake itself did not reproduce at all,
while an unrelated out-of-scope flake (`test_main_print_tuning_works_without_aircraft_layer_url`)
did, exactly as debug.md predicted for that separate bug class. **Do not read a failed
reproduction attempt as evidence against the diagnosis** — it only tells you the race didn't land
this run.

**What does work: write your own standalone injection harness, independent of the debugger's.**
Two ~80-line scripts (not reusing the debugger's repro code) settled this in minutes: (1) run the
real `_ConnectionReporter` call sequence inside a scoped capture while a concurrent thread hammers
an unrelated logger name — unfiltered assertion failed 100/100, filtered (shipped) form 0/100; (2)
model two live `belief.brain_client`-named threads, one with `exc_info` (standing in for a leaked
instance) and one without (standing in for the test's own client) — unfiltered `records[0]` picked
the wrong instance 50/50 times, `record.thread == worker.ident` never did. This is cheap, fast,
deterministic, and does not depend on this host's timing quirks at all.

**Also mutation-test the *content* of the fix, separately from the mechanism.** Removing
`_ConnectionReporter.report_failure`'s `if self._connected is False: return` early-return (a real
behaviour regression — duplicate "disconnected" lines) still failed the filtered assertion as
expected. A caplog-filtering fix narrows *which* records are read, so it is worth confirming
separately that the exact-message-list assertion still catches a real regression in what those
records say, not just that it's immune to the injected noise.

**How to apply:** any `BL-B9x`-style flaky-test fix touching `caplog`/thread-leak mechanisms —
verify the mechanism by writing your own minimal injection repro rather than relying on live
`--randomly-seed` reruns (which this project's own debug reports now correctly caveat as
non-deterministic) or on the debugger's own stress-test code unread. Mutation-test the assertion's
content separately from the leak-filtering mechanism.
