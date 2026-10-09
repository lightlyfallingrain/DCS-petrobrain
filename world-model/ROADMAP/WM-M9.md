# WM-M9 — OSM augmentation (geofabrik)

- [x] **WM-M9 — OSM augmentation (geofabrik) — done 2026-09-12, merged 2026-09-12.** #status/done Re-introduced
  OSM as an augmentation layer from offline geofabrik.de per-country extracts (`.osm.pbf` format,
  parsed via `pyosmium`'s C++-backed sparse_mem_array index to handle node-location resolution
  without Python-side memory blowup). Fills the `nearest_settlement`/`nearest_water`/
  `inside_settlement` gap WM-M7 leaves `null` theatre-wide and unlocks settlement *boundary* polygons
  (DCS only ever gives center points). Stages 1-4 complete: (1) theatre bbox derivation and
  `M9_OSM_RUN_INSTRUCTIONS.md` with exact `osmium-tool` clip/merge commands; (2) `osm/pbf.py`
  parser, tested against synthetic fixture covering all four classification rules + dangling-node
  edge case + relation skip; (3) pipeline integration (`osm_pbf_path` parameter on `build_region`,
  additive alongside `osm_cache_path`, takes precedence); (4) validation against real
  `syria-260911.osm.pbf` extract (no classification-rule gaps found). Stages 5-6 (full 7-country
  merge + rebuild) are user-run prerequisites, documented in RUN_INSTRUCTIONS.md per execution-
  boundary pattern (mirrors WM-M7). Implementation: `src/osm/pbf.py` (new), test coverage
  `tests/test_osm_pbf.py` + `tests/test_ingest_osm.py` (19 tests for classification logic, first
  direct coverage of code live since WM-M3), `pyproject.toml` adds `pyosmium` dependency. Design
  Decision 3 verified: query surface unchanged (both Overpass and pbf paths produce identical
  `OsmFeatureSet` shape, so `query/describe.py` needs zero changes). Reviewer all-clear. DoD PASSED.
  See `plans/m9-osm-geofabrik/plan.md`, `plans/m9-osm-geofabrik/review.md`, `plans/m9-osm-geofabrik/dod-check.md`.
