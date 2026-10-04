### Implementation Summary

Implemented Stages 1, 2, 3 and 5 of `plans/multi-theatre-afghanistan/plan.md`. Stage 4 (live
`coord.LOtoLL` projection verification) is explicitly a user task on the Windows DCS box and was
not attempted; `THEATRE_PROJECTIONS["Afghanistan"]` stays `confidence="provisional"`.

Branch: `feature/multi-theatre-afghanistan`, based on `14ca593` (confirmed via `git rev-parse
HEAD` before starting). Commits: `0515e05` (Stage 1), `d04e992` (Stage 2), `3e6c710`+`a1cf8b9`
(Stage 5), `5f434c3` (Stage 3).

### Files Changed

**Stage 1 — per-theatre count guards / routes provenance (`0515e05`)**
- `world-model/src/dcs_data/towns.py`, `beacons.py` — `EXPECTED_TOWN_COUNT`/
  `EXPECTED_BEACON_COUNT` become `dict[str, int]` keyed by theatre (Syria/Afghanistan/Caucasus
  counts from the 2026-10-04 recon note); `parse_towns_lua`/`parse_beacons_lua` take an explicit
  `theatre` argument, raising `ValueError` (not `KeyError`) naming the theatre if absent.
- `world-model/src/build/pipeline.py` — the two parser call sites pass `region.theatre`; the
  roadnet-ingest stage's `Source(name=...)` and progress label now derive from
  `routes_path.name` instead of the literal `"Syria.routes"`.
- `world-model/tools/derive_m9_osm_clip_bbox.py` — takes an optional `region_name` positional
  arg (default `"syria-full"`, unchanged invocation).
- `world-model/tests/test_pipeline_build_region.py`, `test_pipeline_osm_cache.py`,
  `test_probe_chunk_pipeline.py` — monkeypatch lambdas updated to accept `theatre`.
- `world-model/tests/test_towns_lua.py`, `test_beacons_lua.py` — **not in the plan's own
  "Affected Modules" list**, but both call the real parsers directly and monkeypatch the
  now-dict `EXPECTED_*_COUNT` constants via `monkeypatch.setattr` (which would silently replace
  the dict with a bare int). Updated every call site to pass `theatre="Syria"`, changed
  `_patch_expected_count` to `monkeypatch.setitem`, and added one unknown-theatre `ValueError`
  test to each file.

**Stage 2 — register Afghanistan (`d04e992`)**
- `world-model/src/coordinates/projections.py` — `THEATRE_PROJECTIONS["Afghanistan"]`
  (`central_meridian=63, scale_factor=0.9996, false_easting=-300149.9912,
  false_northing=-3759656.9499`), `confidence="provisional"`, `source` citing the 2026-10-04
  recon note and stating the Stage 4 upgrade path.
