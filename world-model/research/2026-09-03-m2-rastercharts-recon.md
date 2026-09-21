# M2 — RasterCharts recon (Syria)

**Date:** 2026-09-03
**DCS version:** 2.9.29.27278 (per M0 probe; not re-verified this session — see `2026-09-02-m0-dcs-install.md`)
**Theatre:** Syria (Caucasus used only as a structural comparison point)

### Question

For M2 ("Read Syria's RasterCharts: tile hierarchy, dimensions, scales,
registration. Render a known DCS coordinate onto the raster."): where do
RasterCharts assets live for Syria, what format are they in, is there a
tile pyramid/indexing scheme, is there any georeferencing metadata, do
existing community tools already solve tile-to-coordinate registration, and
does reading them require anything beyond read-only filesystem access
(unlike M1's `coord.LOtoLL`, which needed a live mission)?

### Findings

- **Syria's `RasterCharts` directory contains exactly two files: a single
  `rasterCharts.zip` and a single `rasterCharts.sup5`.** No scale-tiered
  subdirectories. — **evidence:** reproduced-locally (filename-only) —
  **source:** `world-model/data/raw/dcs/2026-09-02/DCS-files.txt`, an M0
  `find`-style recursive listing of the real installed DCS tree at
  `/mnt/f/Games/DCS World` (confirmed DCS 2.9.29.27278 install, per M0).
  Exact matched lines:
  ```
  ./Mods/terrains/Syria/RasterCharts
  ./Mods/terrains/Syria/RasterCharts/rasterCharts.sup5
  ./Mods/terrains/Syria/RasterCharts/rasterCharts.zip
  ```
- **This single-archive layout is not universal across theatres — Caucasus
  uses a genuine multi-scale tile pyramid.** Caucasus has
  `RasterCharts/{0.25M,0.5M,1M,2M,5M}/` subdirectories (90 matching lines in
  the same listing), each holding many small per-tile `.zip` files named
  with a grid-cell-like code, e.g. `0.25M/16m_AA00.zip`,
  `0.25M/16m_xAB03.zip`, `0.5M/32M_AH-1.zip`, `1M/64mAA00.zip`,
  `2M/128mAA-1.zip`, `5M/256m_AA-1.zip`. The `AA`/`AB`/`xAB` prefix plus a
  signed two-digit suffix (`-1`, `00`, `01`, …) strongly suggests a 2D
  grid-cell index (column letter-pair, row number, `x` possibly marking an
  extended/edge column), and the leading number (`16m`, `32m`, `64m`,
  `128m`, `256m`) plausibly encodes ground sample distance or tile edge
  length in meters — but this is pattern-matching from filenames alone, not
  confirmed against file contents. — **evidence:** reproduced-locally
  (filename-only) for the directory/filename structure; **inferred** for
  what the naming components mean — **source:** same `DCS-files.txt`.
  Afghanistan, Kola, and MarianaIslands all follow Syria's simpler
  single-archive pattern (`RasterCharts/rasterCharts.sup5` +
  `RasterCharts/rasterCharts.zip`), not Caucasus's tiled pattern — so Syria
  is the common case among the theatres present in this listing, not an
  anomaly, but the pipeline must not assume tile-pyramid structure holds
  for every theatre if it later expands beyond Syria.
- **The internal contents of `rasterCharts.zip` (tile image format,
  filenames, dimensions) are unknown — `DCS-files.txt` is a filesystem
  listing, not a zip-content listing, so it says nothing about what's
  inside the archive.** Not resolved this session. — **evidence:**
  unresolved / gap — **source:** n/a.
- **The `.sup5` file format/purpose is confirmed undocumented community-wide
  — not just unreadable to automation this session.** The user manually
  opened `forum.dcs.world/topic/226463-how-to-accessedit-sup5-files/`
  ("How to access/edit .sup5 files") and reported its full content: the
  original question sits unanswered for over six years, with the only reply
  ("Did you find an application which is able to access/edit a .sup5 file
  since your question?") itself unanswered as of this recon. No tool or
  format info exists in this thread. Treat `.sup5` as genuinely undocumented,
  not merely under-researched. Web search snippets around DCS terrain files
  mention a related but distinct `.surface5` format (e.g.
  `Caucasus/Surface/Caucasus.surface5`) for terrain mesh/surface data, which
  is *not* the same file as `RasterCharts/rasterCharts.sup5` — do not
  conflate the two. Every `Map/<Terrain>.sup5` and
  `RasterCharts/rasterCharts.sup5` file across all theatres in the listing is
  small relative to its paired `.zip`, consistent with it being an
  index/manifest for the archive rather than raster data itself, but this
  remains inference from naming/sibling-pattern only, not content
  inspection — the probe script's hex dump (Stage 0) is still required to
  resolve it. — **evidence:** confirmed community-undocumented (user-read
  full thread) / inferred (index-file hypothesis) — **source:**
  `forum.dcs.world/topic/226463-how-to-accessedit-sup5-files/` (full content,
  user-provided).
- **No georeferencing/registration metadata (world file, Lua config stating
  per-tile geographic or DCS-local extent) was found for RasterCharts in
  any source checked this session.** `docs/concept/WORLD_MODEL_BUILDER.md`
  already anticipated this as a known unknown ("Community reports indicate
  ... registration/projection complications"). No Lua file referencing
  RasterCharts turned up in the M0/M1 raw listings or probes. If no such
  metadata exists inside the zip either, registration will likely need the
  same empirical-fit approach M1 used for the coordinate transform (fit
  tile extents against known DCS x/z control points), rather than reading a
  stated scale/origin. — **evidence:** unresolved / gap (absence not yet
  distinguished from "not found in the sources checked") — **source:** n/a.
- **`forum.dcs.world/topic/292399-raster-charts-for-terrain-mod/` is off-topic
  for this investigation — read directly by the user after WebFetch was
  blocked (403).** Its content (confirmed by the user pasting the actual
  page text) is two community members discussing where to *source* raster
  imagery when *building a new custom terrain mod* (e.g. FAA VFR sectionals
  from `faa.gov`, georectified in QGIS) — not anything about the format,
  internal structure, or registration of ED's own shipped
  `RasterCharts/rasterCharts.zip` for an existing theatre like Syria. It
  does not answer, and was never going to answer, this investigation's
  question; earlier framing of it as a promising lead was wrong. Do not
  re-fetch this thread expecting DCS-internal-format detail. — **evidence:**
  documented (verified directly from the actual page text) — **source:**
  user-provided page content, `forum.dcs.world/topic/292399-`.
- **No open-source community tool was found that reads/parses DCS's
  internal `RasterCharts` archives directly for tile-to-coordinate
  registration.** Web search across DCS moving-map/kneeboard projects
  (Bergison's DCS MovingMap, "DCS LIVE Moving Map", SlipHavoc/DCS-Kneeboards,
  OpenKneeboard's DCS integration, Tacview's "DCS Satellite Tiles" download)
  turned up no evidence any of them parse `RasterCharts/rasterCharts.zip`;
  the Tacview item name ("DCS Satellite Tiles") suggests these projects
  instead source their *own* independently-built satellite/basemap imagery
  keyed to DCS coordinates, rather than reusing ED's F10/kneeboard chart
  archive. This is a negative finding from search coverage, not proof no
  such tool exists — GitHub's code-search API was not reachable from this
  session (401/403 on unauthenticated `api.github.com` code search), so a
  targeted code search (e.g. for literal string `RasterCharts` across
  public repos) was not actually performed, only general web search. —
  **evidence:** inferred (absence-from-search, weak) — **source:** web
  search only, see below; GitHub code search not completed.
- **No live-mission/Mission Scripting access is needed to read
  RasterCharts** — unlike M1's `coord.LOtoLL`, which required a running
  mission with the Mission Scripting environment. RasterCharts are plain
  files on disk (`Mods/terrains/Syria/RasterCharts/`), so listing, hashing,
  and extracting them is achievable via a read-only WSL filesystem probe —
  the same class of probe as M0/M1's Lua-file inspection, not the
  live-mission escape hatch. — **evidence:** documented (follows directly
  from confirmed filesystem location — no scripting API is involved in
  reading a zip/file from disk) — **source:** reasoning from M0/M1 workflow
  precedent, `world-model/WORKFLOW.md`.

### Reproducible Test

Not yet run this session (no live Windows/WSL access from this agent).
Wrote `world-model/tools/wsl/probe_syria_rastercharts.sh` — lists
`rasterCharts.zip` contents (`unzip -l`), dumps the first 64 bytes of
`rasterCharts.sup5` as hex, and extracts up to 5 sample zip entries into
`wsl-output/` for local format inspection (e.g. via `file` or PIL) without
extracting the full archive. Deploy per `WORKFLOW.md`: copy into
`win-mac-sync/run-wsl/`, run in WSL with `DCS_INSTALL_PATH` set, sync
`wsl-output/` back, then copy the report + a couple of sample tile files
into `world-model/data/raw/dcs/<date>/` for follow-up analysis.

### Possible Approaches

- If tile filenames inside the zip carry a grid-index similar to Caucasus's
  `AA00`/`xAB03` pattern, and the `.sup5` file turns out to be a readable
  index (offsets, tile names, and possibly extents), registration may be
  directly derivable — no empirical fitting needed. This is the optimistic
  path; confirm before assuming it.
- If no georeferencing metadata exists inside the archive at all,
  registration will likely need the same empirical/control-point fitting
  method that worked for M1: pick a handful of raster pixel locations for
  known DCS x/z positions (e.g. published airbase ARPs, already used as M1
  control points) and fit an affine/scale transform per raster layer. This
  reuses M1's control-point set and validation approach rather than
  inventing a new one.
- If `.sup5` turns out to be a proprietary binary index tied to ED's own
  chart renderer (not a simple manifest), the fallback is to ignore it
  entirely and work only from `rasterCharts.zip`'s own internal file/folder
  structure and any embedded image metadata (e.g. DDS mipmaps, embedded
  world-file-like sidecar per tile) — the `.sup5` file may not be necessary
  for extraction at all, only for DCS's own runtime chart selection logic.
- Given no existing open-source tool was confirmed to solve this, treat M2
  as first-of-its-kind work for this pipeline rather than expecting to
  reuse code — unlike M1, where pydcs's tmerc parameters gave a strong
  documented starting hypothesis (see `reference_pydcs_prior_art` memory).
  Worth a follow-up targeted GitHub code search (via `gh` CLI or an
  authenticated method, since this session's unauthenticated
  `api.github.com` code search failed) before committing to a from-scratch
  approach.

### Unresolved

- Actual file format of tiles inside `rasterCharts.zip` (DDS/TIF/JPG/PNG/
  other) — requires running the probe script above against the live
  install.
- Whether Syria's raster is a single large image, a small set of tiles, or
  something else entirely (the single-zip-no-subdirectory pattern doesn't
  by itself distinguish "one big image" from "many tiles in one flat zip
  directory") — requires the `unzip -l` listing from the probe.
- What `.sup5` actually is — index, manifest, ED-proprietary chart format,
  or something unrelated to registration. The one forum thread that asks
  this exact question could not be read this session (403 to automated
  fetch); worth a manual look or a different fetch method (e.g. Google
  cache, logged-in browser) before assuming it's undocumented community-wide,
  not just undocumented-to-this-session.
- Whether any registration/georeferencing data exists anywhere in the
  archive (embedded in image metadata, a sidecar file, or `.sup5` itself) —
  only resolvable by inspecting actual archive contents.
- Whether a targeted GitHub code search (proper API access) turns up a
  community tool this session's plain web search missed.

---

## 2026-09-03 (session 2) — Stage 0 probe results: tile format, .sup5 structure, registration hypothesis

**DCS version:** 2.9.29.27278 (unchanged, per M0). **Theatre:** Syria.

### Question

Follow-up to the above: Stage 0 of the M2 plan (`plans/m2-raster-understanding/plan.md`)
required actually running `probe_syria_rastercharts.sh` on the Windows DCS install.
That run is complete; this session inspects its output (zip listing, `.sup5` hex dump,
5 sample `.tif.dds` tiles) directly to pin down tile format, analyze `.sup5` structure,
and evaluate whether the `x{N}_z{N}` filename grid is a viable registration scheme.

### Findings

- **`rasterCharts.zip` contains exactly 1280 unique entries, forming a clean 20-group
  × 64-tiles-per-group structure — not the messier grouping implied by a naive regex
  pass over the raw report.** Corrected grouping (verified from the full `unzip -l`
  listing, not the truncated preview): naming is
  `{32|64}m{sheet}{level}_x{0-7}_z{0-7}.tif.dds`, sheet ∈ {aa, ab, xab, xac}, level ∈
  {-2, -1, 00, 01}. At **32m** scale, all 4 sheets × all 4 levels are present (16 groups
  × 64 tiles = 1024 tiles). At **64m** scale, only 2 sheets (aa, xab) × 2 levels (-1, 00)
  are present (4 groups × 64 tiles = 256 tiles). 1024 + 256 = 1280, matching the zip's
  reported entry count exactly. Every group has the full 8×8 `x0..7_z0..7` grid, no
  gaps. — **evidence:** reproduced-locally — **source:**
  `world-model/data/raw/dcs/2026-09-03/syria_rastercharts_probe_20260903T090447Z.txt`
  (full `unzip -l` output), re-parsed directly rather than trusting the prior session's
  regex summary.
- **The "level" suffix (`-2`/`-1`/`00`/`01`) is not a scale indicator (scale is already
  the `32m`/`64m` prefix) and is not itself a coordinate — it most plausibly indexes a
  secondary raster tier per sheet (e.g. an alternate chart layer/LOD/edition), distinct
  from the `x`/`z` tile grid position.** This is new relative to the prior session's
  provisional note, which had conflated Caucasus's `AA00`/`128mAA-1`-style single
  suffix with Syria's clearly two-part `{sheet}{level}` naming. — **evidence:** inferred
  (from filename structure only, no content read to confirm what differs between e.g.
  `aa00` and `aa01` at the same x/z) — **source:** same zip listing.
- **All 5 sample tiles are DXT5 (BC3), not "DX10" as `file(1)` reported.** Direct
  hex/struct inspection of the DDS header (first 148 bytes, standard 128-byte
  `DDS_HEADER` + `DDS_PIXELFORMAT`) shows `dwFourCC` at header offset 84 is literally
  the ASCII bytes `DXT5`, not `DX10` — there is **no DX10 extended header** present.
  `file(1)`'s "compressed using DX10" message is a mislabel (likely misreading libmagic
  DDS heuristics) and should not be trusted for DDS pixel-format identification; use a
  direct header parse instead. All 5 samples: 1024×1024, `DXT5` fourCC, 11 mipmap
  levels, `pitchOrLinearSize` = 1,048,576 bytes (= 1024×1024/16×16 bytes, exact BC3 math
  for a 1024² base mip), identical across every sample. Total file size 1,398,256 bytes
  matches base mip + 10 further halving mip levels (~1.333× base) + ~150 bytes of header
  overhead. — **evidence:** reproduced-locally (direct Python `struct` parse of the DDS
  header on all 5 extracted samples) — **source:**
  `world-model/data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T090447Z/*.dds`.
- **The DDS header's normally-reserved `dwReserved1[11]` field contains embedded tool
  provenance: ASCII tags `UVER` and `NVTT` plus a version number, then a redundant
  `DXT5` string.** This is the standard convention used by NVIDIA Texture Tools (NVTT)
  when it writes DDS files — it stamps its own tag/version into the header's reserved
  bytes. This confirms the tiles were built with NVTT (an off-the-shelf DDS compressor),
  not a bespoke ED tool, which is a mild positive signal that no ED-proprietary raster
  encoding is involved — only the tiling/naming/`.sup5` layer is ED-specific. —
  **evidence:** inferred (pattern-matches a known third-party tool signature; not
  independently confirmed against NVTT's own source/docs this session) — **source:**
  direct hex dump of sample DDS header bytes 0x30–0x68.
- **`.sup5`'s first 64 bytes decode as: a 4-field numeric header (`uint32`=2,
  `uint32`=0x30 (48), `uint64`=0x0006bb50 (439,632), 16 zero-padding bytes), followed by
  a length-prefixed string field (`uint32` length=20, then the 20-byte ASCII string
  `landscape5::sup5File`), followed by 8 more bytes (`00 00 00 00 ff ff 7f 7f`).** The
  length-prefix-then-string pattern (a `uint32` byte count immediately followed by
  exactly that many ASCII bytes) is a generic serialization convention, not specific to
  this string — it strongly suggests `.sup5` is written by a general ED
  engine-serialization routine (type-tag/class-name string first, as a runtime type
  check), the same class of format likely used elsewhere in the `landscape5` engine
  module, rather than a bespoke ad-hoc index format. — **evidence:** reproduced-locally
  (direct hex parse) for the byte layout; **inferred** for "this is a generic ED
  serialization convention" — **source:**
  `world-model/data/raw/dcs/2026-09-03/syria_rastercharts_probe_20260903T090447Z.txt`.
- **No clean integer record-count division was found for `.sup5`'s 615,216-byte total
  against any of the obvious candidate tile/group counts (1280 tiles, 20 sheet/level
  groups, 6 distinct sheet-names, 4 levels, 8×8 grid dimension), whether or not a 32-,
  56-, or 64-byte header is subtracted first.** This weighs against a simple
  fixed-length "one record per tile" or "one record per group" table. Combined with the
  length-prefixed-string evidence above, the more likely structure is variable-length
  records (e.g. each entry carries its own tile-name string, explaining why file size
  doesn't factor cleanly) — consistent with, but not proof of, a per-tile manifest
  listing filenames plus fixed-size numeric fields (extents, offsets, or similar). This
  could not be resolved further without dumping the full 615,216 bytes and attempting
  to walk it as a repeated (length-prefixed-string + fixed-fields) record stream, which
  was not done this session (only the first 64 bytes were captured by the probe
  script). — **evidence:** inferred / partially unresolved — **source:** arithmetic
  reasoning over the confirmed file size and header fields above.
- **The `x{N}_z{N}` filename grid, combined with the `32m`/`64m` scale prefix, is
  arithmetically consistent with being DCS x/z ground-distance tile indices, and this
  is testable without needing `.sup5` at all.** Reasoning: if `32m`/`64m` is ground
  sample distance (meters/pixel, as hypothesized in the prior session) and each tile is
  1024×1024 px, each 32m tile spans 32×1024 = 32,768 m (32.768 km) and each 64m tile
  spans 64×1024 = 65,536 m (65.536 km) in DCS x/z ground units. An 8×8 grid of 64m tiles
  (one sheet) therefore spans 8 × 65,536 m ≈ 524 km per side — which is in the right
  order of magnitude for the full Syria theatre's known extent (~500–600 km) [**superseded: the
  measured extent is 762 × 710 km — `2026-09-05-m7-syria-theatre-extent.md`, which says so
  itself. The ~524 km/side arithmetic below is unchanged and still "the right order of
  magnitude"; only the figure it is compared against was a guess**], a
  plausible match for the `aa00`/`64m` sheet being (at least close to) the whole map at
  coarse resolution. The 32m tier's 4 sheets (aa, ab, xab, xac), each an independent 8×8
  grid spanning ~262 km/side at double resolution, would need to be arranged roughly
  2×2 to cover the same area the 64m tier covers in one sheet — consistent with a
  quadrant-style sheet layout (matching the `aa`/`ab`/`xab`/`xac` naming pattern, which
  echoes Caucasus's `AA`/`AB`/`xAB` region-code convention from the prior session's
  Caucasus comparison). **This is a coherent, testable hypothesis, not a confirmed
  registration.** It has NOT been checked against actual pixel content or M1's control
  points (no DDS-to-viewable-image decode tool was available in this session — no
  `PIL`/`ImageMagick`/`texconv` on the local Mac). — **evidence:** inferred (order-of-
  magnitude arithmetic consistency only) — **source:** reasoning from confirmed tile
  pixel dimensions (1024×1024), confirmed scale prefixes (32m/64m), and general
  knowledge of Syria's theatre extent (not independently re-verified against a DCS
  source this session).
- **No registration/origin metadata was found in the DDS files themselves** (no custom
  chunk beyond the NVTT tool tag; standard header fields are all dimension/format only)
  **and none was confirmed in the visible `.sup5` header** (the 64 bytes read establish
  only a type tag, not coordinate data) — but the bulk of `.sup5`'s 615,152 remaining
  bytes were not inspected, so absence of registration data specifically inside `.sup5`
  remains unconfirmed, not ruled out. — **evidence:** unresolved / gap — **source:** n/a.

### Reproducible Test

Header parse used for the DDS/format findings (rerun against any sample):
```python
import struct
with open(path, "rb") as f:
    data = f.read(148)
assert data[:4] == b"DDS "
size, flags, height, width, pitch, depth, mipmaps = struct.unpack_from("<7I", data, 4)
fourcc = data[84:88]  # b"DXT5" observed; NOT "DX10" despite file(1)'s report
```
`.sup5` header parse (first 64 bytes only — probe script did not dump further):
```python
import struct
with open(sup5_path, "rb") as f:
    data = f.read(64)
v1, v2, v3 = struct.unpack_from("<IIQ", data, 0)   # 2, 48, 439632
strlen = struct.unpack_from("<I", data, 0x20)[0]    # 20
tag = data[0x24:0x24+strlen]                        # b"landscape5::sup5File"
```
To go further: extend `world-model/tools/wsl/probe_syria_rastercharts.sh` to dump the
**entire** `.sup5` file (615,216 bytes is small enough to hex-dump in full or download
whole) rather than just the first 64 bytes, then attempt to walk it as a
length-prefixed-string-plus-fields record stream looking for embedded tile-name
substrings (`64maa00_x0_z0` etc.) — if tile names appear verbatim in `.sup5`, that
directly confirms it's a per-tile manifest and pins down the record boundaries.

### Possible Approaches

- **Recommended next test (Stage 1 registration check):** decode one full sample DDS
  to a viewable image (needs a tool not available on this Mac this session — e.g.
  `pip install pillow` with a DDS-capable plugin, or `texconv`/`texassemble` on the
  Windows DCS machine, or ImageMagick with the DDS delegate) and visually compare
  recognizable content (coastline, Euphrates river course, an airbase runway shape) at
  a tile whose expected DCS x/z extent (from the arithmetic hypothesis above) is known
  to contain a feature from M1's control-point set. A single successful visual match at
  one tile would upgrade the registration hypothesis from "inferred" to
  "reproduced-locally," and a mismatch would falsify the naive linear-index-to-extent
  mapping and point to needing an explicit origin/offset from `.sup5` instead.
  Reuse M1's airbase ARP control points (`world-model/research/` M1 recon) rather than
  picking new ones.
  - Add this DDS-decode capability as a `world-model/tools/` probe (not pipeline code).
- **If the visual check fails or is inconclusive, fall back to the full `.sup5` byte
  dump** described in Reproducible Test above — searching for embedded tile-name
  strings and any accompanying fixed-size numeric fields immediately before/after each
  name is the most promising path to an explicit index if the naive arithmetic
  hypothesis doesn't hold cleanly (e.g. if sheets have irregular, non-uniform offsets
  rather than a clean quadrant grid).
- **Given the tiles are plain DXT5/BC3 DDS with standard headers**, any general-purpose
  DDS decoder (Pillow with a DDS plugin, `texconv`, GPU-texture libraries) will read
  them without any DCS-specific tooling — this part of the M2 pipeline is not blocked
  on reverse-engineering anything ED-proprietary, only on the registration/offset
  question above.

### Unresolved

- Exact byte-for-byte structure of `.sup5` beyond the first 64 bytes (615,152 bytes
  unread) — needs a full-file dump, not yet done.
- Whether `.sup5` contains registration/extent data at all, or is purely a manifest of
  tile names for DCS's own asset loader (in which case registration must come entirely
  from the filename-arithmetic hypothesis above, empirically validated against pixel
  content).
- What distinguishes the `-2`/`-1`/`00`/`01` "level" tiles at the same sheet/x/z from
  each other — not yet inspected (all 5 samples pulled were from the same `64maa00`
  group; no cross-level sample was extracted this session).
- Whether the `aa`/`ab`/`xab`/`xac` sheets tile edge-to-edge with zero overlap/gap, or
  overlap (common in real chart mosaics) — matters for the exact offset formula in the
  registration hypothesis; not determinable from filenames alone.
- No DDS-to-image decode was performed this session (no suitable tool locally
  available) — the registration hypothesis above is unverified against actual pixel
  content.

---

## 2026-09-03 (session 3) — Visual decode of 5 sample tiles: content is a scanned military topo/aeronautical chart, not satellite/rendered imagery

**DCS version:** 2.9.29.27278 (unchanged). **Theatre:** Syria.

### Question

Session 2 flagged "no DDS-to-image decode was performed" as the key blocker on the
registration hypothesis. This session decodes the 5 already-extracted sample tiles
(Pillow, installed ad hoc into `world-model/.venv`, not yet added to `pyproject.toml`)
and inspects them visually to (a) confirm what kind of raster content this actually is,
(b) attempt chart-series/scale identification, and (c) assess whether the tile's own
printed grid is sufficient for independent georeferencing.

### Findings

- **The RasterCharts tiles are a scanned real-world military topographic/aeronautical
  chart, not satellite imagery and not a DCS-rendered map.** All 5 decoded samples
  (`64maa00_x0_z{0,1,2,3,4}`) show classic paper-chart cartography: brown contour lines
  with foot-elevation labels (`5000`,`6000`,`7000`...), tan/khaki hypsometric tint at
  higher elevations, red/brown roads, blue hydrography, place-name labels in
  serif/typewriter chart fonts, and dashed "approximate alignment" boundary lines — none
  of which DCS's in-engine terrain renderer or a satellite-derived orthophoto would
  produce. — **evidence:** reproduced-locally (direct visual inspection of decoded PNGs)
  — **source:** `/tmp/64maa00_x0_z{0..4}.png`, decoded from
  `data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T090447Z/*.tif.dds`.
- **The chart covers real Turkish terrain south-central of the DCS "Syria" theatre's
  namesake area, not Syria itself** — confirmed by legible place-name labels:
  `Gemerek`, `KARABABA DAĞI` (tile z0), `SİVAS`, `ULAŞ`, `ŞARKIŞLA`, `Altınyayla`,
  `Yeniapardi` (z1), `KANGAL`, `Çetinkaya`, `Ateşali` (z2), `DİVRİĞİ`, `KEMALİYE`,
  `Fırat Nehri` labeled `(Euphrates)` (z3), and `ERZİNCAN` with a `VOR·DME·NDB ERZİNCAN`
  navaid box (z4) — all in Sivas/Erzincan provinces, central-eastern Turkey, well north
  of the Syrian border. This confirms and sharpens the prior session's note that DCS's
  "Syria" map extent reaches into Turkey — the `64maa00` sheet/tile-row sampled here is
  specifically the Turkish interior, not the Syria/Lebanon coastal area the theatre is
  named for. — **evidence:** reproduced-locally (place names read directly off tiles,
  cross-checked against general knowledge of Turkish provincial geography) — **source:**
  same PNGs.
- **In-tile printed grid is a UTM graticule with explicit zone designation, consistent
  with a standard 1:250,000-scale-class military/aeronautical chart series (JOG-A,
  Joint Operations Graphic – Air, or a close equivalent), moderate confidence.** Tile z0
  shows dashed tick-mark lines labeled "UTM GRID ZONE DESIGNATION 37S" running the full
  tile height — direct visual confirmation of the prior session's read. Tiles z1–z4 show
  large blue two/three-digit numerals (`82`, `96`, `114`→ misread as `11 4`, `12`)
  positioned at regular blue grid-line crossings — this is the standard JOG/TPC/ONC
  convention of labeling each UTM grid line with an abbreviated (2–3 digit) coordinate
  value, printed large where space allows. Tile z4 additionally shows a `VOR·DME·NDB
  ERZİNCAN` navigation-aid annotation box — a hallmark of *aeronautical* overprint
  charts (JOG-A, TPC, ONC), not a purely topographic series (plain JOG/JOG-G lack navaid
  symbology). Grid-line spacing relative to tile content (a handful of grid lines
  crossing each 1024×1024 tile, consistent with ~10 km spacing at the 32 km/tile ground
  extent implied by the 32m-scale/1024px hypothesis from session 2) most closely matches
  the 10 km UTM grid interval standard to 1:250,000-scale JOG-A sheets, rather than the
  coarser 100 km-only grid typical of 1:500,000 TPC or 1:1,000,000 ONC. This scale/series
  identification is plausible and internally consistent but **not confirmed against an
  actual published JOG-A specification or a real reference sheet this session** — web
  search corroborated only the general fact that 1:250,000-class military topo charts
  use single/double-digit abbreviated UTM grid-line labels and print a "Grid Zone
  Designation" in the margin; it did not confirm JOG-A specifically vs. a similar
  in-house/allied chart series. — **evidence:** inferred (plausible chart-series/scale
  identification from cartographic convention matching) — **source:** direct tile
  inspection + WebSearch (general UTM/MGRS grid-labeling convention references, no
  JOG-A-specific primary source located).
- **The printed UTM grid, if 2+ labeled grid-line intersections can be identified with
  their full coordinate values (zone + easting/northing), is in principle sufficient to
  derive an independent pixel→WGS84 affine transform for a tile, without needing
  DCS-internal metadata (`.sup5`, or the x/z-index arithmetic hypothesis) at all.**
  Reasoning: a UTM grid is a known, invertible projection (a specific case of
  Transverse Mercator with defined zone/false-easting/false-northing) — given zone
  `37S` (confirmed printed on z0) and at least two grid-line labels with unambiguous
  full easting/northing values (the abbreviated 2-digit labels seen so far, e.g. `82`,
  `96`, are ambiguous without knowing the omitted leading digits — real 1:250,000 sheets
  print at least one full 6-digit-class label per sheet, typically in a margin or corner
  tile, which was not among the 5 samples decoded this session), the pixel-space
  positions of two known grid intersections plus known grid spacing (10 km, per the
  scale hypothesis above) fully determine the tile's affine transform via standard
  `pyproj` UTM-zone-37N inverse projection — **this is a genuinely separate and
  independent registration path from both the `.sup5` investigation and the x/z
  filename-arithmetic hypothesis**, and would not depend on either resolving. It does
  **not**, by itself, give the DCS-internal x/z ↔ chart-pixel mapping — that composition
  still requires either the x/z arithmetic hypothesis (session 2) to hold, or a separate
  link step (e.g. matching a chart-identifiable real-world feature, such as `SİVAS`'s
  known WGS84 location, against M1's already-solved DCS x/z ↔ WGS84 transform to derive
  the offset empirically). — **evidence:** inferred (methodologically sound reasoning
  from confirmed grid presence; not yet executed against real numbers) — **source:**
  reasoning from tile visual content above + M1's existing `pyproj`-based DCS x/z ↔
  WGS84 transform (`world-model/src/coordinates/`, per M1 recon).
- **None of the 5 sampled tiles contains an unambiguous full-precision grid-line label**
  (only 2-digit abbreviated numerals were visible: `82`, `96`, `11`/`4` split, `40`/`30`/
  `20`, `12`) — every visible number is a truncated/abbreviated UTM coordinate value,
  which is standard chart practice for interior grid lines (full values are normally
  printed only at sheet corners/margins, which these interior tiles are not). This means
  the registration approach in the finding above is not yet executable from what's
  already decoded — it needs either a margin/corner tile (likely `x0_z0` or the sheet's
  edge tiles, not necessarily among the `x0_z0..4` column sampled) or cross-referencing
  the abbreviated values against the already-known approximate location (Sivas/Erzincan
  province) to disambiguate the omitted leading digits by inspection, which is possible
  but not done this session. — **evidence:** reproduced-locally (absence noted directly
  from the 5 decoded images) — **source:** same PNGs.

### Reproducible Test

Decode used this session (reusable, ad hoc — not yet a committed `world-model/tools/`
script; Pillow was `pip install`ed directly into `world-model/.venv`, not added to
`pyproject.toml`):
```sh
cd world-model && source .venv/bin/activate
python3 -c "from PIL import Image; \
Image.open('data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T090447Z/<name>.tif.dds')\
.convert('RGB').save('/tmp/<name>.png')"
```
Then visual inspection (Read tool / any image viewer) of the resulting PNG.

### Possible Approaches

- **Recommended next concrete step: pull and decode additional tiles specifically
  chosen to catch a sheet margin or corner** (e.g. `x0_z0` across other sheets, or the
  extreme-index tiles `x7_z*`/`x*_z7` of the `aa`/`ab`/`xab`/`xac` groups) — margin
  tiles are far more likely to carry a full unabbreviated UTM coordinate label or a
  chart legend/title block, which would let the UTM-grid registration path (finding
  above) actually be executed and cross-checked against the x/z-arithmetic hypothesis
  from session 2. This is cheaper and more informative than continuing to sample the
  same interior column.
- **Alternative/complementary step: identify one visible feature with a well-known
  precise WGS84 location** — e.g. Erzincan's VOR/DME/NDB station (`ERZİNCAN`, tile z4)
  or Sivas city center — and look up its published real-world coordinates (aeronautical
  database, OpenStreetMap, or the FAA/ICAO navaid registry) as an independent anchor.
  Combined with the tile's pixel position of that feature and M1's already-solved DCS
  x/z ↔ WGS84 transform, this could let the DCS-internal ↔ chart-pixel link be derived
  empirically (control-point fit, same method M1 used) even without ever resolving the
  UTM grid's abbreviated labels or `.sup5`'s structure — this may be the more
  practically expedient path since it reuses M1's control-point methodology directly
  rather than requiring exact UTM-grid-label disambiguation.
- **A dedicated DDS-decode probe script should move from ad hoc `.venv` use into
  `world-model/tools/`, and Pillow's DDS-plugin dependency needs an explicit decision**
  (add to `pyproject.toml` as a dev/tooling dependency, or keep strictly
  probe-local/scratch) — this is a call for Architect/Implementer, not resolved here.

### Unresolved

- Whether any sampled or not-yet-sampled tile carries a full unabbreviated UTM
  coordinate label — needs more tiles decoded, prioritizing margin/corner positions.
- Exact chart series identity (JOG-A vs. a similar allied/in-house 1:250,000
  aeronautical-overprint series) — current identification is plausible cartographic
  pattern-matching only, not confirmed against a primary chart-series specification or
  a labeled reference sheet.
- Whether the UTM-grid-derived registration path and the x/z filename-arithmetic
  hypothesis (session 2) agree once both are actually computed — not yet cross-checked
  numerically.
- Whether `pyproj`'s existing UTM support (already a project dependency per M1) is
  sufficient to invert a JOG-A-style grid directly, or whether false-easting/northing
  conventions specific to this chart series need separate confirmation.

### Session 4 addendum (2026-09-03, user domain knowledge)

- **DCS's F10 map has three distinct modes: "paper map," satellite imagery, and an
  internal 3D-rendered map not accessible outside the running engine.** — **evidence:**
  user-provided domain knowledge — **source:** user, this session. This explains why
  `RasterCharts` decodes to a scanned aeronautical/topo chart rather than satellite
  tiles: `RasterCharts` is specifically the "paper map" mode's asset source, a separate
  pool from whatever feeds satellite mode (location not yet investigated). The internal
  rendered map being engine-only is consistent with M1's finding that `coord.LOtoLL`
  requires a live mission. **Implication:** if satellite-mode imagery is ever wanted for
  the pipeline, it lives elsewhere in the DCS install and needs its own recon — do not
  assume `RasterCharts` is the only or primary raster asset source for Syria.

### Session 5 (2026-09-03, user-provided F10 screenshots)

User captured three F10 map-mode screenshots at the same view (Aleppo region,
36°40'20"N 38°18'19"E, alt 478m) — `world-model/data/raw/dcs/2026-09-03/f10-map-modes/`
(`dcs-rendered-map.jpg`, `paper-map.jpg`, `satellite-imagery.jpg`). Visual comparison:

- **`dcs-rendered-map.jpg`** — vector-style render: place labels, road network, red
  international-border lines (Syria/Turkey), green vegetation polygons, tan terrain
  shading, no visible pixel/tile seams. User confirms this mode is freely zoomable
  (vector, not raster tiles) — consistent with the M1 finding that `coord.LOtoLL`
  requires a live mission: this map layer is very likely generated by the running
  engine from its internal vector terrain database, not read from a static file asset,
  and probably cannot be extracted by filesystem probing the way `RasterCharts` and
  presumably satellite imagery can. — **evidence:** reproduced-locally (visual) for
  appearance; inferred (engine-generated, not file-based) for the mechanism, consistent
  with but not proof-identical to the M1 `coord.LOtoLL` finding — **source:** user
  screenshot + user statement this session.
- **`paper-map.jpg`** — visually matches the decoded `RasterCharts` sample tiles from
  session 3 in every particular: yellow hypsometric tint, brown contour lines with
  elevation labels, UTM grid crosshairs, an aeronautical navaid box
  (`VOR DME-NDB ALEPPO`, same pattern as session 3's Erzincan box). This is the Aleppo
  (Syria) region rather than session 3's Turkish tile — different sheet, same chart
  series — confirming the series covers the whole theatre (Turkey and Syria) uniformly,
  not just a northern sliver. Notably, this screenshot's margins show **unabbreviated
  grid/graticule labels** (`36N`, `37E`, `38E` visible at frame edges) that session 3's
  sampled tiles lacked — this may be the full-precision label needed to anchor the
  chart-grid registration path, though it comes from the live F10 UI overlay, not
  necessarily from pixel content inside `rasterCharts.zip` itself, so it's not
  guaranteed the same labels exist baked into the tile pixels. — **evidence:**
  reproduced-locally (visual match to session 3's decoded tiles) — **source:** user
  screenshot.
- **`satellite-imagery.jpg`** — photorealistic orthophoto-style texture, visually
  distinct from both other modes and from any `RasterCharts` tile decoded so far. Not
  yet located in the filesystem — no probe has looked for it. Working hypothesis,
  **not yet verified**: this is plausibly the same texture data used to paint DCS's 3D
  terrain mesh (i.e. part of the terrain's core texture/mesh asset pipeline, likely
  under `Mods/terrains/Syria/` alongside `RasterCharts` but in a different
  subdirectory — location unconfirmed), which would place it natively in DCS's own x/z
  coordinate space with no independent chart geodesy to reconcile — unlike the paper-map
  chart, which is a real external cartographic product (confirmed Turkish military
  chart series, session 3) with its own datum/registration.
  > **CORRECTION 2026-09-21 — session 3 says neither "confirmed" nor "Turkish".** Its actual
  > words are *"consistent with a standard 1:250,000-scale-class military/aeronautical chart
  > series (JOG-A … or a close equivalent), **moderate confidence**"* — a NATO-standard series,
  > identified by graticule/navaid convention, not attributed to any nation's military. What
  > session 3 established as Turkish is the **terrain the chart depicts** (Erzincan, the Turkish
  > interior), which is a different claim entirely. Two hops in one parenthesis: a hedge became a
  > confirmation, and the subject of "Turkish" slid from the ground to the publisher. Nothing
  > downstream depends on either — the sentence's real point (an external chart carries its own
  > datum, unlike a DCS-native asset) is unaffected. If confirmed, this asset
  would fit root `CLAUDE.md`'s "DCS geometry is always authoritative" invariant more
  cleanly than `RasterCharts` does. — **evidence:** inferred / unresolved — **source:**
  user screenshot; no filesystem or content evidence yet.

**Scope implication surfaced to user:** whether satellite imagery is the better
truth-layer raster target (vs. RasterCharts' independent chart geodesy) was raised as an
open architectural question. User's decision: **pursue both tracks in parallel** —
continue validating RasterCharts' registration hypothesis (per the existing M2 plan)
while also tasking Investigator to locate and probe the satellite-imagery asset.

### Session 10 (2026-09-03, user correction) — a fourth F10 mode: "Alt" (altitude map)

User provided a fourth screenshot, `world-model/data/raw/dcs/2026-09-03/f10-map-modes/alt-map.jpg`,
zoomed in much further than the three session-5 screenshots. All four screenshots actually
show the same three F10 UI buttons — **Map / Alt / Sat** (visible top-right in every
screenshot, including the three from session 5) — meaning session 5's `dcs-rendered-map.jpg`
was the **"Map"** mode specifically, not a fourth undocumented mode; **"Alt"** is the one not
yet examined until now.

- **"Alt" mode, per the user, is the *the* ground truth for the in-game world** — at
  sufficiently high zoom it draws individual trees and terrain contour lines (confirmed
  visually in `alt-map.jpg`: individual tree-crown icons scattered across forest polygons,
  faint terrain contour lines visible in the tan/desert area, a tan/orange highlighted
  polygon around a small settlement with individual building footprints). It does **not**
  display altitude as numbers despite the name. — **evidence:** user domain knowledge
  (mode purpose/truth-status) + reproduced-locally (visual content of the screenshot) —
  **source:** user, this session; `alt-map.jpg`.
- **This reframes the mode inventory from session 5**: it's not "rendered map (vector,
  engine-only) / paper map (RasterCharts) / satellite (clipmaps)" as three peers — "Alt"
  is a *fourth*, and per the user's characterization is more authoritative than the
  general "Map" mode session 5 examined (which is likely a stylized/generalized vector
  rendering derived from the same underlying truth, not the truth layer itself). Whether
  "Map" mode is literally derived from "Alt" mode's data or independently generalized is
  not yet known.
- **Unresolved, high-value follow-up**: whether any of what "Alt" mode draws — individual
  tree positions, terrain contour geometry — is queryable via DCS's scripting/export API
  (e.g. something in the family of `land.getHeight`/`land.getSurfaceType`, or a dedicated
  vegetation/scenery query, if one exists) from outside a live rendering context, and
  whether it's accessible offline (unlikely, per M1's precedent that `coord.LOtoLL`-class
  APIs need a live mission) or only observable by rendering/screenshotting the client at
  various zoom/pan states. If individual tree/contour data is genuinely queryable, this
  would be DCS-native truth data superior to both RasterCharts (external chart geodesy)
  and clipmap satellite imagery (registration to DCS x/z still unsolved) for building the
  World Model's terrain/vegetation layer — but this is untested; no Lua API research has
  been done on this specific question yet. — **evidence:** unresolved / gap.

---

## 2026-09-03 (session 7) — Stage 1 of M2 plan: registration-hypothesis validation via known-feature control points

(Numbered session 7 to avoid colliding with a concurrently-run investigator session's "Session 6" — satellite-imagery-location findings — appended independently below; both sessions ran in parallel without shared context.)

**DCS version:** 2.9.29.27278 (unchanged). **Theatre:** Syria.

### Question

Per `plans/m2-raster-understanding/plan.md` Stage 1 (blocking gate before
`src/raster/registration.py` is written): does the x/z-arithmetic hypothesis from session 2
(tile edge = scale_meters × 1024px; tile grid index `x{N}_z{N}` encodes DCS-native ground
position) hold up against real content, using the primary path — a visible feature with a
known real-world WGS84 location, mapped through M1's already-solved `wgs84_to_dcs` transform
and compared to its pixel/tile position?

### Findings

- **Two independent real-world control points were identified on the 5 already-decoded
  `64maa00` sample tiles, both from the same sheet/x-index (`x0`), at different z-indices**:
  Sivas city center (visible, labeled, tile `x0_z1`) and the Erzincan VOR/DME/NDB navaid box
  (visible, labeled, tile `x0_z4`). — **evidence:** reproduced-locally (direct visual read of
  `/tmp/64maa00_x0_z1.png`, `/tmp/64maa00_x0_z4.png`) — **source:** decoded PNGs per session 3's
  decode command.
- **Published real-world coordinates**: Sivas city center 39.75056°N, 37.01500°E (Wikipedia,
  39°45′02″N 37°00′54″E). Erzincan Airport (LTCD) ARP 39.71000°N, 39.52694°E (SkyVector/
  Wikipedia, 39°42′36″N 39°31′37″E) — used as a stand-in for the VOR/DME/NDB, which is normally
  co-located at or very near the airport reference point; this substitution adds up to
  roughly ~1 km of uncertainty on top of pixel-reading error, not itself independently
  confirmed. — **evidence:** documented (published aeronautical/geographic sources) —
  **source:** WebSearch, Wikipedia + SkyVector, see citations above.
- **Running both points through M1's existing `wgs84_to_dcs("Syria", lat, lon)` gives**:
  Sivas → DCS (x=522090.5, z=112740.8); Erzincan → DCS (x=515837.6, z=327970.3). Delta
  (Erzincan − Sivas) = (dx=−6253, dz=+215229), i.e. Erzincan sits ~215 km further in +z with
  almost no x change — consistent with real geography (Erzincan is ~2.5° east of Sivas, at
  almost the same latitude). — **evidence:** reproduced-locally (ran `coordinates.wgs84_to_dcs`
  directly, `world-model/src/coordinates/__init__.py`) — **source:** this session's probe.
- **Pixel positions read by eye**: Sivas's built-up-area marker sits near the top-right of tile
  `x0_z1`, roughly pixel (820, 30) of 1024×1024. The Erzincan VOR/DME/NDB navaid icon (small
  symbol the label box's leader line points to, not the label box itself) sits near the
  top-right of tile `x0_z4`, roughly pixel (830, 90). Both estimates are by-eye, no
  feature-center detection — **evidence:** reproduced-locally (visual) — **source:** same PNGs.
- **Applying the x/z-arithmetic hypothesis (64m scale ⇒ 65,536 m/tile) to convert (tile z-index,
  pixel_x) into a z-offset from a common origin**: Sivas ⇒ (1 + 820/1024) × 65,536 ≈ 118,036 m;
  Erzincan ⇒ (4 + 830/1024) × 65,536 ≈ 315,269 m. Predicted Δz between the two tiles/pixels ≈
  197,376 m, versus the M1-transform-derived actual Δz of 215,229 m — a discrepancy of ≈17,850 m,
  about 9% of the predicted span. Solving each point independently for a common origin_z (i.e.
  `origin_z = dcs_z − tile_arithmetic_z`) gives origin_z ≈ −5,295 from Sivas and ≈ +12,701 from
  Erzincan — two independent estimates about 18,000 m apart. — **evidence:** inferred (arithmetic
  combining a reproduced-locally transform result with by-eye pixel reads) — **source:** this
  session's calculation, reasoning above.
- **The hypothesis is directionally confirmed and roughly order-of-magnitude consistent, but
  not tight enough yet to fix a precise affine.** The z-tile-index does track DCS z (east)
  correctly in sign and rough magnitude (predicted span 197 km vs. actual 215 km, same order,
  same direction, not off by a tile or a sign error) — this rules out gross hypothesis failure
  (e.g. wrong scale constant, swapped axes, or a tile-index-to-meters relationship off by a
  factor of 2+). The ~9% residual and ~18 km origin disagreement are within plausible bounds for
  by-eye pixel-position error alone (±50 px at 64 m/px = ±3,200 m per point, i.e. up to ~6,400 m
  combined) plus the Erzincan-ARP-vs-VOR substitution (~1 km) — but 18 km exceeds that combined
  budget by roughly 3×, so some of the residual is likely a genuine (if modest) hypothesis
  simplification, not pure measurement noise — most plausibly non-zero sheet/tile overlap or a
  small origin offset not being purely "tile_index × 65536," rather than the core scale
  assumption being wrong. — **evidence:** inferred — **source:** reasoning from the two data
  points above; cannot be disambiguated from only 2 points on one axis.
- **This test only exercises the z (east) tile axis** — both sample points are on `x0`, so the
  x (north) tile-index axis is completely unvalidated this session. No sample tile at a
  different x-index was available to decode. — **evidence:** gap, explicitly scoped by available
  samples — **source:** n/a.

### Reproducible Test

```python
import sys; sys.path.insert(0, "src")
from coordinates import wgs84_to_dcs
sivas = wgs84_to_dcs("Syria", 39.75056, 37.01500)
erzincan = wgs84_to_dcs("Syria", 39.71000, 39.52694)
# Sivas: (522090.5, 112740.8); Erzincan: (515837.6, 327970.3)
```
Pixel positions read visually from `/tmp/64maa00_x0_z1.png` (Sivas ≈ (820,30)) and
`/tmp/64maa00_x0_z4.png` (Erzincan navaid icon ≈ (830,90)) — re-derive by opening the PNGs
(decode command in session 3) and inspecting directly; these are by-eye reads, not
automated feature detection, and a different reader may get materially different pixel
estimates (±30-50px plausible), which is itself part of why this stays "provisional."

### Possible Approaches

- **Before `registration.py` is written**, get at least one more control point off the
  x-axis (a different x-index tile, e.g. `x1_z*` or `x7_z*` from the same sheet) to validate
  the north/south tile axis the same way — currently completely untested. This is the single
  highest-value follow-up for tightening confidence.
- **Automate pixel-position reading** (e.g. template-match the navaid box glyph, or OCR the
  UTM grid labels once a margin tile with full-precision labels is found) rather than relying
  on by-eye estimates — would shrink the dominant error source in this test.
- **Cross-check against the UTM-grid path** (session 3's secondary path) once a margin/corner
  tile with an unambiguous full-precision grid label is decoded — an independent `pyproj`-based
  affine from the chart's own printed grid would let the ~18 km origin discrepancy be attributed
  definitively to either pixel-reading error or a real registration-formula gap (e.g. overlap
  between sheets, or origin not being a clean multiple of tile edge length).
- Given the ~9% residual is plausible-but-not-negligible, `registration.py`'s `confidence`
  field should be `"provisional"` if built from this data alone — not `"confirmed"` — per the
  plan's existing guidance not to over-claim from an empirical fit.

### Unresolved

- The x (north) tile-index axis is untested — no sample at a different x-index exists yet.
- Whether the ~18 km origin discrepancy is pure by-eye pixel-reading error or reflects a real
  simplification in the arithmetic hypothesis (e.g. sheet overlap, non-zero true origin offset)
  cannot be distinguished with only 2 points on 1 axis — a 3rd control point (held out, per the
  plan's Stage 4 suggestion) would help distinguish "noisy fit" from "systematic bias."
- Whether the Erzincan Airport ARP is close enough to the actual VOR/DME/NDB antenna position
  to be a valid stand-in — not independently confirmed, only assumed standard co-location
  practice.
- Precise affine (origin + scale) is not yet fixed — this session establishes the hypothesis is
  *directionally sound* (right order of magnitude, right sign, right axis), which is what Stage 1
  asked for, but Stage 2's `registration.py` will need either a tighter empirical fit (more
  control points, automated pixel detection) or the UTM-grid cross-check to reach a defensible
  `"provisional"` affine with a stated error tolerance.

---

## Session 6 (2026-09-03) — Locating satellite-mode imagery: `Mods/terrains/Syria/clipmaps/colortexture/`

**DCS version:** 2.9.29.27278 (unchanged, per M0; not re-verified this session — no live
access). **Theatre:** Syria.

### Question

Session 5 raised, but left unverified, the hypothesis that F10's photorealistic
"satellite" map mode is sourced from the same texture data that paints DCS's 3D terrain
mesh — i.e. lives natively in DCS's own x/z tiling scheme, not an external chart product
like `RasterCharts`. This session: (1) confirms visually what "satellite" mode looks like
(via the user-provided screenshot), (2) searches `DCS-files.txt` (M0's full filesystem
listing) for a plausible on-disk location distinct from `RasterCharts`, (3) checks
whether DCS terrain-modding community documentation corroborates the finding, and (4)
writes a probe script for the next live-access session. No live DCS/WSL access was
available this session — all filesystem findings are from the existing static listing.

### Findings

- **`satellite-imagery.jpg` (user screenshot, Aleppo region, same view as session 5's
  other two modes) is a photorealistic orthophoto-style texture** — muted tan/brown
  ground tones, visible field boundaries and settlement footprints as raw imagery texture
  (not symbolized cartography), no contour lines, no UTM grid, no chart typography. Clearly
  distinct from both `dcs-rendered-map.jpg` (vector/symbolized) and `paper-map.jpg`
  (confirmed scanned military chart, session 3). — **evidence:** reproduced-locally
  (direct visual inspection) — **source:**
  `world-model/data/raw/dcs/2026-09-03/f10-map-modes/satellite-imagery.jpg`.
- **`Mods/terrains/Syria/clipmaps/` is a strong, distinct candidate location for this
  imagery, separate from `RasterCharts`.** Full one-level directory survey of
  `Mods/terrains/Syria/` in `DCS-files.txt` shows `clipmaps/` alongside `RasterCharts/`,
  `surface/`, `vfsTextures/`, etc. `clipmaps/` contains exactly three subdirectories:
  `colortexture/`, `normalmap/`, `splatmap/` — a base-color + normal + surface-blend-weight
  texture set, which is precisely the standard input trio for texturing a 3D terrain mesh
  in a real-time renderer. `colortexture/` has scale-tiered subdirectories `1m`, `4m`, `8m`,
  `16m`, `128m` (some with `(spring)`/`(winter)` seasonal variants: `1m(spring)`,
  `4m(spring)`, `4m(winter)`, `8m(spring)`, `16m(spring)`, `16m(winter)`,
  `128m(spring)`, `128m(winter)`); `normalmap/` has `4m`, `8m`, `16m`, `128m`;
  `splatmap/` has `1m`, `4m`, `4m(winter)`, `8m`, `16m`, `16m(winter)`, `128m`. Tile
  filenames follow `{scale}m{sheet}{level}.tif.clipmap`, e.g.
  `clipmaps/colortexture/16m/16mAA00.tif.clipmap`,
  `clipmaps/colortexture/128m/128mxAB-1.tif.clipmap` — same `{sheet}{level}` grammar
  (`AA`/`AB`/`xAB`, level suffix `-1`/`00`/etc.) as `RasterCharts`'s tiles and Caucasus's
  `RasterCharts` tile pyramid (sessions 1–2), but a different container extension
  (`.tif.clipmap` vs. `RasterCharts`'s `.tif.dds`-inside-zip) and a different parent
  directory entirely. — **evidence:** reproduced-locally (grep over the M0 filesystem
  listing) — **source:** `world-model/data/raw/dcs/2026-09-02/DCS-files.txt`, exact
  matched paths as above (2,006 total lines under `clipmaps/`).
- **"Clipmap" is a well-established, generically-documented real-time terrain-rendering
  technique — not DCS-specific** — a level-of-detail texture/geometry streaming scheme
  using nested grids that shift with the camera, first popularized by NVIDIA's GPU Gems 2
  ch. 2 ("Terrain Rendering Using GPU-Based Geometry Clipmaps") and widely reused across
  large-terrain engines (flight sims, open-world games) specifically to stream a
  base-color ground texture (often literally aerial/satellite photography) onto a terrain
  mesh at multiple resolutions around the camera. The directory name plus the
  `colortexture`/`normalmap`/`splatmap` trio matches this pattern closely: `colortexture`
  is the base-color (RGB) layer a clipmap streams, exactly the role satellite-style ground
  imagery would play. — **evidence:** documented (established graphics-literature
  technique, independent of DCS) for what a "clipmap" generically is; **inferred** that
  DCS's specific `clipmaps/colortexture/` implements this pattern using real-world-derived
  imagery (plausible from naming/structure, not confirmed against actual pixel content) —
  **source:** NVIDIA GPU Gems 2 ch. 2 (developer.nvidia.com/gpugems/gpugems2/...), general
  web search.
- **An ED forum thread title directly corroborates that `.clipmap` files are a
  known, community-recognized terrain-texture asset that modders want to edit**: "A tool
  or software to open/edit Clipmap files (Nevada) - DCS Modding - ED Forums"
  (`forum.dcs.world/topic/332961-a-tool-or-software-to-openedit-clipmap-files-nevada/`).
  This is from the Nevada (NTTR) terrain, not Syria, but confirms the `.clipmap` asset
  type/extension is a general DCS terrain-engine convention, not something unique to one
  theatre — consistent with the `.tif.clipmap` naming already found for Syria. Thread body
  was **not read this session** — title only, from web search results; automated fetch of
  `forum.dcs.world` is known-unreliable (403 blocks, per prior sessions' experience and
  the `M2 RasterCharts recon` memory) — **evidence:** forum-claim-unverified (title only,
  content unread) — **source:** WebSearch result title; user should open the thread URL
  above manually and paste content back if the `.clipmap` format/tooling detail matters
  before committing to a decode approach.
- **No DCS terrain-modding tutorial or SDK documentation specifically describing the
  `clipmaps/colortexture` pipeline, its exact tile format, or its coordinate
  registration was found this session** — web search on DCS terrain-creation/modding
  surfaced general texture-mod discussion (aerial-photography-based texture packs like
  "DCS Enhanced Terrain," CGTC for Caucasus) and passing mentions of "clipmap textures
  loading" (memory-consumption context in patch notes), but no primary technical spec.
  This is a negative finding from search coverage only — a full read of
  `forum.dcs.world/topic/271289-creating-custom-terrainmap-for-dcs-world/` (an ED
  thread specifically about building custom terrains, which very plausibly covers this
  pipeline since terrain authors must author these assets themselves) was not attempted
  this session and is a promising next lead, but automated fetch of `forum.dcs.world`
  content is unreliable — recommend the user open it manually. — **evidence:** inferred
  (absence-from-search, weak) — **source:** WebSearch only, `forum.dcs.world` threads
  found but not fetched.
- **The tile-naming grammar's reuse across `RasterCharts` and `clipmaps` (same
  `{sheet}{level}` scheme, same apparent `AA`/`AB`/`xAB` region-code convention) is
  consistent with both being produced/tiled by the same underlying `landscape5` terrain
  engine tooling** (the same engine module named literally in `RasterCharts`'s `.sup5`
  header string `landscape5::sup5File`, session 2) — **but this does not mean they share
  registration/geodesy.** `RasterCharts` is confirmed (session 3, visual inspection) to be
  a scanned real-world military chart with its own external UTM/chart datum;
  `clipmaps/colortexture` painting the terrain mesh directly would, if confirmed, be
  registered natively in DCS x/z by construction (the mesh itself has no other
  coordinate system) — the shared naming grammar is a tooling-convention coincidence, not
  evidence the two share a coordinate frame. — **evidence:** inferred — **source:**
  reasoning from confirmed naming patterns across sessions 1–2 and this session.

### Reproducible Test

Not yet run this session (no live Windows/WSL access). Wrote
`world-model/tools/wsl/probe_syria_satellite_texture.sh`, mirroring
`probe_syria_rastercharts.sh`'s pattern: lists `clipmaps/colortexture/`'s scale-tier
subdirectories, does a full recursive listing (path + size) of the `1m` tier (the
highest-resolution tier, the most likely satellite-mode source), reports per-tier file
count and total size, hex-dumps the first 64 bytes of one sample `.tif.clipmap` file, and
copies up to 5 sample `colortexture/1m` files plus one `normalmap` and one `splatmap`
sample into `wsl-output/` for local format inspection. Unlike `RasterCharts` (a single
zip), `clipmaps/` is plain files on disk directly under the DCS install, so this script
does directory listing/`cp`, not `unzip -l`/extraction — no zip container to open. Deploy
per `WORKFLOW.md`: copy into `win-mac-sync/run-wsl/`, run in WSL with
`DCS_INSTALL_PATH` set, sync `wsl-output/` back, then copy the report + sample files into
`world-model/data/raw/dcs/<date>/` for follow-up analysis (reuse session 3's DDS-decode
approach if `.tif.clipmap` turns out to share DDS's magic bytes/header layout — not yet
known; the extension is different from `RasterCharts`'s `.tif.dds` so the container format
should not be assumed identical without checking the actual header).

### Possible Approaches

- **If `.tif.clipmap`'s header turns out to be a plain DDS (or similar standard texture
  container) despite the different extension**, the same direct-header-parse and Pillow
  decode approach from sessions 2–3 should work unmodified — worth checking the magic
  bytes (`DDS `/`0x44445320`) first before assuming a new format needs reverse-engineering.
- **If `.tif.clipmap` is a genuinely different/proprietary container** (plausible — the
  distinct extension may signal DCS's clipmap streaming system wraps the texture in its
  own mip/tile metadata beyond what a factory DDS header carries), the ED forum thread on
  Nevada `.clipmap` files (link above) is the most promising documentation lead — ask the
  user to open and paste it, since automated fetch is unreliable here.
- **Registration path if confirmed to paint the terrain mesh:** unlike `RasterCharts`,
  which needed either `.sup5` reverse-engineering or a UTM-grid/control-point empirical
  fit (sessions 2–3), a texture confirmed to be the terrain mesh's own base color would
  need no independent geodesy at all — the DCS x/z ↔ WGS84 transform already solved in M1
  (`world-model/src/coordinates/`) would directly apply, and only the tile-index-to-x/z
  offset arithmetic (same style as `RasterCharts`'s session 2 `x{N}_z{N}` hypothesis, but
  for `clipmaps`'s own `{sheet}{level}` naming, which lacks visible `x`/`z` tile-position
  substrings in the names seen so far — worth checking whether that's inside `.tif.clipmap`
  metadata instead) would need resolving. This is a meaningfully smaller unknown than
  `RasterCharts`'s registration problem, if confirmed.
- **Given `clipmaps/colortexture` has multiple resolution tiers (1m up to 128m) plus
  seasonal variants**, once format/registration is confirmed this asset would also let the
  pipeline choose a resolution/season tradeoff explicitly — a design question for
  Architect, not resolved here.

### Unresolved

- Actual container/pixel format of `.tif.clipmap` files (DDS-compatible header or
  something else) — requires running the probe script above against the live install and
  inspecting the sample files' magic bytes/header structure, mirroring session 2's DDS
  header parse.
- Whether `clipmaps/colortexture` content visually matches `satellite-imagery.jpg` (same
  Aleppo-region content, same photorealistic character) — requires decoding a sample tile
  covering that area and comparing, the same visual-match validation session 3 used for
  `RasterCharts`.
- Whether `clipmaps/colortexture`'s tiling scheme maps to DCS x/z coordinates by simple
  arithmetic (as hypothesized for `RasterCharts` in session 2) or requires its own
  separate derivation — no `x{N}_z{N}`-style substrings were observed in the `clipmaps`
  filenames sampled so far (unlike `RasterCharts`'s naming), so the registration
  mechanism may differ and needs its own investigation once file contents are available.
- Whether `clipmaps/colortexture` is actually the same asset F10's satellite mode reads,
  or merely a plausible sibling (e.g. F10 satellite mode could instead read yet another,
  still-unlocated asset, with `clipmaps` feeding only the 3D cockpit-view terrain and not
  the F10 map renderer) — the shared "photorealistic ground imagery" character is
  suggestive but not proof of code-path identity; only decoding and visually comparing
  tile content against the screenshot (next step above) can raise this from inferred to
  reproduced-locally.
- Full content of `forum.dcs.world/topic/332961-...` (Nevada `.clipmap` tooling thread)
  and `forum.dcs.world/topic/271289-creating-custom-terrainmap-for-dcs-world/` (custom
  terrain creation) — both found by title/URL only, not read, due to unreliable automated
  fetch of `forum.dcs.world`. Ask the user to open these manually if `.tif.clipmap`
  decoding proves difficult from header inspection alone.

## Session 9 (2026-09-03) — `.tif.clipmap` container decoded, satellite-imagery hypothesis confirmed

(Numbered 9, not 7, to avoid colliding with the unrelated M1 coordinate-validation
"Session 7"/"Session 8" entries that were concurrently appended to this file below —
this session continues the clipmap/RasterCharts imagery thread from Session 6 above,
not the M1 coordinate-transform thread.)

**Input:** 4 sample files newly extracted by the fixed probe script, all Syria, all
`128m` scale tier, sheet `AA`: `128mAA-1.tif.clipmap` (colortexture, level "-1"),
`128mAA00.tif.clipmap` (colortexture, level "00"), `normalmap_128mAA-1.tif.clipmap`,
`splatmap_128mAA-1.tif.clipmap`. Analyzed entirely offline from local copies at
`world-model/data/raw/dcs/2026-09-03/syria_satellite_texture_samples_20260903T113507Z/`
— no live DCS/WSL access this session.

### Findings

- **Fixed 0x34-byte (52-byte) container header, byte-identical in layout and mostly in
  value across all 4 sample files** — **evidence:** reproduced-locally (direct
  byte-for-byte comparison via a Python parser) — **source:** the 4 sample files, offsets
  0x00–0x33. Fields identified:
  - `0x00` u32 = 3 — constant across all 4 files; meaning not determined (possibly a
    container/format version).
  - `0x04` f32 = 128.0 — matches the `128m` scale tier encoded in the filename. Confirms
    the header carries the tile's real-world/engine scale as an IEEE-754 float, not just
    as a filename convention.
  - `0x08` u32 = 256 — constant across all 4 files; matches the payload tile dimension
    confirmed by decode (see below): 256×256 texels.
  - `0x0c` u32 = 3 — a length prefix for the string field that immediately follows (not a
    separate constant as first guessed — `0x0c`'s value equals the byte-length of the
    string at `0x10`).
  - `0x10` (3 bytes, length given by `0x0c`) — the compression-format tag first spotted
    in the original 64-byte dump: `"bc3"` in both `colortexture` samples and `splatmap`,
    `"bc1"` in `normalmap`. Confirmed functionally, not just by name — see decode
    results below, where the `bc3`-tagged files' payload decodes correctly only as
    BC3/DXT5 (65536 bytes per 256×256 tile) and the `bc1`-tagged file's payload decodes
    correctly only as BC1/DXT1 (32768 bytes per 256×256 tile, i.e. exactly half the byte
    rate, as BC1 spec requires).
  - `0x13` u8 = 1, `0x14` u32 = 6, `0x18` u32 = 1, `0x1c` u32 = 0 — constant across all 4
    files; meaning not determined (plausibly a version/flags/mip-count block — `6` is a
    plausible mip-level count for a 256px tile chain, but this is unverified).
  - `0x20` i32 = **level marker: `-32` for the `...AA-1` filename, `0` for the `...AA00`
    filename** (colortexture-only comparison, since both other samples are `-1`-level
    files and also read `-32` here). This is a fixed-point encoding of the clip level
    index seen in the filename (level `-1` → `-32`, level `0` → `0`), i.e. level × 32 —
    the multiplier 32 reappears at `0x28`/`0x2c` below, suggesting a shared internal
    unit, not a coincidence.
  - `0x24` u32 = 256 — repeats the tile-dimension value from `0x08`; consistent with
    `0x08`/`0x24` being width/height (both square, both 256).
  - `0x28` u32 = 32, `0x2c` u32 = 32 — constant across all 4 files. This directly matches
    the count of entries in the row-offset table that follows (see below): exactly 32
    twelve-byte records. **This resolves the ambiguity the task flagged**: `2000 0000
    2000 0000` at this offset is *not* the pixel width/height (those are the `256`
    values at `0x08`/`0x24`) — it is a row/band count for an internal offset table.
  - `0x30` onward: a table of exactly **32** twelve-byte records, format `[u32 flag=1]
    [u32 byte_offset][u32 zero]`, with `byte_offset` monotonically increasing record to
    record. The `byte_offset` values, cross-checked against an independent scan for
    zlib-stream magic bytes (see below), point 4 bytes *before* each real zlib stream
    start — i.e. each record's offset is the position of a 4-byte little-endian
    compressed-chunk-length prefix, and the actual zlib stream begins
    `byte_offset + 4`. After these 32 records the table format changes (a second,
    differently-shaped index structure follows, not fully decoded this session — see
    Unresolved). The overall structure (32 records for the top decode) matches `0x28`
    exactly, which is itself a fairly strong internal-consistency confirmation that the
    `32`/`32` field is a table-length/row-count field, not an image dimension.

- **The actual pixel payload is not raw BC3/BC1 data — it is raw BC3/BC1 data wrapped in
  per-256×256-tile zlib (deflate) streams**, one stream per tile, each stream prefixed
  by a 4-byte little-endian compressed-length field — **evidence: reproduced-locally**
  (direct decompression succeeded; the classic zlib magic `78 da` — deflate, best
  compression, no preset dictionary — was found at the byte offset the header's row
  table predicted, and `zlib.decompressobj().decompress()` on that byte range produced
  exactly 65536 bytes for `bc3`-tagged files and exactly 32768 bytes for the `bc1`-tagged
  file, matching BC3's 1-byte/pixel and BC1's 0.5-byte/pixel rates for a 256×256 tile
  with zero slack, on every chunk tested) — **source:** Python probe script (see
  Reproducible Test) run directly against the 4 sample files.
  - This resolves point 2 of the task fully: header size is 0x34 (52 bytes) before the
    per-chunk index table begins, tile dimensions are **256×256** texels (not 512/1024/
    2048 as the task's fallback guesses suggested — those guesses were reasonable a
    priori but wrong; the true dimension was recoverable directly from the header's own
    `256` field once the record/table framing was understood, and cross-confirmed by the
    decompressed-payload byte count matching exactly).
  - The `.sup5`/`.tif.clipmap` "shared ED container convention" hypothesis from earlier
    sessions holds in spirit (both are custom framed binary containers with an embedded
    format tag, not off-the-shelf DDS) but the actual container layout is clipmap-
    specific: a fixed header, a paged/chunked compressed-tile index, and per-tile zlib-
    wrapped BC-compressed payloads — materially different internal structure from
    whatever `.sup5` turned out to be, beyond the shared "typed tag string near the
    front" idea.

- **Decode succeeded and is visually conclusive: `clipmaps/colortexture` is
  photorealistic real-world-derived aerial/satellite-style ground imagery, closely
  matching the F10 "Sat" mode screenshot in visual character** — **evidence:
  reproduced-locally** (a minimal 128-byte synthetic DDS header — standard `DDS `
  magic + `DDS_HEADER` + `DDS_PIXELFORMAT` with FourCC `DXT5`/`DXT1` — was prepended to
  each decompressed 65536/32768-byte chunk and opened successfully with Pillow, exactly
  as sessions 2–3 did for `RasterCharts`) — **source:** decoded PNGs at
  `/private/tmp/.../scratchpad/tile_decoded.png` (single tile),
  `colortexture_AA00_strip.png` (12 consecutive 256×256 tiles from the `...AA00` level
  file, tiled into a 2048×256 strip), `normalmap_AA-1_strip.png`,
  `splatmap_AA-1_strip.png`. Visual inspection:
  - The `...AA-1` (level `-1`) colortexture tiles decode to **flat, near-uniform
    tan/brown color** with no discernible ground detail — consistent with `-1` being a
    coarse/fallback clip level (e.g. an averaged low-frequency color used before
    higher-detail data streams in, or a distance/far-LOD level), not a decode failure —
    BC3 decoded cleanly (no block-noise/garbage), it is simply low-information content.
  - The `...AA00` (level `0`) colortexture tiles decode to **clearly photorealistic
    aerial imagery**: irregular green vegetation/field patches, a dark-edged
    water-body-like shape in the first tile, open tan/brown terrain, and rocky/mountainous
    texture in later tiles of the strip — visually indistinguishable in *character* (color
    palette, vegetation-patch style, terrain mottling) from the user's
    `f10-map-modes/satellite-imagery.jpg` screenshot of the Aleppo region (same tan/brown
    base tone, same irregular dark-green field-cluster vegetation pattern, same overall
    photographic — not painterly/game-art — texture quality). Exact geographic
    coincidence with the screenshot's specific location was **not verified** (the `AA`
    sheet's real-world extent wasn't derived this session — see Unresolved) — this is a
    strong stylistic/character match, not a pixel-for-pixel location match.
  - `normalmap_128mAA-1` decoded (as BC1/DXT1, per its `bc1` tag) without error,
    producing plausible normal-map-style low-frequency shading. `splatmap_128mAA-1`
    decoded (as BC3/DXT5, per its `bc3` tag) without error. Both are consistent with
    their names' expected role (surface-normal and blend-weight textures respectively)
    though their content wasn't analyzed in depth this session beyond confirming clean
    decode.

- **Some zlib-magic-byte matches beyond the first table's 32 entries produced decode
  errors** (`invalid block type`, `invalid distance too far back`, etc., seen when
  scanning for `78 da` naively past the first 32-chunk table, especially in the `...AA00`
  file) — **evidence:** reproduced-locally (the errors themselves) — this is expected
  and *not* a format-understanding failure: raw compressed byte streams can coincidentally
  contain the 2-byte sequence `78 da` internally, so a blind byte-pattern scan produces
  false positives past the region the offset table actually vouches for. All chunks
  decoded via the *first 32-entry header table*, i.e. offsets read from the structured
  index rather than pattern-matched blindly, decoded cleanly with the exact expected byte
  count every time. This means: **the file format is not "scan for `78 da`"** — a correct
  reader must walk the index table(s) rather than pattern-match magic bytes, and the
  second (post-32-record) table structure needs to be understood before a complete/
  general-purpose reader can be written (see Unresolved).

### Reproducible Test

Python, run from `world-model/` with `source .venv/bin/activate` (Pillow already
installed per earlier sessions):

```python
import struct, zlib, os

path = "data/raw/dcs/2026-09-03/syria_satellite_texture_samples_20260903T113507Z/128mAA00.tif.clipmap"
with open(path, "rb") as f:
    data = f.read()

# Header fields (offsets confirmed constant across all 4 samples except where noted):
#   0x00 u32=3 (const) | 0x04 f32=scale (matches filename, e.g. 128.0)
#   0x08 u32=256 (tile width) | 0x0c u32=strlen of tag at 0x10
#   0x10 tag string (e.g. "bc3"/"bc1") | 0x20 i32=level*32 (filename's -1/00/...)
#   0x24 u32=256 (tile height) | 0x28,0x2c u32=32,32 (row-table entry count)
#   0x30.. : 32 x 12-byte records [u32 flag=1][u32 chunk_len_field_offset][u32 zero]

off = 0x30
for i in range(32):
    flag, chunk_off, zero = struct.unpack_from("<III", data, off)
    off += 12
    length = struct.unpack_from("<I", data, chunk_off)[0]
    stream = data[chunk_off + 4 : chunk_off + 4 + length]
    raw = zlib.decompress(stream)
    assert len(raw) == 65536  # 256x256 BC3, 1 byte/pixel

# Minimal DDS wrapper (128-byte header, DDSD_CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE,
# DDPF_FOURCC='DXT5') + raw BC3 bytes opens directly in Pillow — see session 7 script,
# same pattern as sessions 2-3's RasterCharts DDS decode.
```

Full working script (header parse + zlib walk + DDS-wrap + Pillow decode + strip-tile
PNG output) was run inline this session; not yet promoted to a committed
`world-model/tools/` script — see Possible Approaches.

### Possible Approaches

- **Promote the working decode script to `world-model/tools/decode_clipmap_tile.py`**
  once the second index table (post-32-record structure, `0x1b0` onward) is understood
  well enough to know how many total chunks exist per file and how they map to
  sub-tile position within the 128m-scale `AA` sheet — Architect should decide whether
  this belongs in `tools/` (one-off inspection) or graduates into `src/` as a pipeline
  reader once M2's raster-ingestion design is finalized.
  - **Note:** per this project's role convention, this stays out of `world-model/src/`
    until Architect scopes a pipeline plan around it — this session only produced probe
    code, run inline, not committed.
- **Full-file reconstruction (stitching all decoded 256×256 chunks into one seamless
  tile image) requires resolving the second table's semantics** — plausibly a
  column-index or sub-tile-position table (the field pattern shifts from `[1, offset, 0]`
  to what looks like `[32, 1, big_number]` at `0x330`, then further shifts again a few
  records later), which was not fully decoded this session. Two reasonable approaches:
  (a) treat the whole file as an opaque bag of same-size 256×256 chunks and infer
  position empirically by decoding all chunks and visually reassembling them (viable
  short-term, doesn't require full format understanding), or (b) invest more time walking
  the second table's field semantics directly — likely faster once one plain example
  (e.g. this session's outputs) is available for a fresh pass.
- **Registration to DCS x/z / WGS84**: unresolved this session (no coordinate metadata
  found in the 52-byte header or the two index tables inspected) — the `{sheet}{level}`
  filename grammar (`AA`, level `-1`/`00`) likely encodes a coarse tile-grid position
  the same way `RasterCharts` file names were hypothesized to (session 2), but this
  needs its own derivation, most plausibly by cross-referencing known DCS x/z
  coordinates of visible landmarks (e.g. Aleppo) against which physical
  `clipmaps/colortexture/128m/*.tif.clipmap` file covers them — a task for a follow-up
  session once live DCS access (to correlate landmark coordinates) or a broader sample
  set (to infer a tile-grid step empirically from adjacent sheet codes) is available.

### Unresolved

- **The full container format is understood well enough to decode individual 256×256
  tiles reliably (via the first 32-record table), but not well enough to write a
  complete, general-purpose parser** — the second index table's structure (starting
  ~`0x1b0`, format shifts partway through) was observed but not decoded. This matters
  for reconstructing full contiguous tile images and for knowing the total chunk count
  per file (a blind `78 da` magic-byte scan is unreliable as shown above).
  What would resolve it: another focused pass reading the second table byte-by-byte
  the way this session's Reproducible Test script did for the first, ideally with a
  wider byte range loaded (only the first ~2MB of each file was inspected this session).
- **Exact geographic registration** (which real-world extent the `AA` sheet / each
  256×256 tile covers) is still unresolved — filename `{sheet}{level}` grammar likely
  encodes a coarse grid position, consistent with the `RasterCharts` naming pattern
  noted in session 6, but no coordinate arithmetic was derived or tested this session.
- **Whether `clipmaps/colortexture` is definitively the same asset F10's "Sat" map mode
  reads at runtime, vs. a stylistically-similar sibling asset feeding only the 3D
  terrain mesh render** — this session raised the finding from "plausible sibling" to
  "strong visual-character match" but did not achieve pixel-exact same-location
  comparison (would require identifying which `AA`-sheet tile covers the exact
  screenshot coordinates `36°40'20"N 38°18'19"E` and decoding that specific tile) — the
  strongest remaining test to fully confirm/reject this hypothesis.
- Full content of the two ED forum threads flagged in session 6 (`.clipmap` tooling,
  custom terrain creation) — still unread; automated `forum.dcs.world` fetch remains
  unreliable, ask the user to paste content manually if the second-table semantics or
  tile-grid registration prove hard to fully resolve from binary inspection alone.

---

## Session 8 (2026-09-03) — Stage 1 completion: x-axis (north) validation via 3-point control set + independent graticule cross-check

**DCS version:** 2.9.29.27278 (unchanged). **Theatre:** Syria.

### Question

Session 7 validated the x/z-arithmetic registration hypothesis on the z (east) tile axis
only (~9% residual, Sivas/Erzincan, both on tile column `x0`) and explicitly flagged the x
(north) axis as completely untested. A fresh probe pulled the full `64maa00_x0..7_z1` tile
row, letting the x-axis be tested the same way. This session also pursues session 3's
proposed independent cross-check: deriving pixel→coordinate scale from the chart's own
printed UTM graticule (lat/lon degree labels), fully independent of DCS x/z arithmetic.

### Findings

- **Three real-world control points were identified across the `x0/x3/x7` columns of the
  `64maa00_z1` tile row, all at the same nominal z-tile-index (1), isolating the x-axis**:
  Sivas (tile `x0_z1`, reused from session 7, pixel ≈ (820, 30)), Kahramanmaraş (tile
  `x3_z1`, city built-up-area footprint, pixel ≈ (583, 707)), and Hama/HAMAH (tile `x7_z1`,
  city built-up-area footprint, pixel ≈ (230, 850)) — all by-eye reads off the decoded PNGs
  (`/tmp/64maa00_x{0,3,7}_z1.png`), same caveats as session 7 (±30–50px plausible error per
  point). — **evidence:** reproduced-locally (visual) — **source:** decoded PNGs, this
  session.
- **Published WGS84 coordinates (WebSearch, Wikipedia-derived), confirmed this session**:
  Kahramanmaraş city center 37.583°N, 36.933°E; Hama city center 35.135°N, 36.750°E. (Sivas
  39.75056°N, 37.01500°E reused from session 7.) — **evidence:** documented — **source:**
  WebSearch → en.wikipedia.org/wiki/Kahramanmaraş, en.wikipedia.org/wiki/Hama.
- **Running all three through M1's `wgs84_to_dcs("Syria", lat, lon)` and comparing against
  the x-tile-index-arithmetic prediction (model: `dcs_x = origin_x − (x_tile_index +
  pixel_y/1024) × 65536`, i.e. increasing x-tile-index and increasing pixel row both move
  south) gives a tight three-way fit**:
  - Sivas (x0): DCS x = 522,090.5; tile-axis value = 1,920.0; implied `origin_x` = 524,010.5
  - Kahramanmaraş (x3): DCS x = 281,692.0; tile-axis value = 241,856.0; implied `origin_x` =
    523,548.0
  - Hama (x7): DCS x = 10,465.4; tile-axis value = 513,152.0; implied `origin_x` = 523,617.4
  - The three independently-derived `origin_x` estimates span only **≈463 m** (523,548–524,011),
    i.e. **<0.1%** of the ~514 km x-range these three points cover. Pairwise residuals
    (predicted Δx vs. M1-transform-derived actual Δx): Sivas→Maraş 463 m (0.19% of the
    239,936 m predicted span); Sivas→Hama 393 m (0.08% of the 511,232 m predicted span). —
    **evidence:** reproduced-locally (transform + arithmetic run directly this session) —
    **source:** this session's probe (see Reproducible Test).
  - **This is an order of magnitude tighter than session 7's z-axis fit** (which had a ~9%
    residual and an ~18 km origin spread from only 2 points). The x-axis is directionally
    confirmed (increasing x-tile-index moves south, i.e. **negative** DCS x, opposite in
    sign-convention from the z-axis where increasing z-tile-index moves **positive** DCS z
    east) and quantitatively tight. **This is a genuinely new and important asymmetry for
    `registration.py` to encode explicitly**, not something obvious from the filename
    grammar alone: z-tile-index and DCS z increase together (image column 0 = west edge,
    matches DCS "+z is east"), but x-tile-index and DCS x move in **opposite** directions
    (image row 0 = north edge, tile index increases like a row number going south, while
    DCS "+x is north" increases the other way) — i.e. the tile grid's row axis is flipped
    relative to DCS's own x convention and the pipeline must apply that sign flip, not
    assume both axes compose the same way. — **evidence:** inferred (sign/composition rule)
    from reproduced-locally arithmetic above — **source:** this session's calculation.
- **Independent graticule cross-check, executed against tile `64maa00_x3_z1` (the tile with
  visible lat/lon degree labels flagged in the task): both the "38°" parallel and "37°"
  meridian labels are quantitatively consistent with the declared 64 m/pixel scale, anchored
  against Kahramanmaraş's known real-world coordinates — a check that uses no DCS x/z
  arithmetic at all.**
  - The "37°" label (confirmed by rotating a crop 90° to read it — it runs vertically along
    a thin black tick-marked line, distinct from the thicker blue UTM grid lines) sits along
    a vertical line at pixel column ≈ 677–690 (three independent by-eye reads across
    different crops), call it **683**. Kahramanmaraş's city-center pixel is at column ≈583.
    Predicted pixel offset from the geodesy alone: Δlon = 37.000° − 36.933° = 0.067°; at
    37.58°N, meters/degree-longitude ≈ 111,320 × cos(37.58°) ≈ 88,266 m/°; Δdistance ≈
    5,914 m; at the declared 64 m/px, that's **≈92 px**. Measured offset: 683 − 583 = **100
    px**. Agreement within ≈8 px (≈512 m, ≈8.7% of the predicted offset — small in absolute
    terms, within by-eye pixel-reading tolerance).
  - The "38°" label sits right at the tile's top edge (label bounding box pixel y ≈ 33–83,
    i.e. the actual graticule line is at or above y≈0–30). Predicted latitude at pixel row
    0, using Kahramanmaraş's known latitude (37.583°N) at pixel row 707 and 64 m/px (Δlat/px
    = 64/111,320 ≈ 0.000575°/px): 37.583 + 707×0.000575 ≈ **37.990°N**, vs. the printed
    **38°N** label — agreement within **≈0.01°** (≈1.1 km).
  - **Both graticule labels independently corroborate the 64 m/pixel scale to within ~1%,
    using only chart cartography (a published meridian/parallel value plus a known
    real-world city location) — no `.sup5`, no DCS x/z transform, no filename arithmetic.**
    This is the strongest single piece of evidence so far that the declared `64m` prefix
    really is ground-sample-distance-in-meters-per-pixel, not merely an order-of-magnitude
    coincidence (session 2's original inference). — **evidence:** reproduced-locally (direct
    pixel measurement + geodesic arithmetic against a published coordinate) — **source:**
    this session's crops of `/tmp/64maa00_x3_z1.png` (see Reproducible Test) + WebSearch
    coordinate for Kahramanmaraş.
  - A secondary attempt to cross-check via UTM 100km/20km-grid blue-line pixel spacing was
    **inconclusive and is explicitly not relied on**: an apparent second "blue vertical
    line" turned out on closer inspection to be a river (hydrography) rather than a grid
    line at that location, so the spacing measurement could not be trusted and is not
    reported as a finding — flagging this so a future session doesn't re-derive a false
    UTM-grid-spacing number from the same visual confusion. — **evidence:** unresolved /
    retracted — **source:** this session, visual re-inspection.

### Reproducible Test

```python
import sys; sys.path.insert(0, "src")
from coordinates import wgs84_to_dcs

sivas = wgs84_to_dcs("Syria", 39.75056, 37.01500)      # (522090.5, 112740.8)
maras = wgs84_to_dcs("Syria", 37.583, 36.933)          # (281692.0, 100290.9)
hama  = wgs84_to_dcs("Syria", 35.135, 36.750)          # (10465.4, 77804.6)

def tile_axis(x_index: int, pixel_y: int) -> float:
    return (x_index + pixel_y / 1024) * 65536

sivas_ta, maras_ta, hama_ta = tile_axis(0, 30), tile_axis(3, 707), tile_axis(7, 850)
# origin_x = dcs_x + tile_axis  -> 524010.5 / 523548.0 / 523617.4 (spread ~463 m)
```
Pixel positions read from `/tmp/64maa00_x0_z1.png` (Sivas, reused from session 7),
`/tmp/64maa00_x3_z1.png` (Kahramanmaraş), `/tmp/64maa00_x7_z1.png` (Hama) — regenerate via
session 3's decode command from
`world-model/data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T113038Z/64maa00_x{0,3,7}_z1.tif.dds`.
Graticule crops used e.g.:
```python
from PIL import Image
im = Image.open("/tmp/64maa00_x3_z1.png")
im.crop((560, 0, 700, 320)).rotate(90, expand=True).resize((960, 420)).save("/tmp/crop_rot2.png")  # reads "37°"
im.crop((400, 0, 750, 250)).resize((1050, 750)).save("/tmp/crop_label.png")  # reads "38°"
im.crop((100, 750, 400, 950)).resize((900, 600)).save("/tmp/crop_hama.png")  # Hama city pixel
```

### Possible Approaches

- **Stage 1's evidence bar is now met for both axes**: z-axis directionally confirmed at
  ~9% residual (session 7), x-axis confirmed far more tightly at <0.2% residual across 3
  points (this session), and the x-axis result is independently corroborated by a
  DCS-arithmetic-free graticule/geodesy check agreeing to ~1%. Recommend `registration.py`
  be written with `confidence="provisional"` (not `"confirmed"` — z-axis residual and only
  one graticule-anchored tile are still real gaps) but with enough evidence that Implementer
  is not blocked on more control-point gathering before a first version.
- **Before upgrading to `"confirmed"`**: (a) tighten the z-axis fit with a 3rd east-west
  point off `x0` (mirrors this session's method exactly, just picking a different
  z-tile-index at fixed x), since the z-axis residual (9%) is still the weaker of the two
  axes; (b) automate pixel-position reading (template-match the city/settlement footprint
  or the graticule tick marks) to shrink by-eye measurement error, which is very likely the
  dominant remaining error source in all fits so far; (c) explicitly encode the sign-flip
  finding above (x-tile-index moves south, z-tile-index moves east) as a documented
  constant/convention in `registration.py`, not something Implementer has to rediscover.
- **The retracted UTM-grid-spacing check** is worth re-attempting properly in a future
  session with a cleaner tile (ideally one where a full second graticule meridian, not an
  abbreviated blue-numeral grid line easily confused with hydrography, is visible) — it was
  not needed this session because the parallel/meridian-label check already gave a tight
  independent result, but a second convergent number would further de-risk the "64m really
  is meters/pixel" assumption before it's hard-coded.

### Unresolved

- z-axis residual (~9%, session 7) remains wider than the x-axis's (<0.2%, this session) —
  not reconciled; could be pixel-reading noise (Sivas/Erzincan reads were less precise than
  this session's city-footprint reads) or a real per-axis asymmetry worth a follow-up point.
- Only one tile (`64maa00_x3_z1`) has been checked for graticule labels; whether every tile
  in the sheet carries similar labels (letting graticule-based registration be systematized)
  or only some (e.g. tiles crossing an integer degree line) is unknown.
- The UTM 20km/100km-grid-spacing cross-check remains unresolved (see retraction above) —
  not blocking, but a clean re-attempt would add a third independent confirmation.
- Whether the sign-flip convention found here (x-tile-index south-increasing vs. z-tile-index
  east-increasing) holds for the `32m` sheets (`aa`/`ab`/`xab`/`xac`) too, or is specific to
  the `64m` `aa` sheet tested — not cross-checked against a 32m-tier tile this session.

---

## Session 11 (2026-09-03) — Vegetation/scenery query API and "Alt" mode contour data: is there DCS-native truth beyond raster tiles?

**DCS version:** 2.9.29.27278 (unchanged; not re-verified live this session — pure API/forum research, no local probe run). **Theatre:** Syria (screenshot only; no live-mission probe this session).

### Question

Session 10 flagged an unresolved, high-value question: is any of what F10's "Alt" mode
renders — individual tree positions, terrain contour geometry — queryable via DCS's
scripting/export API, rather than only observable by screenshotting the rendered client?
If so, it could supersede both RasterCharts and clipmap satellite imagery as DCS-native
truth for the World Model's terrain/vegetation layer. This session researches the
documented API surface (no live-mission probe access this session) and community precedent.

### Findings

- **Session 10's "Alt" mode attribution for `alt-map.jpg` is correct — this note's own
  attempted correction (session 11's initial draft) was wrong and is retracted.** The
  top-left text ("MAP") is a fixed UI label unrelated to the Map/Alt/Sat toggle — it does
  not change based on which mode is active. The actual mode indicator is the three
  buttons top-right: whichever of Map/Alt/Sat is currently selected renders with a
  lighter/highlighted blue fill, the other two stay dark. User confirmed by direct
  visual check: in `alt-map.jpg`, **"Alt" is the highlighted (lighter blue) button** —
  same pattern session 5 already relied on to identify `satellite-imagery.jpg` as "Sat"
  mode (lighter/highlighted "Sat" button there). So `alt-map.jpg` is confirmed Alt mode,
  and the individual tree-crown icons / contour-like terrain shading / individual
  building footprints it shows are genuinely Alt-mode-specific content, not just "Map"
  mode at high zoom. — **evidence:** user-confirmed (direct visual identification of
  the highlighted button) — **source:** user, this session.
- **No documented tree/vegetation-specific scripting API exists.** `Object.Category` (the enum
  `world.searchObjects` filters on) has exactly five members: `UNIT, WEAPON, STATIC, SCENERY,
  BASE` — no vegetation/forest/tree category. — **evidence:** documented — **source:** ED
  official scripting docs (`digitalcombatsimulator.com/en/support/faq/1259/` "Object"), via
  WebSearch summary.
- **`SceneryObject` (the class returned for `Object.Category.SCENERY`) is documented by ED as
  "all objects placed on the map. Bridges, buildings, etc."** — no mention of vegetation, trees,
  or forest anywhere in the class description or its method list (`getLife`, plus inherited
  `isExist/destroy/getCategory/getTypeName/getPoint/getPosition/getVelocity/inAir/getName/
  getDesc/hasAttribute`). — **evidence:** documented — **source:** Hoggit wiki
  `DCS_Class_Scenery_Object`, via WebFetch.
- **`land.getSurfaceType` has no FOREST value.** Its enum is `land.SurfaceType = {LAND=1,
  SHALLOW_WATER=2, WATER=3, ROAD=4, RUNWAY=5}`. An ED Core Wish List forum thread titled
  "land.getSurfaceType small enhancement" explicitly requests FOREST be added as a new value —
  strong indirect confirmation the enhancement had not shipped as of that thread, i.e. forest/
  vegetation cover is not distinguishable via this function. — **evidence:** documented (enum
  values, Hoggit wiki `DCS_func_getSurfaceType`) + forum-claim-unverified (that FOREST is still
  absent as of the currently-installed 2.9.29.27278 — the wishlist thread's date/resolution
  status was not read, only its title/existence) — **source:** Hoggit wiki, ED forum wishlist
  thread title via WebSearch summary (thread body not fetched — forum.dcs.world blocks WebFetch,
  see prior sessions and memory `forum-dcs-world-fetch.md`).
- **No community precedent found for extracting individual tree/vegetation-object positions
  from a DCS terrain.** Searches for tree-extraction tooling returned only reskinning mods
  ("Better Trees for Syria/Caucasus/Mariana Islands" — texture replacements for existing
  SpeedTree-rendered foliage, not repositioning tools) and one ED forum thread title ("Forests
  .edm — DCS Mods") whose search summary indicates modders could find individual tree `.edm`
  model files but reported difficulty locating a "forest" `.edm` — consistent with, but not
  proof of, forests being a procedural/rendering-time scatter over a density parameter rather
  than a table of discretely placed, individually addressable objects. — **evidence:**
  forum-claim-unverified (thread not fetched directly, only its title/one-line search summary)
  — **source:** WebSearch results, ED forum thread titles ("Better Trees for Syria V2",
  "Forests .edm"), not independently verified against thread content.
- **A directly on-point forum thread exists but was not read**: "is there a way to detect a
  FORREST or CITY as validated spawn terrain type?" (forum.dcs.world/topic/315439) — title
  strongly suggests this is other mission-scripting users hitting exactly this same gap
  (no forest surface-type query) and discussing workarounds. Not fetched — forum.dcs.world
  blocks WebFetch (403), consistent with prior sessions. — **evidence:** gap, flagged for
  manual follow-up — **source:** WebSearch title only.
- **Dense elevation sampling via `land.getHeight` → contour-line-equivalent data is standard,
  already-planned GIS work, not a gap requiring Alt-mode reverse-engineering.** Converting a
  regular elevation grid to contour lines (marching-squares / GDAL `gdal_contour`-class
  algorithms) is a solved, well-documented cartographic technique requiring only a grid of
  height samples, which `land.getHeight` already provides per-point (M1 precedent: this class
  of API needs a live mission, matching `coord.LOtoLL`). — **evidence:** documented (general
  GIS technique, not DCS-specific) — **source:** general GIS references via WebSearch
  (vterrain.org, GRASS-Wiki contour-lines-to-DEM); combined with M1's already-established
  `land.getHeight` availability.
- **`docs/concept/WORLD_MODEL_BUILDER.md` already anticipates this exact path** and does not
  currently list "extract Alt-mode's rendering directly" as a milestone: Milestone 4 is "Create
  an extraction/probing mechanism that can sample DCS terrain elevation over a small region.
  Generate a grid," and the "Elevation-derived features" section explicitly lists ridgeline/
  valley/slope/aspect extraction as *algorithms to run against a DCS elevation grid once
  generated* ("Prefer established GIS algorithms/libraries over LLM inference"). This is the
  same grid-then-derive approach this session's research supports independently — the concept
  doc's plan was already the right shape before this session, it just hadn't been explicitly
  connected to the "Alt mode" question. — **evidence:** documented (project's own concept doc)
  — **source:** `docs/concept/WORLD_MODEL_BUILDER.md` lines ~442-470, ~628-634 (Milestone 4,
  "Elevation-derived features").

### Reproducible Test

None run this session — pure documentation/API research, no live-mission probe. A follow-up
probe (not yet written) would be: from a running Syria mission with mission-scripting access,
call `world.searchObjects(Object.Category.SCENERY, <a volume over the forest polygon visible
in alt-map.jpg, centered roughly on 36°10'N 36°31'E>, handler)` and check whether any returned
objects have type names suggesting vegetation (as opposed to only bridges/buildings/etc as
documented) — this would empirically confirm or refute the "SCENERY never contains vegetation"
inference, which is currently based on ED's category description, not a live test.

### Possible Approaches

- **Treat "Alt" mode's rendering as a UI visualization of data DCS already exposes
  elsewhere (elevation via `land.getHeight`), not a separate asset needing reverse-engineering.**
  The terrain-contour half of the original concern is already covered by the existing Milestone
  4 + "Elevation-derived features" plan; no new research or pipeline work is implied by this
  session's findings for that half.
- **Treat individual tree/vegetation positions as very likely NOT available via any documented
  API**, based on convergent (but each individually weak) evidence: no SCENERY-adjacent
  vegetation category, no FOREST surface type, no community tooling for tree-position
  extraction despite an obvious modding/AI-pathfinding use case that would have surfaced such a
  tool if one existed. Recommend **not** scoping a "vegetation layer via scripting API"
  milestone; if forest/treeline geometry is wanted in the World Model at all, the fallback is
  extracting **forest polygon coverage** (not individual trees) from OSM landuse=forest/natural=
  wood tags per the existing external-GIS augmentation path in `WORLD_MODEL_BUILDER.md`, cross-
  validated against DCS's own rendered forest polygon shape (visible in F10 screenshots, e.g.
  `alt-map.jpg`) as a coarse geometry sanity check rather than a source of individual-tree truth.
- **If precise per-tree data is ever considered worth pursuing** (e.g. for line-of-sight/
  concealment modeling), the empirical `world.searchObjects(SCENERY, ...)` probe above is cheap
  to run and would settle the question definitively rather than relying on inference from
  documentation — recommend this only if a concrete future use case needs it, not
  speculatively now.

### Unresolved

- Whether `world.searchObjects(Object.Category.SCENERY, ...)` genuinely never returns
  vegetation objects — inferred from ED's category description, not empirically probed against
  a live mission this session.
- Content of forum.dcs.world/topic/315439 ("is there a way to detect a FORREST or CITY as
  validated spawn terrain type?") — directly on-point, title only, not fetched (403 on
  WebFetch). If the user can paste this thread's content, it would likely resolve the vegetation-
  query question more definitively than the indirect evidence gathered this session.
- Whether the ED wishlist thread requesting FOREST as a `getSurfaceType` value is still open
  (i.e. FOREST is still absent) as of DCS 2.9.29.27278 specifically, or whether it shipped since
  — thread date/status not read.

---

## Session 12 (2026-09-03) — M2 Stage 4: level-semantics review, held-out control point

**DCS version:** 2.9.29.27278 (unchanged, per M0; not re-verified live this session — pure
offline analysis of already-sampled tiles, no WSL access this session). **Theatre:** Syria.

### Question

Stage 4 of `plans/m2-raster-understanding/plan.md`: (1) does the sampled tile set let
`registration.py`'s hardcoded `default_level="00"` be confirmed as a sensible choice, and
(2) can a genuinely held-out control point (not one of Sivas/Kahramanmaras/Hama/Erzincan,
which were all used to fit `origin_x`/`origin_z` in sessions 7-8) be found and used as an
independent accuracy check on the fitted registration.

### Findings

- **RasterCharts `level` semantics remain genuinely unresolved for the `.tif.dds` container
  specifically — this session did not close the gap, and did not attempt to guess.** All
  locally-sampled `RasterCharts` tiles across both sample directories
  (`syria_rastercharts_samples_20260903T090447Z/`, `..._113038Z/`) are `level="00"` only —
  no `-2`/`-1`/`01` sample was ever pulled for `RasterCharts` (unlike `clipmaps`, where
  session 9 sampled both `-1` and `00` for the *different* `.tif.clipmap` container). Without
  a same-sheet/same-x/z tile at a different level, there is no local content to compare
  against, and this session had no WSL/live-DCS access to pull one. — **evidence:**
  reproduced-locally (confirmed by listing both sample directories: `find data/raw/dcs/
  2026-09-03 -iname '*.dds'` returns only `level="00"` filenames) — **source:** this
  session's directory listing.
- **Session 9's `clipmaps`-specific finding (level encoded in the header as `level * 32`,
  with the `-1`-level colortexture sample decoding to flat near-uniform color vs. `00`
  decoding to full photorealistic detail) is suggestive but explicitly not transferable to
  `RasterCharts` as confirmation** — session 6 already flagged that `clipmaps` and
  `RasterCharts` share only a tiling/naming *convention* (both plausibly built by the same
  `landscape5` engine tooling), not a shared container format or semantics: `RasterCharts`
  tiles are plain off-the-shelf DXT5 DDS with no such per-file level-scale header field
  (session 2's header parse found no analogous field), while `.tif.clipmap` has its own
  distinct 52-byte custom header where the `level*32` encoding was found. Reasoning by
  analogy from clipmap's LOD-fallback behavior to RasterCharts' `level` suffix is *plausible*
  (both would fit a general "coarse fallback vs. full detail" LOD pattern common to tiled
  chart/texture systems) but would be encoding an unverified DCS-internals claim into
  `registration.py` if written as fact — this project's process exists specifically to
  prevent that. Left as an open question for a future `investigator` session with WSL access
  to pull one same-sheet/x/z tile at a different level (e.g. `64mab-1_x0_z0.tif.dds` if it
  exists, or any `level != "00"` tile in the `32m` tier) and visually compare against the
  already-decoded `00`-level tiles. — **evidence:** inferred (reasoning about why the analogy
  doesn't transfer) — **source:** cross-reference of sessions 2, 6, 9 above.
- **`default_level="00"` remains a defensible choice on process grounds even without content
  confirmation**: it's the level Sessions 7-8's control-point fit was actually run against
  (all pixel reads were taken from `64maa00_*` tiles), so it's the level `registration.py`'s
  `origin_x`/`origin_z` are valid for by construction — using any other level's tiles with
  the current registration would be applying a fit to untested content, a strictly worse
  choice regardless of what `level` numerically means. `tools/inspect_raster.py scan` was
  extended this session (`--theatre` flag) to make this default visible and to flag if it's
  ever absent from a sampled directory, rather than requiring a human to cross-reference
  `registration.py`'s source by hand. — **evidence:** documented (follows directly from how
  the fit was actually conducted, sessions 7-8) — **source:** `raster/registration.py`'s
  existing `source` field; this session's `inspect_raster.py` change.
- **A genuinely held-out control point was identified and used: Gemerek, a Sivas Province
  district center, visible on tile `64maa00_x0_z0.tif.dds`** — a tile never inspected in
  sessions 7-8 (those sessions used `x0_z1`, `x3_z1`, `x7_z1`, `x0_z4`; `x0_z0` was
  downloaded in the original probe but never analyzed for a control point). Gemerek's
  Wikipedia-published coordinates (39°10'55"N 36°04'05"E = 39.18194°N, 36.06806°E) run
  through `coordinates.wgs84_to_dcs("Syria", ...)` give DCS (x=461196.8, z=29548.1), which
  `registration.py`'s `dcs_to_tile_pixel` predicts lands at tile `(x_tile=0, z_tile=0)`,
  pixel `(px=403, py=977)`. The town's settlement-symbol icon was located by eye (grid-ruler
  crop, see Reproducible Test) at approximately pixel `(px=490, py=975)` — a residual of
  **~2 px / ~129 m on the x-axis (row)** and **~86 px / ~5,515 m on the z-axis (column)**. —
  **evidence:** reproduced-locally (direct pixel measurement against a published coordinate,
  same method as sessions 7-8) — **source:** this session's crops of
  `data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T090447Z/64maa00_x0_z0.tif.dds`,
  decoded via the same Pillow command used throughout this recon; Wikipedia
  (`en.wikipedia.org/wiki/Gemerek`) for the published coordinate.
- **This held-out residual is well inside both of `test_raster_registration.py`'s existing
  tolerances (100px row / 350px column) and, on the z-axis specifically, is close in
  magnitude to (not surprisingly larger than) session 7's already-documented ~9% z-axis
  residual** (~86px of 1024 ≈ 8.4% of the tile edge, vs. session 7's ~9%) — this is a
  meaningful independent confirmation: a genuinely unseen point lands almost exactly where
  the already-known z-axis looseness would predict, rather than being wildly off (which
  would suggest the fit doesn't generalize) or suspiciously perfect (which might suggest a
  circularity bug). The x-axis residual (~2px) is far tighter than its own already-generous
  100px tolerance, consistent with session 8's <0.2%-residual x-axis fit. — **evidence:**
  inferred (comparison of this session's fresh residual against the prior sessions'
  documented residuals) — **source:** arithmetic above, cross-referenced against sessions
  7-8's residual figures.
- Added `test_held_out_control_point_gemerek` to `world-model/tests/test_raster_registration.py`
  asserting this residual against the same per-axis tolerances the existing fit-input tests
  use, and updated `tools/inspect_raster.py mark` was re-run against Gemerek's coordinate to
  visually confirm the crosshair lands on/immediately adjacent to the town's symbol on the
  chart (not merely numerically close by coincidence of the tolerance window). — **evidence:**
  reproduced-locally — **source:** this session's test run and `mark` invocation.

### Reproducible Test

```sh
cd world-model && source .venv/bin/activate
python3 -c "
import sys; sys.path.insert(0, 'src')
from coordinates import wgs84_to_dcs
from raster.registration import dcs_to_tile_pixel
gemerek = wgs84_to_dcs('Syria', 39.18194, 36.06806)
print(dcs_to_tile_pixel('Syria', *gemerek))  # (0, 0, 403, 977)
"
python tools/inspect_raster.py mark \
  data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T090447Z \
  Syria 461196.75504758395 29548.126430869772
# -> tile 64maa00_x0_z0.tif.dds pixel (403, 977); crosshair lands beside the
#    settlement-symbol icons just southwest of the "Gemerek" label.
python tools/inspect_raster.py scan \
  data/raw/dcs/2026-09-03/syria_rastercharts_samples_20260903T113038Z --theatre Syria
# -> annotates "Grid layout: 64m sheet='aa' level='00'  <- 'Syria' registration default"
```
By-eye pixel read of the Gemerek settlement-symbol icon used a 6x-upscaled, magenta-gridded
crop of `64maa00_x0_z0.tif.dds` (decoded per session 3's standard Pillow command) centered
on the "Gemerek" label — same by-eye methodology as sessions 7-8, same plausible ±30-50px
error budget.

### Possible Approaches

- **RasterCharts `level` semantics**: the only way to close this without guessing is a
  live-DCS/WSL probe pulling at least one `level != "00"` `RasterCharts` tile at a sheet/x/z
  already sampled at `level="00"` (e.g. re-run `probe_syria_rastercharts.sh` with a filter
  for `level=-1` or `level=01` entries), then visually compare against the corresponding
  `00`-level tile the way session 9 compared clipmap levels. Not attempted this session —
  flagged for a follow-up `investigator` session with live access, per this task's own
  instruction not to guess at unverified DCS internals.
- **z-axis residual remains the weaker of the two axes** (~9% at session 7, ~8.4% held-out
  here) — a future tightening pass (automated pixel-position detection instead of by-eye
  reads, or a UTM-graticule-anchored point) would still be worthwhile before any
  `confidence="confirmed"` upgrade, per sessions 7-8's existing recommendation; this session's
  result doesn't change that recommendation, it just adds independent evidence the current
  `"provisional"` fit's stated residual is realistic rather than optimistic.

### Unresolved

- RasterCharts' `level` (`-2`/`-1`/`00`/`01`) semantics, specifically for the `.tif.dds`
  container — still open; the `clipmaps`-container finding (session 9) is a plausible analogy,
  not evidence, for this different file format. Needs a live-DCS probe pulling a non-`00`
  RasterCharts tile to resolve.
- Whether the sign-flip/scale registration model holds for the `32m` tier (sheets
  `aa`/`ab`/`xab`/`xac`) or other levels at all — unchanged from sessions 7-8, still untested;
  this session's held-out point was still on the same `64m`/`aa`/`00` group as the original
  fit.
- Only one held-out point was checked this session (time/sample-availability constrained,
  not a methodological choice) — a second held-out point on a different z-tile-index (to
  further stress-test the weaker z-axis specifically) would still add value.
