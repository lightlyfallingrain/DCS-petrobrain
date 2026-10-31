---
name: world_model_progress_logging
description: Shared progress-reporting mechanism in world-model/src/progress.py; symptoms and gotchas around build-stage silence.
metadata:
  type: project
---

`world-model/src/progress.py` (`ThrottledProgress` + `Heartbeat`) is the one mechanism every
world-model build stage should use for "still working, not hung" logging — added 2026-09-15
after the same class of bug recurred three times (Stage 5 junctions, Stage 3 OSM overlay twice).
See `plans/osm-landcover-optimization/progress-logging.md` for the full audit/investigation.

**Bug class to watch for**: a progress counter that counts *elements delivered to a Python
callback* silently undercounts when a C-extension API filters or batches work before it ever
reaches Python (pyosmium's `osmium.filter.KeyFilter`; libosmium's two-pass multipolygon area
assembly has a whole first pass with zero Python callbacks). If a future symptom report is
"build stage logs `starting` then nothing for minutes" against `world-model`, check first whether
the affected loop already uses `progress.ThrottledProgress`/`Heartbeat` — if not, that's very
likely the root cause, not a real performance regression.

**Confirmed by direct measurement** (not assumed): pyosmium 4.3.1's `SimpleHandler.apply_file`
releases the GIL periodically on its own, even across stretches with zero Python callback
invocations — a background heartbeat thread ticked reliably (~1.0s cadence) throughout a 10.3s
`apply_file` call where most elements were filtered out. This is what makes `progress.Heartbeat`
(a background daemon thread) viable for that specific case — don't assume this generalizes to
other C-extension calls without checking the same way (a quick script with a ticking background
thread wrapped around the call).

`pyosmium`/`osmium.io` exposes no byte-offset/block-progress API (`Reader` only has
`header()`/`eof()`/`close()`) — there is no way to get an *exact* progress signal during
`apply_file`'s silent stretches. The chosen fallback is a calibrated elapsed-time-vs-file-size
estimate (`osm/pbf.py`'s `_PBF_CALIBRATED_BYTES_PER_S`, ~1.98 MB/s, measured against one real
160MB Geofabrik extract) — a rough ETA, not exact, always logged with `estimated=True`.

This pipeline has **no** `VACUUM`/`CREATE INDEX`/`ANALYZE` anywhere (grepped, confirmed absent) —
the `feature_bbox` R*Tree is populated incrementally, one row per `insert_features` call, not
built as a separate end-of-build pass. Don't go looking for an index-build stage; it doesn't
exist.

`store.writer.insert_features`/`insert_grid` are fast even at full-theatre scale (measured:
50,000 features/0.78s, 639,216 SRTM grid cells/0.79s) — if a build looks slow around an insert
call, the bottleneck is very unlikely to be the insert itself; look at what's happening in the
loop calling it (e.g. classification/simplification work per feature) instead.
