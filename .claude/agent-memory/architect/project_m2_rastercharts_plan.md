---
name: project_m2_rastercharts_plan
description: M2 (raster understanding) plan status — RasterCharts format unresolved, plan gated on a user-run probe
metadata:
  type: project
---

M2 plan (`plans/m2-raster-understanding/plan.md`) was written 2026-09-03 with a genuine format unknown, not just an unverified claim: Syria's `Mods/terrains/Syria/RasterCharts/` contains exactly `rasterCharts.zip` + `rasterCharts.sup5` (confirmed from M0's real filesystem listing), but what's inside the zip (tile image format) and what `.sup5` is are both unresolved — investigator's GitHub code search and ED forum fetch were blocked this session (403/401), so this is a real gap, not folklore to debunk.

**Why:** Unlike M1 (where pydcs gave a strong documented starting hypothesis for projection parameters), M2 has no community prior art confirmed. The plan therefore has a hard Stage 0 gate: `world-model/tools/wsl/probe_syria_rastercharts.sh` (already written, staged, not yet run) must be run by the user via the Mac/Windows `win-mac-sync` workflow before any raster-parsing code is written. Stages 1+ branch on what that probe reveals (single image vs. tiles; metadata present vs. needing M1-style empirical registration fit) rather than assuming a format up front.

**How to apply:** When this plan is picked up for implementation, check whether Stage 0's probe has been run and its output copied into `world-model/data/raw/dcs/<date>/` and `world-model/research/2026-09-03-m2-rastercharts-recon.md` updated. If not, the Implementer should not proceed past Stage 0 — flag it back to the user rather than guessing the tile format. See [[project_investigator_gating_pattern]] for the general pattern this follows.
