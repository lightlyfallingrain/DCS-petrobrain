### Implementation Summary

Built stages 2 (`body-layer/` subproject + BL-0 harness) and 3 (aircraft-layer `world_objects`
endpoint) of `plans/pb1-perception-logger/plan.md`. Stage 1 (live DCS spike) and stage 4+
(concrete `PerceptionSource` tier implementations) are explicitly out of scope for this pass —
stage 4 is gated on stage 1's result, which the user runs on the Windows box, not an agent.

### Files Changed

**New subproject `body-layer/`**
- `body-layer/pyproject.toml` — own venv, `mypy_path`/`pytest.pythonpath` include
  `../world-model/src` for the in-process world-model seam; `pyproj` declared as the one
  (transitive) dependency.
- `body-layer/CLAUDE.md` — mirrors `aircraft-layer/CLAUDE.md`'s structure/conventions.
- `body-layer/.gitignore` — mirrors `aircraft-layer/.gitignore`.
- `body-layer/src/perception/source.py` — `PerceptionSource` protocol
  (`poll(now_sim, ownship_state) -> list[Observation]`), plus `OwnshipState`, `Observation`,
  `DerivedWorldPosition`. `OwnshipState.from_telemetry_dict` converts the aircraft-layer wire
  dict (radians, DCS x/z) into body-layer's own units (degrees heading, still DCS x/z).
- `body-layer/src/perception/geometry.py` — `bearing_deg`/`range_m`/`line_of_sight_clear`/
  `elevation_at`/`open_world_model`/`GeoPosition`. Bearing is true heading, `atan2(dz, dx)`
  matching DCS's x=north/z=east convention. `range_m` is 3D slant range.
- `body-layer/src/aircraft_client.py` — `AircraftLayerClient` (stdlib `urllib`), real network
  client for `GET /telemetry/latest` and `GET /world_objects/latest`.
- `body-layer/src/replay.py` — `load_ownship_frames`/`replay`: BL-0 harness driving any
  `PerceptionSource` over a recorded ownship sequence.
- `body-layer/src/logger.py` — `PerceptionLogger`/`format_observation_line`: the PB-1 poll-loop
  shape, fully built and tested against a fake source; no `__main__`/CLI yet (see Notable
  Discoveries).
- `body-layer/tests/` — `test_source.py`, `test_geometry.py`, `test_aircraft_client.py`,
  `test_replay.py`, `test_logger.py`, plus `tests/fixtures/telemetry_frames.json` and
  `tests/fixtures/world_objects_sample.json` (both synthetic, not real DCS capture).

**Aircraft-layer additions (stage 3)**
- `aircraft-layer/src/schema/world_objects.py` (new) — `WorldObjectSample`/
  `WorldObjectsSnapshot`, parsing `LoGetWorldObjects`'s wire shape (lat/lon/alt, not DCS x/z;
  heading only, no pitch/bank/yaw). Re-exported from `schema/__init__.py`.
- `aircraft-layer/src/collector/cache.py` — added `WorldObjectsCache`, same shape as
  `TelemetryCache`.
- `aircraft-layer/src/collector/server.py` — `CollectorServer` now takes both caches and
  `_handle_line` routes each incoming JSON line to the matching cache by shape (`"objects"` key
  present -> world objects, else telemetry) rather than try/fallback parsing.
- `aircraft-layer/src/api/server.py` — added `GET /world_objects/latest`, same null-when-empty
  contract as `/telemetry/latest`. `TelemetryAPIServer.__init__`'s new `world_objects_cache`
  parameter defaults to a fresh cache when omitted, so every pre-existing call site (including
  `tests/test_api.py`, left untouched) keeps working unmodified.
- `aircraft-layer/src/collector/__main__.py` — wires the new cache into both servers.
- `aircraft-layer/dcs-export/Export.lua` — added a `LoGetWorldObjects` poll inside the existing
  `LuaExportAfterNextFrame` throttle gate, sent on the same connection right after the telemetry
  line. New `encode_world_objects_line`/`encode_scalar`/`json_escape_string` helpers (the
  existing `encode_json_line` only handled the flat numeric telemetry shape; world objects need
  a string field). One-shot `debug_dump("LoGetWorldObjects()", ...)` mirrors the existing
  `DUMPED_SELF_DATA` pattern.
- `aircraft-layer/tests/test_world_objects_schema.py`, `test_world_objects_cache.py`,
  `test_world_objects_api.py` — new files; no existing test file was modified.
- `aircraft-layer/CLAUDE.md`, `aircraft-layer/WORKFLOW.md` — updated for the new endpoint/schema
  file.
- `CLAUDE.md` (root) — added a `body-layer/CLAUDE.md` bullet under Subprojects.

### Tests Added

**body-layer** (28 tests)
- `test_source.py` — `OwnshipState.from_telemetry_dict` unit conversion (radians->degrees,
  0-360 wrap), missing-field error, `Observation`'s optional `derived_world_position`.
- `test_geometry.py` — bearing for all four cardinal directions plus wraparound, slant range
  (ground-only and altitude-inclusive), `elevation_at` delegating to a monkeypatched
  `describe_position`, `line_of_sight_clear` for clear/blocked/below-sightline/missing-data
  cases (world-model calls monkeypatched, not exercised against a real `.sqlite`).
