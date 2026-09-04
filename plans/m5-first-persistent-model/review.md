### Review Summary

Reviewed M5 Stage 0 (census) + Stage 1 (offline sources) on `feature/m5-first-persistent-model`,
11 commits on top of main at `d4216fe`, against `plans/m5-first-persistent-model/plan.md` and
`checklist.md`. Scope: `src/geometry/`, `src/dcs_data/` (towns + beacons), `src/store/`,
`src/build/` (region, ingest_towns, ingest_beacons, ingest_osm, pipeline), `src/query/describe.py`,
three CLI tools, and the `coordinates` caching fix. This is a clean, disciplined implementation —
one of the stronger M5-class sessions reviewed so far.

**Scope fit.** Confirmed no Stage 2+ work leaked in: `find world-model/src -iname "*roadnet*"`
and `*probe*` return nothing; every `roadnet`/`getSurfaceType`/`getHeight` hit in the diff is a
docstring/comment describing what Stage 1 deliberately does *not* do yet, never a call. No
`ingest_probe.py`. `pyproject.toml`'s `known-first-party` list correctly omits `roadnet` (package
doesn't exist yet) while adding the six Stage-1 packages the plan named.

**Schema fidelity.** `store/schema.py`'s DDL is verbatim against checklist.md's schema — table by
table, column by column, including `feature_bbox USING rtree(...)` and JSON `geom_json` (not
WKB). `SCHEMA_VERSION` meta-row discipline matches the plan.

**Traps.** Both checklist-flagged traps are correctly handled and tested:
- `towns.py`: `parse_towns_lua` returns `list[TownEntry]`, never a dict; `test_towns_lua.py` pins
  a real 3-way "Yeniyurt" duplicate and asserts all three rows survive.
- `beacons.py`: `position = {x, y, z}` correctly maps the middle value to `y` (elevation), third
  to `z`; `test_beacons_lua.py` pins this with `airfield21_3` (HOMER), whose `y=121.7` is
  unambiguously an elevation, not the real `z=5622.08`. `positionGeo` is parsed, kept in the
  dataclass for inspection, and never touched by `ingest_beacons.py` or `describe.py` — confirmed
  by grep, not just the docstring's claim.

**Airfield layer provenance/confidence.** `ingest_beacons.py`'s constants match plan.md exactly:
runway uncertainty 300.0, airfield 500.0 (axis-midpoint) / 1000.0 (centroid). The pairing loop
iterates per-system (`ILS_LOCALIZER`+`ILS_GLIDESLOPE`, `PRMG_LOCALIZER`+`PRMG_GLIDESLOPE`)
independently, so crossing the two systems is structurally impossible, not just avoided by
convention — `test_ils_and_prmg_are_never_crossed` pins the exact beaconId pairing.
`test_derived_features_carry_derived_provenance_and_nonzero_uncertainty` is a real scope guard:
every `runway`/`airfield` feature must carry `derived_from_dcs_beacons` + nonzero uncertainty,
every `navaid` must carry `dcs` + `0.0`.

**Test quality.** Real assertions throughout, not tautological — exact literal values (ILS pair
~2635 m/0.31°, derived airfield point ~(41740.5, 5697.8) to the metre), tolerance bands where the
plan calls for them, and negative tests (malformed entry raises, count-mismatch raises, unpaired
localizer skips and falls back to centroid). `test_store_reader.py`'s R*Tree-vs-brute-force
agreement test is genuine: the brute-force reference is reimplemented independently in the test
using `geometry` functions directly (not by calling into `store.reader`), run over 200 random
synthetic points plus a 30-point mixed point/LineString set, asserting exact distance agreement
(`< 1e-6`) — this is what an index-honesty test should look like. Fixtures for `towns.lua`/
`beacons.lua` are hardcoded literals with explicit provenance comments naming the source research
note and line ranges, matching `test_dcs_grid.py`'s established pattern; `data/` is confirmed
gitignored and not staged.

