---
name: project-m2-rastercharts
description: Syria RasterCharts layout, tile format (DXT5 DDS), .sup5 structure, and registration hypothesis — Stage 0 probe run and analyzed 2026-09-03
metadata:
  type: project
---

**Stage 0 probe results (2026-09-03, session 2):** `rasterCharts.zip` = 1280 tiles,
`{32|64}m{sheet}{level}_x{0-7}_z{0-7}.tif.dds`, sheet ∈ {aa,ab,xab,xac}, level ∈
{-2,-1,00,01}. 32m: all 4 sheets × all 4 levels (1024 tiles). 64m: only sheets
{aa,xab} × levels {-1,00} (256 tiles). Tiles are plain **DXT5/BC3 DDS** (standard
128-byte header, NO DX10 extended header) — `file(1)` reporting "DX10" is WRONG,
don't trust it for DDS; parse the header directly (fourCC at offset 84). 1024x1024,
11 mipmaps, built with NVIDIA Texture Tools (tag in header's reserved bytes).
`.sup5` (615,216 bytes) starts with a generic ED serialization pattern: numeric
header then a length-prefixed string `landscape5::sup5File` — looks like a
type-tag from a general engine serialization routine, not a bespoke format. No
clean integer division of file size against tile/group counts at any header-size
guess — suggests variable-length (per-tile-name-string) records, not a fixed
struct array. Only first 64 bytes were dumped; full-file dump still needed.
**Registration hypothesis (untested):** tile edge in DCS x/z meters = scale_prefix
× 1024px (32,768m or 65,536m); an 8×8 sheet at 64m ≈ 524km/side, order-of-magnitude
match for Syria's full theatre extent — plausible but NOT pixel-verified (no DDS
decoder available locally this session). Full findings:
`world-model/research/2026-09-03-m2-rastercharts-recon.md` (session 2 section).

Syria's `Mods/terrains/Syria/RasterCharts/` contains exactly two files: `rasterCharts.sup5` +
`rasterCharts.zip` — a single archive, no scale-tiered subdirectories. Confirmed via
`world-model/data/raw/dcs/2026-09-02/DCS-files.txt` (a real recursive filesystem listing from the
M0 probe against the actual DCS 2.9.29.27278 install), not inference. Afghanistan/Kola/MarianaIslands
match this same single-archive pattern.

Caucasus is structurally different: `RasterCharts/{0.25M,0.5M,1M,2M,5M}/` each hold many small
per-tile zips named like `16m_AA00.zip`, `128mxAB-1.zip` (grid-cell-code + signed row suffix,
leading number plausibly a scale/GSD in meters — inferred from naming only, not verified). Don't
assume Syria's simple layout generalizes if the pipeline later covers a tiled theatre.

`.sup5` file format is undocumented in every source checked (ED forum thread
`forum.dcs.world/topic/226463-` asks the same question but returned HTTP 403 to WebFetch —
likely bot/UA blocking of forum.dcs.world in general, worth remembering for future sessions).
Do not confuse `RasterCharts/rasterCharts.sup5` with the separate `Map/<Terrain>.sup5` /
`Surface/<Terrain>.surface5` terrain-mesh files — different subsystem, same extension pattern.

No community tool was found (via plain web search only — GitHub code search API was
unauthenticated/blocked, 401/403) that parses RasterCharts directly; DCS moving-map projects
(Tacview "DCS Satellite Tiles", Bergison's, DCS LIVE Moving Map) appear to source their own basemap
imagery instead. Weak/negative finding — worth a real GitHub code search with proper auth before
concluding no prior art exists.

`forum.dcs.world/topic/292399-raster-charts-for-terrain-mod/` (WebFetch blocked, 403) turned out,
per the user pasting its actual text, to be about sourcing imagery for *building new* custom
terrain mods (FAA sectionals via QGIS) — NOT about ED's shipped RasterCharts format/registration.
Don't re-fetch expecting an answer there. `forum.dcs.world/topic/226463-` (the .sup5 thread) is a
separate, still-unread thread — don't conflate the two.

Full findings + recommended probe: `world-model/research/2026-09-03-m2-rastercharts-recon.md` and
`world-model/tools/wsl/probe_syria_rastercharts.sh` (unzip -l + sup5 header hexdump + sample tile
extraction — not yet run against the live install).

Reading RasterCharts needs only filesystem access, no live-mission Mission Scripting escape hatch
(unlike M1's `coord.LOtoLL`) — see [[project_syria_projection]].
