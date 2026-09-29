# Live probe results: `land.*` and `world.*` through the mission-scripting bridge

**Date:** 2026-09-29, flown on the Windows box (~2.5 min mission, Syria).
**Probe:** `aircraft-layer/dcs-export/petrobrain-elevation-cost-probe-hook.lua`.
**Raw:** `Saved Games/DCS/Logs/dcs.log`, 19 lines prefixed `PetrobrainElevProbe`,
`13:28:14` → `13:28:24`.

### Question

Does `land.getHeight` work through `net.dostring_in("scripting", …)`; what does a terrain batch
cost; and (X-B4) do trees and buildings block `land.isVisible`, or can building data be extracted
outright? The user prepared the flight to sit near a town, forest and mountains for the X-B4 half.

### Findings

**1. `land.getHeight` works through the bridge and returns exactly the same surface as the
mission-editor probe. Settled.**

- **evidence: reproduced-locally** — **source:** probe output vs
  `Saved Games/DCS/Logs/elevation_probe_output.jsonl` (M4, 2026-09-06).
- All **8/8** points match, max |delta| **4.6e-05 m** — i.e. identical to float32 print precision.

  | point | bridge (2026-09-29) | mission-editor (2026-09-06) |
  |---|---|---|
  | damascus_osdi | 612.000610 | 612.0006 |
  | latakia_oslk | 28.223125 | 28.2231 |
  | beirut_olba | 12.000013 | 12.0000 |
  | aleppo_osap | 382.191040 | 382.1910 |
  | klieat_olka_coastal | 4.410843 | 4.4108 |
  | mezzeh_os67_urban | 727.811035 | 727.8110 |
  | deir_ez_zor_osdz_desert | 208.432755 | 208.4328 |
  | kahramanmaras_ltcn_mountainous | 478.396729 | 478.3967 |

- **`land.getSurfaceType` works too**, and its output is checkable rather than merely non-nil:
  every point returned `1` (land) except `beirut_olba`, which returned `5` — Beirut OLBA is an
  airport and the spot-check point sits on its runway.
- This closes the last "inferred, high-confidence, never actually watched" item from
  `2026-09-28-live-terrain-probing-feasibility.md` Finding 2.

**2. `world.getPlayer()` works through the bridge.**

- **evidence: reproduced-locally** — centre resolved to `206189.7, 36673.3`, `Mi-24P`. The probe
  no longer needs hardcoded coordinates; it can anchor on the aircraft.

**3. Buildings ARE extractable as data, not merely testable. This is the significant new result.**

- **evidence: reproduced-locally** — `world.searchObjects(Object.Category.SCENERY, <sphere>, …)`.

  | radius | objects | call cost |
  |---|---|---|
  | 50 m | 1 | 0 ms |
  | 150 m | 13 | 0 ms |
  | 300 m | 135 | 1 ms |
  | 600 m | *(skipped — predicted 8 ms over budget)* | — |

- Each object carries a **type name and a world position**: `SYRIA_BLOCK_BUILDING_05`,
  `SYRIA_BLOCK_BUILDING_04/03/01`, `SYRIA_HOUSE_08`, `SYRIA_HOUSE_03`, `SYRIA_CITY_HOUSE_02`,
  `TRASHCAN_EU_SMALL`, and — worth noting for `2026-09-13-dcs-power-lines-recon.md` —
  `POWER_TRANS_LINE_BIG`.
- **135 objects in ~283,000 m² is ~0.48 objects per 1,000 m²** in a built-up area. A theatre-wide
  extraction is not on the table, but an ownship-local bubble plainly is, and the shape
  (type name + position) is what `store.models.StoredFeature` already holds.
- **No tree objects appeared at any radius.** Consistent with trees being terrain-baked rather
  than scenery, which is what was expected — and it means `isVisible` remains the only candidate
  route for trees.
