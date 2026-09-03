### Implementation Summary

Cross-stage decision log for `plans/m2-raster-understanding/plan.md`. Entries
below are appended per stage, oldest first.

---

## Stage 2 — loader + registration

Implemented the M2 RasterCharts tile registration layer: a `raster` module mirroring `coordinates/`'s shape, converting between DCS-native (x, z) and RasterCharts tile + in-tile pixel coordinates for Syria, plus diagnostic tooling and the `pillow` dependency decision.

### Files Changed
- `world-model/pyproject.toml` — added `pillow>=9.1` as a real (non-dev) dependency; tile decoding is core to M2, not scratch tooling.
- `world-model/CLAUDE.md` — recorded the pillow decision in Tech stack, alongside the M1 pyproj entry, pointing at `world-model/research/2026-09-03-m2-rastercharts-recon.md`.
- `world-model/src/raster/registration.py` — new. `RasterRegistration` dataclass (scale, origin_x/z, default sheet/level, source, confidence) with the fitted Syria params, plus `dcs_to_tile_pixel`/`tile_pixel_to_dcs`. Encodes the session 8 finding that the two tile axes are asymmetric relative to DCS's x/z convention: z-tile-index increases east (same direction as DCS +z), but x-tile-index increases south (opposite DCS +x=north).
- `world-model/src/raster/__init__.py` — new. Theatre-agnostic public API: `TileId` dataclass + filename parsing (`parse_tile_filename`), `load_tile` (Pillow DDS→RGB decode), and `dcs_to_pixel`/`pixel_to_dcs` wrapping `registration.py`.
- `world-model/tests/test_raster_registration.py` — new. Control-point tests reusing the already-validated `coordinates.wgs84_to_dcs` to avoid circularity.
- `world-model/tools/decode_raster_tile.py` — new. Promotes the ad hoc Pillow DDS→PNG decode from M2 recon into a reusable CLI probe script.
- `world-model/tools/inspect_raster.py` — new. Scans a directory of `*.tif.dds` tiles and prints per-sheet/level x/z grid coverage.
- `world-model/tests/test_coordinates.py` — fixed a pre-existing ruff import-sort violation (unrelated to M2, but blocking a clean `ruff check`).

### Tests Added
- `test_tile_filename_round_trips` / `test_parse_tile_filename_rejects_unrecognized_name` — filename grammar parsing.
- `test_unknown_theatre_raises_value_error` — registration lookup failure mode across all three public entry points.
- `test_dcs_to_pixel_round_trips_to_within_one_pixel` — arithmetic round-trip sanity, independent of real-world accuracy.
- `test_control_point_maps_to_expected_tile_and_pixel` (parametrized: Sivas, Kahramanmaras, Hama, Erzincan) — validates the registration hypothesis against real-world control points, with asymmetric per-axis tolerances (100px row / 350px column) derived from the recon's documented residuals (x-axis <0.2%, z-axis ~9%).

### Checks
- ruff format --check world-model/src world-model/tests: pass
- ruff check world-model/src world-model/tests: pass
- mypy world-model/src (strict): pass (4 source files)
- pytest world-model/tests -q: pass (13 passed)

### Notable Discoveries
- A pre-existing `ruff check` failure in `tests/test_coordinates.py` (unsorted import block) was present on `main` before this feature branch — fixed in a separate small commit since it blocked a clean lint pass, but it's unrelated to M2 itself. Worth checking why it wasn't caught at the time the M1 commit landed (possibly a ruff version bump since then).
- Registration confidence is explicitly `"provisional"` — fitted only against the Syria `64m` `aa` sheet, level `00`; not cross-checked against the `32m` tier or other levels/sheets. Future M2 work extending to other sheets/scales must not assume this origin carries over (see module docstring in `registration.py`).

---

## Stage 3 — render + control-point validation

Implemented on top of Stage 2's already-merged `src/raster/registration.py`
and `src/raster/__init__.py`. Stage 2's merge (commit `7f7eae6`, "M2:
implement RasterCharts DCS x/z <-> tile-pixel registration") had already
added `world-model/tests/test_raster_registration.py` ahead of the plan's
stage split — it contains the control-point test the plan assigns to Stage
3, and was passing before this session started (its "Tests Added" section
above already covers it). This session's work was therefore: (1) document a
gap in that existing test's docstring, and (2) add the marker-rendering
diagnostic, which did not exist yet.

