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
  order of magnitude for the full Syria theatre's known extent (~500–600 km), a
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
  chart series, session 3) with its own datum/registration. If confirmed, this asset
  would fit root `CLAUDE.md`'s "DCS geometry is always authoritative" invariant more
  cleanly than `RasterCharts` does. — **evidence:** inferred / unresolved — **source:**
  user screenshot; no filesystem or content evidence yet.

**Scope implication surfaced to user:** whether satellite imagery is the better
truth-layer raster target (vs. RasterCharts' independent chart geodesy) was raised as an
open architectural question. User's decision: **pursue both tracks in parallel** —
continue validating RasterCharts' registration hypothesis (per the existing M2 plan)
while also tasking Investigator to locate and probe the satellite-imagery asset.
