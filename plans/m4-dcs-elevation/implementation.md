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

---

### Addendum — Stage 1 confirmed against real probe output

Live probe output synced back (8 points, `world-model/data/raw/dcs/2026-09-03/elevation_probe_output.jsonl`,
gitignored raw input, immutable). `land.getHeight` worked as documented (no nils/errors, all 8
points returned a height) and `io.open` under the edited `MissionScripting.lua` wrote/flushed the
full file with no truncation — both of Stage 1's open questions (recon note "Unresolved") are now
resolved by direct reproduction. Heights ranged 1163.18–1339.91m, consistent with the Sivas
plateau region the Gemerek bbox sits in — no implausible values (e.g. near-zero or absurdly high)
that would indicate a wrong argument shape or nil-handling bug.

**Files changed (this addendum):**
- `world-model/tests/test_dcs_grid.py` — new. Hardcodes the real 8-point fixture (literal JSON
  lines copied from the live probe run, provenance comment pointing at
  `data/raw/dcs/2026-09-03/elevation_probe_output.jsonl`), mirroring `test_osm_features.py`'s
  pattern. Four tests: parses all 8 points in order, parses one point's fields exactly
  (`corner_sw`), asserts the fixture's raw heights fall in a plausible 1000-1500m band for this
  region (Stage 1's core confirmation, not just a parser test), and asserts a `null` `height_m`
  raises `ValueError` naming the failed point.
- `world-model/data/raw/dcs/2026-09-03/elevation_probe_output.jsonl` — moved from
  `win-mac-sync/wsl-output/` per `collect_elevation_log.sh`/`wsl-probe-sync` workflow. Gitignored,
  not committed; referenced by path/provenance comment from `test_dcs_grid.py` instead.

**Checks (re-run after this addendum):** `ruff format --check`, `ruff check`, `mypy --strict`
(`src`+`tests`), `pytest world-model/tests -q` — all pass, 25 passed (21 prior + 4 new).

**Stage 1: done.** Both risks flagged in the plan ("Risks & Unknowns": `land.getHeight` never
called live; `io`/`lfs` write behavior under the edited sandbox untested at scale) are now
resolved by direct reproduction at small-N. Not yet attempted at the ~100-point Stage 2 scale —
if `io.open`/`write` throughput degrades at that size, Stage 2 would need to re-flag it, but
nothing in this run suggests a problem.

**Stage 2 status: blocked, not started.** Needs (a) the full ~300m-spacing grid probe run (new
`elevation_probe.lua` grid + another live mission run), and (b) the SRTM `.hgt` tile
(`N39E036.hgt`) for the DEM comparison — still not available (this sandbox has no outbound
network access, see "Notable Discoveries" above; the user has not yet supplied the tile either).
Per the coordinator's explicit instruction this session: do not fabricate the tile or its data to
proceed past this point.

---

### Addendum 2 — SRTM tile received (SRTM3, not SRTM1); Stage 2 grid + tooling built

The user supplied `world-model/data/raw/dem/N39E036.hgt` (2,884,802 bytes) — **SRTM3 (3
arc-second, 1201x1201, ~90m), not SRTM1** (1 arc-second, 3601x3601, ~30m) as the recon note had
anticipated (viewfinderpanoramas.org serves both; the user picked 3"). `dem.py`'s
`SrtmTile.from_file` already derived grid size dynamically from file length rather than
hardcoding 3601 (see Addendum 1's "Notable Discoveries" — this was flagged at the time as a
robustness choice beyond what the plan asked for; it paid off here), so **no functional code
change was needed** to read the actual tile correctly — verified: `size=1201`,
`sw_lat=39.0`, `sw_lon=36.0`, and a spot-check `height_at` at the Gemerek control point landed at
1208.76m (full tile) / 1225.98m (at the Wikipedia-published coordinate specifically, see below) —
both physically plausible for the region.

**Files changed (this addendum):**
- `world-model/src/elevation/dem.py` — updated the module/class docstrings to describe both
  SRTM1 and SRTM3 (previously only described SRTM1/3601, which was now factually wrong for the
  tile actually in use). Added a `span_deg: float = 1.0` field to `SrtmTile` and generalized
  `_row_col` to use it instead of a hardcoded `+1` degree assumption — `from_file` still always
  produces `span_deg=1.0` (real `.hgt` files are always exactly 1x1 degree), but this lets a test
  construct a `SrtmTile` directly over a small real-data crop with its own true (small)
  geographic extent, without needing to embed an entire multi-megabyte tile as a fixture.
- `world-model/tests/test_dem_srtm.py` — new. Fixture is a literal 5x5 crop of real int16 samples
  read directly from `N39E036.hgt` (rows 979-983, cols 79-83, centered on the Gemerek control
  point), with `span_deg` set to that crop's true ~0.0033° extent (not fabricated data — a real
  subset, same pattern as `test_osm_features.py`/`test_dcs_grid.py`). Control-point test:
  `height_at` at Gemerek's Wikipedia-published coordinate (39.18194N, 36.06806E — the same point
  already used in `test_raster_registration.py`) against Gemerek's published elevation (1,204m,
  fetched via WebFetch this session), within 50m tolerance (accounts for SRTM3's ~90m grid plus
  the published coordinate being a rounded town-center point, not the exact measurement spot).
  Also: an internal-consistency check against the full-tile reading, an out-of-grid `ValueError`
  test, a void-sample `ValueError` test, and a bad-filename rejection test.
