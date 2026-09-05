"""Terrain-semantics subsystem: ridge/valley extraction from a DCS elevation
grid (M6).

Source data is the DCS live-probe elevation grid already built for
`latakia-20km` (`grid.kind == "elevation"`, `store.reader.load_full_grid`) --
not a fresh SRTM raster. `curvature.py` classifies each interior grid cell
as ridge/valley/neither via a discrete Laplacian; `features.py` groups
same-classification cells into connected components and extracts each
component's principal-axis line, producing `store.models.StoredFeature`
rows the existing `feature` table already knows how to hold (no schema
change). See `plans/m6-terrain-semantics/plan.md` for the full algorithm
rationale and the "stdlib only, no numpy" decision.
"""
