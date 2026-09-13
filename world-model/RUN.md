# Running the World Model Builder

Builds a persistent, queryable geographic model of a DCS theatre (roads, settlements, junctions,
elevation, terrain semantics) into a `.sqlite` file, and queries it.

- **Where this runs:** building reads DCS install files, so it runs on the Windows DCS box — in
  WSL (what the commands below show) or native Windows. A built `.sqlite` is just a file: copy it
  anywhere and query it from any platform.
- **Offline:** nothing here talks to a running DCS.
- **Two jobs, in order:** (a) build the OSM dataset once, then (b) build the whole world model.
  (a) is only needed again when you want fresher OpenStreetMap data.

Background docs (not needed to follow this page): `docs/CONVENTIONS.md` (working rules),
`docs/M7_RUN_INSTRUCTIONS.md` (full-theatre validation), `docs/M9_OSM_RUN_INSTRUCTIONS.md` (OSM
design notes and validation), `docs/M8_PROBE_STORE.md` (the separate live-probe store).

---

## 1. One-time setup

```bash
cd world-model
python3 -m venv .venv
.venv/bin/python -m pip install -e .                  # pyproj, pillow, osmium (Python bindings)
.venv/bin/python -m pip install pytest ruff mypy      # only for the development checks, section 6
```

For job (a) you also need the `osmium-tool` command-line program (separate from the Python
`osmium` package above):

```bash
sudo apt install osmium-tool      # WSL / Debian / Ubuntu
brew install osmium-tool          # macOS
```

Native Windows: use `.venv\Scripts\python` instead of `.venv/bin/python`, and `^` instead of `\`
for line continuation. No `PYTHONPATH` is needed; the `tools/` scripts add `src` themselves.

---

## 2. Job (a): build the OSM dataset

**Result:** one file, `syria-theatre.osm.pbf`: OpenStreetMap data for the seven countries the
Syria theatre touches, cut down to the theatre's area and merged. Job (b) reads it via
`--osm-pbf`. It adds settlement *outlines* (DCS only gives centre points) plus extra roads, water
and named places. The world model still builds without it; you just lose that layer.

Pick a working directory for the raw OSM files (e.g. `/mnt/f/dcs-world-model/syria/raw/osm`)
and run everything below from there.

### 2.1 Download the seven country extracts

From Geofabrik. **Turkey and Cyprus are under `europe/`**, the rest under `asia/`:

```bash
OSM_DIR=/mnt/f/dcs-world-model/syria/raw/osm        # your choice
mkdir -p "$OSM_DIR" && cd "$OSM_DIR"

for path in asia/syria asia/lebanon asia/israel-and-palestine asia/jordan asia/iraq \
            europe/turkey europe/cyprus; do
  curl -L -O "https://download.geofabrik.de/${path}-latest.osm.pbf"
done
```

About 1 GB in total, most of it Turkey (~650 MB). You get `<country>-latest.osm.pbf` files; the
older files in this project are named with a date instead (e.g. `syria-260911.osm.pbf`). The name
doesn't matter, just use the same one in the next step.

### 2.2 Clip each extract to the theatre

The bounding box below is the `syria-full` region plus a safety margin, in
`west,south,east,north` order (reproducible with `tools/derive_m9_osm_clip_bbox.py`):

```bash
for country in syria lebanon israel-and-palestine jordan iraq turkey cyprus; do
  osmium extract -b 31.4701,30.5157,40.8808,38.7353 \
      --strategy=smart \
      -o "${country}-clipped.osm.pbf" --overwrite \
      "${country}-latest.osm.pbf"
done
```

Keep `--strategy=smart`: it keeps roads that cross the box edge intact (it matters at the
Turkey–Syria border).

### 2.3 Merge into one file

```bash
osmium merge syria-clipped.osm.pbf lebanon-clipped.osm.pbf israel-and-palestine-clipped.osm.pbf \
    jordan-clipped.osm.pbf iraq-clipped.osm.pbf turkey-clipped.osm.pbf cyprus-clipped.osm.pbf \
    -o syria-theatre-unfiltered.osm.pbf --overwrite
```

### 2.4 Pre-filter to the tags the pipeline actually uses

Cuts parse time and file size by dropping everything the classifier (`build/ingest_osm.py`)
never looks at -- roads, buildings, and dozens of other tags. Filtered once, after the merge, so
this is one command over one file; `osmium tags-filter` re-adds any way/node a kept relation
references, so multipolygons (Lake Assad, city/town/village place areas) stay complete.

```bash
osmium tags-filter syria-theatre-unfiltered.osm.pbf \
    -e <repo>/world-model/tools/osm_tags_filter.txt \
    -o syria-theatre.osm.pbf --overwrite
