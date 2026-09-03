### Implementation Summary

Implemented the M2 RasterCharts tile registration layer per `plans/m2-raster-understanding/plan.md`: a `raster` module mirroring `coordinates/`'s shape, converting between DCS-native (x, z) and RasterCharts tile + in-tile pixel coordinates for Syria, plus diagnostic tooling and the `pillow` dependency decision.

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
