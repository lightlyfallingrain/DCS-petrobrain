---
name: thread-join-timeout-without-is-alive-check
description: concurrency test using thread.join(timeout=N) without asserting not thread.is_alive() passes even when the thread never finished
metadata:
  type: feedback
---

A concurrency test that starts a thread, does `thread.join(timeout=N)`, then asserts on shared
state (`errors == []`, a counter) is not actually proving the thread completed. `join(timeout=...)`
returns silently whether the thread finished or is still blocked — nothing raises, nothing fails,
and the assertions that follow are checked at that moment regardless. If the thread is stuck
waiting on an event that was never set, the test still passes (the shared state is simply still in
its initial "no error yet" shape) and only its wall-clock runtime hints at the gap (it eats the
full `timeout` instead of returning fast).

**Found via mutation** (AA-6 review, `audio-adapter/tests/test_local_playback.py::
test_winsound_two_concurrent_delivers_both_survive_one_interrupt`): mutating `_WinsoundLocalSink.
interrupt()` to release only one of two in-flight `threading.Event`s left the whole test suite
green. The test's own docstring claims "both survive" but never checks `thread_a.is_alive()`/
`thread_b.is_alive()` after the joins — the second thread was still blocked out its own 10s
fallback timeout, `join(timeout=5)` gave up without it finishing, and nothing downstream noticed.
Mutated runtime (~5.1s, hitting both the join timeout and the thread's own fallback) versus
unmutated (~0.03s) was the only visible symptom before mutating the source.

**Why:** per `.claude/agents/reviewer.md`'s "Verify by mutation, per entry, not per set" — this
role's own recurring lesson is that reading a concurrency test's assertions is not the same as
confirming what they'd catch. A `join(timeout=...)` call is exactly the shape that *looks* like a
synchronization point but isn't one unless paired with a liveness check or a timeout value proven
to exceed every path the code can take.

**How to apply:** when reviewing a test that spawns threads and joins them with a timeout before
asserting on shared state, mutate the thing the test claims to prove (here: "releases all in-flight
waits", by truncating the release loop to one entry) and re-run just that test, not the whole file.
If it still passes, the test needs either `assert not thread.is_alive()` after each join, or a
join timeout proven comfortably above every code path's own wait (and ideally a short/deterministic
payload so the test isn't timing-dependent at all). Apply this check to any `thread.join(timeout=`
pattern across subprojects, not just `audio-adapter` — `_InFlightTracker`'s own afplay-side tests
in the same file use real `_FakeProcess.communicate()` semantics rather than real timeouts, so they
were not affected, but any future test built the same way as the winsound one would have the same
gap.