- **`getDesc()` added nothing beyond the type name in this capture** — it was read as
  `d.typeName or d.displayName`, so if a bounding box or dimensions are in there, this probe did
  not look. **Dimensions are what a LOS occluder actually needs**, so that is the next thing to
  read, not more positions.

**4. `land.getIP` works, and its returns are internally consistent — but it hit no buildings, and
that is not evidence either way.**

- **evidence: reproduced-locally** — 8 rays on compass octants from ownship at ground+2 m,
  slope −0.02, 5 km max.
- Hits at 50/48/65/146/474/428/289/238 m, y = 115/116/115/114/107/108/111/112.
- Solving each for the implied ownship ground height under a **pure terrain** model
  (`G = y − 2 + 0.02·d`) gives **114.0, 115.0, 114.3, 114.9, 114.5, 114.6, 114.8, 114.8** — a
  spread of 1 m across rays from 48 m to 474 m. That is a clean, flat-to-gently-descending terrain
  surface, and it says the call is returning real geometry.
- **Every hit is within ~1.5 m of local ground level.** Buildings here are 5–20 m tall, so a
  building hit would have come back at y ≈ 120–135. None did — *but* the nearest building found by
  Finding 3 sits ~15° off the nearest ray, a ~45 m lateral miss at that range. **Eight rays is too
  sparse to conclude anything**; this neither supports nor refutes object-awareness.

**5. The cost measurement failed, and the failure is mine, not DCS's.**

- **evidence: reproduced-locally (a broken estimator, diagnosed from its own output)**.
- `null_call` measured **0.000 ms**. `getHeight_batch_1` logged nine 0 ms samples and one 4 ms
  sample; the plain mean (0.400 ms) was then attributed entirely to *one* `getHeight` call —
  **400 µs each**. `isVisible_batch_1` did the same with a 15 ms outlier and came out at
  **1600 µs**. Both ladders refused their next rung as unaffordable, and **the X-B4 occlusion
  sweep was skipped for want of a cost estimate**.
- Those per-item figures are contradicted by the same run: **135 scenery objects searched in 1 ms**
  and **8 `getIP` raycasts in under 1 ms**.

> **CORRECTION, after flights 2 and 3 (same day).** This note first read those outliers as
> "scheduler/frame contention, not payload", by analogy with
> `2026-09-29-bridge-call-cost-at-scale.md` Finding 3. **That was wrong, and the same run's own log
> refutes it**: `null_call`, which touches no `land.*` at all, returned **max_ms = 0.00 across all
> ten samples** — not one spike. Both `land.*`-touching groups spiked exactly once each. An outlier
> that appears only in calls that touch terrain is not the scheduler. See Finding 7.
- The 1 ms `os.clock()` granularity was called out in that note *and* in the probe's own header,
  and the estimator still walked into it. Writing the caveat down is not the same as defending
  against it.
- **Fixed** (not yet re-flown): trimmed mean discarding the top `TRIM_TOP=2` samples, per-item
  floor lowered to 0.5 µs, call budget raised to 8 ms, and a discarded warm-up call added —
  `known_points` took **19 ms as the very first bridge call** while everything after it sat at
  0–1 ms, which is one-time setup, not per-call cost.

**6. What can still be said about cost, bounded rather than measured.**

- **evidence: reproduced-locally, but as bounds** — every call after the warm-up returned 0 or
  1 ms, including a 135-object scenery search and 8 raycasts. So the true per-call costs are
  **below the clock's resolution**, i.e. well under 1 ms for work of that size.
- Nothing hit the 25 ms abort ceiling. Nothing stuttered that the user reported.
- That is consistent with, but does not replace, a real per-item figure.

**7. Terrain access is cold/warm, and the cold cost is what the pilot feels. This is the most
important finding here.**

- **evidence: reproduced-locally (three flights) + the user's own observation**.
- The user, unprompted, on the two flights: *"In first flight, there was a noticeable stutter every
  few seconds. In the second flight, no stutter."* Flight 1 ran ~10 s of probing; **flight 2
  aborted after two calls and did essentially no work**, so "no stutter" there is not a contrast
  worth much — but flight 1's stutter is real signal, and it lines up with one spike per
  measurement group, groups being ~2.5 s apart.
