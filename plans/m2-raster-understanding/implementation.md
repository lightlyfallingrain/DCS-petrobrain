### Implementation Summary

Implemented M2 Stage 3 (render + control-point validation) on top of Stage 2's
already-merged `src/raster/registration.py` and `src/raster/__init__.py`.
Stage 2's merge (commit `7f7eae6`, "M2: implement RasterCharts DCS x/z <->
tile-pixel registration") had already added
`world-model/tests/test_raster_registration.py` ahead of the plan's stage
split -- it contains the control-point test the plan assigns to Stage 3, and
was passing before this session started. This session's work was therefore:
(1) document a gap in that existing test's docstring, and (2) add the
marker-rendering diagnostic, which did not exist yet.

### Files Changed
- `world-model/tests/test_raster_registration.py` -- added a paragraph to the
  module docstring documenting that all four control points used in
  `test_control_point_maps_to_expected_tile_and_pixel` (Sivas, Kahramanmaras,
  Hama, Erzincan) are the *same* points `registration.py`'s empirical fit was
  derived from (session 8 fit `origin_x` from Sivas/Kahramanmaras/Hama;
  session 7 fit `origin_z` from Sivas/Erzincan). No held-out point exists
  yet, so this test currently validates the `dcs_to_tile_pixel` arithmetic
  and origin wiring, not independent real-world accuracy of the fit --
  a wrong fit and a test checking that same wrong fit would agree. An
  independent held-out third point is explicitly deferred to Stage 4 per
  the plan, not silently glossed over. Also fixed a pre-existing `ruff`
  import-sort (I001) finding on this file while touching it (harmless
  reorder of `import pytest` above the local imports, no logic change).
- `world-model/tools/inspect_raster.py` -- restructured from a single-mode
  script into an `argparse` two-subcommand CLI:
  - `scan <tile_dir>` -- unchanged behavior (grid/dimension dump), now
    factored into `cmd_scan`.
  - `mark <tile_dir> <theatre> <x> <z> [--out out.png]` -- new. Converts the
    DCS coordinate via `raster.dcs_to_pixel`, locates the covering tile in
    `tile_dir`, draws a small red crosshair (cross + circle, via
    `PIL.ImageDraw`) at the resulting pixel, and saves a PNG (default name
    derived from the tile filename + pixel coords if `--out` is omitted).
    This is the plan's concrete "render a known DCS coordinate onto the
    raster" deliverable -- the human-inspectable diagnostic. Exits with an
    error message (not a traceback) if the covering tile isn't present in
    the given sample directory, since `tools/` diagnostics only ever operate
    over locally-sampled tiles, not the full tile set.

### Tests Added
- No new test functions -- `test_raster_registration.py`'s control-point
  test already existed and was left structurally unchanged (only its
  docstring gained the held-out-point caveat above). The `mark` subcommand
  was manually verified against the locally sampled tiles
  (`data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T113038Z/`):
  Sivas' WGS84 position round-tripped through `wgs84_to_dcs` -> `mark`
  correctly resolved to tile `64maa00_x0_z1.tif.dds`, pixel (679, 25) --
  within the test file's documented tolerances of the by-eye-read expected
  pixel (820, 30) (row/py within 100px tolerance: |25-30|=5; column/px
  within 350px tolerance: |679-820|=141). Not added as an automated test
  since `tools/` is explicitly exploratory/diagnostic, not pipeline code
  (per `world-model/CLAUDE.md` Structure section) and depends on a local
  sample-tile directory that isn't part of the committed repo.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass (one pre-existing
  I001 finding in `world-model/tests/test_coordinates.py`, untouched by this
  session -- see Notable Discoveries)
- `mypy world-model/src` (also verified `mypy src tools tests` run from
  `world-model/` so `pyproject.toml`'s `mypy_path` resolves local-package
  imports): pass, 0 issues
- `pytest world-model/tests -q`: pass, 13 passed

### Notable Discoveries
- `world-model/tests/test_coordinates.py` currently fails `ruff check`
  (I001, import-block ordering) on `main` already -- confirmed pre-existing
  via `git stash`, unrelated to this session's changes. Left unfixed per
  scope discipline (M1 test file, not part of this M2 Stage 3 task); worth a
  small standalone fix commit later.
- Running `mypy` (or `ruff`) from the repo root against `world-model/tools`
  or `world-model/tests` directly fails with `import-not-found` for the
  local `raster`/`coordinates`/`control_points` packages, because
  `pyproject.toml`'s `mypy_path = "src:tests"` is relative and only resolves
  when the tool is invoked with `world-model/` as the working directory.
  The command list in `world-model/CLAUDE.md` already accounts for this by
  running `mypy world-model/src` (not `tools`/`tests`) from the repo root --
  worth remembering that any strict type-check of `tools/`/`tests/` files
  must be run with cwd = `world-model/`, not the repo root, or it produces
  spurious import errors.
