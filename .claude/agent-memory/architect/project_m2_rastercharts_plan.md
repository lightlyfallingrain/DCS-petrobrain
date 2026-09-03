---
name: project_m2_rastercharts_plan
description: M2 (raster understanding) plan status — format confirmed, registration hypothesis now the gate; open scope question re: scanned real-world chart vs. DCS-truth invariant
metadata:
  type: project
---

M2 plan (`plans/m2-raster-understanding/plan.md`), Syria `RasterCharts`. Updated 2026-09-03 after
investigator sessions 2–4 (all in `world-model/research/2026-09-03-m2-rastercharts-recon.md`).

**Format resolved (session 2):** 1280 DXT5/BC3 DDS tiles, 1024×1024, 11 mipmaps, named
`{32|64}m{sheet}{level}_x{0-7}_z{0-7}.tif.dds` (sheet ∈ {aa,ab,xab,xac}, level ∈ {-2,-1,00,01}).
Plain NVTT-built DDS — no ED-proprietary image encoding. `.sup5` confirmed as an ED
`landscape5::sup5File`-tagged generic-serialization manifest; only first 64 bytes read, structure
beyond that still unresolved.

**Surprise (session 3):** the tiles are NOT satellite/rendered imagery — they're scans of a
real-world 1:250,000-class military/aeronautical chart (JOG-A-class, moderate confidence) covering
central-eastern Turkey (Sivas/Erzincan), with its own printed UTM grid (zone 37S confirmed). This
opened a second, independent registration path (chart's own UTM grid via `pyproj`) alongside the
original DCS-internal path (`.sup5` / x-z filename arithmetic). Neither is executable yet — the
UTM path needs a margin/corner tile with an unambiguous full-precision grid label (none of the 5
samples have one); the x/z-arithmetic path is untested against real content.

**Why this matters architecturally:** RasterCharts only feeds DCS's F10 "paper map" mode (session
4, user domain knowledge — DCS has three F10 modes: paper map / satellite / engine-only 3D render,
each a separate asset pool). This raster is scanned real-world cartography with its own geodesy,
not DCS-generated truth and not typical OSM/DEM-style "external GIS augmentation" either — a third
provenance category root `CLAUDE.md`'s "DCS geometry authoritative, external GIS augments never
overrides" invariant wasn't written with in mind. Flagged explicitly as a Decision Requiring User
Input in the plan rather than silently resolved — two framings offered: (1) treat as a legitimate
third provenance category and proceed, or (2) reconsider whether registering this raster belongs
in World Model Builder scope at all vs. being a future Mission Interpreter/Petrobrain Runtime
concern (kneeboard/map-rendering use case, not the roads/settlements/terrain "truth" layer).

**Dependency decision made this session:** add `pillow` to `world-model/pyproject.toml` as a real
(non-dev) dependency — tile decoding is core to M2, not incidental tooling. Pillow's built-in DDS
plugin decoded all 5 DXT5 samples with no extra native deps.

**How to apply:** When this plan is next picked up, check (a) whether the user has resolved the
scope/provenance question above, and (b) whether Stage 1's registration-hypothesis validation
(decode margin tiles, empirical-fit via a known real-world feature + M1's x/z↔WGS84 transform,
optionally cross-check against UTM grid) has actually run and been appended to the research doc.
Do not let Implementer write `src/raster/registration.py` until Stage 1 confirms which path
works — this repeats M1/M2's established pattern of not encoding an unverified DCS-internals (or
here, chart-geodesy) claim as fact. See [[project_investigator_gating_pattern]].
