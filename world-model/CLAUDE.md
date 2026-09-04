# world-model/CLAUDE.md

Subproject instructions for the DCS World Model Builder. Augments the root `CLAUDE.md` — read that first for overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply only within `world-model/`.

See `README.md`, `ROADMAP.md`, `WORKFLOW.md` in this directory for project design, milestone status, and the Mac/Windows cross-machine workflow. See `docs/CONVENTIONS.md` for the non-negotiable working rules (DCS reconnaissance, provenance/confidence, read-only DCS access).

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`).
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- **Coordinate transforms: `pyproj`** (M1 decision). Used for DCS x/z <-> WGS84 lat/lon via `+proj=tmerc +axis=neu`, in `src/coordinates/`. This decision is scoped to coordinate transforms only — the separate spatial-storage question (GeoPackage/SpatiaLite/FlatGeobuf/GeoPandas etc.) is **deferred to M5**: M3 confirmed no DB is needed yet (its only persisted artifact is a raw Overpass JSON cache; parsed features live as in-memory dataclasses for one tool invocation — no point-in-polygon/nearest-neighbor/multi-feature-type join workload exists before M5's `describe_position(...)`). See `research/2026-09-03-m3-osm-overlay.md`.
- **Raster tile decoding: `pillow`** (M2 decision). RasterCharts tiles are standard DXT5/BC3 DDS images (NVTT-built, no ED-proprietary encoding) — Pillow's built-in DDS plugin (9.1+) decodes them with no extra native deps, in `src/raster/`. See `world-model/research/2026-09-03-m2-rastercharts-recon.md` for the format recon behind this choice.
- **Elevation / DEM: SRTM (M4 decision)**. DCS-side elevation comes from `land.getHeight`, Mission Scripting-only (same environment as `coord.LOtoLL`) — no offline heightmap exists, so extraction is always a live-mission probe (`tools/dcs-mission-probe/elevation_probe.lua`), parsed by `src/elevation/dcs_grid.py`. External comparison DEM is SRTM's flat `.hgt` format (either SRTM1 or SRTM3 — `src/elevation/dem.py`'s `SrtmTile` derives grid resolution from file size rather than assuming one), parsed with stdlib `array` only, no GDAL/rasterio dependency. See `world-model/research/2026-09-03-m4-elevation-recon.md` (recon) and `.../2026-09-03-m4-dcs-elevation.md` (results) for the findings behind this choice.
- **Persistent spatial storage: stdlib `sqlite3` + R\*Tree (M5 decision)**. One SQLite file per region (`data/world-model/<theatre>.sqlite`), geometry stored as JSON `[[x,z],...]` in DCS x/z metres rather than WKB or GeoPackage — no GDAL/GeoPandas dependency; QGIS access goes through a `tools/export_geojson.py` export instead of a native GeoPackage writer. Implemented in `src/store/`. This decision closes the spatial-storage question left open since M3. See `world-model/research/2026-09-03-m3-osm-overlay.md` (deferral) and `.../2026-09-04-m5-first-persistent-model.md` (decision + milestone results).
- **Roads: DCS-native `.routes`/`.rn4` binary parsing, not live-probe (M5 decision)**. `land.getClosestPointOnRoads`/`findPathOnRoads` are dropped entirely in favor of directly parsing `Mods/terrains/Syria/roads/Syria.routes`'s float64-triple polylines (scan-forward resync over a `landscape4::`-prefixed binary container), in `src/roadnet/`. Road type/subtype from `.rn4` is left `null` in M5 (row→geometry join unconfirmed). See `world-model/research/2026-09-04-m5-roadnet-byte-decode.md` for the byte-exact format decode behind this choice.
- **Towns/beacons: regex Lua parsers (M5 decision)**. `towns.lua` (a list, not a dict) and `beacons.lua` (`{x, y, z}` with the middle value as elevation) are parsed directly from DCS's own terrain Lua source with targeted regexes, in `src/dcs_data/`, rather than a live Mission Scripting probe. See `world-model/research/2026-09-03-m5-nodes-lua-probe.txt` for the source recon behind this choice.

## Commands

```sh
ruff format world-model/src world-model/tests   # format
ruff check world-model/src world-model/tests    # lint
mypy world-model/src                             # type check (strict)
pytest world-model/tests -q                      # test
```

Run a single test: `pytest world-model/tests/path/to/test_file.py::test_name -q`.

## Testing

Every coordinate transform or spatial-query function must have at least one test against a known geographic control point (see `../docs/concept/WORLD_MODEL_BUILDER.md` "Validation"). A transform that "looks about right" without a control-point test is not done.

## Structure

- `src/` — pipeline code: DCS extraction, coordinate subsystem, OSM/DEM reconciliation, spatial DB, query API.
- `tools/` — one-off inspection/probe scripts (raster inspector, coordinate probes). Not part of the pipeline; exploratory.
- `research/` — dated findings from DCS/forum/community investigation. Required before encoding any claim about DCS internals into pipeline code.
- `tests/` — automated tests, including known geographic control points.
- `data/` — gitignored. `raw/` (untouched extracted/downloaded input), `processed/` (intermediate), `world-model/` (final per-theatre spatial DB).
