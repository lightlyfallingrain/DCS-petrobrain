# M6 — terrain semantics (ridge/valley extraction and validation)

Dated: 2026-09-05. Covers Stage 2/3/4 of `plans/m6-terrain-semantics/plan.md`: rebuilding the
real `world-model/data/world-model/latakia-20km.sqlite` with the new `terrain.curvature` +
`terrain.features` pipeline wired in, visually sanity-checking the output with
`tools/inspect_terrain.py`, tuning thresholds, spot-checking against independent (non-DCS)
elevation data, wiring `nearby_ridges`/`nearby_valleys` into `describe_position`, and reading
the result "from an Mi-24 cockpit perspective" per the plan's validation philosophy.

**Bottom line up front**: the algorithm runs correctly and produces geometrically valid
`ridge`/`valley` features, and it clearly and correctly identifies the region's *most dominant*
relief (the single highest peak in-bbox, the single most pronounced coastal-plain trough). But
the per-cell discrete-Laplacian classification is dominated by high-frequency
checkerboard-pattern noise across the region's mountainous quadrant, and several real,
independently-confirmed secondary bumps/troughs are missed or misclassified. This is a real,
recordable "partially useful, not fully useful yet" finding, not hidden — see Finding 2 and the
Usefulness Check below.

## Threshold tuning (Stage 2)

Stage 1 shipped a first-guess `DEFAULT_CURVATURE_THRESHOLD_M = 3.0`, `DEFAULT_MIN_CELL_COUNT = 4`.
Rendering `tools/inspect_terrain.py`'s per-cell classification map against the real, full
41x41 `latakia-20km` elevation grid at that threshold showed **~71% of interior cells**
(1084 of 1521) classified as ridge or valley — visually a near-solid red/blue checkerboard over
the region's north-east (mountainous, An-Nusayriyah-foothill) quadrant, not usable ridge/valley
lines.

Threshold sweep (cell classification / extracted components, `min_cell_count=4` held constant
except where noted):

| threshold_m | ridge cells | valley cells | % of 1521 interior cells | ridge components | valley components |
|---|---|---|---|---|---|
| 3.0 (Stage 1 default) | 491 | 593 | 71.3% | 39 | 33 |
| 10.0 | 393 | 428 | 54.0% | 31 | 23 |
| 20.0 | 308 | 308 | 40.5% | 23 | 20 |
| 30.0 | 247 | 244 | 32.3% | 15 | 15 |
| 50.0 | 166 | 172 | 22.2% | 7 | 11 |
| 80.0 | 92 | 95 | 12.3% | 3 | 3 |
| 120.0 | 42 | 38 | 5.3% | 0 | 2 |

**Finding 1 — raising the threshold reduces but does not eliminate the checkerboard.** Even at
80 m (a curvature magnitude far above what a smooth rolling hill would produce), the rendered
map over the region's rugged north-east quadrant still shows adjacent cells flipping between
ridge/valley classification, not clean contiguous lines. This is a genuine signature of real,
high-frequency local relief at or below the 500 m probe grid's Nyquist-ish resolution floor (the
plan's flagged "Grid resolution vs. feature scale" risk), not a threshold-tuning artifact that a
slightly different number would resolve.

**Chosen defaults**: `DEFAULT_CURVATURE_THRESHOLD_M = 20.0`, `DEFAULT_MIN_CELL_COUNT = 6`
(`terrain/curvature.py`, `terrain/features.py`). This keeps the flat coastal-plain/sea half of
the region (correctly) almost entirely unclassified, while producing a workable, small set of
larger components in the mountainous quadrant rather than either the Stage-1 checkerboard or the
80m+ near-empty extreme. It is a compromise, not a fix for Finding 1 — recorded honestly per the
plan's Stage 2 instruction.

Real rebuild at these defaults (`tools/build_world_model.py latakia-20km --probe-output
data/raw/dcs/2026-09-04/terrain_probe_output_full.jsonl`):

```
airfield: 1
named_place: 108
navaid: 8
ridge: 12
road: 3266
runway: 2
settlement: 338
valley: 12
water: 117
```

`tools/inspect_terrain.py`'s rendered map (12 ridge + 12 valley lines drawn over the per-cell
classification) confirms the geographic shape is right at the macro scale: the south-west
(coastal plain and sea, low real elevation) is almost entirely gray/unclassified, and every
extracted ridge/valley line falls in the north-east quadrant, which is exactly where the real
An-Nusayriyah coastal-range foothills rise inland of Latakia. The checkerboard noise Finding 1
describes is still visible in that same quadrant's background cell coloring, underneath the
extracted lines.

## Real-data spot-check against independent elevation (Stage 3)

No SRTM tile is staged for this region (confirmed again this session — `data/raw/dem/` holds
only the Gemerek/M4 `N39E036.hgt` tile, which does not cover Latakia). Per the plan's Risk
"No SRTM ground truth for this region," an ad-hoc independent cross-check was used instead:
the public Open-Elevation API (`api.open-elevation.com`, SRTM/ASTER-backed), queried live over
several lat/lon transects spanning the region's bbox
`(35.335, 35.834) - (35.521, 36.061)` (south/west - north/east). This is **not** a substitute for
a properly staged SRTM tile (no licensing/attribution review was done, and it is not wired into
the pipeline or stored) — it is a one-off, non-circular sanity check for this research note only,
consistent with the plan's framing of external cross-checks as informal/stretch-goal for M6.

Six points were picked from the transects as genuine local extrema in the *external* data (a
point strictly higher, or strictly lower, than both its immediate transect neighbours),
independent of anything DCS reports, then converted to DCS `(x, z)` via `coordinates.wgs84_to_dcs`
and checked against the real store's `nearest_feature(["ridge"]/["valley"], x, z)`:

