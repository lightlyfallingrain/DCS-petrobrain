# WM-W10 — OSM streaming-ingest memory fix

- [x] **OSM streaming-ingest memory fix (no M-number — a bug fix on M9, not a milestone; done,
  merged 2026-09-13).** #status/done A real `syria-full` rebuild (full 7-country merge, dominated by Turkey's
  646MB extract) stalled after ~8.6M ways / high memory usage on the user's Windows box, killed
  after 22 minutes of total silence — `osm/pbf.py`'s `_FeatureCollector` accumulated every kept
  node/way into Python lists for the entire `apply_file` pass, gigabytes of Python object overhead
  at theatre-merged scale. Fixed: `stream_features` flushes to caller callbacks every `batch_size`
  (50,000) elements instead of buffering the whole file; `build/pipeline.py`'s `osm_pbf_path`
  branch calls it directly, writing each batch to the store immediately (`tracemalloc`-verified
  memory bound, Reviewer confirmed the pipeline actually uses the new path, not just that better
  code exists unused). `load_features` (M9's original entry point) stays a thin
  backward-compatible wrapper (`stream_features` with an unbounded batch), so its existing
  correctness tests are untouched. New regression test proves streaming and bulk paths produce
  byte-identical output. Also produced a memory-exhaustion audit of the rest of the pipeline
  (`plans/osm-streaming-ingest/plan.md`'s addendum) — `roadnet/`, `ingest_srtm.py`,
  `ingest_terrain.py`, `dcs_data/towns.py` all judged fine at current scale; `roadnet/junctions.py`
  flagged as backlog below (unmeasured at `syria-full`+OSM-combined scale, probably fine by
  extrapolation but not confirmed). `M9_OSM_RUN_INSTRUCTIONS.md` updated with what steady-but-slow
  progress looks like vs. a genuine stall. Reviewer approved, no required fixes. See
  `plans/osm-streaming-ingest/plan.md`, `plans/osm-streaming-ingest/review.md`.