- `test_aircraft_client.py` — real loopback `http.server` (mirrors
  `aircraft-layer/tests/test_api.py`'s pattern): parsed-dict success, null-body passthrough,
  unreachable-host error, invalid-JSON-body error.
- `test_replay.py` — fixture loading/sorting/unit-conversion, and a `FakePerceptionSource`
  (seeded from the world_objects fixture) proving the harness drives any `PerceptionSource` in
  order without a live connection.
- `test_logger.py` — `format_observation_line`'s exact text shape, `PerceptionLogger.run_once`'s
  empty-telemetry/normal/print-to-output paths, using fake aircraft-client and source objects.

**aircraft-layer** (12 new tests, 34 total passing)
- `test_world_objects_schema.py` — parse success (multiple objects, empty list, string
  coalition), and the same class of malformed-input rejections `test_schema.py` already covers
  for telemetry (empty line, invalid JSON, non-object JSON, missing field, non-list `objects`,
  bool-as-number rejection), plus a `to_dict` round-trip check.
- `test_world_objects_cache.py` — empty/most-recent, mirrors `test_cache.py`.
- `test_world_objects_api.py` — empty-cache null, most-recent snapshot, telemetry/world-objects
  cache independence, and the default-cache-when-omitted backward-compatibility path.

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass (after `ruff format` auto-fixed
  3 files)
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (strict): pass, 6 source files
- `pytest body-layer/tests -q`: pass, 28 passed
- `ruff format --check aircraft-layer/src aircraft-layer/tests`: pass (after auto-fixing 4
  files)
- `ruff check aircraft-layer/src aircraft-layer/tests`: pass (after `--fix` resolved 2 I001
  import-order findings)
- `mypy aircraft-layer/src` (strict): pass, 8 source files
- `pytest aircraft-layer/tests -q`: pass, 34 passed (12 new + 22 pre-existing, all pre-existing
  tests left untouched and still green)

### Notable Discoveries

- **`build.pipeline.open_region_db` was not reused** for `geometry.open_world_model` — that
  module transitively imports the entire ingest pipeline (`build.ingest_osm`, `terrain.*`,
  `dcs_data.*`, ...) for what is a one-line stdlib `sqlite3.connect(...)` call. Re-implemented
  locally in `geometry.py` instead, documented inline. Keeps body-layer's dependency footprint to
  exactly `pyproj` (transitive, via `query`/`coordinates`), nothing from `build`/`osm`/`terrain`.
- **`geometry.py` does not route every world-model read through `query.describe_position`** as
  the plan's Affected Modules section literally suggests — `elevation_at` does, but
  `line_of_sight_clear`'s repeated per-sample reads call `store.reader.sample_grid` directly,
  since `describe_position` also computes unrelated road/settlement/navaid joins on every one of
  a LOS sample's ~20 points. Documented as a deliberate deviation in the module docstring, not
  silently diverging from the plan.
- **`LoGetWorldObjects` position is lat/lon/altitude, not DCS x/y/z** — unlike `LoGetSelfData`.
  Kept as raw lat/lon in the aircraft-layer wire schema and API response; DCS x/z conversion is
  left to whichever consumer needs it (world-model's `coordinates.wgs84_to_dcs`), not built here,
  since aircraft-layer has no world-model dependency. `perception.geometry`'s `GeoPosition` and
  `bearing_deg`/`range_m` all still operate on DCS x/z — a concrete Tier 3 `PerceptionSource`
  (stage 4, not built) will need to do that lat/lon->x/z conversion itself before calling them.
- **`Observation.source` was left as a plain `str`**, not a closed `Literal`/enum — the two plans
  behind this work list different candidate values (`petrovich_detection`/`inferred`/
  `player_report` vs. `proxy_heuristic`) and no concrete tier exists yet to settle which are
  actually needed. Revisit once stage 4 picks a tier.
- **Stale cross-reference found, not fixed**: `.claude/agents/{architect,reviewer,implementer,
  performance-reviewer,debugger}.md` all still say "Mission Interpreter and Petrobrain Runtime
  modules do not exist yet — do not create them ahead of the World Model Builder proving out."
  `body-layer/` is now real code, and while it's explicitly *not* the Mission Interpreter or the
  full Petrobrain Runtime (it's BL-0/1 scaffolding only, per its own `CLAUDE.md`), that line is
  heading toward inaccurate and living in five separate agent-definition files, not one place.
  Left untouched — editing agent role definitions is outside an Implementer's scope for this
  task; flagging for the user/architect to reword or accept as still-roughly-true for now.
- **`TelemetryAPIServer`'s constructor signature changed** (`world_objects_cache` inserted as
  the second positional parameter, before `host`/`port`) — every existing call site in this repo
  was keyword-arg (`host=..., port=...`) so nothing broke, but any future caller passing `host`/
  `port` positionally would need updating. Same for `CollectorServer` (`world_objects_cache`
  inserted as the second required positional parameter) — its one call site
  (`collector/__main__.py`) was updated.
