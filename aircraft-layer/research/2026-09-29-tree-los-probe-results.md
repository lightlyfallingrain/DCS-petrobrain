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

**5. UNIT-REFERENCED RE-TEST (2026-10-01). The weakness below is closed, and the answer is
unchanged: no scripting call sees trees.**

- **evidence: reproduced-locally, against two vehicles the pilot placed inside visible canopy** —
  `dcs.log` 07:29:59 → 07:30:01, prefix `PetrobrainTreeUnits`.
- The user placed a **BTR-70 and a BTR-60, 201 m apart, both inside the same forest near ownship**
  (`Ground-55-1` at 207827, 35952 and `Ground-54-1` at 207762, 35762). That removes the
  OSM-is-not-DCS circularity: the geometry comes from real objects in cover he can see.

  | sightline | terrain | `getIP` | `isVisible` | SEGMENT |
  |---|---|---|---|---|
  | BTR-70 → BTR-60, 201 m, in forest | **blocked by +1.0 m** | hit @67 m, **aboveGround −0.0 m** | false | 0 |
  | open control, same vector translated | clear (−1.4 m) | none | true | 0 |
  | ownship → BTR-70, 535 m, +30 m → +2 m | clear (−2.4 m) | **none** | **true** | 0 |
  | ownship → BTR-60, 604 m | clear (−2.2 m) | **none** | **true** | 0 |

- **The two ownship rays are the strongest evidence, and they are the realistic case.** A Mi-24P at
  30 m looking at a vehicle sitting in forest 535 m away: terrain clear by 2.4 m, `isVisible`
  **true**, and `getIP` hit **nothing at all** along a ray that passes straight through the canopy
  band. If trees were geometry these calls could reach, that ray would stop.
- **The BTR-to-BTR line is blocked, but by terrain, not trees** — the ground rises 1.0 m above the
  line (the vehicles sit at 162.8 m and 150.4 m, a 12.4 m drop over 201 m), and `getIP`'s intercept
  is at **−0.0 m above local ground**, i.e. the surface. So `isVisible = false` there is fully
  explained without invoking a tree. **It is therefore not a clean tree test**, and should not be
  read as one.
- **The prediction written into the probe header before the flight held**: all four facts behave
  identically in forest and in the open.

**6. `SEGMENT` does not catch terrain — settled, this time with a 950 m margin.**

- **evidence: reproduced-locally** — the corrected ridge, same flight.
- `len=6000 m | terrainBlocked=true | maxTerrainAboveLine=**+952.7 m** | getIP=hit@13 m aboveGround
  −0.0 m | isVisible=false | **SEGMENT=0**`.
- DCS's own `getHeight` put the crest 952.7 m above the sightline, against the 926 m our grid
  predicted — the site selection was right and the earlier 4 m version was purely my row/col error.
- **A SEGMENT scenery search returns nothing for a line buried under a kilometre of rock.** The
  two-call design (`clear = building_clear and terrain_clear`) in `plans/dcs-driven-los/plan.md` is
  correct and its Stage 3 does not collapse.

**7. The AI-detection half did not run — same coalition, exactly as the probe warned.**

- Both vehicles are `side1` (RED), so they are not each other's targets:
  `A_sees_B=detected:false visualTargets:0`, `B_sees_A` identical.
- **`Controller.isTargetDetected` remains the last untested candidate** and the only shipped path
  known to do tree-occluded LOS. **Resolves with:** one unit moved to the opposing coalition and
  the same probe re-flown — ideally also with flatter ground between them, so a positive cannot be
  confused with the 1.0 m terrain intrusion above.

**8. Where the engine's tree-aware LOS actually lives — read from the install, 2026-10-01. It is
not reachable, and that is the answer.**

- **evidence: reproduced-locally (reading the shipped Mi-24P module and `Detection.lua`) +
  documented-absence (no matching strings in `Mi24.dll`)**.
- **Context the user supplied, which reframes the AI test:** forum consensus is that DCS **ground
  units see through trees**, a long-standing complaint — while the Mi-24P's own AI Petrovich *does*
  appear tree-aware when using the 9K113, *possibly only* with the 9K113.
