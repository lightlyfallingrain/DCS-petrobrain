---
name: feedback_reproduce_thread_safety_claims_dont_just_read_them
description: When an orchestrator flags "thread safety" as a specific thing to check on a shared-state class touched by ThreadingHTTPServer plus a background thread, write a short standalone stress script against that class directly and run it — reading the code for a missing lock is not enough to find a real crash, and finding one this way takes minutes.
metadata:
  type: feedback
---

Found reviewing `raster-chart-viewer` (MI-B4) Stages 1-6, `plans/raster-chart-viewer/plan.md`. The
task brief explicitly called out "Thread safety: ThreadingHTTPServer and the warm-up thread share
the cache and zip handles. A zipfile.ZipFile object shared across threads is a known hazard." On a
pure code read, `discovery.read_tile_bytes` opens a fresh `ZipFile` per call — the specific named
hazard doesn't exist, which could read as "thread safety: checked, clear." But `TileCache` (not
named in the hint) has its own unlocked shared state: `_total_bytes` mutated with
`self._total_bytes += ...` and `_enforce_cap`'s `sorted(..., key=lambda f: f.stat().st_mtime)` over
a live directory, both with no lock. Reading this is suspicious but not conclusive — a short
critical section under the GIL often just doesn't lose a race in casual testing.

**What actually found the bug**: a ~20-line standalone script (no HTTP, no pytest, just
`threading.Thread` workers calling `TileCache.put_composed_tile` directly in a loop) under a small
forced-eviction cap. Crashed reliably (31/3200 writes) within seconds, with a clean traceback
pointing at the exact unguarded line. The existing test suite (`test_cache.py`) had zero concurrency
tests, so nothing short of writing this script would have surfaced it — reading the 50 passing
tests gives no signal either way.

**Why:** "no shared `ZipFile`" and "no race in `TileCache`" are two separate claims. The hint named
one specific known hazard; verifying that hazard doesn't apply is not the same as verifying thread
safety generally. The orchestrator's hint is a starting point for where to look, not the complete
list of what could be wrong.

**How to apply:** whenever a review brief names a *specific* concurrency hazard to check, after
confirming that one is absent, also independently ask "what other mutable state do the same two
threads (the request-handling pool and any background thread) touch?" and write a short standalone
stress script against the class that owns it — not a reasoning-only read, and not folded into the
existing test suite first (that risks tuning the repro to pass, same trap as fixing-then-testing).
A low cap that forces eviction, or an artificial delay, is usually what's needed to make a
short-critical-section race observable in a quick script; a lock-free counter alone may not show
drift without many more iterations than feel worth running by hand.
