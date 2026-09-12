---
name: project_m9_tactical_landmarks
description: M9 tactical-landmarks recon (settlement extents, road-junction geometry) — findings and a reusable technique
metadata:
  type: project
---

Session 2026-09-12, `world-model/research/2026-09-12-m9-tactical-landmarks-recon.md`.

- **No DCS-native settlement-extent source exists anywhere in Syria's terrain tree.**
  `towns.lua` is confirmed point-only (`latitude`/`longitude`/`display_name`, no
  radius/bbox/polygon key, whole-file key scan). No other terrain file
  (`.gn4`/`.sup5` under `map/`, `nodes.lua`/`nodesMap.lua`, or any filename
  matching zone/city/settlement/boundary/polygon/region/border/admin) carries one
  either — confirmed by grepping the full theatre file listing
  (`world-model/data/raw/dcs/2026-09-02/DCS-files.txt`). No shared `_Common`
  terrain directory exists across theatres. OSM remains the only path to real
  settlement boundary polygons — this is now settled, don't re-investigate.
- **Road junctions ARE derivable purely geometrically from already-decoded
  `.routes` point arrays, at bit-exact (0.0 m) coordinate coincidence — no
  `.rn4` trailer decoding needed.** Checked against the already-built
  `latakia-20km.sqlite` store's 3,266 `road` features: 1,315 endpoint-endpoint
  exact matches, 3,700 endpoint-to-interior-vertex exact matches (T-junctions),
  vs. only 85 near-misses in the 1.4–5 m band and a clean gap in between (no
  ambiguous middle ground needing a tolerance judgment call). DCS's road
  authoring tool snaps junction vertices to identical float64 coordinates.
- **Reusable technique**: when a question is "does geometry X coincide with
  geometry Y in an already-built world-model store," query the existing
  `<region>.sqlite` `feature` table directly (`geom_json` column) rather than
  re-walking the raw DCS binary file — the store is already a validated decode
  and answering from it is far faster than a multi-GB `iter_routes` walk (which
  itself is very slow: a full-file walk with bbox filtering still processes
  the *entire* file sequentially, since `iter_routes` doesn't support random
  seek to a region — a background attempt at this took >120s with no output
  and was killed in favor of querying the store instead).
- Grid-bucketed (50 m cell) 3×3-neighbor proximity scan in plain Python is fast
  enough for ~6,500 points; no spatial library needed for this scale.