- **The module confirms the Petrovich half is real.** `Cockpit/Scripts/HelperAI/HelperAI_sound.lua`
  carries the event names **`target_obstructed`** and **`sight_blocked`**, each with four and three
  recorded voice lines. So an obstruction judgement is a named, shipped state — not an impression.
- **But it is audio-only.** Those tokens appear *only* in the sound table. `HelperAI_page_common.lua`
  and `HelperAI_reporting_names.lua` — the files behind the indication text that
  `list_indication(HELPERAI_DEVICE_ID)` returns, which aircraft-layer **already reads** — contain
  no obstruction, visibility or tree term at all. **So Petrovich's own tree-aware verdict does not
  surface in any machine-readable channel this project has.** It is a sound file.
- **The decision itself is compiled.** `Mi24.dll` yields 12,725 extractable strings and **not one**
  matching `obstruct|tree|forest|isVisible|getIP|LineOfSight|visibility|occlu|foliage|canopy`, nor
  any `petrovich`/`target_` token — the sound events are selected by index from the Lua table, so
  there is no string surface and no Lua surface to the logic.
- **`Controller.isTargetDetected` cannot reach the 9K113 path either**, and this is structural
  rather than a measurement gap: Petrovich is a **cockpit device** in the player's own aircraft, not
  a Controller-driven AI unit. The `Controller` API addresses AI *groups*; it has no handle on
  another unit's internal sight operator. So the one tree-aware behaviour the user has observed sits
  behind an interface that does not exist.
- `detection_by_optic_sensor` (the table that would govern a 9K113-class sensor) carries **no LOS
  flags of its own** — only scan time, recognition ratio and fog/IR behaviour — so it inherits
  `visual_detection`'s, which do include `trees_LOS_test_T4 = true`. That is consistent with the
  engine having the capability while exposing no way to ask it a question.

**9. So the complete answer to "is there any DCS call for tree-aware LOS" is no.**

| route | tree-aware? | reachable? |
|---|---|---|
| `land.isVisible` | no — measured, 40 rays through 40 buildings | yes |
| `land.getIP` | no — measured, nothing above ground in forest or at vehicles in canopy | yes |
| `world.searchObjects` (any volume) | no — trees are not scenery objects, 11 flights | yes |
| `land.getSurfaceType` | no — `LAND/SHALLOW_WATER/WATER/ROAD/RUNWAY`, no vegetation | yes |
| `visual_detection` / `trees_LOS_test_T4` | **yes** | compiled; no scripting handle |
| Petrovich's `target_obstructed` | **yes** | **audio only**; absent from the indication text |
| `Controller.isTargetDetected` | unknown for ground units (forums say they see through trees) | yes, but cannot address a cockpit device |

**OSM `landcover` is therefore the only source for trees**, which is what
`plans/dcs-driven-los/plan.md` already pre-decided as the fallback. That decision now rests on
measurement rather than on absence of evidence.

**One tension worth naming rather than discovering later:** even if Petrovich's obstruction verdict
*were* machine-readable, consuming it would run against the standing direction to stop taking DCS's
detection output and model perception ourselves. So this route is not merely unavailable — it is
also against the grain of the design.

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

- ~~**Does DCS have trees where OSM says forest?**~~ **Superseded by Finding 5** — the test no
  longer depends on OSM at all; it references vehicles the pilot placed in canopy he can see.
- ~~**Does SEGMENT catch terrain?**~~ **Answered, Finding 6:** no, with a 952.7 m margin.
- **`Controller.isTargetDetected`** — the probe now runs it, but the two vehicles are on the same
  coalition so it has nothing to report (Finding 7). **It remains the only known code path that
  demonstrably does tree-occluded LOS, and is now the last candidate standing.** Resolves with one
  unit flipped to the opposing side.
- **Cost:** all figures in this note are **raw per-call milliseconds with no baseline subtracted**,
  and are not per-item costs. The calls bundle setup, ~12 `getHeight` samples per ray and three
  different APIs.
