---
name: feedback_wait_on_the_real_completion_signal_not_a_proxy_counter
description: In a test waiting on a background thread, a counter that increments at the START of a unit of work (e.g. "entries read") is not the same signal as that work having FINISHED (e.g. its writes landing on disk) -- wait on the actual end state, not a proxy that only correlates with it.
metadata:
  type: feedback
---

Found during `raster-chart-viewer` Stage 6 (`warmup.py`'s background-thread tests,
`plans/raster-chart-viewer/plan.md`). `_CountingReader.open_count` increments the instant
`read_bytes(location)` returns -- but the warm-up loop then still has to decode and write every
small mip for that entry before moving to the next one. A test polling
`_wait_for(lambda: reader.open_count == N)` can observe `open_count == N` while the *last* entry's
mips are still being written, then immediately assert `cache.has_small_mip(...)` and fail --
flaky, not deterministically wrong, which makes it easy to mistake for a one-off and rerun past.

**Why:** the counter and the real completion condition are different events that happen to be
close together in time, not the same event. Nothing enforces they stay close — a slower disk, a
bigger fixture, or a different loop order would widen the gap.

**How to apply:** when a test must wait for background work to finish before asserting on its
*output*, poll the output's own completion predicate (here, `TileCache.has_all_small_mips` for
every key) — not a counter, timestamp, or any other signal that merely tends to arrive around the
same time. If the only available signal really is a proxy, say so in a comment next to the wait,
because the next person widening the fixture will hit the same flake with no warning. Confirmed
flaky (failed on the first run, passed every time after fixing the wait condition) rather than
assumed from reading the code alone — run a change like this a few times before trusting it.