- `world-model/tools/derive_afghanistan_full_region.py` (new) — small reproducible script
  (mirrors `derive_m9_osm_clip_bbox.py`'s discipline) that parses the real installed
  `towns.lua`/`beacons.lua`, projects towns to x/z via the new provisional fit, unions with
  beacons' native x/z, pads +30km/side, and prints the resulting centre/half-extents. Run once
  against the real files (1225 towns, 49 beacons); its output is what's hardcoded below.
- `world-model/src/build/region.py` — `REGIONS["afghanistan-full"]`: `centre_x=13479.5,
  centre_z=115758.0, half_extent_x_m=541969.3, half_extent_z_m=659245.2` (~1083.9 x 1318.5 km).
- `world-model/tests/test_coordinates.py` — a new self-consistency test, deliberately **not** a
  `CONTROL_POINTS` entry (those require an independently-published real-world source, which
  Afghanistan doesn't have): asserts `dcs_to_wgs84("Afghanistan", ...)` reproduces one real
  `beacons.lua` entry's `positionGeo` (Kabul `airfield17_0` VOR_DME) to within 0.2m, the fit's
  own ~0.03m RMS floor with margin.
- Stage 2's `mission["theatre"]` pre-check: independently confirmed (not just taken on the
  coordinator's word) via `zipfile`+regex against a real Afghanistan campaign `.miz`
  (read-only, `Saved Games/DCS/Missions/...`): `["theatre"] = "Afghanistan"`, exact match.

**Stage 3 — real build (`5f434c3`)**
- Ran job (a) (six-country OSM extract/merge/tags-filter) and job (b)
  (`tools/build_world_model.py afghanistan-full`) for real against the installed DCS files and
  staged DEM/OSM data. Output: `data/world-model/afghanistan-full.sqlite` (878MB) +
  `-osm-cache.sqlite` (101MB) + `-terrain-cache.sqlite` (506MB), all in the main checkout's
  gitignored `data/` dirs (the orchestrator's explicit instruction — nothing else was written
  there). Row counts, timings and the Kabul spot-check are in the new research note and RUN.md
  section below; see those for detail.
- `world-model/research/2026-10-05-afghanistan-theatre-build.md` (new) — Stage 2's pre-check
  result and Stage 3's full build results (row counts, per-stage timings, roadnet/SRTM/beacon
  stats, the Kabul spot-check).
- `world-model/RUN.md` — new `## 7. A second theatre: Afghanistan` section: the six-country OSM
  list and real clip bbox, the build command, real timings/counts, the spot-check, and the
  provisional-projection caveat. Also notes that `syria-full`'s own §3.3 stage table is now
  stale on one point (stage 8 ridge/valley no longer needs `--probe-output` — a later milestone,
  landform-geomorphons, generalized it to run off the primary SRTM grid) — flagged, not fixed,
  since fixing Syria's own docs is out of this plan's scope.
- Deleted the OSM job (a) intermediates (`*-clipped.osm.pbf`, `*-unfiltered.osm.pbf`) per
  RUN.md's own stated convention, keeping the six raw country extracts and the final
  `afghanistan-theatre.osm.pbf`.

**Stage 5 — body-layer theatre resolution (`3e6c710`, `a1cf8b9`)**
- `body-layer/src/belief/mission_phase.py` — `MissionUnderstandingData` gains a `theatre: 
  TaggedTheatre | None = None` field. **This did not already exist** despite the plan's "Context
  already established" section implying the Tagged[str] wiring reached all the way into
  body-layer's loader — it only reached the JSON artifact; `load_mission_understanding` only
  ever parsed `phases`/`route`. Added `TaggedTheatre` (mirrors the compact artifact's
  `Tagged[str]` envelope, but with a plain-string `value` — `_unwrap_tagged` can't be reused,
  it asserts `value` is a dict) and `_parse_theatre`; `load_mission_understanding` now requires
  `"theatre"` and raises `ValueError` if missing, same fail-loud posture as `phases`/`route`.
  Default `None` on the dataclass field keeps the several existing tests that construct
  `MissionUnderstandingData` directly (`test_console.py`, `test_logger.py`, `test_tools.py` —
  none test theatre logic) working unchanged.
- `body-layer/src/logger.py` `main()` — `--theatre`/`--world-model-db` are now optional; new
  `--world-model-dir` flag. Resolution: both explicit flags win unchanged if given; otherwise,
  given `--mission-understanding`, theatre/store are derived from the loaded artifact's
  `theatre` field and `<world-model-dir>/<theatre.lower()>-full.sqlite`; neither combination
  satisfiable → `parser.error` naming both valid forms. Mismatch guard (independent of how
  theatre was resolved): opens the resolved `world_model_db`, reads its stored `Region` via
  `store.reader.load_only_region`, and `parser.error`s if its `theatre` disagrees with the
  resolved one — catches "pointed `--theatre Syria` at an Afghanistan store" before the first
  poll. Implemented as a guard directly in `main()` rather than a wrapper next to
  `open_world_model` in `geometry.py` (the plan allowed either) — simpler given there's exactly
  one call site that needs it.
- `body-layer/CLAUDE.md` — "Running the live logger" section updated to document both
  resolution paths.

### Tests Added
- `test_parse_towns_lua_raises_value_error_on_unknown_theatre`,
  `test_parse_beacons_lua_raises_value_error_on_unknown_theatre` — ValueError (not KeyError)
  naming the theatre.
- `test_afghanistan_provisional_fit_self_consistency` — Afghanistan's provisional fit reproduces
  one real beacon's `positionGeo` to within 0.2m.
- `test_load_mission_understanding_raises_on_missing_theatre_key` — fail-loud on absent
  `theatre`; extended `test_load_mission_understanding_parses_the_fixture`'s assertions to cover
  the new field.
- `test_main_rejects_neither_theatre_pair_nor_mission_understanding`,
  `test_main_rejects_mission_understanding_without_world_model_dir`,
  `test_main_rejects_world_model_db_theatre_mismatch` — the three new `main()`-level
  `parser.error` paths, via `sys.argv`+`pytest.raises(SystemExit)`, mirroring the existing
  `--speech-log`/`--no-speech-log` validation test's pattern (the project's established posture
  for testing `main()`'s argparse validation despite its CLI wiring being "untested by design").

### Checks

**world-model/**
- `ruff format --check`: pass (2 pre-existing unformatted files outside this plan's scope,
  unchanged by this work: `tools/m7_kola_square_distortion_probe.py`,
  `tools/validate_m7_stage3.py`)
- `ruff check`: pass on every touched file (pre-existing, unrelated B023 findings in
  `tools/spike_junction_walk.py`/`tools/report_control_point_errors.py`, untouched)
- `mypy --strict` (`cd world-model && .venv/bin/mypy src`): pass, 71 source files
- `pytest`: 542 passed, 3 skipped (baseline was 539 passed, 3 skipped)

**body-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`): pass, 53 source files
- `pytest`: 1402 passed, 4 xfailed (baseline was 1398 passed, 4 xfailed)

Both subprojects' venvs did not exist in this worktree (gitignored) and were created fresh per
their own `RUN.md §1`/`CLAUDE.md` instructions before any check ran.

### Notable Discoveries

- **Plan test-impact gap**: `test_towns_lua.py`/`test_beacons_lua.py` call the real parsers
  directly and were not in the plan's "Affected Modules" list, which only named the three
  pipeline tests that monkeypatch the parsers. Both needed the same signature fix plus a
  `monkeypatch.setitem` change (their old `monkeypatch.setattr(module, "EXPECTED_TOWN_COUNT", n)`
  pattern would have silently replaced the new dict with a bare int). Caught by grepping for
  every call site before starting, per the role's own "treat the test-impact list as a
  hypothesis" instruction — this is exactly the "missing entry" failure mode that instruction
  warns is the dangerous one.
- **Plan "already established" overstatement**: the plan's context section states the
  `Tagged[str]` `theatre` field "carries through to the `--emit-compact` runtime artifact
  body-layer already loads at startup for BL-7 ... → `body-layer/src/belief/mission_phase.py`'s
  `load_mission_understanding`" — read as implying `load_mission_understanding` already parses
  it. It does not; it only ever parsed `phases`/`route`. The field exists in the JSON artifact
  (confirmed against `mission-interpreter/src/runtime/compact.py` and the test fixture), but
  body-layer's own parser needed the new code added here. This is Stage 5's own territory (the
  plan's Stage 5 prose explicitly reads `mission_data.theatre.value`), so implemented in scope
  rather than escalated — flagging here since the plan's own prose reads otherwise.
- **Stage 8 (terrain semantics) ran unexpectedly, in a good way**: `syria-full`'s own RUN.md
  §3.3 stage table says ridge/valley derivation is "skipped" without `--probe-output`. It ran
  for `afghanistan-full` and produced real `ridge`/`valley` counts (634,867 / 551,657) — a later
  milestone (landform-geomorphons) generalized this to run off the primary SRTM grid directly.
  RUN.md's Syria-era stage table is now stale on this one point; flagged in both the new
  Afghanistan RUN.md section and this note, not fixed in Syria's own section (out of scope).
- **Union vs. beacons-alone for region extent mattered concretely**: the derivation script's
  real output shows the towns.lua+beacons.lua union's z-min (-513,487.2) is ~9.3km past the
  beacons-only z-min the recon note measured (-504,146) — confirming the main-loop amendment's
  reasoning (beacons alone would have clipped a real town's worth of territory) rather than just
  trusting the stated rationale.
- Afghanistan's provisional projection, while unconfirmed by a live probe, produced a
  geographically coherent result well beyond the beacon-fit's own self-consistency: the Kabul
  spot-check's SRTM-sampled elevation (1792.2m) landed within ~1m of Kabul's real-world
  elevation (~1791m), which depends on the x/z landing on the correct ground cell, not on the
  fit's output being merely self-consistent.
