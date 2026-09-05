---
name: project_m7_theatre_extent
description: Syria full-theatre bounding box findings for M7 full-pipeline scaling
metadata:
  type: project
---

`MissionGenerator/nodesMap.lua`'s `theatre.nodesMapBorders` (from M5 recon) is FALSIFIED as
a theatre-extent source — real airbases (Ruwayshid, Nevatim, Konya, T2) sit outside it on
every side. Never recommend it as a bbox again.

Best-available DCS-authoritative Syria bbox (2.9.29.27278, reproduced-locally, two
independent point sources agreeing within a few km): x [-421912, 345433] m, z [-320441,
390775] m, lat [31.19, 38.01]°N, lon [32.29, 40.21]°E (~762x710 km). Sources: (1)
`world.getAirbases()`-via-`coord.LOtoLL` dataset already in
`world-model/data/raw/dcs/2026-09-03/coord_probe_output.json` (225 airbases, already
cross-validated to 0.00-0.03m against pydcs tmerc params in the M1 verification note), (2)
`Mods/terrains/Syria/map/beacons.lua` (151 beacons, plain offline-readable Lua, same file
class as towns.lua). This is a point-cloud LOWER BOUND on the true terrain mesh, not the
exact edge — ED's current official marketing figure is "1000x900 km" (larger, as expected,
but imprecise/rounded and not independently corner-verified). Full writeup:
`world-model/research/2026-09-05-m7-syria-theatre-extent.md`.

Installed DCS 2.9.29.27278 already includes the post-eastward-expansion map (Deir ez-Zor,
H3, H3 NW/SW, Ruwayshid, Iraq salient all present) — don't use pre-expansion "900x500km"
figures (e.g. from a 2021 blog review) for this install.

`terrain.cfg.lua.pak.crypt` still packed+encrypted — still no readable projection/extent
param found there as of this session either.
