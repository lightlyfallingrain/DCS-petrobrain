### Implementation Summary

Built M6 (terrain semantics) per `plans/m6-terrain-semantics/plan.md`'s 4-stage sequence:
stdlib discrete-Laplacian curvature classification + 4-connected-component grouping +
closed-form principal-axis line extraction over the existing `latakia-20km` DCS live-probe
elevation grid, wired into the build pipeline and `describe_position`, tuned and validated
against the real store. No numpy/scipy escalation was needed — the stdlib approach from the
plan works end to end as specified.

### Files Changed

- `world-model/src/store/reader.py` — added `load_full_grid(conn, grid_kind) -> ElevationGrid |
  None`, reading every stored `grid_sample` row for the most recent grid of a kind into a full
  `samples[row][col]` matrix (unlike `sample_grid`'s single interpolated point lookup).
  `_GridMeta` extended with `source_id`/`stats_json` to support this.
- `world-model/src/terrain/__init__.py`, `curvature.py`, `features.py` — new package.
  `curvature.classify_curvature` computes `(N+S+E+W) - 4*centre` per interior cell, classifying
  ridge (negative, below threshold)/valley (positive, above threshold)/neither; cells with any
  unsampled neighbour are skipped, never approximated. `features.extract_components` groups
  same-classification cells via 4-connectivity flood-fill, drops components below
  `min_cell_count`, and extracts each surviving component's principal axis via the closed-form
  2x2 covariance-matrix eigenvector (no numpy). `features.to_stored_features` wraps the result as
  `StoredFeature` rows with `provenance={"geometry": "dcs_derived"}` (deliberately distinct from
  `"dcs"`/`"osm"`, confirmed non-colliding with `query/describe.py` and `tools/export_geojson.py`
  before Stage 2, per the plan's "Risks & Unknowns") and `confidence={"geometry": "low"}`.
- `world-model/src/build/ingest_terrain.py` — new ingest step mirroring `ingest_probe.py`'s
  shape: `ingest_terrain(grid, source_id, ...) -> (features, TerrainIngestStats)`.
- `world-model/src/build/pipeline.py` — wired `ingest_terrain` into `build_region`, nested inside
  the existing `probe_output_path` presence check (ridge/valley extraction needs the elevation
  grid the probe stage produces); reads the grid back via `load_full_grid` after `insert_grid`
  rather than reusing the in-memory pre-insert grid, matching the plan's stated module
  responsibilities. Added `terrain_stats`/`terrain_skipped` to `BuildReport`.
- `world-model/src/query/describe.py` — added `TerrainLineInfo` and `nearby_ridges`/
  `nearby_valleys` fields to `PositionDescription`, answered via the same `nearest_feature`
  machinery as `nearest_road`/`nearest_water` restricted to `kind="ridge"`/`"valley"` (per the
  user's confirmed decision: separate fields, not a combined one).
- `world-model/tools/inspect_terrain.py` — new diagnostic CLI rendering the per-cell curvature
  classification (ridge/valley/neither/unsampled) plus extracted lines as a PNG, north-up,
  east-right. Used to tune thresholds against real output before finalizing them (Stage 2).
- `world-model/pyproject.toml` — added `terrain` to `known-first-party` (ruff isort).
- `world-model/ROADMAP.md` — M6 marked done with a summary line.
- `world-model/research/2026-09-05-m6-terrain-semantics.md` — full Stage 2/3 findings (threshold
  tuning table, independent-elevation spot-check table, usefulness check), including the
  "checkerboard noise" limitation recorded honestly rather than smoothed over.

### Tests Added

- `test_store_reader.py`: `load_full_grid` returns the whole matrix, leaves missing cells `None`,
  returns `None` when absent.
- `test_terrain_curvature.py`: synthetic control-point grids (a straight row-aligned ridge/valley,
  4-connected — not diagonal, which would produce isolated single-cell components) — classifier
  recovers the known feature's cells exactly, off-feature cells are `NEITHER`, cells touching an
  unsampled neighbour are skipped entirely.
- `test_terrain_features.py`: connected-component grouping recovers the single ridge/valley line,
  orientation/elevation_range match the hand-computed fixture values, components below
  `min_cell_count` are dropped, `to_stored_features` shapes/provenance/confidence are correct.
- `test_ingest_terrain.py`: wiring test (threshold/min-cell-count plumbing, stats bookkeeping).
- `test_describe_position.py`: `nearby_ridges`/`nearby_valleys` absent without terrain features
  in the store (absence-as-absence), present and correctly shaped once ridge/valley `feature`
  rows exist.

All new unit tests pass an explicit `threshold_m`/`curvature_threshold_m` decoupled from the
production `DEFAULT_CURVATURE_THRESHOLD_M` (see Notable Discoveries) so they stay stable if the
production default is re-tuned again later.

### Checks

- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (`--strict` via `pyproject.toml`): pass
- `pytest world-model/tests -q`: pass (160 passed)

### Notable Discoveries

- **Stage 1's first-guess threshold (3.0 m) was unusably permissive on real data**: it classified
  ~71% of interior grid cells as ridge/valley over the region's mountainous quadrant — a
  near-solid checkerboard, not lines. Raising the threshold to 20.0 m (with `min_cell_count`
  raised from 4 to 6) reduces this to ~40% and produces 12 ridge + 12 valley features on the real
  `latakia-20km` store, but does **not** eliminate the checkerboard pattern — even at 80 m
  threshold the mountainous quadrant still shows adjacent-cell classification flips. This reads
  as real high-frequency relief at/below the 500 m probe grid's resolution floor, not a
  threshold-tuning artifact. Full detail in the research note.
- **Unit test fixtures needed decoupling from the tuned production default.** The Stage 1
  synthetic fixtures were originally sized so their curvature magnitude (20.0) exactly matched
  the eventual tuned default threshold (20.0), which the strict `<`/`>` comparison in
  `classify_curvature` turned into silent `NEITHER` misclassification once the default changed.
  Fixed by passing an explicit small threshold (`3.0`) at every test call site instead of relying
  on the module default — this is the right pattern going forward: algorithm control-point tests
  should never depend on a value Stage 2/4 tuning is expected to keep adjusting.
- **An independent (non-DCS) elevation cross-check was possible without a staged SRTM tile.**
  The public Open-Elevation API gave a legitimate, non-circular external elevation reference for
  spot-checking specific lat/lon points in this region (no tile is staged for Latakia — confirmed
  again this session). This is informal/one-off, not wired into the pipeline, but it let Stage 3's
  validation happen without deferring the whole milestone on a new SRTM tile acquisition.
- **Long-running foreground rebuilds in this environment**: the `Syria.routes` roadnet parse
  (2.25 GB, ~14,833 routes) takes noticeably longer wall-clock than CPU time would suggest when
  the machine is under other load (e.g. Spotlight indexing) — a run that looked "stuck" was
  actually still progressing, just starved of CPU. Foreground-and-log (not backgrounded/`nohup`)
  proved to be the reliable way to run and observe this step to completion in this session.
- **DCS elevation vs. the independent source agreed well** (within ~30 m at every spot-checked
  point) — a reassuring incidental confirmation that the underlying M5 elevation grid is sound;
  M6's ridge/valley limitations are in the derived analysis, not the source data.
