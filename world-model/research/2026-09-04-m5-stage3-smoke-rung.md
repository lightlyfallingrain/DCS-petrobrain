# M5 Stage 3 — probe rung 1/3 (smoke test, 121 points)

Date: 2026-09-04
DCS version/theatre: same install as M1-M4 (Syria terrain) -- not re-queried this session; see
prior M5 research notes for the confirmed version string.
Status: findings recorded after a live-mission run of `tools/dcs-mission-probe/
terrain_probe_smoke.lua` and ingestion sanity-checks against the real output. See
`plans/m5-first-persistent-model/checklist.md` (Stage 3) and
`plans/m5-first-persistent-model/plan.md` Finding C/E for the approved scope and the caution this
session's checks are meant to satisfy.

## What ran

121 points (the 41x41 Latakia grid at every 4th row/col, `probe_grid_for_region`'s coordinate
system -- origin x=34934.892, z=-4314.924, spacing 500m), one `land.getHeight` + one
`land.getSurfaceType` call per point (both `pcall`-wrapped), from a live DCS mission. Output:
`data/raw/dcs/2026-09-04/terrain_probe_output_smoke.jsonl` (gitignored, not committed; a 7-line
representative subset is hardcoded into `tests/test_terrain_probe.py`'s fixture, per
`docs/CONVENTIONS.md`'s "verify claims against the installed DCS version, record in research/"
rule).

## Point-count sanity

121 points requested, 121 lines returned, 0 nulls on either `height_m` or `surface_type`. No
points were silently dropped, and no `pcall` failure was hit for either function.

## `land.getSurfaceType` — first live call against this install, confirmed working

**Documented-only status resolved.** `land.getSurfaceType` had never been called against this
install before this run (same status `land.getHeight` held before M4 Stage 1). It returns
plausible values, no nils, no errors, across all 121 points.

**Enum distribution** (documented Hoggit enum: `LAND=1, SHALLOW_WATER=2, WATER=3, ROAD=4,
RUNWAY=5`):

| value | label | count | % |
|---|---|---|---|
| 1 | LAND | 85 | 70.2% |
| 2 | SHALLOW_WATER | 0 | 0.0% |
| 3 | WATER | 34 | 28.1% |
| 4 | ROAD | 1 | 0.8% |
| 5 | RUNWAY | 1 | 0.8% |

Every observed value falls inside the documented `1..5` range -- no out-of-enum surprise
(`tests/test_terrain_probe.py::test_parse_terrain_probe_output_surface_type_values_are_within_documented_enum`
pins this against the real fixture subset). `SHALLOW_WATER` simply wasn't hit at this rung's
121-point/500m*4-stride resolution -- absence noted, not evidence it doesn't occur; a finer rung
may sample it.

## Spatial plausibility

- **WATER points cluster on the region's west edge** (low-x rows, e.g. `r0c0`..`r0c12` all
  `WATER` at `height_m=0.0`) -- the Mediterranean coastline, exactly where it should be given the
  `latakia-20km` region's west edge sits on the coast (per Stage 0's census).