- The mechanism is visible in flight 1's own numbers. `getHeight_batch_1` probed **the same single
  point ten times**: one 4 ms sample, nine at 0 ms. `isVisible_batch_1` likewise: one 15 ms, nine
  at 0. `null_call`: ten at 0, no spike. **First touch of a terrain location is expensive;
  repeats are free.**
- Flight 3 put a number on the upper end: `known_points`, which reads **eight locations scattered
  across the whole theatre in one call**, took **31 ms** — and tripped the (then 25 ms) abort
  ceiling, ending the sortie before a single measurement ran. A prior run had the same call at
  19 ms. Roughly **~4 ms per cold, distant location**.
- **This matters more than the steady-state figure, because probing new ground is the entire point
  of live terrain sampling.** A probe bubble that follows the aircraft is, by construction, always
  touching cold terrain. The warm number describes re-reading ground already sampled — which the
  M8 probe store is designed to avoid ever doing.
- It also means the trimmed mean added earlier is only half right: correct for estimating
  steady-state per-item cost, **wrong as a basis for "is this affordable"**, because it discards
  exactly the samples that caused the stutter. The probe now reports `steady_ms` and `PEAK_ms`
  side by side, flags any call at or above 12 ms `STUTTER_LIKELY`, and runs **separate cold and
  warm ladders** (`getHeightCOLD` probes a patch 4 km from the last one every repeat;
  `getHeightWARM` re-probes one patch) so the two regimes are measured rather than averaged.

**8. Flight 4 (complete run) — the cost answers, and they are good.**

- **evidence: reproduced-locally** — `dcs.log` 13:57:54 → 13:58:38, full plan, no abort.

  | N points | WARM (same patch) | COLD (patch 4 km on) | warm µs/pt | cold µs/pt |
  |---|---|---|---|---|
  | 500 | 0.125 ms | 0.250 ms | 0.25 | 0.50 |
  | 2601 | 2.250 ms | 2.500 ms | **0.87** | **0.96** |

- **`land.getHeight` costs ~0.9 µs per point, and cold is indistinguishable from warm.** A full
  M8 probe chunk — 2,601 points at 100 m spacing — is **2.25 ms**. That is the number the whole
  live-terrain-sampling design was waiting for, and it is cheap.
- **`land.isVisible` costs ~10 µs per ray**: 200 rays in 2.0 ms. A per-poll detectability gate
  over 200 candidates would cost 2 ms at 5 Hz, ~1% duty cycle.
- **Finding 7's cold/warm hypothesis is refuted at 4 km stride** — the ladders were built to
  separate the regimes and found no separation. The expensive events are elsewhere (Finding 9),
  and calling it "cold terrain" was too coarse.

**9. The stutter is first-touch of a *distant region* or *unused subsystem*, paid once — not a
per-point cost.**

- **evidence: reproduced-locally + the user's observation** (*"It does stutter a bit, shorter than
  first flight, but still noticeable"*).
- The only expensive calls in an otherwise sub-millisecond run: **`getIP` first use, 17 ms**;
  **`occlusion_desert` first chunk, 30 ms** (Deir ez-Zor, ~400 km from the aircraft, never
  touched). `occlusion_urban`'s first chunk, local: **1 ms**.
- `known_points` — eight theatre-scattered locations — cost **31 ms as one call when it ran first**
  (flight 3) and **median 0 ms, peak 5 ms as eight calls running last** (flight 4), after ~45 s of
  other terrain work. So the penalty is not "eight scattered points"; it is being the first thing
  to touch that machinery.
- **Design consequence, and it is favourable**: an ownship-following probe bubble samples ground
  *adjacent* to ground it just sampled. It pays this once at mission start, and again only when the
  aircraft reaches genuinely new terrain — not per chunk, and not per point.

