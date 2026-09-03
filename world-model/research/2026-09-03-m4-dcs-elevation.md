# M4 — DCS elevation extraction & external DEM comparison (Gemerek)

Date: 2026-09-03
Status: findings recorded after implementing `world-model/src/elevation/` and running both the
Stage 1 smoke-test probe and the Stage 2 full-grid probe against a live DCS mission, plus the DEM
comparison. See `plans/m4-dcs-elevation/plan.md` for the approved plan this session implements
and `2026-09-03-m4-elevation-recon.md` for the investigator recon it's built on.

## Extraction mechanism — confirmed

Both open questions from the recon note's "Unresolved" section are now resolved by direct
reproduction, not inference:

- **`land.getHeight` works as documented** against DCS 2.9.29.27278 / Syria, called as
  `land.getHeight({x=.., y=z})` from a live-mission `DO SCRIPT FILE` trigger (same pattern as
  M1's `coord_probe.lua`). No nils, no errors, across both probe runs (8 points, then 100).
- **`io.open`/`write` under the user-authorized `MissionScripting.lua` io/lfs edit works
  correctly**, including at 100-point scale — no truncation, no dropped lines, both runs wrote a
  complete file.

## Stage 1 — smoke test (8 points)

Grid: 4 corners + center + 3 interior points of the Gemerek bbox (south=39.170, west=36.050,
north=39.195, east=36.090), precomputed via `coordinates.wgs84_to_dcs`. Output:
`world-model/data/raw/dcs/2026-09-03/elevation_probe_output.jsonl` (gitignored, not committed;
hardcoded into `tests/test_dcs_grid.py`'s fixture). Heights ranged 1163.18–1339.91m, plausible for
the Sivas plateau region this bbox sits in (~1000–1500m typical elevation) — see `elevation_probe.lua`'s
header comment and the recon note's Finding 1/Unresolved item.

## Stage 2 — full grid (100 points) + SRTM comparison

Grid: 10x10 = 100 points, evenly spaced across the same Gemerek bbox (~280–380m spacing
depending on axis — the bbox isn't square in meters). Output:
`world-model/data/raw/dcs/2026-09-03/elevation_probe_output_full_grid.jsonl` (gitignored, not
committed).

**Point count sanity (Stage 3):** 100 points requested, 100 lines returned, 0 nulls. No points
were silently dropped.

**DEM tile:** `world-model/data/raw/dem/N39E036.hgt`, fetched by the user from
`viewfinderpanoramas.org`. **SRTM3 (3 arc-second, 1201x1201, ~90m), not SRTM1** — the recon note
(Finding 9/12) had anticipated SRTM1 (1 arc-second, 3601x3601, ~30m); the user picked the coarser
3" product when fetching. `elevation.dem.SrtmTile.from_file` derives grid size from file length
rather than hardcoding a resolution, so this required no code change — see
`plans/m4-dcs-elevation/implementation.md` Addendum 2. Future M4-adjacent work wanting tighter
vertical resolution would need to re-fetch the 1" product; not revisited this session.

**Delta report** (`elevation_dcs - elevation_external`, via `tools/inspect_elevation.py compare`;
full 100-row table reproducible with the command below, not reprinted in full here):

| stat | value |
|---|---|
| points compared | 100 (0 off-tile/skipped) |
| mean delta | +13.89 m |
| median delta | +16.61 m |
| stddev delta | 28.02 m |
| min delta | -86.09 m (`r0c0`, the bbox's SW corner) |
| max delta | +69.19 m (`r7c2`) |
| positive / negative split | 76 positive, 24 negative |
| \|delta\| > 50m | 9 of 100 points |

Reproduce: `.venv/bin/python tools/inspect_elevation.py compare data/raw/dcs/2026-09-03/elevation_probe_output_full_grid.jsonl data/raw/dem/N39E036.hgt Syria`

### The `-86m` corner_sw outlier, and the outlier pattern generally — explained, not a bug

The `-86.09m` point flagged after Stage 1's 8-point smoke run (`corner_sw` there, `r0c0` here,
same DCS point) is confirmed real in the full grid, not a fluke of the small sample — and it's
part of a larger, spatially coherent pattern, not an isolated anomaly:

- The 9 points with `|delta| > 50m` are **not scattered randomly** across the grid. Eight of the
  nine cluster along two lines: the bbox's **west edge** (`r0c0`, `r0c1`, `r1c0`, `r2c0`, `r5c0`
  — column 0/1, rows 0–2 and row 5) and a **diagonal band running roughly NW-to-SE through the
  grid's middle** (`r6c1`, `r7c2`, `r8c2`, `r9c3`).
- Walking down the west edge (`c0`) row by row, the delta moves smoothly from -86m (row 0, north)
  through -80m, -60m, -18m, +21m, **+59m** (row 5), +45m, +18m, +14m, +31m (row 9) — a continuous
  gradient, not a jump. This is the signature of a real, localized terrain feature (a slope or
  escarpment edge that DCS's terrain mesh and SRTM3's 90m grid resolve differently), not a
  transform bug.

**Why this is read as terrain-mesh-resolution mismatch, not a vertical datum offset:** the plan's
"Risks & Unknowns" flagged that a *systematic, roughly-constant* delta across the whole grid would
be the signature of a DCS-vs-SRTM vertical datum mismatch (e.g. EGM96 geoid vs. whatever DCS's
terrain art uses), while a *spatially localized, sign-varying* pattern tied to specific points
would indicate mesh-resolution noise instead. This grid shows the latter: the mean (+13.89m) is
modest relative to the full range (up to ±86m), the sign varies by location rather than being
uniform, and the largest deviations concentrate in a geographically coherent slice of the grid
(the west edge and one diagonal band) rather than being spread evenly. Also consistent with the
plan's separately-flagged "DCS terrain mesh LOD" risk: `land.getHeight` likely reflects a
simplified/clipmap-resolution mesh, not full visual-detail terrain art, so some divergence from a
90m external DEM at fine spacing (~300m point spacing here) is expected, especially where the
real terrain has local relief (a slope/valley wall) that a simplified mesh smooths over
differently than a raster DEM resamples it.

**Not fully explained, flagged for future work:** *why* this specific edge/band is where DCS and
SRTM diverge most (an actual valley/escarpment at that location vs. some other cause) was not
investigated further this session — would need either a finer-resolution SRTM1 tile or a visual
cross-check against the RasterCharts imagery (M2) to confirm what's really there. Not blocking for
M4's stated goal (proving the extraction/comparison method works), but worth a look before this
region is used for detailed terrain-semantics work in M6.

## Vertical datum — not established, no evidence of a problem here

Per the plan's Risk item: DCS's own terrain-art vertical reference was not investigated this
session (out of scope, same as the recon note). The delta distribution above shows no clear
signature of a systematic datum offset (see above) — but this is not the same as confirming DCS
and SRTM share a common vertical datum, only that this dataset doesn't obviously demand one. Leave
open for a future session if vertical accuracy becomes load-bearing (e.g. for terrain semantics in
M6).

## `MissionScripting.lua` io/lfs edit status

Not confirmed this session whether the user has reverted the manual `io`/`lfs` edit made for
these probes. Per the plan's Risk item, this is the user's call, not a pipeline decision — flagged
here so it isn't silently forgotten as a standing install modification. Recommendation unchanged
from the plan: revert once no further probes are planned, since it's scoped to investigation
probes only, never pipeline code.

## Attribution

DEM data: SRTM (processed derivative via viewfinderpanoramas.org), public-domain-grade per the
recon note's Finding 9/10 licensing discussion; no attribution requirement beyond normal
provenance tracking (unlike OSM's ODbL, see M3).
