---
name: terrain-watershed-scaling
description: Measured cost/scaling of the marker-controlled watershed terrain pass (world-model/src/terrain/), a one-time offline build stage
metadata:
  type: project
---

Measured 2026-10-01 against `feature/terrain-landform-features` @ `7329ec3`, synthetic grids shaped
like the real theatre (1656x1543 @ 500m = 2,555,208 cells; no real DCS/SRTM data available in a
worktree, per project rule against running real full-theatre builds).

**Numbers (full theatre, basin density calibrated to the plan's own sweep-note measurement of real
data — 10 basins/1600 cells at `latakia-20km`):**
- `smooth_grid`: ~3.2s. `find_basin_seeds`: ~0.2-0.3s.
- `grow_basins` (stdlib heapq priority flood): **31-35s**.
- `extract_components` (ridges+valleys+saddles, also stdlib): **31-41s**.
- Total terrain stage: **~65-80s**, vs. the old per-cell curvature pass's documented 5.8s — an
  **11-14x multiple**, but trivial against OSM ingest's 25-30 *minutes*. Not a problem at current
  theatre scale/resolution.
- Peak RSS for one run: **~2GB** (mostly Python dict/tuple/heap object overhead in `grow_basins`,
  not the numpy arrays themselves).

**Scaling is mildly superlinear, not linear**, at constant basin density: 16x the cells (159,804 ->
2,555,208) gave ~41x the `grow_basins` time and ~37x the `extract_components` time, not ~16-20x. Not
basin-count blowup (density held constant by construction) — most likely CPython object/cache
overhead growing with working-set size. Relevant if a future, larger theatre or a finer grid
resolution (e.g. 250m, 4x the cells) is ever considered: a linear extrapolation from a small test
region will *underestimate* real full-theatre cost by roughly 2x.

**Numpy/scipy is correctly scoped to smoothing+seed-detection only** (per the plan) — but the
plan's own stated reasoning ("basin growth/extraction aren't the bottleneck") was backwards: stdlib
code is >95% of this stage's actual runtime, not a negligible remainder. The scoping *decision* was
still right (the flood is inherently serial, doesn't vectorize, and absolute cost is fine) — the
*justification* just didn't match measurement. Worth checking stated reasoning against measurement
even when the eventual verdict is "no action needed."

**Calibration trap for anyone benchmarking this terrain pass again**: independently-placed
overlapping Gaussian bumps, or i.i.d. per-cell noise, both inflate synthetic basin/seed count by
10-50x through superposition/plateau artifacts — one naive attempt produced an exact-zero plateau
over 28% of the grid, trivially satisfying "value == local min" everywhere. What worked: random
amplitudes on a coarse lattice (spacing ~6 cells), upsampled + Gaussian-smoothed (sigma~2) — lands
within the same order of magnitude as the real-data basin density.

Full writeup: `plans/terrain-feature-probing/performance.md`. See also
[[watch-reporting-scale-notes]] for an earlier instance of basin/cluster-style O(n) scaling work in
this codebase.
