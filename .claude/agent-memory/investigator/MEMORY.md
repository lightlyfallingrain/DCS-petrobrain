# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [Syria projection facts](project_syria_projection.md) — Transverse Mercator, params CONFIRMED live vs coord.LOtoLL (0.03m); real-world residual ~1.0-1.3km (3 ARPs), per-airport not systematic. M1 satisfied.
- [pydcs prior art](reference_pydcs_prior_art.md) — pydcs (LGPL-3.0) has per-theatre tmerc params + airbase positions; its coord_export.lua is a template for our own live-mission probe; also has tool-access notes (gh unavailable, git clone to /tmp blocked, use WebFetch on api.github.com/raw.githubusercontent.com).
- [M2 RasterCharts recon](project_m2_rastercharts.md) — Syria: 1280 DXT5 DDS tiles are scanned real paper charts (JOG-A-like 1:250k, Turkey terrain, UTM grid printed in-tile — independent registration path). .sup5/x-z-arithmetic still untested. forum.dcs.world blocks WebFetch (403).
