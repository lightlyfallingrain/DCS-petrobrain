# M7 full-theatre build — run instructions

Per `plans/m7-full-theatre-pipeline/plan.md`'s "Execution boundary": nobody but the user
builds the real full-theatre `syria-full.sqlite`. This doc is the required deliverable for
that boundary — the implementer/reviewer/DoD verify the pipeline code against small fixtures
only (see `tests/test_pipeline_build_region.py`, `tests/test_build_validate.py`); the real
build, its real feature counts, wall time, and file size are the user's own result.

This doc covers **Stage 1** (DCS-native vector layers: roads, towns, beacons — no OSM, no
elevation), **Stage 2** (SRTM-primary elevation/`surface_type`, plus a DCS live-probe
spot-check validation), and **Stage 3** (a wider geographically-spread control-point pass plus
provenance-at-scale validation). Run Stage 1 first; Stage 2 can be run against the same
`syria-full.sqlite` afterward, or built together in one `build_world_model.py` invocation (see
Stage 2 step 2 below); Stage 3 runs last, once both are in place.

## 1. Check the raw files are staged

Stage 1 needs exactly the same three raw files M5 already used for `latakia-20km` — they are
**whole-theatre files already, not region-clipped** (M5 found this incidentally: `.routes` is
walked in full regardless of region bbox, and `towns.lua`/`beacons.lua` are parsed in full
before being clipped). If you already built `latakia-20km`, you very likely already have these
staged and **no new Windows/WSL round-trip is needed for Stage 1**:

```sh
ls world-model/data/raw/dcs/syria/map/towns.lua
ls world-model/data/raw/dcs/syria/map/beacons.lua
ls world-model/data/raw/dcs/syria/roads/Syria.routes
```

If any are missing, stage them the same way M5 did (read-only copy from the DCS installation's
`Mods/terrains/Syria/...`, via the `wsl-probe-sync` workflow in `world-model/WORKFLOW.md` if
extracting fresh from the Windows machine, or a direct copy if you already have them).

**No OSM cache is needed or used** — M7 drops OSM from scope entirely (see the plan's
clarification 2). Do not pass `--osm-cache` when building `syria-full`.

## 2. Run the build

From `world-model/`, with the venv active:

```sh
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes
```

This writes `data/world-model/syria-full.sqlite` (gitignored, like every other built store).
Expect the `.routes` walk to take roughly the same wall time Stage 0's census measured
(~430 s) — it is the same full-file walk, just now also constructing and inserting
`StoredFeature` rows instead of just counting them, and this time also parsing/inserting the
whole (unclipped) `towns.lua`/`beacons.lua` gazetteer.

The build prints a per-`kind` feature count summary and skip notices for the layers Stage 1
doesn't populate (`osm: skipped`, `probe: skipped`) — those are expected, not failures; M7
Stage 2 fills in elevation/`surface_type` later, and OSM is out of scope for the whole
milestone.

## 3. Validate the build

From `world-model/`, with the venv active:

```sh
.venv/bin/python tools/validate_m7_stage1.py
```

This checks the freshly-built `data/world-model/syria-full.sqlite` against:

- **Road count sanity**: the `road`-kind feature count should land within 5% of Stage 0's real
  full-theatre census (14,833 routes — see
  `world-model/research/2026-09-05-m7-stage0-roadnet-census.md`). A count far outside that band
  means something changed between Stage 0's measurement-only walk and Stage 1's real build (a
  bug, not an expected variance) and is worth investigating before moving on.
- **Coordinate control points**: every point in `tests/control_points.py`'s `CONTROL_POINTS`
  (Stage 1's original four scattered points — Damascus, Latakia, Beirut, Aleppo — plus Stage 3's
  four additional terrain-type points, once that stage has extended the list) transforms to
  within its published real-world ARP's expected residual — this doesn't depend on the store's
  contents (see `tests/test_describe_position.py`'s control-point tests, which already pin this
  in CI), but re-running it here confirms the same theatre/projection is in play for the real
  build.
- **Spot checks**: `describe_position` at each of those same points reports whether a
  nearest road/settlement was found and at what distance — a human-scannable sanity check, not
  an exact-value assertion (Stage 1 has no independent ground truth for "the nearest road to
  this specific point"). If every point comes back with no nearest road at all, something is
  wrong with the roadnet layer; if some do and some don't (e.g. a point that's actually far from
  any real road), that's expected, not a failure.

