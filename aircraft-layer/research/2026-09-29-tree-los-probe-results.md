# Do any scripting calls see trees? And does SEGMENT catch terrain?

**Date:** 2026-09-29, flown on the Windows box (~25 s, Syria).
**Probe:** `aircraft-layer/dcs-export/petrobrain-tree-los-probe-hook.lua`.
**Raw:** `dcs.log`, prefix `PetrobrainTreeLos`, 20:09:21 → 20:09:23.

### Question

Two, both relayed from the user via the Mac session. (1) Does *any* scripting call give
line of sight with trees accounted for — his bar being a blocked/clear verdict, not tree
placement. (2) Does `world.searchObjects` with `VolumeType.SEGMENT` catch **terrain**, or only
scenery? The second is an untested assumption underneath `plans/dcs-driven-los/plan.md`.

### Findings

**1. `land.SurfaceType` has no forest value. `LAND=1 SHALLOW_WATER=2 WATER=3 ROAD=4 RUNWAY=5`.**

- **evidence: reproduced-locally** — enumerated from the live table.
- Every site probed, forest and open alike, returned `surf=1` (LAND). Surface type carries no
  vegetation signal at all, so it is not a cheap back door to tree cover.

**2. `land.getIP` does not see trees. It returned nothing standing above ground, anywhere.**

- **evidence: reproduced-locally** — 8 rays per site, 30 m down to 2 m over 300 m.

  | site | TREE_LIKE | terrain-blocked | clear | scenery rays | max delta above ground |
  |---|---|---|---|---|---|
  | FOREST_A — 251 km², interior 4.3 km from edge | **0** | 2 | 6 | 0 | **0.0 m** |
  | FOREST_B — 85 km², 3.1 km deep | **0** | 0 | 8 | 0 | **0.0 m** |
  | OPEN control — nothing mapped within 400 m | 0 | 0 | 8 | 1 | 0.0 m |
  | OWNSHIP | 0 | 0 | 8 | 3 | 0.0 m |

- **Not one intercept stood above local ground**, in 336 km² of mapped forest. Every `getIP`
  return sat at terrain height, which is the same terrain-only behaviour already established for
  `land.isVisible`.
- Scenery rays behave as expected and confirm the machinery works: 0 in both forests, 1 and 3 near
  the open control and the aircraft, where buildings and power lines are.
- **One ray at FOREST_B had `isVisible` blocked while our terrain sampling said clear.** With
  12 samples over 300 m (25 m spacing) a sharp feature can be stepped over, and `isVisible` was
  shown terrain-only by 40 rays through 40 buildings, so this is almost certainly sampling
  granularity rather than a tree. Recorded rather than dismissed.

**3. `SEGMENT` does NOT catch terrain — but this flight's test was weaker than intended, through
an error of mine.**

- **evidence: reproduced-locally, on a weak case** —

  | case | our terrain verdict | max terrain above the line | SEGMENT hits | `isVisible` |
  |---|---|---|---|---|
  | "ridge" | blocked | **+4 m** | **0** | false |
  | flat control | clear | −2 m | 0 | true |

- The direction is right: DCS's own `getHeight` sampling *and* `isVisible` both called the line
  blocked, and the SEGMENT search returned nothing. That supports the two-call design
  (`clear = building_clear and terrain_clear`).
- **But the intended margin was ~1000 m and the actual one was 4 m.** The elevation grid is indexed
  `x = origin_x + row*spacing`, `z = origin_z + col*spacing` (`store/reader.py:sample_grid`), and
  my site search had row and col swapped — so the ray was fired at gentle hills, not the 2198 m
  crest I had selected. **A 4 m margin against a call that might carry a tolerance is not the
  decisive test this was meant to be.**
- **Corrected coordinates, re-deployed, not yet flown:** A(341088, 167559) h=1689 →
  B(341088, 173559) h=1595, profile 1689/1875/2133/**2615**/2229/1837/1595 — a crest **926 m**
  above the higher endpoint, with nothing built, no landcover and no water within 1200 m.

**4. The site coordinates themselves are sound — cross-checked against DCS's own heights.**

- **evidence: reproduced-locally** — our grid vs the `getHeight` values this flight returned:
  FOREST_B **−1.1 m**, OWNSHIP **+0.4 m**, OPEN_CONTROL +9.2 m, FOREST_A −73.2 m (hill country,
  where a 1000 m grid cell is expected to be poor). So the forest sites are real places at real
  elevations, and Finding 2 rests on valid geometry.

### The weakness in Finding 2, stated plainly

The forest rays were aimed using **OSM** polygons, and OSM forest is not proof of **DCS** trees. If
DCS has no trees at those coordinates, "nothing above ground" is vacuous rather than a negative —
and the probe cannot separate those two by itself, because `getIP` is the call under test and using
it to confirm the trees are there would be circular.

**The pilot breaks the circle.** A dense fan has been added — 24 azimuths × 2 heights (3 m and
12 m, trunk and mid-canopy) out to 150 m from the aircraft — to be flown **parked where trees are
visibly present**. Visual confirmation plus a null result is a real negative. Without it, Finding 2
says only "nothing was found where OSM claims forest".

### Unresolved

- **Does DCS have trees where OSM says forest?** Resolves with the dense fan above, flown somewhere
  the pilot can see trees.
- **Does SEGMENT catch terrain?** Finding 3's direction is right but the margin was 4 m. Resolves
  with the corrected ridge, already deployed.
- **`Controller.isTargetDetected` — the AI path that `Detection.lua` configures with
  `trees_LOS_test_T4`.** Not probed: characterising it needs a purpose-built mission with an AI
  unit and a target deliberately placed behind a treeline, which is mission-authoring work rather
  than another hook. **It remains the only known code path that demonstrably does tree-occluded
  LOS**, and if the answer above stays negative it is the last candidate.
- **Cost:** all figures in this note are **raw per-call milliseconds with no baseline subtracted**,
  and are not per-item costs. The calls bundle setup, ~12 `getHeight` samples per ray and three
  different APIs.
