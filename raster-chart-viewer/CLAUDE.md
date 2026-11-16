# raster-chart-viewer/CLAUDE.md

Subproject instructions for the raster chart viewer. Augments the root `CLAUDE.md` -- read that
first for overall Petrobrain architecture; this file adds stack/testing/structure specifics that
apply only within `raster-chart-viewer/`.

See `mission-interpreter/ROADMAP/MI-B4.md` for this feature's roadmap entry (this subproject has no
`ROADMAP/` of its own -- user direction, 2026-11-16: *"this should really be it's own small
service, not under MI. I just did not want to create another roadmap folder for it."*) and
`plans/raster-chart-viewer/plan.md` for the plan this subproject was built from. See `README.md`
for run instructions, including the Stage 7 Windows live check.

## What this is

A standalone LAN service, independent of every other Petrobrain subproject, that serves an
installed DCS World terrain's `RasterCharts` as a standard pan/zoom tiled map in a browser. **No
Petrovich behaviour depends on this** -- it is a crew reference tool (the paper chart on a tablet),
not a perception/belief/decision feature. It imports nothing from any other subproject and nothing
else in the repo depends on its output.

Tiles are made on demand from the installed DCS terrain's zip(s) -- no bulk extraction, and nothing
here ever writes into the DCS install. See `research/2026-11-16-rastercharts-all-terrains-recon.md`
for the file-layout/naming/sheet-mosaic facts this service is built against.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`).
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- Dependencies: `pillow` only (stdlib otherwise -- `zipfile`, `http.server.ThreadingHTTPServer`,
  `argparse`). No web framework, no GDAL/libvips/tile-server product.
- **DDS/DXT5 mip decode: `ddsmip.py`'s own byte-offset formula + Pillow's `Image.frombytes(...,
  "bcn", 3)` decoder** -- Pillow's DDS plugin only returns the base image (mip 0); every smaller
  mip sits at a computable offset immediately after it in the same contiguous block. See
  `ddsmip.py`'s module docstring and
  `.claude/agent-memory/architect/reference_pillow_dds_dxt5_write_and_mip_offsets.md`.
- **Cache: composed-tile JPEGs plus small-mip PNGs only, one shared 1GB cap** -- see `cache.py`'s
  module docstring for the full shape and why the plan's first ("every mip of every inflated
  entry") design was superseded.
- **Port 7800** -- one past the aircraft-layer family (7790-7799), grepped repo-wide before
  choosing; see `server.py`'s own `DEFAULT_PORT` comment.
- **OpenSeadragon, vendored**: version **4.1.1** (released 2024-04-01, well over a few months old
  as the plan required). Fetched from the official npm package `openseadragon@4.1.1`
  (`https://registry.npmjs.org/openseadragon/-/openseadragon-4.1.1.tgz`) via `npm pack` -- the
  package's own `build/openseadragon/` output, not rebuilt locally. Vendored into
  `static/openseadragon/`: `openseadragon.min.js` and `images/` (the toolbar button sprites) only
  -- the non-minified `openseadragon.js` and both `.js.map` source maps were left out as dead
  weight for a vendored production asset. Licence: BSD-3-Clause, `static/openseadragon/LICENSE.txt`
  (fetched from the same package, `LICENSE.txt` at its root).

## Commands

```sh
ruff format raster-chart-viewer/src raster-chart-viewer/tests   # format
ruff check raster-chart-viewer/src raster-chart-viewer/tests    # lint
cd raster-chart-viewer && .venv/bin/mypy src                     # type check (strict) -- CWD-only config discovery, see below
pytest raster-chart-viewer/tests -q                               # test
```

**`mypy` must run from inside the subproject.** Its config discovery is CWD-only, so
`mypy raster-chart-viewer/src` from the repo root silently drops `strict` and the CWD-relative
`mypy_path` (root `CLAUDE.md`, "Subprojects"). See `world-model/CLAUDE.md`'s own note for the
measured case this mirrors.

Run a single test: `pytest raster-chart-viewer/tests/test_file.py::test_name -q`.

`raster-chart-viewer/.venv` is this subproject's own venv (module-independence rule, root
`CLAUDE.md`) -- reinstall with:

```sh
python3 -m venv raster-chart-viewer/.venv
raster-chart-viewer/.venv/bin/pip install "pillow>=9.1" "ruff==0.16.6" "mypy==2.3.1" "pytest==9.1.1"
```

## Testing

- No live DCS, no network, no real `rasterCharts.zip` anywhere in the test suite -- mirrors
  `aircraft-layer`'s "fixture-based unit tests, no live DCS needed" pattern for everything except
  the one live check (Stage 7, this feature's only manual acceptance step).
- `tests/fixtures/synthetic_dds.py` builds a multi-mip DXT5 DDS entirely with Pillow (no hand-built
  block bytes) -- see its module docstring for the exact method. `tests/fixtures/
  fake_terrain_trees.py` builds temp directory trees mimicking both the single-zip and Caucasus
  zip-per-sheet layouts.
- **Never commit chart images or anything decoded from real DCS files.** They belong to Eagle
  Dynamics. Every test fixture is synthetic.
- `tests/test_server.py` spins up a real `RasterChartViewerServer` on an OS-assigned port in a
  background thread, mirroring `aircraft-layer/tests/test_api.py`'s own pattern.
- The viewer page (`static/index.html`) has no automated UI test -- Stage 5's own acceptance is a
  one-time manual browser check (consistent with this project's js-light posture), done here as a
  real-server smoke test (every endpoint the page calls, served end-to-end) plus a `node --check`
  syntax check on the inline script, not a full browser render.

## Structure

- `src/raster_chart_viewer/` -- `tilename.py` (the universal filename regex, `TileKey`),
  `discovery.py` (walks `Mods/terrains/*/RasterCharts/`, single-zip and Caucasus zip-per-sheet
  layouts unified once the right zip paths are found -- scale/sheet always come from entry names,
  never zip/folder names), `mosaic.py` (sheet/level -> tile-grid coordinate math, pinned against the
  research note's Syria 32m convention), `ddsmip.py` (mip byte-offset formula + decode),
  `cache.py` (disk cache + tile composition), `server.py` (`RasterChartViewerServer`,
  `ThreadingHTTPServer`), `__main__.py` (CLI entry point).
- `static/` -- `index.html` (the OpenSeadragon viewer page: terrain/tier pickers, a custom
  plain-object `TileSource` against this server's own endpoints) and `openseadragon/` (vendored
  release, see Tech stack above).
- `tests/` -- one test module per `src/` module, plus `tests/fixtures/` (synthetic DDS + fake
  terrain tree builders, never real DCS data).
- `research/` -- dated findings from DCS RasterCharts investigation (root `CLAUDE.md`'s
  "investigator" section). `2026-11-16-rastercharts-all-terrains-recon.md` is the authority on file
  layout, naming, the sheet mosaic, and timing.
