# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Syria projection facts](project_syria_projection.md) — Transverse Mercator, params CONFIRMED live vs coord.LOtoLL (0.03m); real-world residual ~1.0-1.3km (3 ARPs), per-airport not systematic. M1 satisfied.
- [pydcs prior art](reference_pydcs_prior_art.md) — pydcs (LGPL-3.0) has per-theatre tmerc params + airbase positions; its coord_export.lua is a template for our own live-mission probe; also has tool-access notes (gh unavailable, git clone to /tmp blocked, use WebFetch on api.github.com/raw.githubusercontent.com).
- [M2 RasterCharts recon](project_m2_rastercharts.md) — Syria: 1280 DXT5 DDS tiles are scanned real paper charts (JOG-A-like 1:250k, Turkey terrain, UTM grid printed in-tile — independent registration path). forum.dcs.world blocks WebFetch (403). F10 satellite mode's likely asset is `clipmaps/colortexture/` (separate dir, own probe script), not RasterCharts. Stage 1: z-axis ~9% residual (2pt), x-axis <0.2% residual (3pt) + graticule cross-check ~1% agreement. x-tile-index increases SOUTH (opposite DCS +x), z-tile-index increases EAST (same as DCS +z) — sign flip `registration.py` must encode. confidence="provisional" justified.
- [clipmap container format](clipmap-container-format.md) — `.tif.clipmap` byte-level structure (header, zlib-chunked BC3/BC1 tiles), decode recipe. Confirms clipmap = real satellite imagery, distinct from RasterCharts.
- [forum.dcs.world fetch unreliable](forum-dcs-world-fetch.md) — always ask user to paste forum content manually, don't record as unread gap.
- [research file session numbering](research-file-session-numbering.md) — check for concurrent session-number collisions before appending to a shared research/*.md file.
- [M4 elevation recon](project_m4_elevation_recon.md) — land.getHeight is Mission-Scripting-only, no offline heightmap exists; net.log bypasses io/lfs sandbox for bulk output; SRTM .hgt recommended over Copernicus COG (no new dep).