| point | external elevation | DCS elevation (`sample_grid`) | nearest ridge | nearest valley | verdict |
|---|---|---|---|---|---|
| R1 (35.50, 36.05) — local peak | 542 m | 514.7 m | **197 m** | 1695 m | **hit** |
| R2 (35.46, 36.01) — local bump | 211 m | 186.8 m | 1650 m | 907 m | **miss** (nearer to a valley than a ridge) |
| R3 (35.42, 36.02) — local peak | 288 m | 258.9 m | 1130 m | 468 m | **miss** (nearer to a valley than a ridge) |
| V1 (35.50, 35.95) — local trough | 43 m | 31.9 m | 1407 m | **50 m** | **hit** |
| V2 (35.42, 35.93) — local trough | 17 m | 15.5 m | 3649 m | 3901 m | **quiet** (nothing nearby either way) |
| V3 (35.46, 35.96) — local trough | 58 m | 60.8 m | 1995 m | 878 m | **partial** (valley nearer, but not close) |

Two side findings from this same table, both worth recording:

**Finding 2 — the classifier reliably catches the single most dominant peak/trough in-bbox, but
misses secondary ones.** R1 (the region's single highest external elevation, 542 m) and V1 (a
pronounced coastal-plain trough) both land within ~200 m of a same-kind extracted feature —
a genuinely good result given the 500 m grid spacing. But R2 and R3, real local peaks by the
external data, are *closer* to an extracted valley than to any extracted ridge; V2, a shallow
near-coastal dip, has nothing extracted nearby in either direction. This is consistent with
Finding 1: a checkerboard-noisy classification field means the connected-component step can
group a mix of nearby ridge- and valley-labelled cells in ways that do not track a real
secondary bump/trough cleanly, especially where the underlying relief is subtler than the
region's one dominant peak.

**Finding 3 (incidental, positive) — DCS elevation agrees well with the independent source.**
Every spot-check point's `sample_grid(..., "elevation", ...)` value sits within ~30 m of the
external (SRTM/ASTER-backed) value at the same lat/lon (e.g. V2: 15.5 m DCS vs 17 m external).
This is not a formal cross-check (no tile was staged, no systematic delta/stddev was computed
the way M4's `ingest_probe` SRTM-delta stats do), but it is a reassuring incidental confirmation
that the underlying elevation grid this milestone's terrain analysis builds on is itself sound
for this region — the ridge/valley limitations above are in the *derived analysis*, not in the
source DCS elevation data.

## Usefulness check — reading `describe_position` output as a crew member would (Stage 3/4)

`nearby_ridges`/`nearby_valleys` (separate fields, per the confirmed decision) were wired into
`describe_position` (`query/describe.py`) using the same `nearest_feature` machinery as
`nearest_road`/`nearest_water`, restricted to `kind="ridge"`/`"valley"`. Three real positions:

| position | elevation | nearby ridge | nearby valley |
|---|---|---|---|
| Bassel Al-Assad ARP (coastal, control point) | 28.5 m | 3202 m, orientation 79 deg | 3202 m, orientation 76 deg |
| Region centre (still coastal plain) | 37.1 m | 2062 m | 2693 m |
| Eastern foothills point (x=52000, z=12000) | 258.3 m | **1081 m** | 2655 m |

This is directionally sensible and, at this coarse level, a real "yes" on the usefulness
question the plan poses: a crew position on the coastal plain correctly reports both features
several kilometres away (nothing masking nearby), while a position already up in the foothills
correctly reports a much closer ridge. That is the qualitative signal a crew member would expect.

**But** — per the plan's explicit instruction to record "not useful yet" findings rather than
hide them — this usefulness check does **not** extend to the fine-grained tactical question the
plan poses as the real test ("is there a ridge between me and the target," "am I in a valley
that masks me from the east"). At 500 m grid spacing with the checkerboard-noise problem from
Finding 1/2, `nearby_ridges`/`nearby_valleys` can currently answer "is there large-scale relief
in my general vicinity" but cannot be trusted for a specific bearing/masking claim — Finding 2's
R2/R3 misses show the *nearest* feature is not reliably the *geographically correct* one once
you move away from the single most dominant peak/trough in the bbox. This is the "only marginally
useful" finding the plan's Stage 3 explicitly asked to surface, not a full pass.

## What would improve this (not built this milestone, per the plan's escalation rule)

Per `plans/m6-terrain-semantics/plan.md`, no new dependency or new live DCS probe was added
unilaterally this milestone — both are flagged as open, user-decision items, not solved here:

- **A denser probe grid** (finer than 500 m spacing) would directly address Finding 1's
  Nyquist-floor problem, at the cost of a new live-mission probe run (real wall-clock cost on the
  DCS machine, per M5's precedent).
- **A smoothing/pre-filter step, or a proper multi-scale curvature method** (would likely need
  `numpy`/`scipy.ndimage`, per the plan's flagged fallback) could suppress the checkerboard noise
  without needing a denser grid — but this is a new dependency, explicitly deferred to a future
  decision rather than added mid-implementation.

Neither is needed to ship M6's minimal, honestly-labelled feature (`confidence: "low"` on every
emitted ridge/valley feature already signals this to any downstream consumer), but both are the
concrete next steps if ridge/valley semantics need to support finer-grained tactical questions
later.

## Escalation status

No numpy/scipy escalation was needed or used — the stdlib discrete-Laplacian + connected-component
+ closed-form principal-axis approach from the plan works as specified, runs correctly end to end,
and produces the results in this note. The findings above are about the *algorithm's ceiling at
this grid resolution*, not about stdlib being insufficient to implement it.
