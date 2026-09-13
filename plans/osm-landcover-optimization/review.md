### Review Summary

Reviewed `feature/osm-landcover-optimization` (commit `26d4e4c`, diff base `6cdf077`) against
`plans/osm-landcover-optimization/plan.md`, `implementation.md`, and the Stage 6 validation note.
Full read of the core pipeline (`osm/pbf.py`, `osm/features.py`, `geometry/__init__.py`,
`build/ingest_osm.py`, `store/reader.py`, `query/describe.py`), the coastline sign-convention code
and its control-point test, the tags-filter drift guard, the OSM cache round-trip/invalidation
path, the body-layer consumer (`belief/enrichment.py`, `belief/speech.py`), RUN.md, and both
subprojects' CLAUDE.md doc entries. Ran world-model's and body-layer's full check suites myself.

The implementation matches the plan closely and is well-tested. Ring/hole assembly, per-ring
min-area/exemption logic, the DCS axis-flip coastline sign convention (verified through the real
`wgs84_to_dcs` transform against real Syrian-coast geography), streaming/batched memory bounds,
and the OSM cache's `CLASSIFIER_VERSION`-gated invalidation all check out against the code, not
just the plan's prose. `nearest_road_osm`'s removal has zero live consumers anywhere in the repo
(mission-interpreter reads `nearest_settlement` only, via untyped dict access, so it is unaffected
by every field change in this branch). Found two required fixes, both small and mechanical, plus
several optional refinements.

### Required Fixes

