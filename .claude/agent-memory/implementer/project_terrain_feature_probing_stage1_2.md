---
name: terrain-feature-probing-stage1-2
description: Stage 1-2 un-gating + spacing calibration findings for ridge/valley terrain extraction
metadata:
  type: project
---

`plans/terrain-feature-probing/plan.md` Stages 1-2 (2026-09-29): un-gated `build.pipeline`'s
terrain-semantics stage from the DCS-probe branch (it had never run against an SRTM-sourced grid,
which every real `syria-full`-scale build supplies), then picked a processing/storage spacing
empirically.

**Key finding, worth remembering because it inverts the plan's own stated expectation**: the plan
anticipated a likely "process fine, store coarse" split (curvature pass over a fine transient grid,
only the LineString features stored). A real sweep (1000/500/250/100m x several thresholds, over
`latakia-20km` real SRTM data) found the opposite — M6's already-documented checkerboard-noise
ceiling is **spacing-invariant, not just threshold-invariant**. Finer processing reproduces the
same noise pattern at higher cell density rather than resolving cleaner landmark lines at any
threshold tested. So there was no benefit to decoupling processing from storage spacing; one grid
(500m, chosen because it reproduces M6's own DCS-probe-500m tuning almost exactly on SRTM data)
serves both. **Lesson for future spacing/resolution tuning work in this pipeline**: don't assume a
plan's anticipated design shape (here, the fine/coarse split) survives contact with real data —
sweep first, then decide the shape, even when the plan already laid out sizing numbers for the
anticipated case.

See `world-model/research/2026-09-29-terrain-feature-probing-spacing.md` for full tables.
