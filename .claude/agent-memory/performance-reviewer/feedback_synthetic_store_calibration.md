---
name: synthetic-store-calibration
description: When no built .sqlite fixture exists, a synthetic store measures ratios honestly but understates absolute cost — anchor on the committed real measurement instead.
metadata:
  type: feedback
---

A synthetic store built to a real build's recorded counts gives trustworthy **ratios** (what a fix
buys) and trustworthy **cost shape** (where the time goes), but systematically understates
**absolute** cost, because synthetic placement is less clustered than real geography.

**Why:** measured 2026-10-05. A synthetic syria-full (real counts from `world-model/ROADMAP.md`'s
2026-09-15/16 build, real 827x771 km footprint, 20 Gaussian population centres) gave
`describe_position` 40.8 ms at its densest point. M7's committed measurement on the **real** store
is 136.8 ms mean / 497.7 ms p95 — 3-12x higher. Real OSM features cluster along coasts and valleys
far harder than any plausible synthetic draw, and query cost here tracks **local** density.
This is the same calibration trap already recorded for terrain
([[project_terrain_watershed_scaling]]), in a different subsystem.

**How to apply:** build the synthetic store anyway — it is the only way to get `EXPLAIN QUERY PLAN`,
statement counts, and before/after ratios without the user's machine. But in the report, state the
committed real figure as authoritative, present synthetic numbers as ratios, and say the multiplier
between them. Never let a recommendation rest on a synthetic absolute. `*.sqlite` is gitignored in
world-model, so this situation recurs every time that subproject is reviewed.

Practical notes for rebuilding this harness: the worktree has **no venv** (deps uninstalled);
`world-model/src/query/__init__.py` imports `coordinates`, which needs `pyproj` **and** `numpy`, so
a scratchpad venv with both is required even to import the LOS primitive. Worst-case LOS must be
measured with a **clear** sightline — a blocked one early-returns on the first sample and reports
5 statement executions instead of 95.
