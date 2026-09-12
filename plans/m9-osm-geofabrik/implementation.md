### Implementation Summary

Implemented plan Stages 1-4 (bbox derivation + run instructions, `osm/pbf.py` + fixture tests,
`build_region` wiring, real-data validation against `syria-260911.osm.pbf`). Stages 5-6 (full
7-country clip+merge and full-theatre rebuild) are documented as user-run steps in
`docs/M9_OSM_RUN_INSTRUCTIONS.md`, per the plan's execution boundary — not run in this session.

**Dependency correction (worth flagging explicitly)**: the plan's "pyosmium" name is the
project's own name (pyosmium.org), not the PyPI distribution/import name — both are `osmium`.
`pip install pyosmium` 404s on PyPI; `pip install osmium` is correct and ships a cp314 (this
project's actual interpreter, per `world-model/.venv`) wheel for macOS arm64 as of `osmium==4.3.1`.
The plan's own "Risks & Unknowns" flagged this session's earlier sandbox install failure as
unresolved — root cause is now known: it was never a wheel-availability problem, just the wrong
package name. `pyproject.toml`'s dependency comment documents this so it isn't rediscovered.

### Files Changed
- `world-model/pyproject.toml` — added `osmium>=4.3` to `dependencies`, with a comment
  explaining the pyosmium/osmium naming discrepancy.
- `world-model/src/osm/pbf.py` *(new)* — `osmium.SimpleHandler`-based `.osm.pbf` -> `OsmFeatureSet`
  parser (`load_features(pbf_path)`), producing the exact same dataclass shapes
  `osm.features.load_features` (Overpass) already produces. Only tagged nodes are kept (untagged
  nodes exist purely for way-geometry resolution, handled internally by pyosmium's
  `sparse_mem_array` location index — never touched by Python). A way with any node whose
  location the index never resolved is a counted skip
  (`ways_skipped_unresolved_nodes`), never a crash or silent drop.
- `world-model/src/osm/features.py` — added `ways_skipped_unresolved_nodes: int = 0` field to
  `OsmFeatureSet` (always 0 on the Overpass path; exists so both parsers share one dataclass
  shape) and a docstring note that `osm.pbf.load_features` supersedes this module on the real
  pipeline path.
- `world-model/src/osm/overpass.py` — docstring note only: superseded on the pipeline path,
  still used by `tools/inspect_osm_overlay.py`.
- `world-model/src/build/pipeline.py` — `build_region` gains a trailing `osm_pbf_path: Path |
  None = None` parameter (added after `junction_min_degree`, not next to `osm_cache_path`, so it
  doesn't shift `tools/build_world_model.py`'s existing positional call). When given and the
  file exists, it takes precedence over `osm_cache_path` for that build; downstream logic
  (`ingest_osm`, `BuildReport.osm_stats`/`osm_skipped`) is completely unchanged either way, per
  Design Decision 3.
- `world-model/tools/build_world_model.py` — added `--osm-pbf` CLI flag, wired into
  `build_region(..., osm_pbf_path=args.osm_pbf)`.
- `world-model/tools/derive_m9_osm_clip_bbox.py` *(new)* — one-off script computing the padded
  theatre clip bbox from `syria-full`'s region corners; its output is transcribed verbatim into
  the run-instructions doc rather than recomputed at build time.
- `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md` *(new)* — clip bbox, exact `osmium extract`/
  `merge` commands for all 7 countries, the real Stage 4 validation numbers from this session,
  and the full-theatre build/measure/record steps for the user to run.
- `world-model/tests/test_osm_pbf.py` *(new)* — fixture built at test time via
  `osmium.SimpleWriter` rather than a committed binary blob (see "Notable Discoveries" for why).
  Covers all four `_classify_way` rule shapes, the tagged/untagged node split, one
  `type=multipolygon` relation (counted skip), and one way with a dangling node reference
  (counted `ways_skipped_unresolved_nodes` skip).
- `world-model/tests/test_ingest_osm.py` *(new)* — first direct coverage of
  `_classify_way`/`_ingest_node`/`_ingest_way`/`ingest_osm`, using real `wgs84_to_dcs`
  conversions for region-clipping math rather than opaque literal DCS coordinates. 19 tests
  across classification, node/way ingest edge cases (missing name/place, out-of-region,
  degenerate geometry, unclassified tags), and end-to-end stat aggregation.
- `world-model/tests/test_pipeline_build_region.py` — added two tests: `osm_pbf_path` takes
  precedence over a simultaneously-given `osm_cache_path`, and a missing `osm_pbf_path` degrades
  to `osm_skipped=True` rather than erroring (mirrors the existing `osm_cache_path`-missing
  test's pattern).

### Tests Added
- `test_osm_pbf.py` (5 tests) — parser correctness against a synthetic `.osm.pbf`.
- `test_ingest_osm.py` (19 tests) — classification/clipping logic, previously untested.
- `test_pipeline_build_region.py` (+2 tests) — `osm_pbf_path` wiring and precedence.

### Checks (world-model/)
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (strict): pass, no issues in 52 source files
- `pytest world-model/tests -q`: pass, 292 passed

### Notable Discoveries
- **PyPI package name is `osmium`, not `pyosmium`** (see summary above) — the plan's stated
  install-verification risk is now resolved, and was never a wheel-availability problem.
- **Real Syria-only extract validation** (`data/raw/osm/syria-260911.osm.pbf`, 82 MB): parsed in
  ~60s to 260,101 tagged nodes / 1,865,289 ways / 2,818 relations / 0 unresolved way-nodes.
  Ingested against the existing `latakia-20km` region in ~6s: 3,136 road, 338 settlement, 117
  water, 106 named_place features. `ways_skipped_unclassified` was 1,439,259, dominated by
  `building` tags (1,377,796 — out of scope by design) — confirms `_classify_way`'s four rules
  are not missing an obviously-common case; no change to `build/ingest_osm.py` was needed.
- **`boundary=administrative` ways checked specifically** (1,228 in the extract) since they
  could plausibly represent settlement extents missed by the four rules — sampled and confirmed
  all are national/governorate-level borders (Syria-Turkey, Syria-Lebanon, Syria-Iraq,
  UNDOF armistice line), never city/settlement boundaries. Correctly left unclassified.
- **Design Decision 5's documented gap directly observed on real data**: the real Latakia city
  centre (not the airport) has no settlement polygon at that exact point
  (`inside_settlement=None`) despite 1,635 settlement-classified ways within ~15 km (cemeteries,
  parks, `village_green` parcels) — the city's own administrative extent is relation-mapped in
  this extract, exactly the multipolygon-relation gap the plan predicted, not a bug.
- **Query surface required zero changes**, confirmed against real OSM polygon data (not just the
  fixture): `describe_position` against `latakia-20km`'s region centre returned a real
  `nearest_settlement` (distance ≈70.2 m) and `nearest_road_osm` (≈39.7 m) sourced from the
  freshly-ingested extract, validating Design Decision 3 end-to-end.
- Deviated from the plan's literal "tiny committed fixture `.pbf`" wording:
  `test_osm_pbf.py` builds its fixture at test time with `osmium.SimpleWriter` (the plan's own
  named alternative, "or pyosmium's own writer") instead of committing a binary blob, so the
  fixture's exact content is visible in the test file's diff rather than opaque in git history.
  Verified equivalent behavior against the real extract during implementation.
