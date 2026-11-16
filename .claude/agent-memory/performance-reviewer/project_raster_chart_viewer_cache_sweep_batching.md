---
name: project_raster_chart_viewer_cache_sweep_batching
description: raster-chart-viewer's TileCache evicts exactly one file per over-cap write via a full rglob+stat+sort of the whole cache dir, held under the global lock — measured ~280ms at 24.6k files, recurring on every write at steady state, not a one-off.
metadata:
  type: project
---

`raster-chart-viewer/src/raster_chart_viewer/cache.py`'s `TileCache._enforce_cap_locked` (RC-1,
reviewed 2026-11-16) does `self._cache_dir.rglob("*")` + `.stat()` of every file + a full sort by
mtime, then unlinks files one at a time until back under `CACHE_MAX_BYTES` (1GB) — called from
`_write` while `self._lock` is already held, so every concurrent reader/writer (any terrain/tier,
the warm-up thread included) queues behind this sweep.

Measured directly (not estimated): at a realistic one-terrain small-mip file count (Afghanistan
32m's exact 3072 entries x 8 small mips = 24,576 files — the real per-entry x per-mip-level
formula, confirmed collision-free before timing), pinning the cap exactly at the current total and
writing one more file triggers the sweep: mean 278.9ms over 20 reps, stable (file count returns to
exactly 24,576 every cycle — real eviction each time, not a skipped no-op).

**Why this recurs rather than being a one-off startup cost**: the sweep only runs on `_write` calls
that push `_total_bytes` over the cap, which — once the cache is actually AT the cap — is every
single write thereafter, since the design (small mips persist across restarts, warm-up populates
every tier ever touched, composed tiles accumulate with ordinary panning, no cap headroom target,
just "stop as soon as back under") never gets ahead of the next write. The cap is 1GB; all 5
terrains' small-mip sets alone sum to roughly 12,500 entries (the plan's own total) at ~32KB/entry
≈ 400MB, leaving well under 1GB to fill with ordinary multi-session composed-tile accumulation.
Reaching steady state is a matter of *when*, not *if*, for a tool meant to be reused across
sessions — cache persistence across restarts is a deliberate design choice (RC-1's own warm-up
"skip entries whose small mips are already cached" acceptance criterion), which is exactly what
makes long-term accumulation toward the cap inevitable rather than contrived.

**The generalizable lesson**: a disk-cache eviction sweep that stops at "just enough to cross back
under the cap" rather than "down to some margin below it" pays its O(file-count) scan-and-sort cost
on every write once full, instead of amortizing it across the many writes that follow. This is the
same "poor batching" failure mode as [[feedback_reopen_zipfile_per_entry_within_one_call]] from the
same review, applied to cache eviction instead of zip reads: both are "the right unit of work is
a batch, and the code does it one item at a time instead."

**Cheap, scoped mitigation** (not yet applied as of 2026-11-16): sweep down to a margin below the
cap (e.g. 90% of `CACHE_MAX_BYTES`) instead of stopping exactly at it — no lock or correctness
change, just the loop's stopping condition.

Full review: `plans/raster-chart-viewer/performance-review.md`, Finding 2.