The script prints a JSON report to stdout. There is no automatic pass/fail exit code beyond the
"store doesn't exist yet" case — read the report and use judgement, the same way M5's Stage 4
validation note did.

## 4. Record the result

Once you've run the build and the validation script, note the real numbers (feature counts,
wall time, file size, validation output) — either directly in a new dated
`world-model/research/` note (mirroring M5/M7 Stage 0's convention) or by reporting them back
so they can be written up. This is the actual Definition-of-Done evidence for M7 Stage 1 — an
agent-produced or agent-reported full-theatre store/count does not satisfy it, per the plan's
"Execution boundary".

## Stage 2 — SRTM-primary elevation, DCS-probe spot-check validation

Per the plan's locked Stage 2 decision: **SRTM is the primary full-theatre elevation/
`surface_type` source**, not the live DCS mission probe. The probe is repurposed to a small,
scattered spot-check control-point set that validates SRTM alignment accuracy — it is *not* run
as a full grid and its output is *not* stored as a `grid` row for `syria-full` (see
`build.pipeline`'s module docstring on why ordering keeps this unambiguous if you ever do pass
both). Two separate real actions are involved, in either order:

### 2a. Stage the SRTM `.hgt` tiles

Syria's padded bbox (31.19–38.01°N, 32.29–40.21°E, per
`world-model/research/2026-09-05-m7-syria-theatre-extent.md`) spans roughly 7 degrees of
latitude and 8 of longitude, so covering it needs on the order of several dozen 1x1-degree
`.hgt` tiles — every tile whose 1-degree cell overlaps that lat/lon envelope. M4 Stage 2 already
sourced one tile (`N39E036.hgt`) from the viewfinderpanoramas.org no-login mirror (SRTM3, ~90m);
fetch the remaining tiles from the same source (or SRTM1 if you want ~30m instead — `SrtmTile`
handles either, deriving resolution from file size) and put them all in one directory, e.g.
`data/raw/dem/syria-full/`.

**Row-count sizing is a real decision you should make before running this for real** (see
`build.ingest_srtm`'s module docstring and `build.pipeline`'s `DEFAULT_SRTM_GRID_SPACING_M`):
at the default 1000m storage spacing, `syria-full`'s ~827x771 km bbox is roughly 828 x 772 ≈
639,000 grid cells; at 500m (matching the older probe-grid convention) it's ~2.5 million. SQLite
handles millions of rows fine per M5's own findings, but this is the first full-theatre-scale
grid this pipeline has ever built for real — consider timing a smaller test run first, or pass
`--srtm-grid-spacing-m` explicitly if you want a different tradeoff than the default.

### 2b. Run the build with `--srtm-dir`

From `world-model/`, with the venv active — this can be combined with Stage 1's build (same
command, one more flag) or run again against an existing `syria-full.sqlite` (the build is
idempotent; it deletes and recreates the file each time, so re-run the full command, not just
this flag):

```sh
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes \
    --srtm-dir data/raw/dem/syria-full/
```

The build prints `srtm stats: SrtmIngestStats(...)` on success (`points_sampled`,
`points_void_or_uncovered`, `tiles_used`) or `srtm: skipped` if `--srtm-dir` was omitted or had
no `.hgt` files. `probe: skipped` and `terrain: skipped` are still expected here too — Stage 2
does not run a full-grid DCS probe or M6's ridge/valley classifier (locked out of M7 entirely).

### 2c. Run the DCS live-probe spot-check mission

Unlike Stage 1's vector layers, this step needs the actual installed DCS copy on the Windows
machine — it is the one part of M7 that cannot be done from already-staged files. Run
`tools/dcs-mission-probe/elevation_probe.lua` (unchanged from M4/M5 — see the plan's Stage 2:
"no chunking/resumability redesign needed") against a **small, scattered point set spread
across the theatre** — one or two points per major region/airbase cluster (e.g. near Damascus,
Aleppo, Latakia, Beirut, and a few inland/mountain points), not a dense grid. Follow the
`wsl-probe-sync` workflow (`world-model/WORKFLOW.md`) to run the mission and sync the resulting
JSON-lines output file back to the Mac, e.g. into
`data/raw/dcs/syria/probes/syria-full-spot-check.jsonl`.

### 2d. Validate SRTM alignment against the spot-check

From `world-model/`, with the venv active — this does **not** need `syria-full.sqlite` to exist
yet; it only reads the probe output file and the `.hgt` tiles directly:

```sh
.venv/bin/python tools/validate_m7_stage2_elevation.py \
    --probe-output data/raw/dcs/syria/probes/syria-full-spot-check.jsonl \
    --srtm-dir data/raw/dem/syria-full/
```

This prints a JSON report: per-point `dcs_probe_m`/`srtm_m`/`delta_m`, plus `mean_delta_m`/
`median_delta_m`/`stddev_delta_m`/`min_delta_m`/`max_delta_m` across every point the probe and
SRTM both cover (`points_skipped` counts any spot-check point outside the staged tiles'
coverage). Compare the summary against M4's single-region Gemerek baseline (mean +13.89m,
stddev 28.02m) — the open question this step answers (per the plan's Risks section) is whether
alignment quality is roughly uniform across the theatre or degrades with distance from
Gemerek/the tmerc central meridian. Report it plainly either way; there is no automatic pass/
fail threshold here, the same as Stage 1's validator.

### 2e. Record the result

Note the real SRTM ingest stats, the spot-check delta report, and (if it changed) the rebuilt
`syria-full.sqlite`'s file size/wall time — same convention as Stage 1's step 4. This is the
actual Definition-of-Done evidence for M7 Stage 2; an agent cannot produce it per the plan's
"Execution boundary".

## Stage 3 — validation: wider control-point set + provenance at scale

Per the plan's Stage 3: a full `describe_position` correctness pass over a wider,
geographically-spread control-point set (coastal, mountainous, urban, desert — broader than
Stage 1's four Damascus/Aleppo/Beirut/Latakia points), plus confirming `elevation`/
`surface_type` provenance is never ambiguous about `"srtm"` vs `"dcs_probe"` at scale. This
stage does **not** include the M5 roadnet resync audit — that's a separate follow-up task,
tracked in the plan's "Deferred / Out of Scope", not part of M7.

Run this once `syria-full.sqlite` has both its Stage 1 vector layers and Stage 2 SRTM elevation
grid built (the earlier steps in this doc).

### 3a. Run the Stage 3 validator

From `world-model/`, with the venv active:

```sh
.venv/bin/python tools/validate_m7_stage3.py
```

This reads `tests/control_points.py`'s full set — Stage 1's original four points plus four new
Stage 3 additions spread across terrain types the first four didn't cover:

- **Coastal** — Rene Mouawad AB / Klieat (OLKA), Akkar, northern Lebanon.
- **Urban** — Mezzeh Air Base (OS67), inside Damascus city.
- **Desert** — Deir ez-Zor Airport (OSDZ), Euphrates valley, far eastern edge of the theatre.
- **Mountainous** — Kahramanmaras Airport (LTCN), at the foot of the Taurus range, far northern
  edge of the theatre.

Each pairs a DCS-authoritative `(x, z)` from `beacons.lua` with an independently-published
real-world ARP (Wikipedia/SkyVector — never that same beacon's own `positionGeo` field, per M1
Finding 2's non-circularity rule) — see `tests/control_points.py`'s docstrings for the exact
sources.

The script's JSON report has three parts:

- **`road_count_check`** / **`coordinate_control_point_checks`** / **`spot_checks`** — the same
  checks `validate_m7_stage1.py` runs, just now over all eight points instead of four.
- **`provenance_checks`** — for each point, `describe_position`'s `elevation.source` and
  `surface_type.provenance`, and whether each is unambiguously `"srtm"` or `"dcs_probe"` (never
  `"unavailable"`, and never a stale/other value — see `build.validate.check_elevation_
  provenance`'s docstring). For a real `syria-full` build (SRTM-primary, no stored DCS-probe
  grid — Stage 2 repurposes the probe to a spot-check report only), every point should report
  `elevation_source == "srtm"`. If `provenance_checks.all_ok` is `False`, or any point reports
  `"unavailable"`, that means a layer didn't build as expected — investigate before treating the
  store as done, since per this project's provenance invariant a `.sqlite` with ambiguous or
  missing grid provenance is not a valid deliverable.

There is no automatic pass/fail exit code beyond the "store doesn't exist yet" case — read the
report and use judgement, the same as Stages 1 and 2.

### 3b. Record the result

Note the real coordinate-residual and provenance numbers — same convention as Stages 1 and 2's
"record the result" steps. This is the actual Definition-of-Done evidence for M7 Stage 3; an
agent cannot produce it per the plan's "Execution boundary".
