# MI-B4 — Raster chart viewer: DCS RasterCharts as a pan/zoom map on the LAN

- [ ] **MI-B4 — Serve each terrain module's RasterCharts as a standard tiled map, zoom and pan in
  a browser, from a server on the Windows DCS machine, readable from any device on the LAN. One
  more standalone service, independent of every other one.** #status/open Filed 2026-11-16 by
  user direction.

  **The request, in the user's words:**

  > *"Terrain modules contain raster charts. `<terrainName>/RasterCharts/rasterCharts.zip`, except
  > Caucasus which has different structure. The chart files are .tif.dds files. I want those raster
  > charts exposed via a local server to local network. Standard map tile stuff, a map I can zoom
  > and pan. Server will have to run on windows, because the raster charts are in DCS, but I can
  > then open the web page on any device on LAN."*
  >
  > *"This would be one more service that is independent of the other ones we have. Prefer simple
  > solution and existing solutions and components. You are welcome to suggest existing libraries
  > or application that achieve this or part of this. The less we have to implement, the better."*

  **Why (inferred, not stated by the user):** the crew's paper chart, on a tablet or a second
  screen, before or during a sortie. No Petrovich behaviour depends on it, so goal-aligner and
  plan-aligner have nothing to check here.

  ## What is already known — WM-M2 did the reconnaissance

  [[WM-M2]] read Syria's RasterCharts in full. Sources: `world-model/research/2026-09-03-m2-rastercharts-recon.md`,
  `notes/raster-charts-and-registration.md`, `world-model/src/raster/`.

  - **Layout, Syria:** one `rasterCharts.zip`, 1280 entries, named
    `{32|64}m{sheet}{level}_x{0-7}_z{0-7}.tif.dds`. 32m: 4 sheets (`aa`, `ab`, `xab`, `xac`) × 4
    levels (`-2`, `-1`, `00`, `01`) × an 8×8 grid. 64m: 2 sheets × 2 levels × 8×8. No gaps.
    Afghanistan, Kola and Marianas follow the same single-archive pattern; Caucasus has
    `RasterCharts/{0.25M,0.5M,1M,2M,5M}/` with many small per-tile `.zip`s.
  - **Format:** every sampled tile is a 1024×1024 DDS, DXT5/BC3, 11 mipmaps, written by NVIDIA
    Texture Tools. `file(1)` mislabels it "DX10". **Pillow decodes it**: proven in the same
    research with `Image.open(...).convert('RGB')`, and Pillow is already a world-model dependency.
  - **Content:** scanned real-world 1:250k military charts with a printed UTM grid.
  - **Axes:** z-tile index grows east, x-tile index grows **south**. A viewer that puts `x` on the
    vertical axis top-down gets this right for free; the sign flip only matters for DCS coordinates.
  - **Georeferencing:** `world-model/src/raster/registration.py` maps tile pixels to DCS x/z for
    Syria `64maa00` only, `confidence="provisional"`, ~5.5 km z-axis error at a held-out point. Not
    needed for a pan/zoom viewer; relevant only if coordinates or markers are ever overlaid.

  **Unverified, and it decides the zoom design:** the sheet letters look like a **column** index
  and `level` like a **row** index, which would make each scale tier one big square mosaic rather
  than "levels of detail". The arithmetic agrees: a 32m sheet is 8 × 1024 px × 32 m ≈ 262 km, so
  4 × 4 sheets ≈ 1048 km; a 64m sheet ≈ 524 km, so 2 × 2 sheets ≈ 1048 km. Same extent, two
  different chart scales, the way a real crew switches from a 1:500k to a 1:250k sheet. Decoding
  the four corner tiles of two adjacent sheets confirms or kills it in minutes.

  ## Recommended shape — a build step and a static site, no tile server code

  The tiles are already a regular grid of fixed-size images. So nothing needs to run per request:

  1. **Build, once per theatre, on Windows.** A short Python script opens the zip, decodes each
     `.tif.dds` with Pillow, writes it as a JPEG/WebP tile at the native zoom, and builds the
     coarser zooms by 2×2 downsampling. Output is a plain `{z}/{x}/{y}` directory per theatre and
     tier. Minutes of run time; output size is unmeasured, plausibly a few hundred MB per theatre.
  2. **View.** One static HTML page with **Leaflet** in `L.CRS.Simple` mode (pixel space, no
     projection), a theatre picker, and the 64m tier as an optional layer. Leaflet is vendored next
     to the page so a LAN device needs no internet.
  3. **Serve.** Any static file server bound to `0.0.0.0`. Python's own `http.server` is enough
     for one user. Windows Firewall will ask once.

  **Existing components, and what each would save:**

  | need | recommended | alternative | licence |
  |---|---|---|---|
  | decode DXT5 DDS | Pillow, already proven on these tiles | Microsoft `texconv`, ImageMagick | HPND / MIT / Apache |
  | build the zoom pyramid | ~50 lines over Pillow | `vips dzsave` writes the whole pyramid in one command, but it is a new Windows install | — / LGPL-2.1 |
  | pan/zoom page | Leaflet with `CRS.Simple`, room for overlays later | OpenSeadragon, zero code when paired with `dzsave` | BSD-2 / BSD-3 |
  | serve on the LAN | `python -m http.server --bind 0.0.0.0` | any static server, e.g. Caddy | PSF / Apache |

  **Not recommended:** TileServer GL, MapTiler Server or GeoServer. They expect georeferenced
  MBTiles or vector data and bring a runtime for what is a folder of images. GDAL `gdal2tiles` would
  work in `--profile=raster` mode but is a heavy Windows install for no gain over Pillow. Every
  licence above is compatible with the project's CC BY-NC-SA intent; none is GPL.

  ## Constraints

  - **The chart images belong to Eagle Dynamics.** Generated tiles go to a gitignored output
    directory and are never committed or published. LAN only.
  - **Runs on its own** (root `CLAUDE.md`, "Module independence"). Own venv, no import from
    world-model. The filename grammar is one regex, so copy it with a pointer to
    `world-model/src/raster/__init__.py` rather than importing it. Where the code lives under
    `mission-interpreter/` is a plan-time decision.
  - **Theatre layouts differ.** Read layouts through one small per-theatre adapter. Syria first,
    because it is the only one decoded so far. Caucasus needs its own adapter. Theatres newer than
    the 2026-09 listing are unchecked.

  ## Open questions for plan time

  1. Is the column/row reading above right? Settles how the 32m and 64m tiers stack.
  2. Which theatres beyond Syria are wanted in the first cut?
  3. Overlays — DCS grid, lat/long, the player's own marks — are out of scope for the first cut.
     Leaflet is the recommended viewer partly so they stay cheap later.
