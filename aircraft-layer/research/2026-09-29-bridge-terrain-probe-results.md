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
  and **8 `getIP` raycasts in under 1 ms**. An outlier that large is scheduler/frame contention,
  not payload — precisely the shape `2026-09-29-bridge-call-cost-at-scale.md` Finding 3 recorded
  (maxima an order of magnitude over p99, indifferent to payload size).
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
- **Whether a `dostring_in` payload blocks DCS's own frame.** Still unestablished, and still the
  question that decides whether any of this is safe at production rates.
