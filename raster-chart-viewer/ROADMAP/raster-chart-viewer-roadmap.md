# Raster Chart Viewer — Roadmap

A standalone LAN service on the Windows DCS machine. It serves every installed terrain's
`RasterCharts` as a pan/zoom map in a browser, making tiles on demand from the zips without
extracting them. It is the crew's paper chart, on a tablet or a second screen. No Petrovich
behaviour depends on it. It imports nothing from any other subproject, and nothing imports from it.

**It became a subproject in its own right on 2026-11-16** (user: *"Let's treat it as a proper sub
module of Petrobrain."*). Before that it was the mission-interpreter backlog item [[MI-B4]],
filed there only to avoid creating a roadmap folder. That entry moved here as [[RC-1]].

**ID prefix: `RC-`**, for milestones; `RC-B<n>` is for backlog items and `RC-W<n>` for work items,
as in every sibling. Numbers are never reused. Mint them with `.claude/scripts/mint-id.sh`.

This is the pointer's index. See `docs/DOC_CONVENTIONS.md` for the directory layout, ID scheme
and link form it follows. The index carries links and titles only; status lives on each entry.

Plan: `plans/raster-chart-viewer/plan.md`. Facts: `raster-chart-viewer/research/`.

## Milestones

- [[RC-1]] — Raster chart viewer: DCS RasterCharts as a pan/zoom map on the LAN (first cut, all
  installed terrains)

## Backlog

- [[RC-B1]] — Unbounded `level`/`vx`/`vy` digit length crashes a single request with an uncaught
  exception (Security deep analysis, 2026-11-16; low-risk, not a blocker)