### Files Changed
- `world-model/tests/test_raster_registration.py` — added a paragraph to the
  module docstring documenting that all four control points used in
  `test_control_point_maps_to_expected_tile_and_pixel` (Sivas, Kahramanmaras,
  Hama, Erzincan) are the *same* points `registration.py`'s empirical fit was
  derived from (session 8 fit `origin_x` from Sivas/Kahramanmaras/Hama;
  session 7 fit `origin_z` from Sivas/Erzincan). No held-out point exists
  yet, so this test currently validates the `dcs_to_tile_pixel` arithmetic
  and origin wiring, not independent real-world accuracy of the fit —
  a wrong fit and a test checking that same wrong fit would agree. An
  independent held-out third point is explicitly deferred to Stage 4 per
  the plan, not silently glossed over. Also fixed a pre-existing `ruff`
  import-sort (I001) finding on this file while touching it (harmless
  reorder of `import pytest` above the local imports, no logic change).
- `world-model/tools/inspect_raster.py` — restructured from a single-mode
  script into an `argparse` two-subcommand CLI:
  - `scan <tile_dir>` — unchanged behavior (grid/dimension dump), now
    factored into `cmd_scan`.
  - `mark <tile_dir> <theatre> <x> <z> [--out out.png]` — new. Converts the
    DCS coordinate via `raster.dcs_to_pixel`, locates the covering tile in
    `tile_dir`, draws a small red crosshair (cross + circle, via
    `PIL.ImageDraw`) at the resulting pixel, and saves a PNG (default name
    derived from the tile filename + pixel coords if `--out` is omitted).
    This is the plan's concrete "render a known DCS coordinate onto the
    raster" deliverable — the human-inspectable diagnostic. Exits with an
    error message (not a traceback) if the covering tile isn't present in
    the given sample directory, since `tools/` diagnostics only ever operate
    over locally-sampled tiles, not the full tile set.
- `world-model/tests/test_coordinates.py` — the I001 import-sort fix that
  Stage 2's log (above) recorded making had been lost by the time this
  session started (confirmed via `git stash` that it failed `ruff check` on
  `main`). Re-fixed here in its own commit, no logic change.

### Tests Added
- No new test functions — `test_raster_registration.py`'s control-point
  test already existed (added in Stage 2) and was left structurally
  unchanged (only its docstring gained the held-out-point caveat above).
  The `mark` subcommand was manually verified against the locally sampled
  tiles
  (`data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T113038Z/`):
  Sivas' WGS84 position round-tripped through `wgs84_to_dcs` -> `mark`
  correctly resolved to tile `64maa00_x0_z1.tif.dds`, pixel (679, 25) —
  within the test file's documented tolerances of the by-eye-read expected
  pixel (820, 30) (row/py within 100px tolerance: |25-30|=5; column/px
  within 350px tolerance: |679-820|=141). Not added as an automated test
  since `tools/` is explicitly exploratory/diagnostic, not pipeline code
  (per `world-model/CLAUDE.md` Structure section) and depends on a local
  sample-tile directory that isn't part of the committed repo.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (also verified `mypy src tools tests` run from
  `world-model/` so `pyproject.toml`'s `mypy_path` resolves local-package
  imports): pass, 0 issues
- `pytest world-model/tests -q`: pass, 13 passed

### Notable Discoveries
- Confirmed (again) that running `mypy` (or `ruff`) from the repo root
  against `world-model/tools` or `world-model/tests` directly fails with
  `import-not-found` for the local `raster`/`coordinates`/`control_points`
  packages, because `pyproject.toml`'s `mypy_path = "src:tests"` is relative
  and only resolves when the tool is invoked with `world-model/` as the
  working directory. The command list in `world-model/CLAUDE.md` already
  accounts for this by running `mypy world-model/src` (not `tools`/`tests`)
  from the repo root — worth remembering that any strict type-check of
  `tools/`/`tests/` files must be run with cwd = `world-model/`, not the
  repo root, or it produces spurious import errors.
- The `test_coordinates.py` I001 fix regressed between Stage 2 and this
  session despite being recorded as fixed in Stage 2's log — worth a look at
  whether the merge to main (`475d580`) dropped a commit, or whether a
  later, unrelated commit reintroduced the unsorted import. Not investigated
  further here since it's outside Stage 3 scope; re-fixed and noted.

## Stage 4 — Refine

