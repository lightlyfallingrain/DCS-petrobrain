---
name: project_raster_chart_viewer_performance_fix_review_approved
description: RC-1's performance-review fixes (zip-handle batching in discovery.py, low-water-mark eviction in cache.py) reviewed and APPROVED 2026-11-16 -- both NOW findings fixed correctly and minimally, verified by mutation, no scope drift.
metadata:
  type: project
---

Reviewed `plans/raster-chart-viewer/performance-review.md`'s two NOW findings (Finding 1: per-entry
`ZipFile` reopen inside one request's/warm-up pass's own loop, 4.1x measured; Finding 2: cache
eviction sweep stopping exactly at the cap rather than a margin below it, ~280ms/sweep at steady
state) against the implementer's fix, commit `32df4b38` (plus memory commit `6a653545`), diffed
against `1c21296b`. Verdict: **APPROVED**, no required fixes.

**Fix 1** (`discovery.BatchZipReader`/`batch_tile_reader()`): a call-scoped `dict[Path, ZipFile]`
reader, opened fresh per `compose_view_tile` call or per warm-up pass via `with
discovery.batch_tile_reader() as reader:`, never stored on `self` or shared across threads --
confirmed by tracing every call site, not just reading the class. See
`[[feedback_sentinel_default_mutate_call_site_not_whole_file]]` for the mutation technique used to
verify the `None`-sentinel default actually wires production call sites to the new reader rather
than merely defining it.

**Fix 2** (`cache._CACHE_LOW_WATER_MARK_FRACTION = 0.9`): changes `_enforce_cap_locked`'s stopping
condition from `<= self._max_bytes` to `<= low_water_mark`, inside the same pre-existing lock scope
from the prior thread-safety fix (`[[project_raster_chart_viewer_threadsafety_round2_approved]]`).
Verified the lock scope, the vanished-file tolerance, and the stat-before-sort structure from that
prior fix were all untouched by this diff -- only the comparison value changed.

Both fixes' new tests were shown red against a targeted revert and green against the shipped code,
with files restored byte-identical (`sha256sum`) afterward. The existing concurrency regression
test was rerun 5x individually and stayed green, confirming no interaction between the two
independent fixes and the locking they both sit inside. Checks (ruff format/check, mypy strict,
pytest) all pass, 55/55. Scope was correctly narrow: Finding 3 (MONITOR-only) and `RC-B1` were both
correctly left untouched, confirmed by their absence from the diff rather than just trusting the
implementer's own statement.