- **`world-model/ROADMAP.md` was never updated.** The plan's Implementation Plan step 8 and
  `implementation.md`'s own Stage 8 description both call for "a `world-model/ROADMAP.md` entry,
  including the milestone-completion question (does this change what comes next?)" — required by
  root `CLAUDE.md`'s "Milestone Completion" section for every subproject milestone. `grep -in
  landcover world-model/ROADMAP.md` returns nothing; the file has no entry for this branch at all,
  and `implementation.md`'s Stage 8 files-changed list (`RUN.md`, `CLAUDE.md`,
  `M9_OSM_RUN_INSTRUCTIONS.md`, `body-layer/CLAUDE.md`) silently omits `ROADMAP.md` with no
  deviation noted anywhere. Every prior milestone on this same roadmap (osm-classified-cache,
  osm-streaming-ingest, the junctions memory fix) has its own `[x]` entry in exactly this format —
  this branch is the one gap. Add the entry (with real-data numbers already sitting in
  `research/2026-09-13-osm-landcover-optimization-validation.md`, so this is a five-minute write-up,
  not new investigation) and answer the milestone-completion question before merge.

- **Stale docstring in `world-model/src/store/reader.py:263`** — `nearest_feature`'s docstring
  still reads: "`provenance_geometry`, if given, restricts candidates to features whose
  `provenance["geometry"]` equals it -- e.g. `query/describe.py` uses this to answer `nearest_road`
  (DCS-only) and `nearest_road_osm` (OSM-only) separately even though both share `kind ==
  "road"`." `nearest_road_osm` no longer exists anywhere in `PositionDescription` — it was removed
  in this same branch (`query/describe.py`'s own module docstring documents the removal
  correctly, and `tests/test_describe_position.py:791` asserts its absence). This is exactly the
  failure mode the plan's own D6 rationale warns against ("a dead field invites someone to wire it
  back up") — a docstring that still describes a removed field as live is a milder version of the
  same risk, and is actively misleading to the next reader of `nearest_feature`. Reword to name
  only `nearest_road`'s DCS-only restriction (the current, real use of `provenance_geometry`).

### Optional Refinements

- **`test_api.py` and `test_pipeline_build_region.py`**, both named in the plan's "Affected
  Modules" test list for "update and extend," were not touched by any stage. Both subprojects'
  full suites still pass and the gap looks benign on inspection (`asdict()` is generic over new
  dataclass fields, so `test_api.py`'s existing assertions don't break; `test_pipeline_build_region.py`'s
  OSM-path tests already used a `place`+`name` node fixture, unaffected by the classifier rewrite),
  but neither `implementation.md` nor any commit message documents why these two named files were
  dropped from scope, unlike this project's usual practice of disclosing every deviation from a
  plan's stated file list (optional: add one line to `implementation.md`, or a small `test_api.py`
  assertion that `nearest_road_osm` is absent / `nearest_coastline`/`inside_landcover` are present
  in the live JSON response, mirroring what `test_describe_position.py` already does one layer
  down).
- **Independent hole/outer-ring simplification (D3 step 5) has no test or guard against an inner
  ring crossing or escaping its simplified outer ring.** `geometry.simplify_ring` simplifies the
  outer ring and each kept hole independently (`build/ingest_osm.py:479-490`); nothing checks the
  result stays a valid polygon-with-holes afterward. At 30 m tolerance against a 5 ha minimum ring
  size (a 5 ha square is ~224 m per side), this is a low-probability edge case in practice — but
  it is untested and not called out as an accepted risk anywhere (the plan's own Risks & Unknowns
  section doesn't mention it). Worth either a boundary-case test (a hole deliberately close to its
  outer ring's edge) or one line acknowledging the gap.
- **The D5 coastline control-point test exercises only one real-geography orientation**
  (north-to-south, sea-to-the-west, Syrian coast, `tests/test_geometry.py:321-339`). The
  convex/concave shared-vertex tests (`:298-313`) cover different local vertex geometry but use
  synthetic coordinates, not a second real-transform orientation (e.g. an east-west or south-north
  coastline). The underlying sign math is orientation-agnostic and separately unit-tested, so this
  is low risk, but a second real-geography orientation would close the gap between "the formula is
  right" and "the formula is right for every coastline orientation DCS will actually have."
- **`inside_settlement` and `inside_landcover` independently call `containing_polygons` and
  re-parse the same candidate rows' JSON geometry** when a built-up settlement polygon (which
  carries `landcover_class="built_up"`) is a candidate for both queries in one `describe_position`
  call (`query/describe.py:635` and `:652-654`). Not a correctness issue, and Stage 6's real-data
  numbers (mean 4-14 ms, p99 34 ms, vs. the ~800 ms M7 full-theatre baseline) show plenty of
  headroom — noted only as a possible small win if `describe_position` ever gets closer to budget.
- **No automated (pytest-level) performance regression guard for `inside_landcover`/
  `nearest_coastline` against a realistically large polygon.** The only numbers on record are
  Stage 6's one-off manual validation run (`tools/validate_osm_landcover.py`, not wired into
  `pytest`) against Lake Assad's real 3,359-vertex simplified polygon. This matches the plan's own
  explicit framing ("tiling of giant polygons... only if Stage 6 shows it is needed" — it didn't),
  so not a blocker, but a future larger relation (Tishreen reservoir, a big forest polygon) at
  `syria-full` scale would have no CI signal if it regressed this path.
- **mission-interpreter's own test suite could not be executed in this review** — no `.venv`
  exists for that subproject in this environment. Static analysis (`grep` across
  `mission-interpreter/src` and `tests`) shows zero references to `nearest_road_osm` or any of the
  other changed field names; `synth/prompts.py::_place_name` reads `position.get("nearest_settlement")`
  as an untyped dict and only ever touches `["name"]`, so it is structurally unaffected by every
  change in this branch. Believed safe on that basis, not directly confirmed by test execution —
  matches the plan's own Design D7 framing (mission-interpreter fallback to
  `named_places_within_radius` is an explicitly out-of-scope follow-up, not a defect of this
  branch).

### Check Results

**world-model/** (from `world-model/`, using `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (104 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (`--strict`): pass, 62 source files, no issues
- `pytest tests -q`: pass, 465 passed, 3 skipped (gitignored real-data-gated tests, unrelated to
  this branch)

**body-layer/** (from `body-layer/`, using `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (64 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (`--strict`): pass, 30 source files, no issues
- `pytest tests -q`: pass, 506 passed

**mission-interpreter/**: not run — no `.venv` present in this environment, and this branch made
no changes there (see Optional Refinements above for the static-analysis basis for believing it's
unaffected).

**git status**: clean except the pre-existing untracked files the task explicitly said not to
stage (`world-model/run.sh`, `world-model/run.sh~`, `world-model/src/dcs_world_model.egg-info/`,
`world-model/wolrd-build.log`) plus this review file.

### Verdict

APPROVED WITH MINOR FIXES

Both required fixes are small and mechanical (a ROADMAP.md entry using numbers already on hand in
the validation note, and a one-line docstring correction) — neither requires touching pipeline
logic, geometry code, or tests. No correctness defect was found in ring/hole assembly, the
coastline sign convention, streaming memory bounds, cache invalidation, or the body-layer/
mission-interpreter consumer contract.

### Review Confidence

Full read of the core geometry/ingest/query pipeline (`osm/pbf.py`, `osm/features.py`,
`geometry/__init__.py`, `build/ingest_osm.py` including `_classify_area`/`_ingest_ring`/
`_ingest_area`, `store/reader.py`, `query/describe.py`, `coordinates/__init__.py`), the D5
coastline test, the tags-filter drift guard and expression file, the OSM cache write/invalidation
path, `store/models.py`'s reserved-tag docstring, `body-layer/src/belief/enrichment.py` and
`speech.py`'s rounding regex, RUN.md §2/§3, and both subprojects' `CLAUDE.md` tech-stack entries —
all read in full, not sampled. Ran both subprojects' full format/lint/type/test suites directly
(not delegated/trusted from `implementation.md`'s own report). Spot-checked rather than fully
traced: `osm_cache/writer.py`/`reader.py`'s byte-level serialization (relied on the existing
`test_second_build_hits_cache_and_matches_first_build_byte_for_byte` test's `holes_kept == 1`
assertion as evidence of a real round-trip, rather than re-deriving the SQL by hand), and
mission-interpreter (grep-based only, no test execution — no `.venv` available in this
environment). Never opened or queried `syria-full.sqlite`/`syria-full-osm-cache.sqlite`, and no
`syria-full` build was run, per the task's hard rule.