Two Stage 4 items per the plan: (1) confirm the registration/`mark` code picks a sensible
default sheet/level when scanning multi-sheet/multi-level tile layouts, and (2) add a
genuinely held-out control point (not one of Sivas/Kahramanmaras/Hama/Erzincan, all of
which fed `registration.py`'s empirical fit) as an independent accuracy check.

### Files Changed
- `world-model/tools/inspect_raster.py` — `scan` subcommand gained an optional `--theatre`
  flag: when given, it looks up that theatre's `RasterRegistration` default
  `(scale, sheet, level)` group, annotates the matching grid-layout block with
  `<- '<theatre>' registration default`, and prints a `WARNING:` line if that default group
  isn't present among the scanned tiles at all. This is the concrete "confirm the code picks
  the right tile group" diagnostic the plan asked for — a human running `scan --theatre
  Syria` can see at a glance whether the registration's chosen default is even backed by
  locally sampled data, rather than only discovering a mismatch when `mark` fails later.
- `world-model/tests/test_raster_registration.py` — added `test_held_out_control_point_gemerek`
  and updated the module docstring (the "no held-out point yet" caveat from Stage 3 is now
  resolved). Gemerek (a Sivas Province district center, published coordinates from
  Wikipedia) sits on tile `64maa00_x0_z0.tif.dds`, a tile downloaded during the original
  probe but never used by sessions 7-8's fit or examined for a control point until this
  session. Residual: ~2px/~129m on the x-axis (row), ~86px/~5,515m on the z-axis (column) —
  both comfortably inside the existing per-axis tolerances (100px row / 350px column), and
  the z-axis residual (~8.4% of tile edge) closely matches session 7's already-documented
  ~9% z-axis residual — an independent confirmation the stated `"provisional"` fit accuracy
  is realistic, not optimistic.
- `world-model/research/2026-09-03-m2-rastercharts-recon.md` — appended session 12: the
  level-semantics review (RasterCharts' `.tif.dds` `level` suffix remains genuinely
  unresolved — no locally-sampled `RasterCharts` tile exists at any level other than `"00"`,
  so there's no local content to compare; session 9's clipmap-specific `level*32` header
  finding is explicitly flagged as *not* transferable evidence, since `clipmaps`'
  `.tif.clipmap` is a different, custom-header container from `RasterCharts`' plain DXT5 DDS
  — reasoning by analogy across the two would be exactly the kind of unverified-DCS-internals
  claim this project's process exists to prevent) and the held-out-point findings/residual
  derivation above.
- `world-model/tests/test_coordinates.py` — the recurring `ruff` import-sort (I001) finding
  reappeared again (third time across Stages 2-4, per the note already in Stage 3's log) and
  was re-fixed in the same small pass as the other lint fixes this session; still not
  investigated further (out of Stage 4 scope), see Notable Discoveries below.

### Tests Added
- `test_held_out_control_point_gemerek` — independent (non-fit-input) control-point check;
  asserts Gemerek's predicted tile/pixel position against the same tolerance constants the
  existing fit-input tests use.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass
- `mypy world-model/src` (strict): pass, 4 source files
- `mypy src tools tests` (also run with cwd=`world-model/`, per the known `mypy_path`
  quirk documented in Stage 3's log): pass, 10 source files
- `pytest world-model/tests -q`: pass, 14 passed

Note: `world-model/tools/` is not in the project's official `ruff format`/`ruff check`
command scope (`world-model/CLAUDE.md`'s Commands section only lists `src`/`tests`), but
was spot-checked anyway this session (`ruff format tools`, `ruff check` after fixing) — the
one real finding (`inspect_raster.py`'s changed print statement needing reformatting) was
fixed; two pre-existing `EXE001` ("shebang present but file not executable") findings in
`tools/decode_raster_tile.py` and `tools/inspect_raster.py` were left alone as out of scope
(neither is new this session, and `tools/` isn't part of the enforced lint surface).

### Notable Discoveries
- **RasterCharts' `level` semantics are still an open question, deliberately left
  unresolved rather than guessed at.** No locally-sampled `RasterCharts` tile exists at any
  level other than `"00"` (confirmed by listing both sample directories) — closing this
  needs a live-DCS/WSL probe to pull at least one `level != "00"` tile at an already-sampled
  sheet/x/z, which this session had no access to run. `registration.py`'s
  `default_level="00"` stays correct regardless of what `level` numerically means, because
  it's the level the empirical fit was actually run against (sessions 7-8) — but this is a
  process/provenance justification, not a content-based one, and the module docstring/plan
  should keep flagging it as such rather than letting a future session assume it was
  resolved.
- The `test_coordinates.py` I001 import-sort finding has now reappeared a third time across
  Stages 2-4 despite being "fixed" in each prior stage's log. This strongly suggests either
  a `ruff` version/config drift between sessions/environments, or a workflow step (e.g. a
  merge, a stash pop, an editor auto-format) that's silently reintroducing it — worth an
  actual investigation (not just another re-fix) before Stage 5/close-out, since re-fixing
  it a fourth time without finding the cause just defers the same finding to whoever works
  on this branch next.
- The held-out control point (Gemerek) landing at almost exactly the z-axis's
  already-documented ~9% residual, rather than being either much tighter or much looser, is
  a reassuring but not airtight signal: with only one held-out point, "matches the expected
  looseness" and "got lucky within a wide tolerance window" aren't fully distinguishable. A
  second held-out point at a different z-tile-index (not attempted this session, time/sample
  constrained) would meaningfully strengthen this if pursued later.