**10. `isVisible` and `getIP` look terrain-only — they do not appear to test buildings or trees.**

- **evidence: reproduced-locally, two independent lines, with one confound still open**.
- **Occlusion sweep, 40 pairs per area:**

  | area | terrain-clear but `isVisible`-blocked | both clear | both blocked | terrain-blocked but visible |
  |---|---|---|---|---|
  | ownship (town/forest/mountains) | **1** | 26 | 13 | 0 |
  | Deir ez-Zor (desert control) | **0** | 27 | 13 | 0 |

  The urban-minus-desert gap is **1 in 40** — within the sampling noise the control exists to
  expose. If buildings and trees blocked `isVisible`, the ownship area should be markedly higher.
- **`getIP` corroborates independently.** Solving all eight rays for the implied ownship ground
  height under a pure-terrain model (`G = y − 2 + 0.02·d`) gives **119.5, 119.6, 119.9, 119.9,
  119.5, 120.2, 120.3, 119.8** — a **0.8 m spread across distances from 24 m to 1,788 m**. A ray
  that clipped a 5–20 m building would be metres out. None is.
- **The confound that stops this being final:** 40 random pairs in a 3 km box mostly miss a town
  occupying a small part of it, so "no gap" is not yet distinguishable from "no sightline crossed
  a building". **Resolved by the `through_buildings` step added after this flight**, which asks
  `world.searchObjects` where the buildings are and fires a ray through each one, 60 m either
  side at 2 m AGL. Nothing to interpret: blocked or clear.

**11. Scenery objects carry no extent — position and type name only.**

- **evidence: reproduced-locally** — full `getDesc()` dump:
  `life=20 | _origin= | category=4 | typeName=POWER_TRANS_LINE_BIG | displayName=`.
- No bounding box, no dimensions. So using scenery as LOS occluders needs a **type-name → size
  table** built once offline. The type names are a finite catalogue
  (`SYRIA_BLOCK_BUILDING_01..05`, `SYRIA_HOUSE_03/08`, `SYRIA_CITY_HOUSE_02`, …), so this is
  tedious rather than hard — but it is work that did not exist in the plan.

**12. X-B4 ANSWERED: `land.isVisible` is terrain-only. Buildings do not block it. Flight 6.**

- **evidence: reproduced-locally, confound removed** — `dcs.log` 14:16:38 → 14:16:55, full run.
- `through_buildings` asks `world.searchObjects` where the buildings actually are, then fires a
  ray through each one — 60 m either side of its centre, 2 m above local ground — with the
  terrain-only verdict computed over the same 120 m so a rise between endpoints cannot be mistaken
  for the building.

  | test | buildings | blocked by something | clear | terrain-blocked |
  |---|---|---|---|---|
  | 200 m radius | 12 | **0** | 12 | 0 |
  | wider | **40** | **0** | **40** | 0 |

  Named in the sample: `SYRIA_BLOCK_BUILDING_05`, `SYRIA_BLOCK_BUILDING_04`, `SYRIA_HOUSE_08`,
  `TRASHCAN_EU_SMALL` — every one `CLEAR`.
- **Forty rays fired deliberately through forty known buildings, not one blocked.** This is not a
  statistical argument and there is no sampling confound left: the ray geometry was derived from
  the buildings' own reported positions.
- The same flight's occlusion sweep agrees and is cleaner than flight 4's: **0/40 terrain-clear-
  but-`isVisible`-blocked in both areas** (ownship 37 clear / 3 terrain-blocked; desert 27 / 13).
- **Trees: the same conclusion, one step weaker.** No tree ever appears as a scenery object, so
  there is nothing to fire a ray *through* by construction; the evidence is the 0/40 sweep in an
  area the user deliberately positioned near forest. Combined with buildings being definitively
  invisible to the call, a tree-only exception would be a strange thing for the engine to make.
