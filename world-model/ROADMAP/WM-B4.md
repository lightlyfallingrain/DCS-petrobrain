# WM-B4 — Smooth the ridge/valley polylines into curves

- [ ] **WM-B4 — Smooth the ridge/valley polylines into curves instead of cell-edge staircases.** #status/open
  User direction, 2026-10-01, after looking at the first real watershed output: *"what I'd change is
  using bezier (or similar) lines instead of straight segments. That would solve much of the
  jaggedness and give a more realistic ridge (or other divider)."* The axis-sliced extraction that
  shipped is monotone and no longer wanders (sinuosity 2.2 → 1.2 on the real theatre), but it still
  emits one point per 500 m grid slice, so a crest renders as a staircase of cell-aligned steps that
  no real ridge has.

  **The tension to resolve before implementing, not after**: `terrain/features.py`'s own standard is
  *"an honest polyline through actual sampled grid points"*, and a fitted curve introduces positions
  that were never sampled. The counter-argument is that the staircase is itself an artifact — of
  500 m quantisation, not of the terrain — so a curve constrained to stay within the sampled band is
  the *better* estimate, not a fabrication. Suggested resolution: keep the fitted curve's maximum
  deviation from the sampled points below half a cell (250 m), which is already inside the stored
  `position_uncertainty_m`, and say in the docstring what the points now are. A centripetal
  Catmull-Rom or Chaikin pass is likely a better fit than a Bézier, since both interpolate rather
  than requiring control points off the crest.

  Consumers to check before changing the stored geometry: `geometry.signed_side_of_polyline`
  (proven on coastline), `geometry.bearing_deg`, and whatever Stage 3's adjacency ends up reading.
  Densifying into the same `LineString` shape keeps all three working unchanged.

  **Superseded by [[WM-B6]] and parked with it, 2026-10-01.** Implemented on
  `feature/landform-curve-smoothing` (unmerged, Chaikin, measured max deviation 182 m against the
  250 m cap) — but smoothing a line that is in the wrong place does not help, and the user's verdict
  below retires this as a standalone item. Keep the branch; revisit only once detection quality is
  fixed.
