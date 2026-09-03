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
- **`io`/`lfs` sandbox status**: stripped by default in `MissionScripting.lua` (3+ convergent
  community sources). User has since directly authorized (this session, not relayed) manually
  uncommenting the `io`/`lfs` lines in the installed `MissionScripting.lua` for investigation
  probes specifically — never for pipeline code, not a long-term change. M4's probe therefore uses
  `io.open` to write its own dedicated log file, rather than routing through `net.log`/`dcs.log`.
  See `world-model/CLAUDE.md`-adjacent memory note; this is a standing per-project preference for
  future probes too, not a one-off exception.
- **DEM choice: SRTM (`.hgt`, ~30 m), not Copernicus GLO-30.** SRTM's `.hgt` is a flat big-endian
  int16 grid, parseable with stdlib `struct`/`array` — zero new dependency, consistent with the
  `pyproj`/stdlib/`Pillow` stack M1-M3 already established. Copernicus GLO-30 has friendlier
  no-login access but ships as Cloud-Optimized GeoTIFF, which realistically needs GDAL/rasterio (or
  a COG-aware TIFF library) to read correctly — a disproportionate new dependency for this
  milestone's stated goal.

**Resolved**: the investigator's research note had flagged, unprompted, that "the user has
indicated willingness to manually edit `MissionScripting.lua` to open io/lfs" — with no record of
that instruction anywhere in this conversation at plan-drafting time. The user has since confirmed
directly, in-session: `MissionScripting.lua` may be manually edited to unlock `io`/`lfs` for
investigation/probe scripts (not pipeline code, not a permanent change), and probes should prefer
io/lfs over `net.log` when available so output goes straight to its own log file. This plan now
uses that approach for `elevation_probe.lua`. Requires a one-time manual edit before Stage 1's
probe run: uncomment the `io`/`lfs` lines in the installed `Scripts/MissionScripting.lua`.

### Affected Modules / Files

- `world-model/tools/dcs-mission-probe/elevation_probe.lua` — new. Mirrors `coord_probe.lua`'s
  structure/header-comment conventions. Iterates a hardcoded grid of DCS `(x, z)` points (generated
  offline in Python, pasted in as a literal Lua table — no runtime grid-generation logic needed in
  Lua), calls `land.getHeight({x=.., y=z})` per point, and writes one JSON line per point via
  `io.open(...):write(...)` to a dedicated output file (not `dcs.log`). Header comment must note
  the prerequisite: `io`/`lfs` uncommented in the installed `Scripts/MissionScripting.lua` before
  running (investigation-probe-only exception — never required for pipeline code).
- `world-model/tools/dcs-mission-probe/README.md` — add the new script's entry + the
  `MissionScripting.lua` io/lfs prerequisite (one-time manual edit, probe-only, not a permanent
  install change) + workflow note (output is the probe's own file, collected directly — no
  `dcs.log` grep step needed, unlike a `net.log`-based probe).
- `world-model/tools/wsl/collect_elevation_log.sh` — new, read-only. Copies the probe's own output
  file from `Saved Games/DCS/` into `win-mac-sync/wsl-output/`. Pure read — no installation change
  itself (the `MissionScripting.lua` edit is a separate, explicit manual step documented in the
  probe's README, not performed by this script).
- `world-model/src/elevation/__init__.py` — new package, mirrors `coordinates/`/`osm/` structure.
- `world-model/src/elevation/dcs_grid.py` — new. `DcsElevationSample` (frozen dataclass: `x: float,
  z: float, height_m: float`); `parse_probe_output(path: Path) -> list[DcsElevationSample]` parses
  the probe's own JSON-lines output file (stdlib `json`, no new dep).
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
- `world-model/tests/test_dcs_grid.py` — new. Parses a small **hardcoded fixture** (literal probe
  output lines copied from the one-shot live probe run, with a provenance comment — same pattern
  `tests/test_osm_features.py` uses) — no dependency on a live probe output file in tests.
- `world-model/research/<date>-m4-dcs-elevation.md` — new dated research note recording: the grid
  extent/spacing actually used, the DCS-vs-SRTM delta table and summary stats, and confirmation
  that the `MissionScripting.lua` io/lfs edit was probe-only (reverted or left as user prefers —
  note which).
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
   those points — after uncommenting `io`/`lfs` in the installed `Scripts/MissionScripting.lua` —
   run it once in a throwaway mission (same manual workflow as `coord_probe.lua`: trigger, `TIME
   MORE 5`, `DO SCRIPT FILE`), collect the probe's output file via `collect_elevation_log.sh`, and
   confirm: (a) `land.getHeight` returns plausible meter values, not nil/error — this is the first
   real confirmation of Finding 4/the "Unresolved" item in the recon note; (b) `io.open`/`write`
   works as expected under the edited sandbox, no truncation issue. Only proceed to a full grid
   once this smoke test passes. Write `dcs_grid.parse_probe_output` against the real output.
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
4. **Refine / close out.** Write the dated research note (including whether the
   `MissionScripting.lua` io/lfs edit was left in place or reverted after the probe runs), add the
   `world-model/CLAUDE.md` stack line, run the full verification sequence (`ruff format`, `ruff
   check`, `mypy --strict`, `pytest`), get user sign-off on the delta report, flip M4's
   `ROADMAP.md` checkbox.

### Risks & Unknowns

- **`land.getHeight` itself has never been called against the live install** — only `coord.LOtoLL`
  (same documented environment) has been confirmed in M1. Stage 1's smoke test is the first real
  test of this; if it behaves unexpectedly (wrong argument shape, unavailable, wildly implausible
  values), the whole extraction mechanism needs rethinking before Stage 2, not after.
- **`io`/`lfs` behavior under the edited sandbox is untested at scale** — Stage 1's small-N smoke
  test exists specifically to catch any write/flush/truncation issue before a ~100-point run is
  built around it.
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
- **Reverting the `MissionScripting.lua` edit**: since io/lfs access is probe-only and explicitly
  not for long-term use, close-out should note whether the user reverted the edit after M4's probe
  runs are done — not this plan's decision to make, but worth surfacing so it isn't silently
  forgotten as a standing install modification.

### Decisions Requiring User Input

- **io/lfs / `MissionScripting.lua` edit — resolved.** User confirmed directly, in-session:
  probes may uncomment `io`/`lfs` in the installed `MissionScripting.lua`; probe-only, not
  permanent, never for pipeline code. Plan updated to use `io.open` in `elevation_probe.lua`
  accordingly.
- **SRTM source**: NASA Earthdata (official USGS/NASA channel, now requires a free account signup)
  vs. `viewfinderpanoramas.org` (no login, third-party-processed derivative redistributing the same
  `.hgt` format). This plan defaults to `viewfinderpanoramas.org` for zero setup friction — say if
  you'd rather set up Earthdata credentials for the more authoritative source instead; the parser
  (`dem.py`) is identical either way since both distribute plain `.hgt` files.