- **This reconciles with `Scripts/AI/Detection.lua` rather than contradicting it.**
  `objects_LOS_test = true` and `trees_LOS_test_T4 = true` describe **ED's AI detection**, which is
  a different code path from the scripting API. Both facts hold; they were never about the same
  thing. The install file was never going to answer this, which is why it needed a flight.

**13. What this costs the project, and what it opens.**

- **`land.isVisible` cannot replace our own LOS.** It sees exactly what we already see — the bare
  terrain mesh — so routing occlusion through it would buy nothing but a bridge call. The hope
  recorded in X-B4 ("if it is cheap and does see objects, it could replace our elevation-grid LOS
  outright") is dead.
- **But the raw material for doing better ourselves is now in hand**, and that is the more useful
  outcome:
  - **Buildings**: `world.searchObjects` returns **590 objects in a 600 m radius**, each with a
    world position and a type name. That is denser and more authoritative than OSM's building
    footprints.
  - **Trees**: world-model already holds **44,811 OSM `landcover` polygons** (forest/orchard/scrub),
    which is the only tree source there is going to be.
  - **The gap is extent.** Scenery carries no dimensions — the full `getDesc()` is
    `life / _origin / category / typeName / displayName`, and `life` is hit points, not size
    (`SYRIA_BLOCK_BUILDING_05` = 100, `_03` = 150, `POWER_TRANS_LINE_BIG` = 20). A type-name → size
    table, built once offline over a finite catalogue, is the missing piece.

**14. Cost, third independent confirmation, and where the stutter actually lives.**

- `getHeight` **0.8 µs/point** warm, **1.1 µs/point** cold — 2,601 points (a full M8 chunk) in
  **2.0 ms**. `isVisible` **10.6 µs/ray** — 200 rays in 2.1 ms. Three flights now agree.
- **Scenery search cost is the one that bites, and it is superlinear:**

  | radius | objects | cost | µs/object |
  |---|---|---|---|
  | 150 m | 12 | 0 ms | — |
  | 300 m | 126 | 1 ms | 8 |
  | 600 m | 590 | **18 ms** | 31 |

  **Keep scenery searches at or below 300 m.** 600 m is an 18 ms call, a dropped frame on its own.
- **The stutter is confirmed as distance, not volume.** `occlusion_desert`'s first chunk cost
  **41 ms** (Deir ez-Zor, ~400 km away, untouched) while `occlusion_urban`'s identical first chunk
  cost **1 ms** locally. `known_points`, eight theatre-scattered locations, ran at median 7 ms /
  peak 9 ms. Local work is sub-millisecond throughout. **An ownship-following probe bubble is the
  cheap case; jumping across the map is the expensive one** — and the probe is the only thing here
  that jumps.

**15. The API surface, dumped from the running engine — three leads, one of them cheap.**

- **evidence: reproduced-locally** — `pairs()` over the live tables, flight 7, `dcs.log` 14:31:15.
- Asked because the user's question ("is there any DCS call that accounts for buildings and
  trees?") **cannot be answered from the install** — every one of these is native, and `grep` over
  `Scripts/`/`MissionEditor/` finds no definition, only `class(SceneryObject, Object)`.

  | table | members that matter |
  |---|---|
  | `land` (9) | `getHeight` `getSurfaceType` `isVisible` `getIP` — all tested, all terrain-only. Plus **`profile`**, `getSurfaceHeightWithSeabed`, `getClosestPointOnRoads`, `findPathOnRoads` |
  | `world.VolumeType` | **`SEGMENT=0`** `BOX=1` `SPHERE=2` `PYRAMID=3` |
  | `Controller` (23) | **`isTargetDetected`** `knowTarget` `getDetectedTargets` `Detection:table` |
  | `world` (16) | `searchObjects` **`weather:table`** `getAirbases` `getMarkPanels` `removeJunk` |

- **`world.VolumeType.SEGMENT` exists.** `searchObjects` takes a volume and a segment volume is a
  line, so a segment search along a sightline should return the scenery intersecting it — building
  occlusion computed by DCS's own intersection test, **removing the type-name → size table**
  (Finding 11) that is otherwise the one thing standing between us and an occluder layer. This is
  the cheap win.
- **`land.profile` exists**, and is a straight upgrade to `query/line_of_sight.py` regardless of
  buildings: our LOS currently spends 20+ `getHeight` calls per sightline, and this returns the
  terrain along a line in one call.
- **`Controller.isTargetDetected` exists**, and is the AI path `Detection.lua` configures with
  `objects_LOS_test`/`trees_LOS_test_T4`. So the engine **can** test trees — only the `land.*`
  calls do not. **But it answers "has this AI detected that target"**, folding skill, alertness,
  range and reaction time on top of line of sight. It is not a clean LOS primitive and must not be
  treated as one; it is also the wrong shape for Petrovich, whose knowledge is supposed to be
  bounded by his own perception, not an AI unit's.
- **Trees remain out of reach either way.** They are not scenery objects — seven flights of
  `searchObjects` have never returned one — so a SEGMENT search cannot find them. If buildings
  work this way, trees stay OSM landcover's job.

**16. A SEGMENT volume search DOES return buildings on the sightline. This is the answer to the
user's question, and it costs nothing.**

- **evidence: reproduced-locally, with a discriminating control** — flight 8, `dcs.log` 14:41:08.

  | 120 m segment, 2 m AGL | scenery hits |
  |---|---|
  | through a building (position taken from `searchObjects` itself) | **3** — `SYRIA_BLOCK_BUILDING_05`, `_06`, `_03` |
  | open ground, 3 km away, same length | **0** |
  | `land.isVisible` on the identical endpoints, same payload | `true` (clear) |

  Cost: **0.00 ms**.
- The open-ground control is what makes this a result rather than a coincidence: it rules out
  "the search returns everything near the line" and leaves "it returns what the line intersects".
- **So the answer to "is there any DCS call that accounts for buildings" is yes** —
  `world.searchObjects` with `world.VolumeType.SEGMENT`. And it needs **no type-name → size
  table**, which Finding 11 had identified as the blocker.
- **Trees are still not covered** and cannot be by this route: they are not scenery objects.

**17. Three other things the same flight settled, free.**

- **`land.profile` works**: a 1 km line returned **14 points at ~77 m spacing** carrying real
  terrain y (117.5 → 148.6 m), in **1 ms**. One call in place of the 20+ `getHeight` calls
  `query/line_of_sight.py` currently issues per sightline. Note it did **not** start at the
  requested `from` — first point was 160 m along — so the sampling rule needs establishing before
  use.
- **Fog is readable through the bridge**: `world.weather.getFogThickness()` = **320**,
  `getFogVisibilityDistance()` = **2300**. That is the first half of X-B4's weather question
  answered — meteorological visibility is a ceiling on detection for every optic, and it is now
  reachable. (Setters exist too; we have no business calling them.)
- **`Controller.Detection`** is a bitmask: `VISUAL=1 OPTIC=2 RADAR=4 IRST=8 RWR=16 DLINK=32`.

**18. The question that decides whether Finding 16 is usable: 3D or 2D?**

- **Not yet answered, and it is not a detail.** Every segment in Finding 16 was at **2 m AGL**, so
  the result is equally consistent with a true 3D intersection *and* with a 2D footprint test that
  ignores `y` altogether. If it is the latter, a Mi-24P at 200 m flying **over** a town would read
  as blocked by every building beneath it — worse than useless, and wrong in precisely the
  situation the aircraft spends the sortie in.
- **Resolves with:** `petrobrain-segment-altitude-probe-hook.lua` (deployed) — the same segment
  through the same buildings at 2/15/50/200/500 m, plus the realistic slanted geometry (200 m up,
  1 km back, down to a point past the buildings). Hits falling to zero with altitude is a 3D test;
  hits staying flat is a footprint.

**19. The SEGMENT search is a TRUE 3D intersection test. Finding 16 is usable.**

- **evidence: reproduced-locally** — flight 9, `dcs.log` 14:49:53. Same segment, same buildings
  (`SYRIA_BLOCK_BUILDING_04`, ground 110.9 m), only the altitude varied.

  | segment altitude | scenery hits |
  |---|---|
  | 2 m AGL | **6** |
  | 15 m | **0** |
  | 50 m | 0 |
  | 200 m | 0 |
  | 500 m | 0 |
  | **realistic slant** — 200 m up, 1 km back, down to 2 m past the buildings | **2** |

- **Flying *over* a town is not blocked; looking *down through* it is.** That is exactly the
  behaviour required, and it rules out the 2D-footprint failure mode that would have made the
  mechanism worse than useless for a helicopter.
- Hits vanish by **15 m**, so these `SYRIA_*` buildings are under 15 m — consistent, and it means
  the test is sensitive to real geometry rather than to a fixed bounding height.
- **So the route to building-aware LOS is settled**: `world.searchObjects` with
  `world.VolumeType.SEGMENT` along the sightline, no size table, correct in 3D.

**20. The per-search cost figure from that flight is WRONG, and by the same mistake as twice
before.**

- The flight logged `segment_cost_1: ms=1.00 -> ~1000 us per segment search`, then refused the
  next rung on it. **Wrong by one to two orders of magnitude**, and flight 8 had already
  contradicted it — a standalone SEGMENT search measured **0.00 ms**.
- Two compounding errors, both mine:
  1. **Setup inside the measurement.** The cost payload reused a preamble that runs a 200 m SPHERE
     search to locate a building. At N=1 that sphere search *is* essentially the entire cost, and
     dividing by one segment charged all of it to the segment.
  2. **One sample at the clock's resolution.** 1 ms granularity means a single "1.00 ms" reading
     is "somewhere in 0–2 ms" — and it was then multiplied by 20 to refuse the next rung.
- **This is the third instance of one shape**: fixed overhead charged to per-item cost, off a
  quantisation-limited sample. It produced the bogus 400 µs and 1600 µs figures earlier (Finding
  5), where it shut down two ladders and the entire X-B4 sweep; then a cold estimate gating warm
  work; now this. Noticing it each time has not prevented the next one. **The defence has to be
  structural**: no setup inside a cost payload, an explicit N=0 baseline measured identically and
  subtracted, and trimmed repeats with the peak still logged.
- **Resolves with:** `petrobrain-segment-cost-probe-hook.lua` (deployed), which does all three.

### Reproducible Test

Re-fly with the fixed probe (deployed). Extract with:

```sh
grep "PetrobrainElevProbe" "$DCS_SAVED_GAMES_PATH/Logs/dcs.log"
```

### Unresolved

- **X-B4's core question — do trees and buildings block `land.isVisible`?** Unanswered; the
  occlusion sweep was skipped by Finding 5's bad estimate. **Resolves with:** one more sortie on
  the fixed probe, same setup (town + forest + mountains within ~1.5 km of the aircraft).
- **Per-item cost of `getHeight` and `isVisible`.** Same sortie.
- **Do scenery objects carry dimensions?** Finding 3 read only the type name. A LOS occluder needs
  extent, not just a point. **Resolves with:** dumping a full `getDesc()` table for one object.
- **Whether a `dostring_in` payload blocks DCS's own frame.** **Effectively answered yes** by
  Finding 7 — the pilot felt a stutter that tracks the probe's own cold calls — but not yet
  measured against DCS's frame-time counter, which is what would turn "he felt it" into a number.
- **The cold penalty's shape**: is it per location, per terrain page, or per distance from
  the last access? That decides whether a *contiguous* expanding bubble (cheap, one page at a
  time) behaves differently from scattered sampling (expensive). The cold/warm ladders measure
  the magnitude; they do not yet separate these.
- **Per-item cost of `getHeight` and `isVisible` in the warm regime.** Flight 3 aborted before
  reaching them.
