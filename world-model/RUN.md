# Running the World Model Builder

Builds a persistent, queryable geographic model of a DCS theatre — roads,
settlements, elevation, terrain semantics — into a single `.sqlite` file, and
queries it.

**Where this runs:** building needs DCS-derived source files, so it is normally
run on the Windows DCS box. Once a `.sqlite` exists it is just a file — copy it
anywhere and query it from either platform.

This is an **offline** tool. Nothing here talks to a running DCS.

For working rules (DCS reconnaissance, provenance, read-only DCS access) see
`docs/CONVENTIONS.md`; for the full-theatre procedure see
`docs/M7_RUN_INSTRUCTIONS.md`.

---

## 1. One-time setup

Two dependencies: `pyproj` (projections) and `pillow` (raster tiles).

**Windows (Command Prompt)**

```bat
cd world-model
python -m venv .venv
.venv\Scripts\python -m pip install -e .
```

**macOS (zsh)**

```zsh
cd world-model
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

No `PYTHONPATH` needed — the `tools/` scripts add `src` to `sys.path`
themselves.

## 2. Build a region

Available regions: **`latakia-20km`**, **`gemerek-20km`**, **`syria-full`**.

### The small regions

`latakia-20km` and `gemerek-20km` have registered default input paths, so the
common case needs only the region name.

**Windows (Command Prompt)**

```bat
cd world-model
.venv\Scripts\python tools\build_world_model.py latakia-20km
```

**macOS (zsh)**

```zsh
cd world-model
.venv/bin/python tools/build_world_model.py latakia-20km
```

### Full theatre

`syria-full` has **no registered defaults** and no OSM cache, so every input
must be given explicitly.

**Windows (Command Prompt)**

```bat
.venv\Scripts\python tools\build_world_model.py syria-full ^
  --towns <path\to\towns.lua> ^
  --beacons <path\to\beacons.lua> ^
  --routes <path\to\Syria.routes> ^
  --srtm-dir <path\to\hgt_tiles\>
```

**macOS (zsh)**

```zsh
.venv/bin/python tools/build_world_model.py syria-full \
  --towns <path/to/towns.lua> \
  --beacons <path/to/beacons.lua> \
  --routes <path/to/Syria.routes> \
  --srtm-dir <path/to/hgt_tiles/>
```

Expect roughly 7–8 minutes and a ~460 MB output for the full Syria theatre.

### Options

| flag | meaning |
|---|---|
| `--towns` | DCS `towns.lua` — named places |
| `--beacons` | DCS `beacons.lua` — navigation beacons |
| `--routes` | DCS `.routes` binary — road network |
| `--osm-cache` | cached OSM overlay JSON (small regions only) |
| `--srtm-dir` | directory of `.hgt` tiles, ingested as the **primary** elevation grid |
| `--srtm-tile` | a single `.hgt`, metadata-only delta stats for a probe grid |
| `--srtm-grid-spacing-m` | elevation grid cell spacing, default 1000 m |
| `--probe-output` | a live mission probe's `.jsonl` output |
| `--out` | output `.sqlite` path |

> **A real trap.** Optional flags with no registered default are **silently
> skipped**, not errors — a rebuild that omits `--routes` produces a store with
> zero roads and reports success. **Always verify row counts after a rebuild**
> rather than trusting the CLI summary. `build_region` deletes and recreates the
> whole `.sqlite` on every call; there is no incremental per-layer build yet.

## 3. Query a built model

```zsh
.venv/bin/python tools/describe_position.py <db.sqlite> <theatre> <x> <z>
```

```bat
.venv\Scripts\python tools\describe_position.py <db.sqlite> <theatre> <x> <z>
```

Or by latitude/longitude instead of DCS x/z:

```zsh
.venv/bin/python tools/describe_position.py <db.sqlite> Syria --latlon 35.53 35.78
```

## 4. Diagnostics

Each writes an image or report for eyeballing a layer.

| tool | shows |
|---|---|
| `tools/inspect_raster.py` | raster chart tiles and their registration |
| `tools/inspect_elevation.py` | the elevation grid |
| `tools/inspect_terrain.py` | ridge/valley classification |
| `tools/inspect_osm_overlay.py` | the OSM overlay |
| `tools/export_geojson.py` | GeoJSON export for external viewers |

Run them the same way as the tools above. Pass `--help` for arguments.

## 5. Development checks

Run from the repository root.

**macOS (zsh)**

```zsh
ruff format world-model/src world-model/tests
ruff check world-model/src world-model/tests
mypy world-model/src
pytest world-model/tests
```

**Windows (Command Prompt)**

```bat
ruff format world-model\src world-model\tests
ruff check world-model\src world-model\tests
mypy world-model\src
pytest world-model\tests
```

---

## Troubleshooting

**`No module named pyproj`** — system Python instead of the venv interpreter.
Use the `.venv/bin/python` (or `.venv\Scripts\python`) prefix.

**A layer is missing from the built store** — the corresponding input flag was
omitted or its file was absent. Missing inputs are reported as skipped, not as
errors. Check the build summary and verify row counts.

**`Syria.routes` not found** — it is ~2.25 GB and lives in the DCS install, not
this repo. A fresh checkout without it builds fine, just with no roads.

**Elevation looks wrong at a region's edge** — usually a real
terrain-mesh-resolution mismatch between SRTM and DCS rather than a bug. See
`research/2026-09-03-m4-dcs-elevation.md`.

**Queries are slow on `syria-full`** — a known tail; p99 for
`describe_position` sits around 800 ms on the full theatre.