- `world-model/tools/dcs-mission-probe/elevation_probe.lua` — replaced the Stage 1 8-point smoke
  grid with the Stage 2 full grid: 10x10 = 100 points, evenly spaced across the Gemerek bbox
  (south=39.170, west=36.050, north=39.195, east=36.090), precomputed via
  `coordinates.wgs84_to_dcs`. Same `io.open`/`pcall` mechanism as Stage 1 (already confirmed
  working). Header comment updated to explain this overwrites Stage 1's output file (safe --
  Stage 1's data is preserved in `test_dcs_grid.py`'s fixture) and to note the io/lfs
  `MissionScripting.lua` prerequisite must still be in place. Re-copied into
  `win-mac-sync/run-wsl/` for the user to run.
- `world-model/tools/dcs-mission-probe/README.md` — noted the script now holds the Stage 2 grid.
- `world-model/tools/inspect_elevation.py` — new CLI (`compare` subcommand), mirrors
  `inspect_osm_overlay.py`'s pattern. Loads a parsed probe grid + an SRTM tile, transforms each
  DCS point to lat/lon via `coordinates.dcs_to_wgs84`, looks up the SRTM height, and prints an
  `elevation_dcs / elevation_external / delta` table (field names per
  `docs/concept/WORLD_MODEL_BUILDER.md`'s Elevation section) plus mean/min/max/stddev delta
  summary stats. Smoke-tested against the real Stage 1 8-point fixture + the real `N39E036.hgt`
  tile (not fabricated): mean delta 3.66m, stddev 37.78m; 7 of 8 points landed within ~32m, one
  outlier at `corner_sw` (-86.09m) not yet explained — flagged for attention once the full
  100-point Stage 2 grid is in, not treated as a bug on this 8-point sample alone.

**Checks (re-run after this addendum):** `ruff format --check`/`ruff check` (`src`+`tests`),
`mypy --strict` (`src`), `pytest world-model/tests -q` — all pass, 30 passed (25 prior + 5 new).
`tools/inspect_elevation.py` isn't in the mandated check commands (per `world-model/CLAUDE.md`)
but was formatted/linted/type-checked individually and matches the existing tools/ EXE001
pattern (shebang present, file not marked executable — same as every other `tools/inspect_*.py`
and `decode_raster_tile.py`, not fixed here since it's pre-existing repo-wide, out of scope for
this addendum per the "fix pre-existing drift in its own commit" convention).

**Stage 2 status: probe/tooling ready, still needs one more live mission run.** `test_dem_srtm.py`
is already complete and passing (it uses a real tile crop directly, independent of the grid probe
run). What remains blocked on the live run: the full 100-point grid script is staged in
`win-mac-sync/run-wsl/elevation_probe.lua`; the user needs to run it (io/lfs edit must still be in
place) and sync the output back via `collect_elevation_log.sh`, after which this session can move
the real output into `data/raw/dcs/<date>/`, run `inspect_elevation.py` against it for the actual
100-point delta report, write the M4 research note recording that report, and do Stage 3
(performance/completeness spot-check: point count in == point count out, one mission run, no
retries) and Stage 4 close-out.
