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

---

### Stages 4-9 (2026-09-08)

Built the remaining stages against the plan's redesigned hybrid architecture (Session 4's live
spike falsified the original two-tier framing — see plan's Session 4 and "Association design"
sections). `petrovich_feed.py`/`proxy.py` were **not** created, per the plan's explicit
supersession note; there is one concrete `PerceptionSource`
(`perception.hybrid_source.HybridPerceptionSource`).

### Files Changed

**Aircraft-layer (stage 4 — permanent HelperAI feed)**
- `aircraft-layer/dcs-export/Export.lua` — added `HELPERAI_DEVICE_ID = 6` and a permanent
  `list_indication(HELPERAI_DEVICE_ID)` push, same throttle/socket/pcall-guard/one-shot-debug-dump
  mechanism as the existing `LoGetWorldObjects` push, sent right after it in
  `LuaExportAfterNextFrame`. New `encode_petrovich_indication_line`/`get_helperai_indication`
  helpers; reuses the existing `encode_scalar`/`json_escape_string` string-escaping path.
- `aircraft-layer/src/schema/petrovich_indication.py` (new) — `PetrovichIndicationSample` +
  `parse_indication_text`, a from-scratch recursive-descent parser over the confirmed
  `-----...-----\n<name>\n<value-if-any>\nchildren are {...}` tree format, flattening it into a
  `{leaf_name: text}` record. Degrades gracefully (skips/treats-as-childless) on malformed tree
  content rather than raising — only structurally-invalid JSON at the outer line level raises
  `PetrovichIndicationParseError`. Re-exported from `schema/__init__.py`.
- `aircraft-layer/src/collector/cache.py` — added `PetrovichIndicationCache`, same shape as
  `WorldObjectsCache`.
- `aircraft-layer/src/collector/server.py` — `CollectorServer` now takes a third cache;
  `_handle_line` routes on `"indication"` key presence, same pattern as the `"objects"` branch.
- `aircraft-layer/src/api/server.py` — added `GET /petrovich_indication/latest`;
  `TelemetryAPIServer`'s new `petrovich_indication_cache` parameter defaults to a fresh cache
  (same backward-compatibility pattern as `world_objects_cache`).
- `aircraft-layer/src/collector/__main__.py` — wires the new cache into both servers.
- `aircraft-layer/tests/test_petrovich_indication_{schema,cache,api}.py` (new) — parser unit
  tests (nested children, empty-string, garbage-input graceful degradation, all the
  `WorldObjectsSnapshot`-style malformed-JSON rejections), cache tests, API endpoint tests
  including the default-cache-when-omitted path. No existing test file modified.