```

`<repo>` is this repository's root. Note: `tags-filter` holds about 2-3 GB of ID tables in memory
regardless of input size -- fine on a 15 GB+ box, worth knowing before you run it on something
smaller.

### 2.5 Check it

```bash
osmium fileinfo -e syria-theatre.osm.pbf | head -30
```

Filtered counts should be roughly a quarter of `syria-theatre-unfiltered.osm.pbf`'s node count and
a few percent of its way count (the 2026-09-13 Syria/Turkey clips: ~13%/~29% of nodes, ~3%/~6% of
ways survived the filter). Don't judge by the `Bounding box` line: `--strategy=smart` pulls in
whole relations such as national borders, so the data box reaches far beyond the clip box
(23.6–48.0°E, 27.0–40.0°N for the 2026-09-11 unfiltered extract). That's expected. The
per-country `*-clipped.osm.pbf` files and `syria-theatre-unfiltered.osm.pbf` can be deleted
afterwards.

**Refreshing the data later:** redo 2.1–2.4. The next world-model build notices the new file
automatically (see "OSM cache" in 3.4) and re-processes it once.

---

## 3. Job (b): build the whole world model (`syria-full`)

### 3.1 Inputs

| flag | file | where it comes from |
|---|---|---|
| `--towns` | `towns.lua` | DCS install: `Mods/terrains/Syria/map/towns.lua` |
| `--beacons` | `beacons.lua` | DCS install: `Mods/terrains/Syria/beacons.lua` |
| `--routes` | `Syria.routes` (~2.25 GB) | DCS install: `Mods/terrains/Syria/roads/Syria.routes` |
| `--srtm-dir` | directory of `.hgt` elevation tiles | SRTM 1×1-degree tiles covering the theatre (~130 tiles, e.g. from viewfinderpanoramas.org; see `docs/M7_RUN_INSTRUCTIONS.md` §2a) |
| `--osm-pbf` | `syria-theatre.osm.pbf` | job (a) |

The DCS files are read in place, read-only; nothing in the DCS install is modified.

> **Trap: a missing input is skipped, not an error.** Mistype `--routes` and you get a store with
> zero roads and a "success" message. Always check the summary and row counts (3.5).

### 3.2 Run it

From `world-model/`. Note `2>&1`: progress is logged to stderr, so without it `tee` saves an
empty log file.

```bash
DCS="/mnt/f/Games/DCS World/Mods/terrains/Syria"

.venv/bin/python tools/build_world_model.py syria-full \
    --towns   "$DCS/map/towns.lua" \
    --beacons "$DCS/beacons.lua" \
    --routes  "$DCS/roads/Syria.routes" \
    --srtm-dir /mnt/f/dcs-world-model/syria/raw/dem/syria-full/ \
    --osm-pbf  /mnt/f/dcs-world-model/syria/raw/osm/syria-theatre.osm.pbf \
    2>&1 | tee syria-full-build.log
```

Output (override with `--out`): `data/world-model/syria-full.sqlite`. The builder **deletes and
recreates** that file on every run; there is no incremental rebuild.

### 3.3 What you'll see: the 8 stages

Every stage logs `[i/8] <name>: starting` and `[i/8] <name>: done (Ns)`. The long ones also log
progress in between, so a gap of a minute or two between lines is normal. Several minutes with
no new line at all during a progress-logging stage is worth reporting.

| # | stage | progress lines in between |
|---|---|---|
| 1 | `towns.lua` | — (fast) |
| 2 | `beacons.lua` | — (fast) |
| 3 | `OSM overlay (.osm.pbf)` | `osm.pbf: N elements seen (N tagged nodes, N ways kept, N areas kept, Ns elapsed)` every ~10–20 s. Low minutes on the first run against the pre-filtered file (§2.4 cuts this from the old "tens of minutes" — a 20 km region's OSM stage measured well under a minute end to end during validation); low minutes when the OSM cache hits too (3.4) |
| 4 | `Syria.routes (N bytes)` | — (reads the 2.25 GB road file) |
| 5 | `road junctions` | `ingest_junctions: R roads, N chunks ...` once, then `chunk i/N (x%, J junctions kept, Ts elapsed, ~Ts remaining)` at most every 30 s. The remaining-time figure is rough, since chunk cost varies a lot |
| 6 | `SRTM elevation grid (N tile(s))` | `ingest_srtm: row i/N (...)` every 50 rows |
| 7 | `elevation/surface probe grid` | skipped for `syria-full` (needs `--probe-output` from a live mission probe) |
| 8 | `terrain semantics (ridge/valley)` | skipped with stage 7. Full-theatre ridge/valley data comes from the separate probe store (`docs/M8_PROBE_STORE.md`) |

The final summary prints feature counts by kind and a stats line per stage. For `syria-full`,
`probe: skipped` and `terrain: skipped` are expected; any other `skipped` means an input was
missing.

### 3.4 Files it produces

| file | what | safe to delete? |
|---|---|---|
| `data/world-model/syria-full.sqlite` | the world model (several GB with OSM) | yes, rebuildable |
| `data/world-model/syria-full-osm-cache.sqlite` | **OSM cache**: stage 3's classified OSM features, kept between builds | yes; the next build is just slower |

**OSM cache.** The first build against a given `syria-theatre.osm.pbf` fills the cache. Later
builds with the same file, the same OSM classification rules and the same region skip the OSM
parse (log: `osm_cache: ... matches current .osm.pbf/classifier/region -- serving OSM overlay from
cache, skipping the parse`). A new `.osm.pbf` from job (a) invalidates it automatically. To force
a full re-parse anyway, delete the cache file.

### 3.5 Check the result

```bash
.venv/bin/python - <<'EOF'
import sqlite3
conn = sqlite3.connect("data/world-model/syria-full.sqlite")
for kind, n in conn.execute("SELECT kind, COUNT(*) FROM feature GROUP BY kind ORDER BY kind"):
    print(f"{kind:20} {n}")
