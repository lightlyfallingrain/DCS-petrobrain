# Elevation cost probe — results

Dated: 2026-10-05. Flown by the user on the Windows box with DCS alone, Syria mission, per
`docs/acceptance/2026-09-29-elevation-cost-probe.md`. Log: `win-mac-sync/from-windows/dcs.log`,
31 lines prefixed `PetrobrainElevProbe`. Closes the two questions
`research/2026-09-28-live-terrain-probing-feasibility.md` left open, and answers them in
opposite directions.

## Headline: it works, it is cheap per item, and **it stutters**

> *"I did notice a small but annoying stutter every few seconds."* — the user, unprompted, during
> the probe window.

That is the result this flight existed to get, and no log could have produced it. The log agrees
with the feeling, which is what makes it actionable rather than a mystery: the probe itself
flagged `STUTTER_LIKELY` on one batch and recorded a 26 ms single call on another, while the
*steady-state* numbers look entirely comfortable. **A design that read only the medians would have
concluded this was free.**

## Question 1 — does `land.getHeight` work through the mission bridge? **Yes, exactly.**

Eight coordinates across the theatre, compared against the 2026-09-06 mission-editor probe's own
recorded values (`win-mac-sync/from-windows/elevation_probe_output_20260906T132234Z.jsonl`):

| point | bridge | recorded | delta |
|---|---|---|---|
| damascus_osdi | 612.001 | 612.001 | +0.000 |
| latakia_oslk | 28.223 | 28.223 | +0.000 |
| beirut_olba | 12.000 | 12.000 | +0.000 |
| aleppo_osap | 382.191 | 382.191 | +0.000 |
| klieat_olka_coastal | 4.411 | 4.411 | +0.000 |
| mezzeh_os67_urban | 727.811 | 727.811 | +0.000 |
| deir_ez_zor_osdz_desert | 208.433 | 208.433 | +0.000 |
| kahramanmaras_ltcn_mountainous | 478.397 | 478.397 | +0.000 |

**Bit-identical at every point**, including the coastal and urban cases where a different surface
model would have shown up. `land.getSurfaceType` returned alongside each (1 = land at seven, 5 at
Beirut). So the bridge reaches the same surface the mission-editor probe read — the inference held,
and is now demonstrated rather than assumed.

## Question 2 — what does it cost? Per item, very little. Per *batch*, enough to drop a frame.

`null_call` measured **0.00 ms** across ten repeats, so there is no meaningful fixed bridge
overhead to amortise. Everything below is per-item cost.

| batch | steady | median | **peak** | steady/item | **peak/item** |
|---|---|---|---|---|---|
| `getHeight` warm, 2601 pts | 3.375 ms | 4 ms | 6 ms | 1.3 µs | 2.3 µs |
| `getHeight` **cold**, 2601 pts | 4.500 ms | 4 ms | **24 ms** | 1.7 µs | **9.2 µs** `STUTTER_LIKELY` |
| `isVisible`, 200 rays | 2.000 ms | 2 ms | 3 ms | 10.0 µs | 15.0 µs |
| `occlusion_desert` chunk | — | — | **26 ms** | — | — |

**Cold is 4× worse than warm at the peak, not at the median.** First touch of a region costs ~9.2
µs/item against 2.3 µs warm; the steady-state figures barely differ (1.7 vs 1.3). This is the same
cold/warm shape the 2026-09-29 bridge measurement hinted at with its 20 ms outliers, now isolated
and attributed.

**`isVisible` is ~7× the cost of `getHeight` per item** (10 µs vs 1.3 µs steady). Any LOS design
that treats the two as interchangeable is wrong by nearly an order of magnitude.

### Where the felt stutter came from

The probe runs **one bridge call per 250 ms**, deliberately spread across frames. So a 24–26 ms
call lands roughly every quarter second during the batch phases — and at 60 fps that is 1.5
frames' worth of work on DCS's own thread, repeatedly. "Every few seconds" matches the phase
boundaries, not a one-off.

**The throttle did its job and the stutter still happened**, which is the lesson worth keeping:
spreading calls across frames bounds the *duty cycle*, not the *single-call* cost. A 2601-point
batch is one call no matter how far apart the calls are.

## What this means for `X-B29` (batched LOS in the aircraft layer)

The plan is not dead — it is **bounded**, and the bound is batch size rather than call frequency.

Working from the measured peaks, not the medians, and budgeting **≤2 ms per call** (an eighth of a
60 fps frame):

- `getHeight`, cold, at 9.2 µs/item → **~215 points per call**
- `isVisible`, at 15 µs/item → **~130 rays per call**

For a 10 km player bubble that is comfortable: ~130 rays is far more than the contact count a
sortie actually carries, and `PLAYER_BUBBLE_RADIUS_M` already bounds the candidate set upstream.
**The 2601-point batch this probe used is ~12× larger than anything the real design needs** — it
was sized to find the ceiling, and it found it.

Design constraints this hands X-B29, none of which were known before:

1. **Cap the batch, not just the rate.** A per-call item cap is the control that matters; spreading
   calls out does not help a single oversized one.
2. **Budget against the cold figure.** A sweep entering a region the engine has not touched pays
   9.2 µs/item, and that is exactly when a player is flying somewhere new — the worst case is
   correlated with the interesting case.
3. **Price `isVisible` separately from `getHeight`.** 7× apart.
4. **Warm-up is real and exploitable**: the same batch costs 2.3 µs/item peak once touched.

## An unplanned finding: `isVisible` **does** see buildings

`occlusion_urban` reported **`TERRAIN_CLEAR_VIS_BLOCKED=2`** against `occlusion_desert`'s **0** —
two of forty urban pairs where terrain alone was clear but `land.isVisible` said blocked, and none
in open desert. `scenery_search` resolved real building objects at the same place (`BUNKERHILL`,
`TAXI_OMNI_BLUE`, with life values), and the 600 m radius found 106 of them.

This **refines rather than contradicts** `research/2026-09-29-tree-los-probe-results.md`'s
conclusion that no DCS call sees *trees*: that note's own wording was "terrain and scenery only",
and buildings are scenery. What is new is a positive measurement that the scenery half actually
fires, on real geometry, which the tree probe could not show because it was looking for the half
that does not exist.

So `X-B30` (building occlusion) has its evidence: it is reachable, it costs 10 µs a ray, and
nothing occludes behind a building in either current path. Caveat worth stating — the directly
targeted `through_buildings` and `through_buildings_wide` checks both reported **6/6 clear, 0
blocked**, so the two positives came from the broader sweep rather than the aimed test. Whether
that is geometry (the aimed pairs happened not to cross a building) or a difference between the
two call shapes is **not established here** and should not be assumed either way.

## Not answered, and not attempted

- **`.surface5` per-node heights.** Still only the envelope decoded. This probe does not touch the
  file route, and if live probing is affordable at the batch sizes above, that decode may never
  need attempting — see `todo/backlog.md`'s `X-B26`.
- **Whether a 2 ms budget is actually imperceptible.** The user felt 24–26 ms. Nobody has flown a
  2 ms version. The arithmetic says it should vanish; that is a prediction, not a measurement.