- **`r12c20` is `RUNWAY`, 805.7m from the Stage 1 derived LATAKIA airfield point**
  (41740.54, 5697.76, from `ingest_beacons`'s ILS-axis-midpoint derivation). This is an
  independent, unplanned cross-subsystem sanity check that the plan formally reserves for Stage 4
  ("Cross-subsystem check (Finding C)") -- a `getSurfaceType` RUNWAY hit landing well within a
  plausible runway's length of the beacon-derived airfield point, from a completely different DCS
  subsystem, is a good early sign for that later check.
- **`r32c20` is `ROAD`, 9.2km from the airfield point** -- plausible for a road elsewhere in the
  region; not cross-checked against the `.routes` roadnet layer this session (that's Stage 4's
  job, once the full grid exists).
- **Four `WATER` points have non-zero elevation**, not just the 0.0m coastal points:
  `r0c32` (79.86m), `r8c32` (119.98m), `r20c24` (34.43m), `r28c8` (5.79m). All four sit inland,
  away from the coastal edge, and their `LAND` neighbours have similar elevations (e.g. `r0c32`'s
  neighbours `r0c28`=83.2m, `r0c36`=127.8m, `r4c32`=116.0m) -- consistent with these being real
  inland water features (river channels / a reservoir in the Jabal Ansariyah foothills; the plan's
  Finding B independently notes the Nahr al-Kabir river runs through this region) rather than a
  parser bug or a `getHeight`/`getSurfaceType` desync. Not confirmed against a river/lake
  reference this session -- flagged for Stage 4's cross-subsystem check if a definitive read is
  wanted.
- **Height range 0.0-556.3m**, plausible for coastal Latakia rising into the Jabal Ansariyah
  foothills; no negative or absurdly large values.

## No code changes needed

`build.ingest_probe`/`elevation.dcs_grid.parse_terrain_probe_output` (implemented and tested
against synthetic fixtures before this rung ran) required **no changes** to correctly parse and
place this real output -- confirmed by running `ingest_probe` standalone against the real file
(row/col placement, surface-type label counts, no exceptions). This is recorded as a successful
prediction from the synthetic-fixture test suite, not just a pass.

## Next

Per the checklist's incremental ladder: proceed to rung 2 (~500 points, `terrain_probe_500.lua`),
then rung 3 (full 1,681, `terrain_probe_full.lua`), each collected and sanity-checked the same way
before scaling up further. Only after rung 3 lands does the real Latakia `.sqlite` get rebuilt
with `--probe-output`/`--srtm-tile` and the SRTM delta / final coverage numbers get computed.

---

## Rung 2/3 update (500 points) — 2026-09-04

441 points (every 2nd row/col of the 41x41 grid), same mechanism, same live-mission workflow.
Output: `data/raw/dcs/2026-09-04/terrain_probe_output_500.jsonl` (gitignored).

**Point-count sanity:** 441 requested, 441 lines returned, 0 nulls on either field, 0 duplicate
names.

**Enum distribution:**

| value | label | count | % |
|---|---|---|---|
| 1 | LAND | 324 | 73.5% |
| 2 | SHALLOW_WATER | 0 | 0.0% |
| 3 | WATER | 112 | 25.4% |
| 4 | ROAD | 4 | 0.9% |
| 5 | RUNWAY | 1 | 0.2% |

Consistent with rung 1's proportions (70.2%/0%/28.1%/0.8%/0.8%); no new out-of-enum value.
`SHALLOW_WATER` still unobserved. Height range unchanged (0.0-556.3m).

**Determinism cross-check (new this rung).** All 121 of rung 1's grid points are also present in
rung 2's 441 (rung 2 is a superset at finer stride, same grid coordinate system) -- every
overlapping point's `height_m` and `surface_type` are **bit-identical** between the two live
mission runs. This is a real, if informal, reproducibility check: `land.getHeight`/
`land.getSurfaceType` return the same value for the same `(x, z)` across two separate live-mission
invocations, not noisy or session-dependent.

**Spatial plausibility, updated:**
- The same `r12c20` RUNWAY point recurs (805.7m from the derived airfield point, identical
  height) -- expected, since it's the same grid cell re-sampled.
- 4 ROAD points now visible (`r6c16`, `r10c30`, `r32c18`, `r32c20`), scattered 4.3-9.3km from the
  airfield point -- plausible for roads elsewhere in the region; not cross-checked against the
  `.routes` layer this session (Stage 4's job).
- 6 non-zero-elevation WATER points now visible (up from 4 at rung 1's coarser stride, all rung 1
  points recur plus 2 new ones: `r6c38` 161.1m, `r18c40` 179.8m) -- same inland-water-feature
  interpretation as rung 1, strengthened by more samples rather than contradicted.

**No code changes needed.** `ingest_probe`/`parse_terrain_probe_output` handled the real 441-point
file correctly with zero changes.

**Next:** rung 3 (full 1,681, `terrain_probe_full.lua`) staged for the user; see
`plans/m5-first-persistent-model/implementation.md` for the exact run instructions.

---

## Rung 3/3 update (full grid, 1,681 points) — 2026-09-04

The full 41x41 grid, same live-mission mechanism. Output:
`data/raw/dcs/2026-09-04/terrain_probe_output_full.jsonl` (gitignored).

**Point-count sanity:** 1,681 requested, 1,681 lines returned, 0 nulls on either field, 0
duplicate names. **Exact match against the expected `{r{row}c{col} : row,col in 0..40}` name set**
-- no missing points, no unexpected extra names. This is the strongest completeness check
available: the grid is not just "1,681 lines" but provably the *specific* 1,681 cells the plan
calls for.

**Enum distribution:**

| value | label | count | % |
|---|---|---|---|
| 1 | LAND | 1,236 | 73.5% |
| 2 | SHALLOW_WATER | 0 | 0.0% |
| 3 | WATER | 412 | 24.5% |
| 4 | ROAD | 29 | 1.7% |
| 5 | RUNWAY | 4 | 0.2% |

Proportions essentially unchanged from rungs 1/2 (LAND/WATER split stable at ~73.5%/~24.5% across
all three sample densities -- consistent with a real, spatially coherent coastal/inland split
rather than sampling noise). `ROAD`/`RUNWAY` counts scale up with finer sampling as expected (more
grid cells now land on the (still narrow, still aliased at 500m spacing per Finding C's stated
limitation) road/runway strips). `SHALLOW_WATER` remains unobserved at any rung -- noted as a real
absence in this grid's sampling, not evidence the value doesn't exist in the enum.

**Determinism cross-check (three-way).** All 121 rung-1 points and all 441 rung-2 points recur in
the full grid with **zero mismatches** on `height_m` or `surface_type` -- three independent live
mission runs, fully consistent.

**No code changes needed.** `ingest_probe` handled the real 1,681-point file with zero changes.

## SRTM tile availability -- gap, not resolved this session

`data/raw/dem/` holds only `N39E036.hgt` (the Gemerek/M4 tile). The Latakia region's lat/lon
envelope (~35.0-35.5N, ~35.85-35.95E) needs a **different** tile (`N35E035.hgt`), which is not
present. An attempted automated fetch this session (viewfinderpanoramas.org / USGS mirrors) was
blocked by the sandbox's network policy, consistent with M4's own precedent of the *user*
manually fetching the DEM tile via viewfinderpanoramas.org's interactive map (not an automated
pipeline step). **The real Latakia rebuild therefore proceeds without `--srtm-tile`** --
`elevation.stats["srtm"]` is `null` for the real store, an honest absence rather than a fabricated
or borrowed-from-the-wrong-region number. Fetching `N35E035.hgt` (or the region's actual covering
tile(s) -- the region may straddle a tile boundary, unconfirmed) and re-running
`build_world_model.py --srtm-tile ...` is a cheap follow-up once the user has it locally; the
`ingest_probe`/`ElevationGrid.stats` code path is already implemented and tested (see
`test_ingest_probe.py`'s SRTM tests against a synthetic tile).
