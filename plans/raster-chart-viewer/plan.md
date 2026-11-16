### Goal

Serve every installed DCS terrain's `RasterCharts` as a zoom/pan map in a browser, from a small
standalone LAN service on the Windows DCS machine, with tiles made on demand (no bulk extraction).

**No Petrovich behaviour depends on this** — it is a crew reference tool (the paper chart on a
tablet), not a perception/belief/decision feature. Goal-aligner and plan-aligner have nothing to
check here (confirmed already in `mission-interpreter/ROADMAP/MI-B4.md`).

**Investigator was not invoked.** Every DCS-internals fact this plan depends on — zip layout per
terrain, the universal filename grammar, the DDS/DXT5/mipmap format, the Syria sheet-mosaic
convention, and live timing — is already recorded in
`raster-chart-viewer/research/2026-11-16-rastercharts-all-terrains-recon.md` and
`world-model/research/2026-09-03-m2-rastercharts-recon.md`, which is exactly the "already in
`research/`" skip condition. The two remaining technical uncertainties (whether the installed
Pillow can *write* a multi-mipmap DXT5 DDS for test fixtures, and the exact mipmap byte-offset
arithmetic) are not DCS-internals questions — I verified both directly against the
`world-model/.venv` Pillow install in this session (below) rather than asking investigator to.

**Graph/memory checked first** (`gq.sh`, `memory-search.py`): no prior plan or memory entry on this
feature; the graph's only relevant hits are the already-read `notes/raster-charts-and-registration.md`
and `world-model/src/raster/` (read for reference, confirmed not to import from).

**Second-order effect:** none identified. `raster-chart-viewer/` imports nothing from any other
subproject and nothing else in the repo is planned to depend on its output (overlays/georeferencing
are named as later work, not committed to).

### Measured directly in this session (not from the research note)

Run against `world-model/.venv`'s Pillow 12.3.0 on the dev machine — not DCS-internals, just "can
our tooling do this":

- **Pillow 12.3.0 can *write* DXT5 DDS**: `Image.save(path, pixel_format="DXT5")` works, confirmed
  by reading back the written header (`fourCC=b'DXT5'`). It writes a **single-level** DDS
  (`dwMipMapCount=0`) — no mip chain — so a multi-mip test fixture has to be assembled by hand.
- **That assembly works end-to-end, tested locally**: encode each mip's image individually via the
  same `save(..., pixel_format="DXT5")` call, strip each one's 128-byte header, concatenate the raw
  block data in mip order, and write one combined header with `dwMipMapCount` set and
  `DDSCAPS_MIPMAP` in `dwCaps`. Reading it back: `Image.open()` recovers the base image, and
  `Image.frombytes("RGBA", (32, 32), data[128+mip0_size : 128+mip0_size+mip1_size], "bcn", 3)`
  recovers mip 1, decoding to the expected downsample. **This settles the offline test strategy —
  no hand-built block bytes needed, Pillow alone builds and reads back every test fixture.**
