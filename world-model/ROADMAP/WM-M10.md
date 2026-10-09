# WM-M10 — Road-junction detection

- [x] **WM-M10 — Road-junction detection (done, merged 2026-09-13).** #status/done Derives road-junction
  landmarks purely from geometry over the already-parsed `.routes`/road layer — no new
  dependency, no OSM data. Grid-bucketed union-find over road-segment endpoints/interior
  vertices (`src/roadnet/junctions.py`); a junction is emitted at degree ≥ 3 (endpoint = 1 arm,
  interior-attachment = 2 arms). New pipeline stage 5 (`src/build/ingest_junctions.py`,
  `_TOTAL_STAGES` 7→8), new query surface `describe.nearest_junction`/`JunctionInfo`. Real
  numbers against `latakia-20km`: 3,266 roads → 6,496 endpoints + 155,900 interior vertices →
  3,980 clusters → 3,634 junctions kept (346 dropped as degree-2 route continuation); pipeline
  stage 0.6s, `nearest_feature(["junction"])` mean 8.2ms (cheaper than the pre-existing road
  lookup). Known bounded limitation: ~32/3,634 false positives where DCS represents one road
  corridor as multiple exactly-coincident `.routes` polylines, indistinguishable from a genuine
  multi-way junction by tolerance/min-degree tuning alone — documented in `junctions.py`'s
  docstring, not fixed. Also clarified (docstring-only, no behavior change): `nearby_ridges`/
  `nearby_valleys` both `None` already means "flat terrain," no new classification needed. 266
  tests pass. Raised while scoping tactical-landmark enrichment for Mission Interpreter — see
  `plans/world-model-tactical-landmarks/plan.md` and `plans/m10-road-junctions/`.
