### Review Summary

Reviewed the M9 Geofabrik `.osm.pbf` ingestion work (Stages 1-4 of the plan; Stages 5-6 are
correctly left as user-run per `docs/M9_OSM_RUN_INSTRUCTIONS.md` and the project's standing
execution-boundary rule — not treated as missing here).

Checked:
- `src/osm/pbf.py` against `osm/features.py`'s `OsmFeatureSet`/`OsmNode`/`OsmWay` shapes — the
  pbf parser produces identical dataclass shapes to the Overpass path. Only tagged nodes are kept
  (matches Overpass's `out geom;` behaviour, documented). `ways_skipped_unresolved_nodes` is a
  genuine counted skip (never a crash, never silently dropped), following the `relations_skipped`
  precedent exactly as the plan required.
- `src/build/pipeline.py`'s `osm_pbf_path` wiring — clean `if osm_pbf_path exists -> elif
  osm_cache_path exists -> else skip` branching, additive as designed. `osm_pbf_path` correctly
  takes precedence, `osm_cache_path`/Overpass path is untouched and still exercised by its own
  existing tests. Parameter appended after `junction_min_degree` specifically to avoid shifting
  `tools/build_world_model.py`'s positional call — verified this is true by reading that call site.
- Design Decision 3's "zero downstream changes" claim: confirmed by diff — `query/describe.py`,
  `store/schema.py`, and `store/reader.py` have no changes in this branch at all. Only
  `osm/features.py` (additive field + docstring), `osm/overpass.py` (docstring only), and the new
  `osm/pbf.py` were touched in that area. The assertion held.
- Test coverage: `test_osm_pbf.py` (5 tests, fixture built at test time via `osmium.SimpleWriter`
  rather than a committed binary blob — reasonable deviation from the plan's literal wording,
  explicitly justified and logged), `test_ingest_osm.py` (19 tests, first direct coverage of
  `_classify_way`/`_ingest_node`/`_ingest_way`/`ingest_osm`, using real `wgs84_to_dcs` conversions
  rather than opaque literals — good practice), and two new `test_pipeline_build_region.py` cases
  (precedence, missing-file-degrades-to-skip). Coverage is meaningful, not decorative — edge cases
  (dangling node reference, degenerate ways, out-of-region drop, multipolygon skip) are all
  exercised.
- Provenance/invariants: OSM source rows carry `attribution`/`raw_path`/`notes`, features carry
  `provenance={"geometry": "osm", "name": "osm"}` (never overwriting DCS rows), matches
  `nearest_road` vs `nearest_road_osm` precedent. No writes to any DCS installation path — pbf
  parsing only reads from `data/raw/osm/`. No `world-model/data/` paths staged; `.gitignore`
  confirmed still covers `data/raw/`, `data/processed/`, `data/world-model/`.
- `pyproject.toml`'s dependency comment on the `pyosmium`/`osmium` naming discrepancy is accurate
  and directly verifiable (confirmed `pip show osmium` / PyPI import both resolve to `osmium`).
- Ran the actual `world-model/CLAUDE.md` Commands myself (not just trusting the implementation
  log): `ruff format --check`, `ruff check`, `pytest -q` (292 passed) all green. `mypy src` is
  **not** clean in the current venv — see Required Fixes.

### Required Fixes
- `src/osm/pbf.py:42` — `class _FeatureCollector(osmium.SimpleHandler):  # type: ignore[misc]` now
  fails `mypy --strict` with "Unused 'type: ignore' comment". The installed `osmium==4.3.1` in
  `world-model/.venv` ships `py.typed` and full `.pyi` stubs (`osmium/_osmium.pyi`,
  `osmium/osm/_osm.pyi`, etc.), so `SimpleHandler` is no longer untyped and the suppression is
  stale — `strict = true` in `pyproject.toml` implies `warn_unused_ignores`, which fails the build.
  This is not a hypothetical: I ran `mypy src` directly in this repo's venv and it reproduces.
  Remove the `# type: ignore[misc]` (and re-run `mypy src` to confirm nothing else surfaces once
  it's gone — a stub-typed `SimpleHandler` may reveal a real signature mismatch that the ignore was
  previously masking, though a first pass suggests the class body itself type-checks cleanly
  without it). This is a one-line fix, not a design problem — likely the implementer's dev venv had
  an older `osmium` build without shipped stubs when `mypy` was last run for the implementation log.

### Optional Refinements
- None of significance. The scope is tight and matches the plan; no unnecessary abstraction,
  duplication, or misplaced responsibility found.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read — read `osm/pbf.py`, `osm/features.py` in full, the complete `build/pipeline.py` diff,
both new test files in full, `pyproject.toml`/`build_world_model.py`/`test_pipeline_build_region.py`
diffs, `M9_OSM_RUN_INSTRUCTIONS.md`, and `derive_m9_osm_clip_bbox.py`. Confirmed via `git diff`
that `query/describe.py`, `store/schema.py`, `store/reader.py`, and `build/ingest_osm.py` carry no
changes (Design Decision 3 verified directly, not taken on the plan's word). Ran
`ruff format --check`, `ruff check`, `mypy src`, and `pytest -q` myself in `world-model/.venv`
rather than trusting the implementation log's reported results — this is what caught the mypy
discrepancy above.
