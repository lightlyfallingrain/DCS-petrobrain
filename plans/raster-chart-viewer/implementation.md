### Implementation Summary

Stages 1-6 of `plans/raster-chart-viewer/plan.md` implemented in a new standalone top-level
subproject, `raster-chart-viewer/`. Stage 7 (the live Windows/LAN check) is the user's own task;
only its run instructions were written (`README.md`).

### Files Changed

- `raster-chart-viewer/pyproject.toml` -- new subproject, `pillow>=9.1` dependency only.
- `raster-chart-viewer/.gitignore` -- own venv/caches, plus `cache/` for the tile/mip disk cache.
- `raster-chart-viewer/src/raster_chart_viewer/tilename.py` -- the universal filename regex,
  `TileKey`.
- `raster-chart-viewer/src/raster_chart_viewer/discovery.py` -- `discover_terrains`, the single-zip
  and Caucasus zip-per-sheet layouts. Simplified from the plan's own framing: once the right zip
  paths are selected (`rasterCharts.zip`, or every `*/*.zip` for the Caucasus layout -- globbed
  generically rather than a hardcoded `{0.25M,0.5M,1M,2M,5M}` list), indexing is identical for both
  layouts, since scale/sheet always come from entry names, never zip/folder names (confirmed
  against the research note's own section D). `ReadTileBytes` type alias and `read_tile_bytes` are
  the injectable seam every counting test in `cache.py`/`warmup.py` uses.
- `raster-chart-viewer/src/raster_chart_viewer/mosaic.py` -- `MosaicGrid`, sheet/level -> tile-grid
  coordinate math, pinned against the research note's exact Syria 32m sheet set.
- `raster-chart-viewer/src/raster_chart_viewer/ddsmip.py` -- mip byte-offset formula + Pillow BCn
  decode of one mip from one entry's already-inflated bytes.
- `raster-chart-viewer/src/raster_chart_viewer/cache.py` -- `TileCache` (composed-tile JPEGs +
  small-mip PNGs, 1GB shared cap, oldest-mtime-first eviction) and `compose_view_tile`. **Any
  inflate -- not only one triggered by a small-mip request -- opportunistically populates every
  small mip (`>= SMALL_MIP_MIN`) not yet cached**, via the shared `read_and_populate_small_mips`
  helper both `compose_view_tile` and `warmup.py` call. This reads the plan's "written whenever an
  entry is inflated for any reason" literally; my first draft only populated small mips on the
  small-mip-triggered path, which the plan's own wording does not support once reread carefully.
- `raster-chart-viewer/src/raster_chart_viewer/server.py` -- `RasterChartViewerServer`
  (`ThreadingHTTPServer`, mirrors `aircraft-layer`'s `TelemetryAPIServer` shape): `GET /terrains`,
  `GET /terrains/<t>/tiers`, `GET /terrains/<t>/tiers/<tier>` (grid metadata for the viewer's
  `TileSource` -- see "Notable Discoveries"), `GET /tile/<terrain>/<tier>/<level>/<x>/<y>.jpg`,
  static file serving (path-traversal-guarded). Port 7800 (corrected to 7801 2026-11-16 -- see
  `plan.md`'s "Port and firewall" section).
- `raster-chart-viewer/src/raster_chart_viewer/__main__.py` -- CLI entry point.
- `raster-chart-viewer/src/raster_chart_viewer/warmup.py` -- `WarmupScheduler`, one background
  thread per `(terrain, tier)` started on first touch, skipping entries whose small mips are
  already cached.
- `raster-chart-viewer/static/index.html` -- OpenSeadragon viewer page: terrain/tier pickers, a
  custom plain-object `TileSource`. Declares the logical canvas as a square power-of-two multiple
  of the tile size (`2^max_level * tile_size_px`), not the mosaic's own `tiles_wide x tiles_tall`
  extent -- see "Notable Discoveries".
- `raster-chart-viewer/static/openseadragon/` -- vendored OpenSeadragon 4.1.1 (`openseadragon.min.js`,
  `images/`, `LICENSE.txt`), fetched via `npm pack openseadragon@4.1.1` against the official
  registry. Non-minified build and `.js.map` source maps deliberately left out.
- `raster-chart-viewer/CLAUDE.md` -- stack/testing/structure, OpenSeadragon provenance.
- `raster-chart-viewer/README.md` -- dev commands plus Stage 7's full run instructions (documents
  only; Stage 7 itself was not attempted).
- `raster-chart-viewer/tests/` -- see "Tests Added".

### Tests Added

- `test_tilename.py` -- every real filename variant (scale+underscore, scale+no-underscore, no-
  scale-prefix, negative level, case-insensitivity), non-matching names.
- `test_discovery.py` -- single-zip and Caucasus layouts from fake trees, U2's "unscaled" tier,
  sparse-sheet coverage, a terrain stub with no `RasterCharts/`, a missing `Mods/terrains/`.
- `test_mosaic.py` -- `test_syria_32m_sheet_mosaic_convention` pins the research note's exact
  sheet/level set against every (row, col) combination (not just one axis in isolation); within-
  sheet x/z placement; a sparse sheet leaves blank gaps, not an exception; `max_level`/grid extent
  for a single-sheet and single-tile grid.
- `test_ddsmip.py` -- the mip-byte-size formula at the smallest sizes and against the measured
  Syria total (1,398,128 + 128 header = 1,398,256); cumulative byte offsets; decoding any mip of a
  synthetic multi-mip fixture matches an independent (plain pixel-averaging, never Pillow's own
  `resize`) reference downsample within a measured tolerance.
- `test_cache.py` -- a repeated full-res request opens no entry twice; a small-mip-tier request
  after every entry it covers was already inflated (via full-res touches) opens none either; a
  middle-zoom request populates small mips too (not only mips `< SMALL_MIP_MIN` as ingredients,
  which are never written) and a repeat of the *same* middle-zoom tile opens nothing new;
  `put_small_mip` rejects a mip below `SMALL_MIP_MIN`; a write past a tiny configured cap evicts
  the oldest file first.
- `test_server.py` -- a real server on an OS-assigned port (mirrors `aircraft-layer/tests/
  test_api.py`): terrain/tier listing, tier-info grid metadata, a tile request returns valid JPEG
  bytes, out-of-range level and unknown tier 404, an out-of-bounds `(x, y)` composes blank rather
  than erroring, static serving (index, vendored asset, path-traversal rejection), unknown path 404.
- `test_warmup.py` -- warm-up completes and populates small mips (waited on via
  `TileCache.has_all_small_mips`, not the read counter -- see "Notable Discoveries"); never starts
  for a tier nobody touched; a second warm-up after a simulated restart skips already-cached
  entries; a warmed tile request doesn't reopen the entry; a second `touch` for the same tier is a
  no-op.

### Checks

(raster-chart-viewer/ -- own venv, pillow>=9.1 / ruff==0.16.6 / mypy==2.3.1 / pytest==9.1.1,
matching the repo's current pins)

- `ruff format --check`: pass
- `ruff check`: pass
- `mypy --strict` (`cd raster-chart-viewer && .venv/bin/mypy src`): pass, 9 source files
- `pytest -q`: pass, 50 passed

### Notable Discoveries

- **The plan's own endpoint list didn't name a grid-metadata endpoint, but the viewer client
  cannot work without one.** `GET /terrains/<t>/tiers/<tier>` (`tiles_wide`, `tiles_tall`,
  `max_level`, `tile_size_px`) was added in Stage 4/5 as the natural extension of the already-built
  tier-listing endpoint, not a new mechanism -- flagged in a separate commit rather than folded in
  silently.
- **OpenSeadragon's own level convention already matches this service's `level`/`k` mapping
  exactly** -- level 0 is the most zoomed-out single tile, `maxLevel` is full native resolution,
  same direction both ways -- so no inversion was needed in `index.html`'s `getTileUrl`. I mixed
  this up myself during the real-data smoke check (see below) and it cost one round of confused
  investigation before I reread `compose_view_tile`'s own `k = grid.max_level - level` correctly.
- **Declaring the viewer's logical canvas as a square power-of-two multiple of the tile size,
  rather than the mosaic's own `tiles_wide x tiles_tall` pixel extent, avoids a real correctness
  risk I did not fully resolve, just sidestepped.** Most real grids are not an exact power-of-two
  multiple of 1024 in both dimensions (Afghanistan is 48x64 tiles; 48 is not a power of two).
  OpenSeadragon's default edge-tile handling expects a *cropped* tile at the image's true edge when
  the dimensions aren't an exact power-of-two multiple of the tile size; this server always returns
  a full `tile_size_px` square (blank-padded), which would conflict with that expectation. Declaring
  a canvas that is itself an exact power-of-two multiple sidesteps the conflict entirely (every
  tile OpenSeadragon ever requests, in bounds or past the real grid, gets the same full-square
  shape) rather than reconciling the two. This was verified live against real terrains (Afghanistan,
  Kola, Caucasus, Syria, Mariana) at the HTTP/decode level -- every fetched tile decoded correctly
  and sparse gaps rendered as blank, not errors -- but the actual OpenSeadragon *pan/zoom rendering*
  itself was never exercised (no browser available in this environment); Stage 7's manual check is
  where a residual edge-tile visual glitch, if the sidestep doesn't fully hold, would show up.
- **`compose_view_tile`'s small-mip population had to be restructured once, after writing
  `cache.py` the first time.** My first draft only populated the small-mip cache on the branch
  triggered by a small-mip request (`mip >= SMALL_MIP_MIN`); rereading the plan's "written whenever
  an entry is inflated for any reason" made clear every inflate (including middle-zoom and full-res
  ones) should opportunistically populate small mips too, since the cost of reading the entry is
  already paid. Caught before committing Stage 3, not after, by taking the plan's own test
  acceptance wording ("a request at k >= SMALL_MIP_MIN after any inflate of the entries it covers
  opens none either") and designing the test cases from it directly, which only passed once the
  implementation matched the literal reading.
- **A genuine timing defect in my own first-draft `test_warmup.py`, not the implementation**:
  waiting on `reader.open_count == N` is not the same as warm-up having finished *writing* that
  entry's small mips to disk -- the write for the last entry opened can still be in flight when the
  read counter reaches N. Fixed by waiting on `TileCache.has_all_small_mips` for every key instead,
  the real completion signal. Confirmed flaky before the fix (failed on the first run, passed every
  time after) rather than assumed from reasoning alone.
- **Real-data smoke run** (optional, not committed, cache dir deleted afterward): ran the server
  read-only against `--dcs-install "/mnt/f/Games/DCS World"`. Discovered all 5 installed terrains
  with the expected tiers each: Afghanistan (32m), Caucasus (16m/32m/64m/128m/256m -- the
  `0.25M/0.5M/1M/2M/5M` layout), Kola (32m), MarianaIslands (16m/32m/64m/unscaled -- U2 confirmed
  live), Syria (32m/64m). Fetched and decoded real tiles from every terrain/tier -- genuine varied
  pixel content, not blank, except where a sampled grid position happened to be a real sparse-sheet
  gap (confirmed by sampling nearby positions and finding real content, rather than assuming), which
  rendered blank exactly as designed rather than erroring. The single most-zoomed-out overview tile
  for the larger tiers (Afghanistan's 3072-entry 32m, in particular) is genuinely slow to compute
  cold -- consistent with the research note's own measured ~16ms/entry warm, ~115ms/entry cold over
  this same WSL-to-`/mnt/f` bridge -- which is exactly the cost Stage 6's background warm-up exists
  to hide; this was observed directly (a first attempt at fetching it for all 8 sampled tiers in
  one script timed out) rather than assumed from the plan's own estimate.
- **No deviation from the plan's scope** beyond the one added endpoint and the discovery-layout
  simplification above, both already noted. Stage 7 was not attempted, as instructed -- only its
  run instructions were written and verified (the exact `python -m raster_chart_viewer` invocation
  was run for real, from `src/`, against a fake `--dcs-install` path, to confirm the command and
  the "stand in `src/`" instruction are both correct, not merely copied from `aircraft-layer`'s
  precedent by analogy).

## Performance review fixes (the two NOW items, 2026-11-16)

Addressed `plans/raster-chart-viewer/performance-review.md` Findings 1 and 2. Finding 3 (warm-up
racing its triggering request) is MONITOR only, per the review's own verdict, and was not touched.
`RC-B1` (tile-URL integer bound) was not touched either, per the task's own instruction.

### Fix 1: `discovery.BatchZipReader` -- one `ZipFile` handle per call, confined to that call

Added `discovery.BatchZipReader` and its factory `discovery.batch_tile_reader()`: a
`ReadTileBytes`-shaped callable that lazily opens and caches one `zipfile.ZipFile` per distinct
`zip_path` it is asked to read, for as long as it stays open, and closes every handle it opened on
`close()`/context-manager exit. `read_tile_bytes` (the single-entry, always-fresh-open function) is
unchanged and still exists for genuine one-off reads; its docstring is corrected -- it previously
called the reopen cost "negligible" unconditionally, which the review's own measurement (4.1x
slower across a 100-entry batch) showed is only true for a single-entry call.

**Chose a lazy per-call cache over the plan's literal "group by zip_path up front" wording** because
it is simpler and behaviourally identical for this purpose: `compose_view_tile`'s existing
per-entry loop decides, entry by entry, whether a read is even needed (the `mip >= SMALL_MIP_MIN`
branch checks the small-mip cache first and skips the read entirely on a hit) -- pre-grouping would
have required restructuring that loop into two passes to know in advance which locations need
reading. A lazy dict keyed by `zip_path`, opened on first use, achieves the same "one open per zip
per call" result without touching the loop's control flow at all, so the fix is a pure addition at
the reader level plus one small dispatch change at each call site, not a loop rewrite.

**Call-site change, both `cache.compose_view_tile` and `warmup.WarmupScheduler._warm_up`:** the
`read_bytes` parameter's default changed from the bare `discovery.read_tile_bytes` function to
`None`, with `None` meaning "open a fresh `batch_tile_reader()` scoped to this one call/pass."
`compose_view_tile`'s body was split into itself (decides the reader) and a new
`_compose_view_tile_uncached` (the unchanged composition loop, now taking `read_bytes` as a required
parameter). `WarmupScheduler._warm_up` similarly dispatches to a new `_run_warm_up`. **This was the
deliberate design choice that kept every existing test unmodified**: every test in `test_cache.py`
and `test_warmup.py` already injects its own `read_bytes=reader` / `WarmupScheduler(cache,
read_bytes=reader)` explicitly (the `_CountingReader` test double), so the `None`-sentinel default
is never on their path -- they keep exercising entry-level open counts exactly as before, and only
the production default (what `server.py`/`__main__.py` actually get, since neither passes
`read_bytes`) changes behaviour.

**Added, not modified, three tests** (existing tests untouched, per the above):
- `test_discovery.py::test_batch_tile_reader_opens_one_zip_once_across_many_entries` -- the reader in
  isolation, against a real on-disk zip, counting real `zipfile.ZipFile` constructions via
  `monkeypatch.setattr(discovery.zipfile, "ZipFile", ...)` rather than trusting the reader's own
  book-keeping.
- `test_cache.py::test_compose_view_tile_opens_its_zip_once_across_many_entries` -- the same real-zip
  construction-count probe, through a full `compose_view_tile` call with `read_bytes` left at its
  production default, at the level that touches all 64 entries in the fixture's 8x8 sheet.
- `test_warmup.py::test_warmup_pass_opens_its_zip_once_across_many_entries` -- same probe, through a
  full `WarmupScheduler` pass with `read_bytes` left at its production default.

**Each of the three was confirmed red for the stated reason before being left green**: temporarily
reverted the relevant call site back to the old fresh-open-per-entry path (captured and restored
each source file byte-for-byte via `sha256sum` before/after, not by eye), reran, and got
`open_count == 64`/`8` against the asserted `== 1` -- not a hypothetical counterfactual.

**Re-measured against the real, installed DCS copy** (`/mnt/f/Games/DCS World`, read-only; scratch
cache under `/tmp`, deleted after): 200 real Afghanistan 32m entries, old fresh-open-per-entry path
vs. `batch_tile_reader()` -- **2.34x** (5.18s vs 2.21s). Lower than the review's own measured 4.1x,
most likely session-to-session WSL-bridge variance (the review's own numbers already note this
bridge's timing is noisy; the review separately confirmed the underlying cost is CPU-bound, not
bridge-bound, which this remeasurement does not contradict -- it still shows a clear, real,
more-than-2x win from the same fix on the same real data).

### Fix 2: `TileCache`'s eviction sweep stops at a low-water mark, not the cap itself

Added `cache._CACHE_LOW_WATER_MARK_FRACTION = 0.9` and changed `_enforce_cap_locked`'s stopping
condition from `self._total_bytes <= self._max_bytes` to `self._total_bytes <= low_water_mark`
(`low_water_mark = int(self._max_bytes * _CACHE_LOW_WATER_MARK_FRACTION)`). Nothing else in the
method changed -- same lock scope, same stat-before-sort structure, same `try/except OSError`
tolerance for a vanished file, all from the reviewer's thread-safety fix, untouched.

Plain module-level constant, not run through any tuning mechanism -- this service has no Petrovich
dependency at all, and the tuning loader described in root `CLAUDE.md` does not exist outside
`body-layer` (`cache.py` already states this reasoning for `CACHE_MAX_BYTES`; the new constant's
own comment says the same).

**Added `test_cache.py::test_eviction_sweep_descends_to_low_water_mark_not_just_under_cap`**: ten
equal-sized 1000-byte files exactly fill a 10,000-byte cap (no sweep yet), an 11th crosses it, and
the assertion is the *exact* resulting total (9,000), not merely "at or under the cap" -- the old
behaviour would have stopped after evicting just one file (back to 10,000, already `<=` the cap),
so an "at or under 10,000" assertion would not have distinguished the two. **Confirmed red for the
stated reason** before being left green: reverted the stopping condition to the old `self.
_max_bytes` locally (restored byte-for-byte after, confirmed by `sha256sum`), reran, got
`actual_total == 10_000` against the asserted `== 9_000`.

**Existing concurrency test re-verified, run 5 times**: `test_concurrent_writes_under_a_forcing_cap_
never_raise_and_respect_cap` still passes -- the low-water-mark change only affects how far a sweep
descends once triggered, not the locking that test exercises. 5/5 clean passes
(`pytest -v`, each run individually).

### Checks (from inside `raster-chart-viewer/`, this round)

- `ruff format --check src tests`: pass (19 files already formatted)
- `ruff check src tests`: pass (one lint finding along the way -- `PYI034`, `BatchZipReader.
  __enter__` should return `Self`, not its own class name; fixed by importing `typing.Self`,
  matching `server.py`'s existing `RasterChartViewerServer.__enter__` pattern in this same
  subproject)
- `mypy src` (strict, cwd inside the subproject): pass, 9 source files, no issues
- `pytest tests -q`: pass, **55/55** (51 from the prior review round + 4 new: the three
  zip-open-count tests above, plus the low-water-mark test)
