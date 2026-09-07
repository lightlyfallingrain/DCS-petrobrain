---
name: pb1-stage2-3-body-layer
description: body-layer BL-0 scaffolding + aircraft-layer world_objects endpoint (2026-09-07) -- key non-obvious choices for future PB-1 stages
metadata:
  type: project
---

Built `plans/pb1-perception-logger/plan.md` stages 2-3: the `body-layer/` subproject's
tier-independent `PerceptionSource` scaffolding, and aircraft-layer's `GET /world_objects/latest`.
Stage 1 (live DCS spike for HelperAI's device ID) and stage 4+ (concrete tier implementations)
are not built -- gated on the user running the spike on the Windows box.

**Key non-obvious choices, useful for whoever builds stage 4:**

- `body-layer/src/perception/geometry.py` does **not** route every world-model read through
  `query.describe_position`, despite the plan's Affected Modules section reading that way.
  `elevation_at` does; `line_of_sight_clear`'s ~20-sample-per-call loop calls
  `store.reader.sample_grid` directly instead, since `describe_position` also computes
  unrelated road/settlement/navaid joins per sample. Documented in the module docstring.
- `geometry.open_world_model` reimplements `build.pipeline.open_region_db`'s one-line
  `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` rather than importing that module --
  `build.pipeline` transitively pulls in the entire ingest pipeline (`osm`, `terrain`,
  `dcs_data`, SRTM ingest, ...), none of which a read-only query path needs.
- **`LoGetWorldObjects` returns lat/lon/altitude, not DCS x/y/z** (unlike `LoGetSelfData`).
  `aircraft-layer/src/schema/world_objects.py` keeps it as raw lat/lon -- aircraft-layer has no
  world-model dependency, so the x/z conversion is deferred to whichever body-layer tier
  consumes it (`coordinates.wgs84_to_dcs`), not built yet. A concrete Tier 3 `PerceptionSource`
  will need to do this conversion itself before calling `perception.geometry`'s bearing/range
  functions, which operate on DCS x/z only.
- `Observation.source` (in `perception/source.py`) was left as a plain `str`, not a closed
  enum -- the two governing plans (`body-layer/plan.md` §5 vs. `pb1-perception-logger/plan.md`)
  list different candidate values and neither concrete tier exists yet to settle the real set.
- `PerceptionSource.poll(now_sim, ownship_state)` only takes ownship state -- a concrete source
  fetches its own tier-specific data (Petrovich feed string, or `aircraft_client`'s
  `world_objects` call) internally, typically via an injected/fakeable client. `replay.py`'s
  harness therefore only drives the ownship half of the loop and knows nothing about
  `world_objects` payload shape -- don't try to thread tier-specific fixture data through
  `replay.replay()` itself when building stage 4/6's interface-swap smoke test; inject it into
  the concrete `PerceptionSource` instead.
- `body-layer/CLAUDE.md` documents `mypy body-layer/src` as the canonical command, but per
  [[project_worldmodel_mypy_path_cwd]] this only works correctly with `cwd=body-layer/` --
  invoked from repo root, mypy silently drops both strict mode and `mypy_path`, so
  `query.describe`/`store.reader` imports report false `import-not-found` errors. Always verify
  from inside the subproject.
- Found but deliberately left unfixed: `.claude/agents/{architect,reviewer,implementer,
  performance-reviewer,debugger}.md` all still say "Mission Interpreter and Petrobrain Runtime
  modules do not exist yet" -- `body-layer/` is now real code (though still just BL-0/1
  scaffolding, not the real Mission Interpreter/Runtime). Editing agent role definitions is
  outside an Implementer's scope; flagged for the user/architect.