EOF
```

`road`, `junction`, `settlement`, `named_place`, `water`, `landcover` and `coastline` should all be
non-zero with every input given. **`road` is DCS-only** (`Syria.routes`) — OSM no longer
contributes `road` rows at all (dropped from ingest entirely; DCS's own roadnet is authoritative).
`landcover` (forest/orchard/fields/scrub/barren polygons) and `coastline` (the shoreline, as its
own kind, separate from `water`) are new as of the osm-landcover-optimization milestone. Then
spot-check a known place (section 4).

### Small regions

`latakia-20km` has registered default inputs (raw files under the repo's `data/raw/`), so only
the region name is needed. `gemerek-20km` has none; give it inputs explicitly like `syria-full`.

```bash
.venv/bin/python tools/build_world_model.py latakia-20km
```

### All options

| flag | meaning |
|---|---|
| `--towns` | DCS `towns.lua`: named places |
| `--beacons` | DCS `beacons.lua`: navigation beacons |
| `--routes` | DCS `.routes` binary: road network (junction detection runs automatically on it) |
| `--osm-pbf` | merged theatre `.osm.pbf` from job (a); takes precedence over `--osm-cache` |
| `--osm-cache` | cached OSM overlay JSON (small regions only, M3's live-Overpass path) |
| `--srtm-dir` | directory of `.hgt` tiles, the primary elevation grid |
| `--srtm-grid-spacing-m` | elevation grid cell spacing, default 1000 m |
| `--srtm-tile` | a single `.hgt`, metadata-only delta stats for a probe grid |
| `--probe-output` | a live mission probe's `.jsonl` output (enables stages 7–8) |
| `--out` | output `.sqlite` path |

---

## 4. Query a built model

```bash
.venv/bin/python tools/describe_position.py data/world-model/syria-full.sqlite Syria <x> <z>
.venv/bin/python tools/describe_position.py data/world-model/syria-full.sqlite Syria --latlon 35.53 35.78
```

## 5. Diagnostics

Each writes an image or report for eyeballing one layer. Pass `--help` for arguments.

| tool | shows |
|---|---|
| `tools/inspect_raster.py` | raster chart tiles and their registration |
| `tools/inspect_elevation.py` | the elevation grid |
| `tools/inspect_terrain.py` | ridge/valley classification |
| `tools/inspect_osm_overlay.py` | the OSM overlay |
| `tools/export_geojson.py` | GeoJSON export for external viewers |

## 6. Development checks

From the repository root, with the venv's tools:

```bash
V=world-model/.venv/bin
$V/ruff format world-model/src world-model/tests
$V/ruff check world-model/src world-model/tests
(cd world-model && ../$V/mypy src)
(cd world-model && ../$V/pytest tests -q)
```

---

## Troubleshooting

**`No module named pyproj` / `osmium`**: system Python instead of the venv. Use the
`.venv/bin/python` prefix, and re-run `pip install -e .` if `osmium` is missing.

**`osmium: command not found`** during job (a): install `osmium-tool` (section 1). The Python
`osmium` package does not provide the command.

**Log file is empty**: you piped only stdout. Use `2>&1 | tee <file>` (3.2).

**A layer is missing from the built store**: its input flag was omitted or the path was wrong;
missing inputs are reported as skipped, not errors. Check the summary and row counts (3.5).

**Stage 3 takes as long as a fresh parse again although nothing changed**: the OSM cache missed.
Look for the `osm_cache:` log line; a changed `.osm.pbf`, a classifier update in the code, or a
region change all invalidate it by design. (A fresh parse against the §2.4-filtered file is itself
now low minutes, not the old "tens of minutes" against an unfiltered extract — but it's still far
slower than a cache hit.)

**Elevation looks wrong at a region's edge**: usually a real terrain-resolution mismatch between
SRTM and DCS, not a bug. See `research/2026-09-03-m4-dcs-elevation.md`.

**Queries are slow on `syria-full`**: a known tail; `describe_position` p99 is around 800 ms on
the full theatre.
