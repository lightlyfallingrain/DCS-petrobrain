---
name: project_m7_kola_stress_test
description: Kola used as stress test for Syria's square-region assumption; result splits into two separable findings.
metadata:
  type: project
---

M7 architecture question: does Kola falsify "square DCS x/z region is good enough" (Syria aspect ratio ~1.07)?

Findings (2026-09-05, see `world-model/research/2026-09-05-m7-kola-square-vs-rectangle-stress-test.md`):
- Kola has NO `THEATRE_PROJECTIONS` entry in `src/coordinates/projections.py` — only Syria implemented. Kola tmerc params derivable from pydcs `dcs/terrain/kola/projection.py` (central_meridian=21, false_easting=-62702.0, false_northing=-7543625.0, scale_factor=0.9996) — same generation tool as Syria's (later confirmed live in M1) but **unverified for Kola** (no live Kola coord.LOtoLL probe run).
- Kola's real-world footprint IS meaningfully elongated vs Syria: ED/Orbx marketing ~1400x1000km (ratio ~1.4); pydcs 9-airfield DCS-grid bbox 800x478km (ratio ~1.67). This is real and decisive against square-only, regardless of exact Kola numbers.
- BUT: tmerc distortion/grid-convergence at high latitude does NOT itself break "DCS square ≈ real-world square" — verified via pyproj geodesic-square probe (`world-model/tools/m7_kola_square_distortion_probe.py`): even 500km half-extent near Kola's edge, edge-ratio deviation <1%, corner angle deviation <0.2deg. Tmerc is locally conformal — only overall scale factor k varies with distance from central meridian, not local shape/anisotropy. The elongation is an ED map-footprint artifact, not a projection-math effect.
- Conclusion: Kola DOES justify rectangular half-extents in RegionDefinition, but for a different reason than "high-latitude tmerc distortion" — it's simply that theatre map footprints vary in aspect ratio per ED's art choices.
