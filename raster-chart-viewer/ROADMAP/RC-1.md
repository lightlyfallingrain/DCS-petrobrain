# RC-1 — Raster chart viewer: DCS RasterCharts as a pan/zoom map on the LAN

- [~] **RC-1 — Serve each terrain module's RasterCharts as a standard tiled map, zoom and pan in
  a browser, from a server on the Windows DCS machine, readable from any device on the LAN. One
  more standalone service, independent of every other one.** #status/in-progress #needs-flight
  Filed 2026-11-16 by user direction. **Planning started 2026-11-16 on `feature/raster-chart-viewer`**; plan:
  `plans/raster-chart-viewer/plan.md`.

  **DoD-PASSED 2026-11-16 for Stages 1-6** (`plans/raster-chart-viewer/dod-check.md`, tip
  `91e2296c4236164633624121b0d587e4bac92b0a`); **merged to `main` 2026-11-16 as `f00ac0c3`** per root
  `CLAUDE.md`'s auto-merge workflow. **Branch to fly after merge: `main`.** Stage 7 — the user's
  own live LAN check on the Windows box — has not been flown; this entry stays `[~]`/
  `#status/in-progress` until it is. What Stage 7 must verify (full detail and run instructions:
  `raster-chart-viewer/README.md`, "Stage 7 — the live check"):

  - **Syria (both tiers, 32m/64m) and Caucasus** pan/zoom continuous, not scrambled — settles U3
    (the sheet-mosaic convention, measured on Syria only, generalised to every terrain).
  - **Afghanistan, Kola, Mariana Islands** (incl. Mariana's "unscaled" tier, U2) — a quick look;
    a scrambled terrain is a follow-up to file, not a blocker (U3's own answer).
  - **The first fully-zoomed-out view of a tier** is fast once Stage 6's background warm-up has
    had a few seconds — the one slow path the whole cache design exists to hide.
  - **No DCS session needed** — pausing/closing the mission, or not having one running, makes no
    difference, since the service reads only installed files.

  Record the result (which terrains/tiers looked right, which didn't, and the warm-up timing) on
  this entry, and clear `#needs-flight` once flown — naming which sortie/session cleared it.

  **Acceptance card:** https://claude.ai/artifact/21AkKixYQcXaLDKfnbRSvN (source:
  `docs/acceptance/2026-11-16-raster-chart-viewer-rc1-stage7-sortie.md`).

  **Moved here from [[MI-B4]] on 2026-11-16, user direction:** *"move the backlog item for the
  chart viewer to a proper ROADMAP folder structure under the chart viewer sub-project. Let's
  treat it as a proper sub module of Petrobrain."* The text below is MI-B4's, unchanged apart
  from this note and the ID; where it says "MI-B4" it means this entry. It takes a new ID because
  an ID belongs to one directory's sequence (root `CLAUDE.md`, "Backlog Management"), and it is a
  milestone here rather than a backlog item because it is this subproject's first deliverable.

  **Scope set 2026-11-16 (user):** *"All terrains except Caucasus follow the same structure, as far
  as I know. Therefore, the same code should work on all terrains, except Caucasus which needs a
  special case. Do this so that any terrain folder that is on disk can be opened."*

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

  **Sheet mosaic — measured 2026-11-16, and it reversed the guess first written here.** This entry
  first guessed that the sheet letters were the column and the level the row. Edge matching on
  every Syria sheet showed the opposite: **the level is the column, increasing east, and the
  letters are a signed row index increasing north** (ab = +1, aa = 0, xab = −1, xac = −2). Each
  scale tier is one big mosaic, and Syria's 32m and 64m tiers cover the same ground as two
  different chart series. All terrains, naming variants, sparse sheets and timings:
  `raster-chart-viewer/research/2026-11-16-rastercharts-all-terrains-recon.md`.

  ## Direction so far — user, 2026-11-16

  Three answers, in order, each narrowing the shape:

  > *"what if we took the OpenSeadragon route. I'm ok installing libvips."*
  >
  > *"Would it be feasible to extract files on the fly, as needed and then cache them to temp
  > folder? Just so that we would not need to extact many gigabytes of images to just sit on disk.
  > I'd rather it happen as needed and then the temp folder gets wiped occasionally (by OS)."*
  >
  > *"I'll be running it from WSL (bash), so linux tools ok."*

  The first version of this entry recommended a pre-rendered static site with Leaflet. Those
  answers replace it: **OpenSeadragon as the viewer, tiles made on demand, a temp-folder cache.**
  On-demand tiles also drop libvips — its only job, building the pyramid ahead of time, goes away.

  ## Recommended shape — one small on-demand tile server

  ```mermaid
  flowchart LR
    B[OpenSeadragon page, any LAN device] -->|GET tile| S[Python + Pillow server]
    S -->|hit| C[(temp cache, size-capped)]
    S -->|miss| Z[rasterCharts.zip]
    Z -->|read one entry, pick mipmap, decode| S
    S -->|write JPEG| C
  ```

  1. **Viewer.** One HTML page, OpenSeadragon vendored next to it so a LAN device needs no
     internet. A custom tile source points at the server; a theatre picker and a 32m/64m tier
     switch. Pinch zoom and a navigator minimap come built in.
  2. **Tile requests map straight onto the source grid**, because the source is already a regular
     grid of 1024 px tiles with mipmaps. At native zoom one view tile is one DDS tile. Each step
     out, one view tile covers 2×2 more source tiles, each read at the next mipmap down. So **every
     zoom level touches each zip entry at most once in total**, and no zoom level ever decodes more
     than it shows.
  3. **Reading a mipmap.** Pillow's DDS plugin returns only the base image. The smaller mipmaps sit
     at computable offsets after it (DXT5: 16 bytes per 4×4 block, halving per level), and Pillow's
     own BCn decoder — the one the DDS plugin itself uses — decodes a slice handed to it. About ten
     lines; check the decoder's call signature against the installed Pillow at plan time.
  4. **Cache.** Encoded JPEG tiles go to a temp folder keyed by theatre/tier/level/x/y. **The
     server caps the folder itself** and drops the oldest tiles at startup: Windows clears `%TEMP%`
     only when Storage Sense is on or Disk Cleanup runs, never on reboot, so "the OS wipes it" does
     not hold on its own. The cap is a constant with a stated default.
  5. **Inflate each zip entry once, and keep every mipmap it yields.** Every entry is deflated
     (measured below), so even the smallest mipmap costs inflating the whole ~1.4 MB entry. The
     mipmaps sit *after* the base image, so there is no shortcut to them. When the server inflates
     an entry for any reason, it caches the small mipmaps of that tile too, not only the one it was
     asked for. They add about a third of the base image and are tiny as JPEG. Without that, each
     zoom level would inflate the whole tier again on its first view, about five times over.
  6. **The one slow moment is the first fully-zoomed-out view of a tier**: its single tile needs
     all 1024 entries of that tier, about 0.5 GB read and inflated. Estimated at seconds, not
     measured, and cached after. If it feels slow, a background warm-up at server start can inflate
     a tier once and keep only the small mipmaps.

  **Running it from WSL — follow aircraft-layer's precedent, not a native Linux process.**
  `aircraft-layer/WORKFLOW.md` already settled this for a LAN-facing server on the same machine:
  WSL bash launches **Windows** `python.exe`, so the process binds the Windows network interface
  and needs one firewall rule, exactly like the telemetry API on 7791. A native Linux Python in
  WSL2's default NAT networking is reachable from Windows itself but **not from the rest of the
  LAN** without `networkingMode=mirrored` or a `netsh portproxy` — configuration that WORKFLOW.md
  already judged not worth it. It also keeps the zip read on the Windows filesystem rather than
  through WSL's slower `/mnt/c` bridge. Linux tools stay useful around it: `unzip -v` for the
  check below, and the probe-script conventions in `world-model/tools/wsl/` (`DCS_INSTALL_PATH`,
  `to_wsl_path`). **Found 2026-11-16: Windows `python.exe` is 3.14.7 with no Pillow**, so this
  route needs a Windows-side venv with Pillow. Reading the zip from WSL over `/mnt/f` measured
  16 ms per entry warm and 115 ms cold, which native Windows I/O should beat.

  **Existing components:**

  | need | use | licence |
  |---|---|---|
  | pan/zoom viewer | OpenSeadragon, custom tile source | BSD-3 |
  | decode DXT5, incl. mipmaps | Pillow (proven on these tiles; base image via its DDS plugin, mipmaps via its BCn decoder) | HPND |
  | serve | Python stdlib `http.server` (`ThreadingHTTPServer`), run as Windows `python.exe` | PSF |
  | read the archive | Python stdlib `zipfile` | PSF |

  No libvips, GDAL or tile-server product. Nothing above is GPL, so all of it fits the project's
  CC BY-NC-SA intent.

  ## Checks before planning — on the DCS machine, from WSL

  ```sh
  ZIP="/mnt/c/<DCS install>/Mods/terrains/Syria/RasterCharts/rasterCharts.zip"
  unzip -v "$ZIP" | tail -1                                   # raw total, zipped total, ratio
  unzip -v "$ZIP" | grep -c ' Stored '; unzip -v "$ZIP" | grep -c ' Defl:'
  ```

  The last line counts entries by method. **`Stored`** means a mipmap is one seek away and the
  zoomed-out first load is fast. **`Defl:*`** means each read inflates the whole ~1.4 MB entry
  first: still workable, slower on that first load. The middle line gives the real raw and zipped
  totals.

  **Result, Syria, run by the user 2026-11-16:**

  ```
  1789767680         648198619  64%                            1280 files
  0
  1280
  ```

  - **All 1280 entries are deflated, none stored.** Hence step 5 above: inflate an entry once and
    keep every mipmap it yields.
  - **Raw total is 1,789,767,680 bytes, exactly 1280 × 1,398,256.** That is the size of one
    1024×1024 DXT5 tile with its full mipmap chain. So every entry in the archive has the same
    format, not only the five WM-M2 sampled.
  - **The zip is 648 MB on disk, about 506 KB per entry.** Extracting everything would put 1.8 GB
    of DDS on disk, which is the cost the on-demand design avoids.

  ## Constraints

  - **The chart images belong to Eagle Dynamics.** Cached tiles live in a temp folder outside the
    repo and are never committed or published. LAN only.
  - **Its own small service, in its own top-level directory `raster-chart-viewer/`**, with its own
    `pyproject.toml`, venv and `CLAUDE.md`. User, 2026-11-16: *"this should really be it's own
    small service, not under MI. I just did not want to create another roadmap folder for it."*
    So **this entry is its only roadmap home** and `raster-chart-viewer/` gets no `ROADMAP/`
    directory. No import from world-model or mission-interpreter (root `CLAUDE.md`, "Module
    independence"). The filename pattern is one regex, written fresh from the research note.
  - **Every terrain on disk opens.** User, 2026-11-16, above. One reader for the single-zip
    terrains, one special case for Caucasus's zip-per-sheet folders. Terrains are discovered from
    `Mods/terrains/*/RasterCharts/`, not listed in code. Sparse sheets and missing tiles are normal.

  ## Open questions for plan time

  1. Mariana has 62 tiles with no scale prefix. Their tier is unknown: drop them, or place them by
     edge matching?
  2. Is the sheet convention measured on Syria the same on every terrain? Caucasus's `0.5M` rows
     AG–AK would be rows +6..+10 under it.
  3. Overlays — DCS grid, lat/long, the player's own marks — are out of scope for the first cut.
     OpenSeadragon places markers in image pixels, and `registration.py` already maps DCS x/z to
     tile pixels, so marks and own-ship would be cheap later; a lat/long grid would be hand-drawn.
