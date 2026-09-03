### Goal

Build a live-mission probe that samples DCS terrain elevation (`land.getHeight`) over a grid
covering a small region already used in M1-M3, parse the results, compare them point-by-point
against an external DEM (SRTM), and produce a `elevation_dcs / elevation_external / delta`
report — proving the extraction method, not building the M5 persistent elevation store.

### Investigator gate — invoked

Step 2 of this role requires invoking `investigator` before finalizing a plan that depends on an
unverified DCS-internals claim. M4 depended on three: whether `land.getHeight` is Mission
Scripting-only (no offline heightmap alternative), whether the Mission Scripting `io`/`lfs`
sandbox is actually stripped on this install (blocks the naive "write a grid to a file" approach
M1's `coord_probe.lua` already flagged as an open caveat), and which external DEM source fits the
existing no-heavy-deps stack. Findings: `world-model/research/2026-09-03-m4-elevation-recon.md`.
Summary relevant to this plan:

- **No offline heightmap exists.** `Mods/terrains/Syria/surface/` holds proprietary,
  undocumented binary formats (`.ng5`, `.surface5`, `.tile`, `.sup4`); `terrain.cfg.lua.pak.crypt`
  is packed and encrypted. `land.getHeight` via a live-mission trigger script (same pattern as
  M1's `coord.LOtoLL` probe) is the only known extraction route.
- **`io`/`lfs` sandbox status is not directly confirmed on this install**, but strongly and
  convergently reported (3+ independent sources, matching function/variable names) as stripped by
  default in `MissionScripting.lua`. This is now **not load-bearing**: `net.log(string)`
  (Hoggit-documented, separate module from `os`/`io`/`lfs`, untouched by the sandbox) writes to
  `Saved Games/DCS/Logs/dcs.log`, which can be read afterward as a normal read-only log file. M4's
  probe uses `net.log`, not `io.open`, so it works whether or not `io`/`lfs` are actually open.
- **DEM choice: SRTM (`.hgt`, ~30 m), not Copernicus GLO-30.** SRTM's `.hgt` is a flat big-endian
  int16 grid, parseable with stdlib `struct`/`array` — zero new dependency, consistent with the
  `pyproj`/stdlib/`Pillow` stack M1-M3 already established. Copernicus GLO-30 has friendlier
  no-login access but ships as Cloud-Optimized GeoTIFF, which realistically needs GDAL/rasterio (or
  a COG-aware TIFF library) to read correctly — a disproportionate new dependency for this
  milestone's stated goal.

**Flag before this plan proceeds** (see "Decisions Requiring User Input"): the investigator's
research note also records, unprompted, that "the user has indicated willingness to manually edit
`MissionScripting.lua` to open io/lfs." No such instruction has been given to me (Architect) in
this conversation, and no agent-relayed statement counts as user authorization to alter a
non-negotiable invariant (`CLAUDE.md`: "Never modify the DCS installation"). This plan does **not**
rely on or plan around an edited install — it uses `net.log`, which needs no such edit and works
identically either way — but the discrepancy needs the user's direct confirmation before anyone
acts on it, not silent pass-through.

### Affected Modules / Files

- `world-model/tools/dcs-mission-probe/elevation_probe.lua` — new. Mirrors `coord_probe.lua`'s
  structure/header-comment conventions. Iterates a hardcoded grid of DCS `(x, z)` points (generated
  offline in Python, pasted in as a literal Lua table — no runtime grid-generation logic needed in
  Lua), calls `land.getHeight({x=.., y=z})` per point, and emits one `net.log("ELEV_PROBE " ..
  json)` line per point. No `io`/`lfs` usage.
- `world-model/tools/dcs-mission-probe/README.md` — add the new script's entry + workflow note
  (output is `dcs.log`, not a dedicated file — different collection step from `coord_probe.lua`).
- `world-model/tools/wsl/collect_elevation_log.sh` — new, read-only. Greps
  `Saved Games/DCS/Logs/dcs.log` for the `ELEV_PROBE` prefix, writes matching lines to
  `win-mac-sync/wsl-output/`. Pure read of an existing DCS-managed log — no installation change.
- `world-model/tools/wsl/probe_missionscripting_sandbox.sh` — new, read-only, optional/cheap.
  `cat`s the installed `Scripts/MissionScripting.lua` (no mission launch required) so the io/lfs
  finding can be upgraded from "convergent community evidence" to "reproduced locally." Not
  load-bearing for M4's design (see above) but cheap enough to run anyway; output goes to
  `research/` as a one-line addendum to the M4 recon note, not into pipeline code.
- `world-model/src/elevation/__init__.py` — new package, mirrors `coordinates/`/`osm/` structure.
- `world-model/src/elevation/dcs_grid.py` — new. `DcsElevationSample` (frozen dataclass: `x: float,
  z: float, height_m: float`); `parse_net_log(path: Path) -> list[DcsElevationSample]` extracts and
  parses `ELEV_PROBE` lines from a collected `dcs.log` excerpt (stdlib `json`/regex, no new dep).
- `world-model/src/elevation/dem.py` — new. `SrtmTile` wrapping one `.hgt` file (stdlib
  `struct`/`array` parse per the recon note's documented format: 3601×3601 big-endian int16,
  row-major from NW corner, void `-32768`); `height_at(lat: float, lon: float) -> float` with
  bilinear interpolation between the 4 nearest grid cells.
- `world-model/tools/inspect_elevation.py` — new CLI, mirrors `inspect_osm_overlay.py`'s pattern.
  Loads a parsed DCS grid + the corresponding SRTM tile, runs each DCS point through
  `coordinates.dcs_to_wgs84` to get lat/lon, looks up the SRTM height, prints/saves a
  `elevation_dcs / elevation_external / delta` table (per `docs/concept/WORLD_MODEL_BUILDER.md`'s
  Elevation section field names) plus summary stats (mean/min/max/stddev delta).
- `world-model/tests/test_dem_srtm.py` — new. Control-point test per `world-model/CLAUDE.md`'s
  testing rule: parse a real (or minimal synthetic, if the real tile is too large to fixture)
  `.hgt` sample and assert `height_at(...)` against a published real-world elevation for a known
  point in the study region (e.g. a Sivas/Gemerek-area airfield elevation, cross-checked against
  M1's existing ARP data where available) within a stated tolerance.
- `world-model/tests/test_dcs_grid.py` — new. Parses a small **hardcoded fixture** (literal
  `ELEV_PROBE` log lines copied from the one-shot live probe run, with a provenance comment — same
  pattern `tests/test_osm_features.py` uses) — no dependency on a live `dcs.log` in tests.
- `world-model/research/<date>-m4-dcs-elevation.md` — new dated research note recording: the grid
  extent/spacing actually used, `net.log` throughput/line-count behavior observed, the DCS-vs-SRTM
  delta table and summary stats, and the MissionScripting.lua sandbox-check addendum if run.
- `world-model/CLAUDE.md` — add an "Elevation / DEM: SRTM (M4 decision)" line to the Tech stack
  section, same style as the existing pyproj/Pillow entries.
- `world-model/ROADMAP.md` — flip M4's checkbox once the diagnostic runs and the user has reviewed
  the delta report.

No changes to `src/coordinates/`, `src/raster/`, or `src/osm/` — `coordinates.dcs_to_wgs84` is
consumed as-is.

### Implementation Plan

1. **Minimal working version — smoke-test the extraction mechanism itself.** Before committing to
   a full grid: precompute DCS x/z for a small handful (5-10) of points scattered around the
   Gemerek bbox already established in M2/M3 (`south=39.170, west=36.050, north=39.195,
   east=36.090` — reuses the held-out, independently-validated tile registration, keeps M4
   consistent with M1-M3 rather than opening a new region). Write `elevation_probe.lua` with just
   those points, run it once in a throwaway mission (same manual workflow as `coord_probe.lua`:
   trigger, `TIME MORE 5`, `DO SCRIPT FILE`), collect `dcs.log` via
   `collect_elevation_log.sh`, and confirm: (a) `land.getHeight` returns plausible meter values,
   not nil/error — this is the first real confirmation of Finding 4/the "Unresolved" item in the
   recon note; (b) `net.log` lines survive intact (no truncation/rotation issue) — resolves the
   recon note's "untested at scale" flag, at small N first. Only proceed to a full grid once this
   smoke test passes. Write `dcs_grid.parse_net_log` against the real output.
2. **Validate correctness — full grid + DEM comparison.** Expand the Lua grid to cover the full
   Gemerek bbox at a stated spacing (proposed: ~300 m spacing, ~10×10 ≈ 100 points — adjust if
   Stage 1's `net.log` line count suggests a different comfortable ceiling). Re-run the mission
   once, collect the full grid. Fetch the one SRTM tile covering the region (`N39E036.hgt` — the
   whole Gemerek bbox fits inside a single 1°×1° tile), write `dem.py`, and run
   `inspect_elevation.py` to produce the delta table. Write `test_dem_srtm.py`'s control-point test
   against a known real-world elevation. Sanity-check the delta distribution against expectations
   already on record (M1's ~1.0-1.3 km horizontal DCS-vs-real-world residual, M2/M3's raster/OSM
   displacement) — a non-zero, roughly-consistent-magnitude vertical delta is expected, not a bug;
   a wildly discontinuous or sign-flipping delta pattern would indicate a real bug (e.g. a
   lat/lon-vs-lon/lat swap, or a vertical-datum mismatch worth flagging explicitly either way — see
   Risks).
3. **Validate performance.** Confirm the full-grid probe was genuinely one mission run (no retries
   needed), confirm `collect_elevation_log.sh` + `parse_net_log` complete instantly against a ~100
   line log excerpt (not a performance-sensitive path at this scale, no profiling needed), and spot
   check no grid points were silently dropped (expected point count == parsed point count).
4. **Refine / close out.** Run the optional `probe_missionscripting_sandbox.sh` read-only check if
   convenient (cheap, upgrades an existing recon finding but isn't load-bearing). Write the dated
   research note, add the `world-model/CLAUDE.md` stack line, run the full verification sequence
   (`ruff format`, `ruff check`, `mypy --strict`, `pytest`), get user sign-off on the delta report,
   flip M4's `ROADMAP.md` checkbox.

### Risks & Unknowns

- **`land.getHeight` itself has never been called against the live install** — only `coord.LOtoLL`
  (same documented environment) has been confirmed in M1. Stage 1's smoke test is the first real
  test of this; if it behaves unexpectedly (wrong argument shape, unavailable, wildly implausible
  values), the whole extraction mechanism needs rethinking before Stage 2, not after.
- **`net.log`'s practical throughput/line-length/rotation behavior is untested** — Hoggit's own
  docs flag the full argument set as undocumented. Stage 1's small-N smoke test exists specifically
  to catch this before a ~100-point run is built around it. If it proves awkward at scale, the
  recon note's fallback is a `io.open`-based write (same as `coord_probe.lua`), which reopens the
  io/lfs sandbox question as load-bearing again — worth deciding then, not preemptively.
- **Vertical datum mismatch between DCS and SRTM is a real, currently unaddressed risk.** SRTM
  heights are typically referenced to the EGM96 geoid; it is not established what vertical
  reference DCS's own terrain art uses (this wasn't investigated this session — out of scope for
  the current recon, but should be called out explicitly in the M4 research note rather than
  silently absorbed into "expected residual"). A systematic multi-meter offset across the whole
  grid, rather than point-to-point noise, would be the signature of a datum mismatch rather than a
  transform bug — the research note should distinguish the two explicitly.
- **DCS terrain mesh LOD**: `land.getHeight` likely reflects a simplified/clipmap-resolution mesh,
  not full visual-detail terrain art — expect some noise at fine spacing; M4's goal is proving the
  method works, not chasing sub-meter precision.
- **SRTM access friction** (NASA Earthdata login vs. `viewfinderpanoramas.org` no-login mirror) —
  resolved below, but flagged since it's a one-time manual step either way, not a scripted fetch
  (unlike M3's Overpass call).
- The unprompted "user has indicated willingness to edit MissionScripting.lua" note from the
  investigator's research file is **not acted on** in this plan and should not be treated as
  authorization — see "Decisions Requiring User Input."

### Decisions Requiring User Input

- **io/lfs / `MissionScripting.lua` edit — needs your direct confirmation, not a relayed one.**
  The investigator's recon note states you'd indicated willingness to de-sanitize `io`/`lfs` on the
  DCS install. I have no record of that instruction in this conversation, and editing
  `MissionScripting.lua` would be a deliberate, scoped exception to `CLAUDE.md`'s "never modify the
  DCS installation" invariant — not something I'll plan around on an agent's say-so. This plan
  defaults to the `net.log` approach (needs no install edit, works identically whether io/lfs are
  open or not). If you do want to authorize an install edit for some other reason, say so
  explicitly here and I'll fold it in as a documented exception; otherwise this is a non-issue and
  the plan proceeds as written.
- **SRTM source**: NASA Earthdata (official USGS/NASA channel, now requires a free account signup)
  vs. `viewfinderpanoramas.org` (no login, third-party-processed derivative redistributing the same
  `.hgt` format). This plan defaults to `viewfinderpanoramas.org` for zero setup friction — say if
  you'd rather set up Earthdata credentials for the more authoritative source instead; the parser
  (`dem.py`) is identical either way since both distribute plain `.hgt` files.
