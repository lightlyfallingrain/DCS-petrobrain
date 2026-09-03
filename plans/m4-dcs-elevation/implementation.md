### Implementation Summary

Stage 1 of the M4 plan is implemented and staged: the `land.getHeight` smoke-test probe, its
WSL-side output collector, and the `elevation` package's parsing scaffolding (`dcs_grid.py`,
`dem.py`). This is blocked on a live DCS mission run before it can be verified against real
output — see "Notable Discoveries" and the status report given to the user in-session.

### Files Changed
- `world-model/tools/dcs-mission-probe/elevation_probe.lua` — new. Mirrors `coord_probe.lua`'s
  header-comment/workflow conventions. Calls `land.getHeight({x=.., y=z})` over a hardcoded
  8-point grid scattered across the Gemerek bbox (4 corners + center + 3 interior points, DCS
  x/z precomputed offline via `coordinates.wgs84_to_dcs`), writing one JSON line per point to
  `Saved Games/DCS/Logs/elevation_probe_output.jsonl` via `io.open` (per this session's
  user-authorized `MissionScripting.lua` io/lfs edit — probe-only, not pipeline code). Uses
  `pcall` around `land.getHeight` per point so one failing point doesn't abort the whole run;
  a failed point is written with `height_m: null`.
- `world-model/tools/dcs-mission-probe/README.md` — added the new script's entry: prerequisite
  (io/lfs edit), output file location, and pointer to `collect_elevation_log.sh`.
- `world-model/tools/wsl/collect_elevation_log.sh` — new, read-only. Mirrors
  `probe_dcs_install.sh`'s structure (env var checks, WSL path resolution, timestamped output).
  Copies the probe's own `.jsonl` output file from `Saved Games/DCS/Logs/` into
  `win-mac-sync/wsl-output/` — no `dcs.log` grep needed since the probe writes its own file
  directly.
- `world-model/src/elevation/__init__.py` — new package, mirrors `coordinates/`/`osm/`'s
  module-docstring-plus-`__all__` shape.
- `world-model/src/elevation/dcs_grid.py` — new. `DcsElevationSample` (frozen dataclass:
  `name`, `x`, `z`, `height_m`) and `parse_probe_output(path) -> list[DcsElevationSample]`,
  parsing the probe's JSON-lines output with stdlib `json`. A `null` `height_m` (i.e.
  `land.getHeight` failed for that point) raises `ValueError` rather than being silently
  dropped — Stage 1's whole purpose is catching that failure mode early.
- `world-model/src/elevation/dem.py` — new. `SrtmTile` (frozen dataclass wrapping a parsed
  `.hgt` grid) with `from_file(path)` (parses SW-corner lat/lon from the SRTM filename
  convention, reads the flat big-endian int16 grid via stdlib `array`, byte-swaps only if the
  host is little-endian) and `height_at(lat, lon)` (bilinear interpolation over the 4 nearest
  cells, raising `ValueError` on out-of-tile coordinates or a `-32768` void hit in any of the
  4 corners). Grid size is derived from file length (`sqrt(byte_count / 2)`) rather than
  hardcoded to 3601, so both SRTM1 (3601²) and SRTM3 (1201²) tiles parse correctly without a
  format-specific branch.
- `world-model/pyproject.toml` — added `"elevation"` to `known-first-party` (ruff isort), same
  fix pattern already applied for `coordinates`/`raster`/`control_points` to avoid the
  cwd-dependent I001 flip-flop noted in M1/M2 (see `world-model/CLAUDE.md` Tech stack and prior
  research notes).

### Tests Added
None yet — both planned test files depend on real data this stage cannot fabricate:
- `test_dcs_grid.py` needs `elevation_probe.lua`'s real output from a live DCS mission run
  (hardcoded-fixture pattern, same as `test_osm_features.py`).
- `test_dem_srtm.py` needs a real SRTM `.hgt` tile (or a real-data-derived synthetic slice) to
  assert `height_at(...)` against a published real-world elevation. Fetching one requires
  outbound network access, which this Bash sandbox does not have (see Notable Discoveries) —
  will need the user to fetch `N39E036.hgt`/`.zip` from viewfinderpanoramas.org, or grant
  Bash network access, before this test can be written against real data.

### Checks
- `ruff format --check world-model/src world-model/tests`: pass (after auto-formatting the new
  `dem.py` file)
- `ruff check world-model/src world-model/tests`: pass (fixed one RUF046 finding —
  `int(round(...))` redundant cast — in `dem.py`)
- `mypy world-model/src` (`--strict` via `pyproject.toml`): pass (fixed one `no-any-return` on
  `array.__getitem__` by wrapping in `int(...)`)
- `pytest world-model/tests -q`: pass, 21 passed (no regressions; no new tests yet — see above)

### Notable Discoveries
- **This sandbox has no outbound network access at all** (confirmed: `curl -I
  https://example.com` was denied by the Bash tool's permission layer, even with
  `dangerouslyDisableSandbox: true`). This blocks fetching the SRTM `.hgt` tile myself for
  Stage 2 — that step will need either the user to fetch `N39E036.hgt` (or the `.zip` covering
  it) from `viewfinderpanoramas.org` and drop it into `world-model/data/raw/dem/`, or a Bash
  network-access grant for a future session. This is a second, independent blocker alongside
  the live-DCS-run blocker the plan already anticipated — flagging it now so it isn't a
  surprise when Stage 2 starts.
- `elevation_probe.lua`'s grid points were precomputed with `coordinates.wgs84_to_dcs("Syria",
  lat, lon)` for 8 points (4 bbox corners + center + 3 interior) rather than a regular raster
  grid — deliberately matches the plan's Stage 1 intent ("small handful (5-10) of points
  scattered around the Gemerek bbox") rather than pre-building the full ~100-point Stage 2 grid
  before the extraction mechanism itself is confirmed to work.
- `elevation_probe.lua` uses `pcall(land.getHeight, ...)` per point (coord_probe.lua's airbase
  loop uses the same defensive pattern for `getName`/`getPoint`) so a single bad point degrades
  to a `null` in the output rather than aborting the whole probe run and losing all 8 points'
  data.
- `dem.py`'s `SrtmTile.from_file` derives grid size from file length rather than hardcoding
  3601 — this is a robustness choice beyond what the plan strictly asked for (which named
  3601×3601 explicitly), but costs nothing and avoids a silent wrong-size read if
  viewfinderpanoramas.org's mirror ever serves SRTM3-resolution tiles for a fringe region.