**`describe_position` honesty rules.** All four followed: `nearest_road`/`nearest_road_osm` are
answered independently via `nearest_feature`'s new `provenance_geometry` filter (rule 2, DCS vs
OSM disagreement observable rather than fused); every returned `*Info` dataclass carries
provenance/confidence/uncertainty fields; absent layers (elevation, surface_type, nearest_road)
correctly return `None`/null with a stage-status note in the module docstring, not a placeholder
value (rule 3); output is structured dataclasses only (rule 4). `test_describe_position.py`
correctly frames itself as the Stage 1 smoke test, not the Stage 4 control-point tolerance-band
test the plan specifies for later — appropriately scoped, not overclaiming.

**`coordinates.py` caching fix.** `@cache` on `_dcs_to_wgs84_transformer`/`_wgs84_to_dcs_transformer`,
keyed only on theatre name. Safe: a `pyproj.Transformer` is stateless with respect to the
coordinates passed to `.transform()` — reusing one across calls is `pyproj`'s documented intended
usage pattern (it's the CRS/pipeline setup, not per-call state, that's expensive), and the cache
key (theatre) is exactly the value the transformer's construction depends on. Public
`dcs_to_wgs84`/`wgs84_to_dcs` signatures, return values, and the "unregistered theatre raises
`ValueError`" behavior are unchanged — confirmed by reading both wrapper functions, not just the
docstring's claim. This is the same fix pattern M1-M4 established for other per-call setup costs
and doesn't touch behavior for M1-M4 code paths.

**Verification commands** (run directly, canonical invocation per `world-model/CLAUDE.md`, from
repo root):
- `ruff format --check world-model/src world-model/tests` — pass (42 files already formatted)
- `ruff check world-model/src world-model/tests` — pass, 0 findings
- `mypy world-model/src` — pass, 27 source files, 0 errors
- `mypy` on `world-model/tests` (run with `cwd=world-model`, matching `mypy_path` config resolution
  — see note below) — pass, 15 files, 0 errors
- `pytest world-model/tests -q` — 96 passed

**Note, not a defect:** running `mypy world-model/tests` from the repo root (rather than
`cwd=world-model`) produces 32 spurious `import-not-found` errors, because `pyproject.toml`'s
`mypy_path = "src:tests"` resolves relative to mypy's config-file location only when mypy is
invoked with a cwd where that config is discoverable in the expected way. This is the identical
cwd-dependent-resolution issue already on file for `ruff`'s isort bucket (see reviewer memory
`project_ruff_cwd_dependent_isort.md`) — worth eventually pinning down for tests too, but it does
not affect `world-model/CLAUDE.md`'s literal canonical command (`mypy world-model/src`, which
never mentions tests) and is not this session's regression.

### Required Fixes

None.

### Optional Refinements

- `query/describe.py`'s `_road_info`/`_settlement_info`/`_water_info`/`_airfield_info`/
  `_runway_info`/named-place/navaid builders all do `feature.position_uncertainty_m or 0.0`.
  `StoredFeature.position_uncertainty_m` is typed `float | None`, but every current ingest module
  (`ingest_towns`, `ingest_beacons`, `ingest_osm`) always sets an explicit numeric value, so this
  path is currently unreachable — not a live bug. If a future ingest module ever left uncertainty
  unset, `or 0.0` would silently report "zero uncertainty" (i.e. surveyed-exact) for a genuinely
  unknown quantity, which is exactly the kind of collapsed-fact rule 1 exists to prevent. Consider
  either tightening `position_uncertainty_m` to non-optional `float` at the `StoredFeature`
  boundary (writers must supply a real number) or having `describe.py` pass `None` through rather
  than defaulting it, so a future violation surfaces as a visible null instead of a silent zero.
- The `mypy world-model/tests` cwd-dependence noted above is worth a one-time investigation
  (parallel to the existing ruff isort finding) so a future session doesn't waste time chasing 32
  phantom import errors before realizing it's an invocation-cwd artifact, not a real regression.

### Verdict
APPROVED
