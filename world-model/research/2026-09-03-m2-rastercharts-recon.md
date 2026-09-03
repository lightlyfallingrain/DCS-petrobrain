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