**Body-layer (stages 5-8)**
- `body-layer/src/perception/association.py` (new) — `WorldObjectCandidate` (DCS-native x/z,
  built via `from_dict`'s `wgs84_to_dcs` conversion), `AssociationResult`, `associate()`
  implementing the plan's algorithm exactly: no coalition/IFF filtering, `RANGE_CAP_M=5000`/
  `FORWARD_HEMISPHERE_HALF_WIDTH_DEG=90`/`TYPE_MATCH_TIE_MARGIN=0` as named constants,
  keyword-overlap type scoring, confident/ambiguous/drop decision (ambiguous emits from the
  nearest tied candidate at `confidence=0.25`). Pure — no network I/O, no world-model queries
  beyond `geometry.py`'s bearing/range math.
- `body-layer/src/perception/hybrid_source.py` (new) — `HybridPerceptionSource`. Gates on
  `middle_list_text`, debounces on text change (resets when the field goes empty, so a detection
  reappearing with identical text still re-emits after a real gap), calls `association.py` then
  builds an `Observation` with `source="petrovich_detection_associated"` and a provenance string
  distinguishing confident vs. ambiguous association. Logs drops as a count/rate signal
  (`_dropped_count`), not per-instance noise.
- `body-layer/src/aircraft_client.py` — added `get_petrovich_indication_latest()`, mirroring
  `get_world_objects_latest()` exactly.
- `body-layer/src/logger.py` — added `main()` (argparse CLI: `--aircraft-layer-url`, `--theatre`,
  `--poll-interval-s`), the one place that plugs in `HybridPerceptionSource` and drives
  `PerceptionLogger`'s poll loop. `PerceptionLogger` itself was **not** modified — it already only
  depended on the `PerceptionSource` protocol.
- `body-layer/tests/test_association.py` (new) — hand-authored fixtures (noted as such in the
  module docstring): single-candidate confident match, zero-candidate drop, range-cap and
  forward-hemisphere filtering, ambiguous same-type multi-candidate scene (nearest-tied-candidate
  selection), type-match tie-breaking, heading-relative-not-compass-relative bearing window, and
  `WorldObjectCandidate.from_dict`'s coordinate-conversion call (monkeypatched `wgs84_to_dcs`).
- `body-layer/tests/test_hybrid_source.py` (new) — no-indication/no-classification/no-world-objects/
  no-plausible-candidate all return `[]`; confident and ambiguous emission paths (provenance,
  confidence); debounce (repeated identical text emits once, world-objects fetched only once);
  classification-change re-emits; detection-clears-then-reappears-with-same-text re-emits.
- `body-layer/tests/test_aircraft_client.py` — added
  `test_get_petrovich_indication_latest_returns_parsed_dict`; existing tests untouched.
- `test_logger.py` (stage 8) — confirmed to pass **unmodified**: the fake-`PerceptionSource`
  interface-conformance evidence the plan asked for, no new file needed.

**Docs (stage 9)**
- `docs/concept/PETROBRAIN_RUNTIME.md` — replaced the "Perception adapter" section's open-question
  framing with the shipped design and why (Session 4's four-dead-channels/one-alive-channel
  result), including the realized `source: petrovich_detection_associated` observation shape.
- `aircraft-layer/CLAUDE.md`, `body-layer/CLAUDE.md` — updated endpoint lists and `Structure`
  sections for the new `petrovich_indication` feed, `association.py`, and `hybrid_source.py`.

### Tests Added

**aircraft-layer** (18 new tests, 52 total passing)
- `test_petrovich_indication_schema.py` — flattening of populated leaves, childless/valueless
  nodes ignored, nested children, empty-string input, graceful degradation on non-conforming
  text, all the standard JSON-line-level malformed-input rejections, `to_dict` round-trip.
- `test_petrovich_indication_cache.py`, `test_petrovich_indication_api.py` — mirror the
  `world_objects` cache/API test shape exactly, including the default-cache-when-omitted
  backward-compatibility case.

**body-layer** (19 new tests, 47 total passing)
- `test_association.py` (9 tests) — see Files Changed above.
- `test_hybrid_source.py` (9 tests) — see Files Changed above.
- `test_aircraft_client.py` (1 new test) — `get_petrovich_indication_latest`.

### Checks

- `ruff format --check aircraft-layer/src aircraft-layer/tests`: pass (after auto-formatting 3
  files, then fixing 2 FLY002 f-string-preference findings by hand)
- `ruff check aircraft-layer/src aircraft-layer/tests`: pass
- `mypy aircraft-layer/src` (strict): pass, 9 source files
- `pytest aircraft-layer/tests -q`: pass, 52 passed
- `ruff format --check body-layer/src body-layer/tests`: pass (after auto-formatting 2 files)
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (strict, run via `cd body-layer && mypy src` per this subproject's
  CWD-only config-discovery note): pass, 8 source files
- `pytest body-layer/tests -q`: pass, 47 passed

### Notable Discoveries

- **`association.py`'s decision needed one interpretation call the plan text left slightly
  underspecified**: "one is unambiguously top-scored (score margin above a threshold over the
  next candidate)" could mean either "top score minus second score exceeds a positive margin" or
  "any strict inequality counts, margin=0 only catches exact ties." Implemented the latter
  (`TYPE_MATCH_TIE_MARGIN=0`, a named/tunable constant) — simpler, and "one is unambiguously
  top-scored" reads most naturally as "no other candidate matched the score," not "beat it by a
  specific amount." Flagged here in case Reviewer/user wants a nonzero starting margin instead.
- **`range_m` includes the altitude component** (confirmed already documented in
  `geometry.py`, but easy to trip over writing new fixtures) — `test_association.py`'s helper
  candidates default to ownship's own altitude so tests can assert exact ground-distance values
  without hand-computing slant range; caught by a first failing test run before the fix.
- **`WorldObjectCandidate.from_dict`'s coordinate conversion is intentionally excluded from
  `associate()`'s own tests** — `test_association.py` builds candidates directly with DCS-native
  x/z, and `test_hybrid_source.py` monkeypatches `association.wgs84_to_dcs` to an identity-ish
  mapping, so neither pure-logic test suite depends on real per-theatre projection math (already
  covered by world-model's own coordinate-subsystem tests and by
  `test_world_object_candidate_from_dict_converts_lat_lon_via_coordinates`'s own monkeypatched
  call-shape check).
- **`logger.py`'s `main()` is intentionally untested** — a live/replay poll-loop driver with no
  automated coverage, same posture this repo already accepts for
  `aircraft-layer/src/collector/__main__.py`'s own `main()`. `PerceptionLogger` and
  `HybridPerceptionSource`, the logic it wires together, are both fully tested.
- **Debounce reset-on-empty was a design choice beyond the plan's literal text**: the plan left
  "exact debounce window ... an implementation detail, not architectural" open. Implemented as
  "emit on any change from the last-emitted text, and treat a momentary empty/no-detection poll
  as clearing that memory" — chosen so a detection that disappears and later reappears with
  *identical* text (e.g. Petrovich re-acquires the same truck after briefly losing it) still
  re-emits, rather than silently staying suppressed indefinitely. Noted in the module docstring;
  flagged here as a judgment call, not a plan requirement, in case live testing shows it needs
  retuning (e.g. a minimum re-emit interval even without a gap).
