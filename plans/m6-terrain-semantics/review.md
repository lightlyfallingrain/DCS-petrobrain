### Review Summary

M6 (terrain semantics: ridge/valley extraction) was reviewed against
`plans/m6-terrain-semantics/plan.md`, root `CLAUDE.md`/`AGENTS.md` invariants, and
`world-model/docs/CONVENTIONS.md`. The implementation matches the plan closely: stdlib
discrete-Laplacian curvature classification (`terrain/curvature.py`), 4-connected-component
grouping + closed-form principal-axis line extraction (`terrain/features.py`), a new
`store.reader.load_full_grid`, `build/ingest_terrain.py` mirroring `ingest_probe.py`'s shape,
pipeline wiring gated on probe-grid presence (absence-as-absence preserved), and
`nearby_ridges`/`nearby_valleys` in `describe.py` following the exact `nearest_road`/
`nearest_water` per-kind pattern (separate fields, not combined — per the user's confirmed
decision). No new dependency was added; the plan's numpy/scipy escalation was correctly not
triggered.

Provenance: `provenance={"geometry": "dcs_derived"}` is used consistently, distinct from
`"dcs"`/`"osm"`, and the plan's Risk item ("confirm it doesn't collide with any assumption
`query/describe.py` or `tools/export_geojson.py` makes") was genuinely checked — both treat
`provenance["geometry"]` as an open string, not a fixed enum, confirmed by reading both files.
`confidence={"geometry": "low"}` is carried on every emitted feature and surfaces correctly
through `TerrainLineInfo.confidence` in `describe.py`.

Tests are genuine control-point tests, not smoke tests: `test_terrain_curvature.py` and
`test_terrain_features.py` hand-build grids with a closed-form height function
(`100 + sign*10*abs(row-3) + 2*col`), assert exact recovered cell sets, exact orientation
(90°, hand-derived from the axis-aligned fixture), and exact hand-computed `elevation_range_m`
— this meets `world-model/CLAUDE.md`'s "a transform that looks about right without a
control-point test is not done" bar. `test_describe_position.py` extensions correctly test
both absence-as-absence (no terrain features in store → `None`) and presence with full field
shape/provenance/confidence assertions.

The research note's "usefulness" validation is honest and reasonably rigorous for an
unstaffed, no-SRTM-tile situation: it uses a live third-party API (Open-Elevation) as a
genuinely independent, non-circular check, shows a real threshold-sweep table (not just the
final chosen value), and explicitly reports the negative result (Finding 2 — R2/R3 misses,
checkerboard noise not eliminated even at 80m) rather than smoothing it over. This is
consistent with the plan's explicit instruction to record "not useful yet" findings.

Ran all four required checks fresh, all pass:
- `ruff format --check world-model/src world-model/tests` — pass (62 files, no cwd-dependent
  isort flip this time — `terrain` was correctly added to `known-first-party` in
  `pyproject.toml`).
- `ruff check world-model/src world-model/tests` — pass.
- `mypy world-model/src` (`--strict` via `pyproject.toml`) — pass, 38 source files.
- `pytest world-model/tests -q` — 160 passed.

No writes to a DCS installation; all `world-model/data/` machinery stays gitignored (verified
nothing under `world-model/data/` appears in `git status --porcelain`). No debug/TODO/FIXME
left in the new code; `print()` calls in `tools/inspect_terrain.py` are the same
diagnostic-CLI pattern as every other `tools/inspect_*.py` script.

### Required Fixes

- **Agent-memory files are not staged.** `git status` shows
  `.claude/agent-memory/implementer/MEMORY.md` modified-but-unstaged and two new untracked
  files (`feedback_decouple_fixtures_from_tuned_defaults.md`,
  `project_m6_terrain_semantics.md`) under the same directory. Per root `CLAUDE.md`'s
  Definition of Done ("All new/modified files staged and committed... confirm a clean working
  tree"), these must be `git add`ed before this milestone can be declared done. This is a
  recurring pattern across M4/M5/M6 (see reviewer memory) — worth the implementer treating
  `git add -A` on the whole `.claude/agent-memory/` tree as a standard last step before
  reporting DoD.

### Optional Refinements

- The research note's Finding 2 (classifier reliably catches only the single dominant
  peak/trough, misses secondary bumps/troughs, persistent checkerboard noise in the
  mountainous quadrant) is a real limitation on tactical usefulness ("is there a ridge between
  me and the target" cannot yet be trusted). This is correctly recorded as an honest finding
  rather than hidden, and the plan explicitly treats "only marginally useful" as an acceptable
  M6 outcome — not a blocker, but worth keeping visible for M7/Mission-Interpreter-layer
  planning so a denser probe grid or a smoothing pre-filter isn't assumed to already exist.
- The Open-Elevation API spot-check (Stage 3) is informal/one-off and not wired into the
  pipeline or the research-note conventions used for M4's formal SRTM delta stats — this is
  explicitly and honestly flagged in the note itself as not a substitute for a staged SRTM
  tile, so no action needed now, just worth remembering if a later milestone wants to treat
  this number as more authoritative than it is.
- `terrain/features.py`'s `_principal_axis` closed-form 2x2 eigenvector solve is correct but
  dense; a short worked-example comment (e.g. the numbers from the test fixture) alongside the
  existing prose docstring would make future maintenance easier — pure readability, no
  correctness concern (tests already pin the behavior).

### Verdict

APPROVED WITH MINOR FIXES