- **Mipmap byte-size formula, confirmed against the research note's own numbers.** DXT5 is 16
  bytes per 4×4 block, and a mip smaller than one block still occupies one whole block (never 0):
  `mip_bytes(level) = ceil(max(1, 1024 >> level) / 4) ** 2 * 16`. Summing all 11 levels of a
  1024×1024 base gives exactly **1,398,128** bytes; header is always 128 bytes
  (`"DDS "` + 124-byte `DDS_HEADER`); **1,398,128 + 128 = 1,398,256`, exactly the per-entry raw size
  the research note measured on the real Syria zip.** This is the formula the server uses to find
  where each mip starts in a real entry's inflated bytes — no guessing, no second live probe needed.

### Affected Modules / Files — all new, one new top-level subproject

```
raster-chart-viewer/
  pyproject.toml          — own venv, deps: pillow only (stdlib otherwise)
  CLAUDE.md                — stack/testing/structure, following mission-interpreter's shape
  README.md                — run instructions (WSL command, firewall rule, LAN URL)
  research/2026-11-16-rastercharts-all-terrains-recon.md   — already present (this branch)
  src/raster_chart_viewer/
    __main__.py             — CLI entry point: --dcs-install, --host, --port, --cache-dir, --cache-cap-bytes
    tilename.py              — the universal regex (§ below), TileKey dataclass
    discovery.py             — walks Mods/terrains/*/RasterCharts/, builds one TerrainIndex per
                                terrain: single-zip reader for 4 of 5 terrains, Caucasus's
                                zip-per-sheet reader as the stated special case
    mosaic.py                — sheet/level -> global tile-grid coordinate math (§ below); one
                                MosaicGrid per (terrain, tier) built from the TileKeys actually
                                found, so sparse/partial coverage is structural, not an error path
    ddsmip.py                — mip-offset formula above + Image.frombytes(..., "bcn", 3) decode
                                of one specific mip from one entry's already-inflated bytes
    cache.py                 — disk cache: per-tile-mip "ingredient" entries (written once per
                                inflate) and per-request composed-tile entries, one shared
                                size cap, LRU-by-mtime eviction
    warmup.py                — background thread, started at server startup: for each discovered
                                (terrain, tier), inflate every entry once but keep only its two or
                                three smallest mips
    server.py                — ThreadingHTTPServer: GET /terrains, GET /terrains/<t>/tiers,
                                GET /tile/<terrain>/<tier>/<level>/<x>/<y>.jpg, static file serving
  static/
    index.html                — OpenSeadragon page: terrain picker, tier picker, custom TileSource
    openseadragon/             — vendored release (JS, LICENSE — BSD-3)
  tests/
    fixtures/synthetic_dds.py  — Pillow-built multi-mip DDS fixture builder (method above)
    fixtures/fake_terrain_trees.py — temp dirs mimicking both layouts, incl. a sparse sheet and
                                a Caucasus-style scale-subfolder tree
    test_tilename.py, test_discovery.py, test_mosaic.py, test_ddsmip.py, test_cache.py, test_server.py
```

No change to any existing file outside `raster-chart-viewer/` (MI-B4.md already links this plan).

### The universal filename grammar and tile-grid math

**Regex** (research note §B, matches 100% of entries on every terrain, case-insensitive):

```
^(?:(\d+)m_?)?([a-z]+)(-?\d+)_x(\d+)_z(\d+)\.tif\.dds$
```
groups: `scale` (optional — see U2), `sheet`, `level` (signed int), `x`, `z` (tile-local, 0–7).

**Within a sheet** (research note §E, measured on Syria, both tiers): `z` is the column (increases
east), `x` is the row (increases south). So, in image pixel space with the conventional top-left
origin: `pixel_x_in_sheet = z * 1024`, `pixel_y_in_sheet = x * 1024`.

**Between sheets, per (terrain, tier)**: the level is the sheet's column, increasing east; the
sheet letters are a signed row index increasing **north** (`ab=+1, aa=0, xab=-1, xac=-2, …` — `x`
means minus, the second letter is the magnitude). At discovery time, scan every `TileKey` found for
that tier and take `min_level`/`max_row_index` actually present (never assume a fixed sheet count):

```
sheet_col      = level - min_level_present
sheet_row      = max_row_index_present - row_index(sheet_letters)   # north-is-up: highest row index -> smallest pixel y
pixel_x_global = sheet_col * 8192 + z * 1024   (+ in-tile x)
pixel_y_global = sheet_row * 8192 + x * 1024   (+ in-tile y)
```

Each sheet cell is always treated as a full 8×8 (8192×8192 px) block regardless of how many of its
64 tiles actually exist — missing tiles render blank. This is the one test that pins the convention
(`test_mosaic.py`, built from the research note's exact Syria 32m sheet set
`{aa,ab,xab,xac} × {-2,-1,00,01}`) — any future change to this formula must fail that test first.

### Mapping OpenSeadragon levels to source tiles and mipmaps

This is the part that makes "every zoom level touches each zip entry at most once" literal, not
just descriptive:

- Declare OpenSeadragon's tile size as **1024px** — the native tile size — so full-zoom tiles need
  no resampling.
- `maxLevel = ceil(log2(max(grid_tiles_wide, grid_tiles_tall)))`, computed per (terrain, tier) from
  the discovered grid's tile-cell extent (not pixel extent).
- For a request at OpenSeadragon level `ℓ`, tile `(vx, vy)`: let `k = maxLevel - ℓ` (how many
  doublings out from full res) and `mip = min(k, 10)` (defensive cap; `k` never exceeds 10 for any
  discovered terrain here — the largest grid, Afghanistan 32m, is 48×64 tiles, needing `k ≤ 6`).
  The native tiles this view tile covers are the `2^k × 2^k` block starting at
  `(vx * 2^k, vy * 2^k)` in the global tile-grid coordinate from `mosaic.py`.
- Each covered native tile contributes its mip-`k` image (size `1024 / 2^k` px — exactly the slot
  size, so no further resizing), pasted into its position in the output canvas. A native tile with
  no entry on disk (sparse sheet, partial coverage) leaves that slot blank. The composed canvas is
  JPEG-encoded and returned.
- At `k=0` (full res) this degenerates to: one native tile, one mip (the base image), one output
  tile — the simplest and most common case stays a single read + single decode.

### Cache: two kinds of entry, one cap

- **Ingredient cache** — `<terrain>/<tier>/<sheet><level>_x<X>_z<Z>/mip<N>.png`, written the first
  time any request causes that zip entry to be inflated, for **every** mip it yields in one write
  (the inflate-once policy MI-B4 Stage 5 asks for — a 1.4 MB deflated entry is never opened twice).
  Lossless PNG, not JPEG, so repeated recomposition never compounds lossy artifacts.
- **Composed-tile cache** — `<terrain>/<tier>/<ℓ>/<vx>_<vy>.jpg`, the literal HTTP response bytes,
  written once per distinct view tile ever requested.
- **One shared cap, one constant with a stated default**: `CACHE_MAX_BYTES = 2_000_000_000` (2 GB)
  — comfortably covers a fully-warmed ingredient cache for the largest terrain (Afghanistan, 3072
  entries; "about a third of the base image" per entry across all mips, per MI-B4 Stage 5, is on
  the order of a few hundred MB) plus composed tiles for ordinary browsing, while staying a trivial
  slice of disk. Swept LRU-by-mtime at startup and whenever a write pushes the folder over the cap.
  Not behaviour-affecting in the project's tuning sense (it changes nothing Petrovich does), so it
  stays a plain constant with a comment, not routed through `body-layer`'s tuning mechanism, which
  does not exist outside `body-layer` anyway.

### Mitigating the slow first fully-zoomed-out view

Chosen mitigation: **a background warm-up thread at server startup**, one per discovered
`(terrain, tier)`, that inflates every entry once and writes only its two or three smallest mips to
the ingredient cache (tens of KB total even for Afghanistan's 3072 entries — the expensive part,
inflating the ~1.4 MB deflated entry, is paid once regardless of which mip is kept). The server
starts accepting requests immediately; warm-up fills in behind it. If a real visitor's first
zoomed-out request beats warm-up for that tier, it simply pays the cost once itself (same as
today, just not guaranteed pre-paid) — no new request/response protocol, no polling, no change to
`server.py`'s handler shape. Rejected: doing this synchronously in the request path risks a
multi-second block on `ThreadingHTTPServer`'s single-threaded-per-request-but-shared-process
decode step; a "not ready, poll me" response protocol is real complexity for a one-time, one-tier,
cached-forever-after cost. `ThreadingHTTPServer` (already chosen, MI-B4's component table) means a
slow zoomed-out request never blocks other concurrent tile requests either way.

### Caucasus — the special case

`discovery.py` detects the layout at the terrain level: no root `rasterCharts.zip` → look for
`RasterCharts/{0.25M,0.5M,1M,2M,5M}/*.zip`. Each such zip is always exactly one sheet (research
note §D); the scale tier and sheet come from the zip's **inner entry names** via the same universal
regex, never from the zip's own filename (confirmed inconsistent in case/underscore). Reading one
zip's `namelist()` to find its sheet/level costs nothing (no decompression); discovery opens all 83
Caucasus zips once at startup to build the index, same cost class as listing 83 files.

### Offline test strategy

- `synthetic_dds.py` builds a multi-mip DXT5 DDS exactly as measured above: per-mip
  `Image.save(..., pixel_format="DXT5")`, header stripped, concatenated, one hand-built combined
  header. Parametrized by base size and mip count so tests can use small (e.g. 64×64) fixtures —
  the byte-offset formula is scale-invariant, no need for slow 1024×1024 fixtures in most tests.
- `fake_terrain_trees.py` builds temp directory trees for both layouts: a single-zip terrain with a
  sparse sheet (missing tiles, to prove blank-render-not-error), and a Caucasus-style
  scale-subfolder tree with a couple of per-sheet zips.
- No live DCS, no network, no real `rasterCharts.zip` anywhere in the test suite — mirrors
  `aircraft-layer`'s "fixture-based unit tests, no live DCS needed" pattern for everything except
  the one live check (Stage 7).

### Port and firewall

Checked every `DEFAULT_PORT` in the repo: aircraft-layer owns 7790–7793 and 7795–7799 (7794 retired,
not reused — a freed number reused later reads as confusing, not careful), world-model's API is
7792 (collision already covered by aircraft-layer's own file, not this plan's problem), brain-layer
7796, audio-adapter 7795. **Chosen: 7800** — one past the aircraft-layer family, unused anywhere in
the repo. Firewall rule, same shape as aircraft-layer's:

```
netsh advfirewall firewall add rule name="raster-chart-viewer" dir=in action=allow protocol=TCP localport=7800
```

### Implementation Plan

1. **Discovery + filename parsing + mosaic grid math** (`tilename.py`, `discovery.py`, `mosaic.py`).
   Pure functions, no Pillow/network involved. Acceptance: unit tests build both layouts from fake
   trees and confirm the Syria sheet-mosaic convention (pinned test) plus a sparse-sheet case
   produces the right grid with blank gaps, not an exception.
2. **DDS mip decode** (`ddsmip.py`) + the synthetic-fixture builder. Acceptance: decoding any mip
   of a synthetic multi-mip fixture matches an independently-computed downsample of the base image
   (MAD-style tolerance, same check the research note used on real data).
3. **Cache + tile composition**, wiring 1+2 together with no real zip needed yet (fake trees +
   synthetic DDS). Acceptance: a counter on the fake zip's "open entry" call proves each entry is
   read at most once across several overlapping requests at different zoom levels; writing past
   the configured cap evicts the oldest file first.
4. **HTTP server** (`server.py`, `__main__.py`): tile endpoint, terrain/tier listing, static
   serving. Acceptance: a real server instance on an OS-assigned port (mirrors
   `aircraft-layer/tests/test_api.py`) answers a tile request against a fake terrain tree with
   valid JPEG bytes, and a listing request names every discovered fake terrain/tier.
5. **Viewer page**: vendor OpenSeadragon + its `LICENSE`, write `index.html` with a custom
   TileSource against this server's endpoints, terrain/tier pickers. No new Python. Acceptance:
   opened locally against the Stage 4 test server (or a quick local run), the page pans and zooms a
   fake-tree mosaic without console errors — a one-time manual browser check, not an automated test
   (consistent with this project's js-light posture).
6. **Background warm-up** (`warmup.py`). Acceptance: against a fake tree, warm-up completes without
   error and logs per-terrain/tier completion; a request issued after warm-up for the smallest mip
   of a warmed tile does not re-open the fake zip (same counter technique as Stage 3).
7. **Live check, Windows machine, from WSL bash** — closes the loop this plan cannot close from a
   fixture:
   - One-time setup: create a Windows-side Python venv (`python.exe -m venv raster-chart-viewer\.venv-win`),
     `pip install pillow` into it (Windows `python.exe` is 3.14.7 with no Pillow — confirmed in the
     research note).
   - Run from WSL bash: `cd /mnt/c/<path>/raster-chart-viewer && .venv-win/Scripts/python.exe -m raster_chart_viewer --dcs-install "F:\Games\DCS World"`.
   - One-time firewall rule above.
   - From a LAN tablet/phone: open `http://<windows-box-lan-ip>:7800/`, pan/zoom **Syria** (both
     tiers, 32m and 64m) and **Caucasus** (the special case) and confirm each mosaic looks
     continuous, not scrambled — this is what settles U3. Confirm the first fully-zoomed-out view
     after warm-up is fast, and that pausing/closing the mission (no DCS session needed at all,
     since this reads only installed files) doesn't matter either way.

### Risks & Unknowns

- **The Syria sheet-mosaic convention is unverified on any other terrain** (research note, "Not
  tested"). Mitigated by Stage 7's visual check, not by an automated cross-terrain edge-match —
  see U3.
- **Afghanistan's full-tier warm-up cost is estimated, not measured** — the research note only
  timed Syria's 1024-entry 32m tier (16.1 s over the slower WSL bridge). Afghanistan is 3× the
  entries; native Windows I/O in Stage 7 should beat the WSL-bridge number, but by how much is
  unmeasured. Low risk: warm-up is background and one-time per tier, and the composed-tile and
  ingredient caches persist across restarts.
- **No index file for either `.sup5` or the zip itself** (research note §D) — discovery always
  costs a full directory/zip-namelist walk; cheap at the sizes measured (largest is 83 zips for
  Caucasus) but would need rethinking if a future terrain's RasterCharts were far larger.
- **OpenSeadragon vendoring**: pin an exact release version (not "latest") so a later repo clone
  gets the same vendored behaviour; the Implementer should record the exact version and its BSD-3
  `LICENSE` file path in `raster-chart-viewer/CLAUDE.md`.

### Decisions Requiring User Input

- **U1: Where the service process runs.** Two options: (a) a Windows-side Python venv with Pillow
  installed, launched via WSL bash running `python.exe` (follows `aircraft-layer/WORKFLOW.md`'s
  precedent exactly — binds the Windows interface, needs one firewall rule, keeps zip reads on
  native Windows I/O rather than WSL's slower `/mnt/f` 9P bridge); (b) a native WSL2 Linux process
  with `networkingMode=mirrored` or a `netsh portproxy`, reading the zip across `/mnt/f`.
  **Recommend (a)** — it is the only option with a working precedent already written down and
  measured in this repo (`WORKFLOW.md` already judged the networking configuration in (b) "not
  worth it" for aircraft-layer's own LAN server, for the same reason), and it avoids the slower
  bridge for exactly the operation (bulk zip inflate) this feature's one slow path depends on.
  **What the user has to do once:** create a Windows-side venv and `pip install pillow` into it —
  this project has never needed a third-party dependency on the Windows side before, so there is no
  existing setup to reuse.

- **U2: Mariana's 62 no-scale-prefix tiles.** They parse fine (sheet/level/x/z all present, only
  `scale` is absent) and their sheet/level can be placed in the grid with the exact same math as
  every other tile — the metres-per-pixel scale isn't needed for grid placement, only for
  georeferencing, which is out of scope. **Recommend: expose them as their own tier, labelled
  "unscaled" in the picker**, rather than dropping them — same code path, no extra complexity, and
  it is more faithful to "any terrain folder that is on disk can be opened" than silently discarding
  4% of one terrain's tiles. Flagged as a user decision because it is a visible product choice
  (what appears in the tier picker), not an implementation detail.

- **U3: What happens if Stage 7's live check finds the sheet-mosaic convention wrong on a terrain
  other than Syria** (a visibly scrambled, non-contiguous mosaic). **Recommend: ship anyway for the
  terrains that render correctly, file a follow-on backlog item for the terrain(s) that don't**,
  rather than blocking the whole feature on a second from-scratch edge-matching recon pass like the
  one the research note ran for Syria. This is a product call about acceptable partial coverage on
  a first cut, not something to decide silently either way.
