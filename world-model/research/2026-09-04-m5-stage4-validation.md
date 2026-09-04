# M5 Stage 4 — validate correctness (real Latakia store)

Dated: 2026-09-04. Follows on from `2026-09-04-m5-stage3-smoke-rung.md` (elevation/surface_type
probe complete, real store rebuilt with all six layers populated). This note covers Stage 4 of
`plans/m5-first-persistent-model/plan.md` / `checklist.md`: validating the real, already-built
`world-model/data/world-model/latakia-20km.sqlite` against independent, non-DCS-derived sources
wherever the checklist calls for one, per the project's standing rule against validating
DCS-derived data against DCS-derived data (M1 Finding 2).

All numbers below come from a single run of `tools/analyze_m5_stage4_validation.py` (a throwaway,
read-only analysis script, not part of the pipeline) against the real store, transcribed by hand.
The one pinnable check (the control-point tolerance band) is also a real, CI-running test:
`tests/test_describe_position.py::test_describe_position_control_point_latakia_arp`.

## Summary — pass/fail per checklist bullet

| # | Checklist item | Result |
|---|---|---|
| 1 | Control-point test at Latakia ARP | **PASS** |
| 2 | R\*Tree-vs-brute-force agreement test | **Already satisfied** (Stage 1, no extension needed) |
| 3 | 6-8 point manual spot-check table | **PASS** (8 points, all plausible; outside-coverage degrades to explicit nulls) |
| 4 | Airfield: derived point vs in-game ARP gap (~1504 m) | **PASS** (1504.28 m) |
| 5 | Airfield: ILS/PRMG bearing agreement (~1°) | **PASS, better than expected** (0.0085°) |
| 6 | Airfield: ILS axis length vs published 2797 m (~2635 m expected, shorter) | **PASS** (2635.04 m) |
| 7 | Cross-subsystem: `getSurfaceType` ROAD/RUNWAY vs `.routes` centerline distance | **PASS** (reported, plausible distribution) |
| 8 | DCS-vs-OSM road displacement (~1.0-1.3 km expected) | **Computed, does not match expectation** — see Finding 2 below (open, explained) |

One genuine defect was found and is **not smoothed over**: a single corrupted DCS road feature in
the real store, and its downstream effect on `describe_position`. See Finding 1.

---

## 1. Control-point test (Latakia ARP)

Independent source: `tests/control_points.py`'s `"Bassel Al-Assad / Latakia (OSLK)"` entry — a
live-DCS `coord.LOtoLL`-derived `(dcs_x, dcs_z)` paired with a **published, non-DCS** real-world
ARP (SkyVector), never validated against DCS-derived data (per M1 Finding 2 / the plan's repeated
non-circularity requirement).

| | value |
|---|---|
| DCS-native `(x, z)` | (43237.96875, 5841.16455078) |
| `describe_position`'s `(lat, lon)` | (35.412866, 35.949954) |
| Published real-world ARP `(lat, lon)` | (35.40109, 35.94868) |
| Residual (haversine) | **1314.5 m** |
| Expected max residual (M1's ~1.0-1.3 km DCS-terrain-placement figure, plus margin) | 1500.0 m |

**PASS** — within the tolerance band, consistent with M1's already-established, explained
DCS-terrain-art displacement (not a transform bug). `elevation.dcs_m` at this point is 28.69 m,
`surface_type` is `LAND` — both plausible for a paved airfield apron.

Pinned as a real test: `tests/test_describe_position.py::test_describe_position_control_point_latakia_arp`
asserts `residual_m <= expected_max_residual_m` as a tolerance band, not an exact value, and needs
no store content beyond an empty schema (`lat`/`lon` come purely from `coordinates.dcs_to_wgs84`)
— so it runs in CI without the gitignored real `.sqlite`.

## 2. R\*Tree-vs-brute-force agreement

Already satisfied by Stage 1's `tests/test_store_reader.py`, which runs this exact agreement check
over 200 random synthetic point features (50 query points) and a mixed point/LineString set (30
query points), comparing `store.reader`'s R\*Tree-pruned `nearest_feature` against a brute-force
reference implemented independently in the test using `geometry` functions directly (not by
importing store internals). No extension was needed for Stage 4's purposes — the existing test
already proves the property this bullet asks for (index-pruned results agree with a full scan),
and it does so against synthetic fixtures rather than the real store, which is the right call for
a structural/correctness property that has nothing to do with what data happens to be loaded.

## 3. Manual spot-check table (8 points, real store)

Real coordinates picked from the actual built store (not synthetic). `describe_position` output,
transcribed directly:

| label | x, z (DCS) | lat, lon | elev (m) | surface | nearest_road DCS (m) | nearest_road OSM (m) | nearest_water (m) |
|---|---|---|---|---|---|---|---|
| town centre (Jablah) | 37875.86, 3613.91 | 35.363965, 35.927291 | 14.17 | ROAD | 89.10 | 56.31 | 987.59 |
| open country (grid r20c20, region centre) | 44934.89, 5685.08 | 35.428102, 35.947661 | 37.13 | LAND | 935.64 | 39.66 | 345.79 |
| DCS road vertex (well-formed feature, first point) | 37027.47, 2762.75 | 35.356088, 35.918226 | 1.85 | WATER | 0.00 | 170.88 | 2139.26 |
| coastal water (grid r0c0) | 34934.89, -4314.92 | 35.335238, 35.841176 | 0.00 | WATER | 3411.09 | 7213.89 | 8192.27 |
| inland water anomaly (grid r20c24) | 46934.89, 3685.08 | 35.445551, 35.924974 | 20.54 | LAND | 427.55 | 15.13 | 244.48 |
| runway grid vertex (r12c20) | 40934.89, 5685.08 | 35.392086, 35.949020 | 27.02 | RUNWAY | 204.64 | 212.62 | 918.53 |
| outside coverage, far east | 200000.00, 5685.08 | 36.824106, 35.893076 | null | null | 23096.50 | null | null |
| outside coverage, far southwest | -300000.00, -300000.00 | 32.204280, 32.821335 | null | null | null | null | null |

**PASS.** Every field degrades honestly:
- `elevation`/`surface_type`/`nearest_settlement`/`nearest_water` are `null` outside the 1,681-point
  probe grid's coverage and the OSM fetch envelope respectively — explicit absence, not a
  plausible-looking wrong answer.
- The far-east point's `nearest_road_dcs_m = 23096.5` is **not** a bug: `ingest_roadnet` keeps a
  route's full, untruncated geometry whenever any single point of it intersects the region bbox
  (Stage 2's "never silently truncated" rule), so a genuinely long real route (`id=3717`,
  `route:6243@717667470`, spanning x=-13305 to x=194333) can legitimately answer from 23 km away.
  Confirmed by inspecting the feature directly — not corrupted (see Finding 1's contrast case).
- The "DCS road vertex" point was deliberately **not** taken from the first DCS road feature
  fetched by row order, which turned out to be Finding 1's corrupted feature — see below.
- The originally-planned "outside coverage, origin (0, 0)" point was replaced with a far-southwest
  point after (0, 0) turned out to be polluted by the same corrupted feature (Finding 1) — using it
  would have silently validated a bug as a pass.

## 4-6. Airfield spot-checks

Derived point: `[41740.535156, 5697.756836]` (the ILS-pair runway-axis midpoint, per Stage 1's
`ingest_beacons.py`). Independent source: `tests/control_points.py`'s OSLK ARP,
`(43237.96875, 5841.16455078)` — the same live-`coord.LOtoLL`-plus-published-ARP pairing used for
the control-point test, deliberately never used to derive the beacon-based airfield point itself.

| check | computed | expected (plan) | published reference | result |
|---|---|---|---|---|
| Derived airfield point vs in-game ARP gap | **1504.28 m** | ~1504 m | — (different reference points: beacon-antenna-derived vs. in-game ARP; report, don't reconcile, per the plan) | **PASS** |
| ILS axis length | **2635.04 m** | ~2635 m | OSLK 17/35 published length 2797 m | **PASS** — 162 m shorter than published, consistent with "antenna-to-antenna, not threshold-to-threshold" |
| PRMG axis length | 2277.98 m | — (not separately pinned) | — | reported, not scored |
| ILS-vs-PRMG bearing agreement | **0.0085°** | ~1° | — | **PASS, tighter than expected** |

The gap and ILS-axis-length figures land essentially exactly on the plan's own worked numbers
(within 0.3 m and 0.04 m respectively) — strong confirmation that `ingest_beacons.py`'s
runway-pairing and airfield-derivation logic (built in Stage 1, unchanged since) is correct against
real data, not just the plan's hand-derived expectation. The bearing agreement (0.0085°, vs. an
expected ~1°) is better than predicted, not a discrepancy worth investigating — ILS and PRMG are
both physically anchored to the same runway centerline, so near-perfect 180° opposition between
their independently-derived headings is the geometrically correct outcome, and the plan's "~1°"
figure reads as a conservative estimate rather than a measured target.

## 7. Cross-subsystem check (`getSurfaceType` ROAD/RUNWAY vs `.routes` centerline)

Every one of the 1,681 probe-grid cells where `getSurfaceType` (Stage 3) returned `ROAD` (4) or
`RUNWAY` (5) — 33 cells total (29 ROAD + 4 RUNWAY, matching Stage 3's own per-rung census exactly)
— compared against distance to the nearest DCS `.routes` centerline (Stage 2), using
`geometry.distance_point_polyline` and the **clean** (corruption-excluded, see Finding 1) DCS road
polyline set.

| stat | value (m) |
|---|---|
| count | 33 |
| min | 0.17 |
| median | 129.05 |
| mean | 290.83 |
| p90 | 942.43 |
| max | 1372.42 |

**PASS** — the distribution is exactly what's expected for two independently-decoded layers that
should be describing the same real road network at different resolutions: most cells sit within
~1-300 m of an actual road centerline (median 129 m, well under the grid's own 500 m spacing), with
a long tail out to ~1.4 km for cells near road curves/intersections where a straight-line grid
point can be further from the nearest polyline vertex. This is a genuine, non-trivial confirmation
that the `.routes` parser (Stage 2) decoded real road geometry, not resync noise — a random/garbage
polyline set would not produce sub-500m median agreement with an independently-probed
`getSurfaceType` grid.

## 8. DCS-vs-OSM road displacement distribution

Sampled 200 DCS road vertices (fixed seed `20260904`), restricted to points falling inside the
region bbox (see Finding 2 for why), against the nearest OSM road feature.

| stat | value (m) |
|---|---|
| count | 200 |
| min | 0.11 |
| median | 5.30 |
| mean | 15.66 |
| p90 | 46.99 |
| max | 171.48 |
| **expected (M1's ~1.0-1.3 km transform residual)** | **1000-1300** |

**Computed result does not match the plan's expectation** — the actual displacement is roughly two
orders of magnitude *smaller* than predicted, not comparable to it. See Finding 2 for the
investigation and most likely explanation. This is reported honestly as a surprising, checked
result rather than forced to match the plan's prior guess.

---

## Finding 1 (defect, real) — one corrupted DCS road feature in the live store

While picking a real "DCS road vertex" point for the spot-check table, the first DCS road feature
returned by row order (`id=3711`, `source_ref="route:3311@464953201"`) decoded to two garbage
leading points (`(-5.607157514132566e-195, 1.36211130863e-312)`,
`(46368.0, 1.371949926365e-312)` — subnormal/denormalized float64 values, never a genuine DCS
coordinate in this theatre) followed by 61 points of exact `(0.0, 0.0)` padding.

**Root cause (consistent with a known, already-documented Stage 2 risk, now confirmed to
manifest):** Stage 2's implementation notes flagged that some fraction of `.routes` full-file walk
matches could be false-positive scan-forward resyncs — garbage byte sequences that happen to pass
the pre-filter and full N-point envelope validation (`sync_loss_events=302` out of the whole-file
walk, ~2%) — and left this as an open, unresolved risk rather than something proven safe. This is
the first confirmed real instance landing inside the Latakia region specifically: the corrupted
route's second garbage point, `(46368.0, ~0.0)`, has an x inside the Latakia bbox (`[34934.89,
54934.89]`) and a near-zero z that also happens to fall inside the bbox's z range
(`[-4314.92, 15685.08]`) purely by coincidence — one denormalized-but-technically-in-range point was
enough for `ingest_roadnet`'s "any point inside bbox keeps the whole route" rule to include the
entire garbage route.

**Scope:** 1 of 131 DCS road features (0.76%) in the real Latakia store.

**Downstream consequence, checked directly:** `describe_position(conn, "Syria", 0.0, 0.0)`
resolves its `nearest_road` (DCS) answer to this exact corrupted feature at a misleading
**0.0 m** — not a crash, not a null, but a specific, wrong-looking-plausible distance sourced from
garbage geometry. This is exactly the failure mode Stage 4's "outside-coverage degrades to explicit
nulls, not plausible-wrong answers" gate exists to catch, and it does catch it here: the spot-check
table's original "outside coverage, origin (0, 0)" point was replaced with a genuinely far point
once this was discovered, rather than silently keeping a passing-looking result that was actually
validating a bug.

**Disposition — open issue, not fixed this session.** Stage 4 is validation-only per the checklist
("mostly test-writing and a research note, not new pipeline modules"); fixing the root cause
(tightening `roadnet.container.find_next_point_block`'s validation, or adding a plausibility filter
to `ingest_roadnet` that rejects a route whose points contain subnormal/degenerate values) is a
Stage 2 concern and is flagged here for whoever next touches `roadnet`/`ingest_roadnet`. The
throwaway analysis script (`tools/analyze_m5_stage4_validation.py`) excludes this one feature from
its cross-subsystem and OSM-displacement aggregate statistics (checks 7-8 above) via a
`_is_subnormal_point` filter, documented in the script itself, so the aggregate numbers this note
reports are not polluted by it — but the corrupted row remains in the real `.sqlite` and in
`describe_position`'s live answers for anyone who queries near `(0, 0)`.

## Finding 2 (surprising, investigated, explained) — OSM displacement is far tighter than expected

The checklist's own text predicts DCS-vs-OSM road displacement "~M1's 1.0-1.3km residual" — M1's
figure for how far DCS's terrain-art placement of features (specifically, airport
buildings/ARPs) diverges from independently-published real-world coordinates. The actual computed
road-vs-road displacement (median 5.3 m, p90 47.0 m) is roughly **two orders of magnitude tighter**
than that prediction, not merely within a wider-than-expected band.

**Investigation performed before writing this down** (per the standing instruction not to smooth
over a surprising result):

1. **Checked for a sampling bug first.** An initial unfiltered run (before this note's final
   version) sampled from *all* DCS road vertices regardless of whether they fell inside the region
   bbox, and got a very different, much wider distribution (mean 4.7 km, p90 13.6 km, max 55.4 km)
   — closer to, though still not matching, the plan's expectation. Root cause: `ingest_roadnet`
   keeps a route's full untruncated geometry whenever any one point intersects the bbox
   (`tags["clipped"]`, confirmed 88 of 131 DCS road features carry this flag, and 51.8% of all DCS
   road vertices — 60,239 of 116,334 — lie outside the bbox as a direct consequence), while
   `ingest_osm` only ingests OSM ways whose *every* vertex is inside the same bbox. Sampling from
   points far outside the bbox therefore compared DCS geometry against a region where no OSM data
   was ever fetched — a coverage-mismatch artifact, not a real displacement signal. Fixed by
   restricting the sample to the 56,092 in-bbox DCS road vertices, which is the correct
   like-for-like comparison and is what this note's Finding 8 numbers reflect.
2. **Confirmed the small numbers aren't a geometry-math bug.** `distance_point_polyline` is the
   same function exercised extensively by Stage 1's R\*Tree-vs-brute-force agreement test (item 2
   above) — no reason to distrust it here. The distribution itself is smooth (min 0.11 m, median
   5.30 m, p90 46.99 m, max 171.48 m across 200 samples), not bimodal or suspiciously clustered at
   exactly 0, which would suggest a degenerate-input artifact rather than a real measurement.
3. **Considered whether this is actually implausible.** It is not, on reflection: M1's ~1.0-1.3 km
   figure specifically measures a **single point-object's** (an airport ARP/building) placement
   error, which plausibly reflects how a DCS terrain artist hand-placed one structure relative to
   its real-world position. A road **centerline**, by contrast, is far more likely to have been
   digitized by DCS's map artists directly from the same kind of satellite/aerial reference
   imagery that OSM's own contributors trace roads from — so two independently-sourced tracings of
   the same physical road are plausibly much more tightly correlated than one hand-placed point
   object's absolute position error.

**Disposition — reported honestly, not forced to match the plan's prior guess.** The plan's "~M1's
1.0-1.3km residual" figure was a reasonable prior expectation before this data existed, not a
requirement; the real computed result (tight road-to-road agreement, tens of metres not over a
kilometre) is a genuinely useful, more specific finding about this theatre's DCS-vs-OSM road layer
quality than the plan anticipated, and is recorded here as such rather than silently adjusted to
look like a pass against the original number.

---

## Files

- `world-model/tools/analyze_m5_stage4_validation.py` — the analysis script behind every number in
  this note (read-only against the real store, no pipeline code, not part of `src/`).
- `world-model/tests/test_describe_position.py` — added
  `test_describe_position_control_point_latakia_arp` (the one CI-pinnable Stage 4 check).

## Checks

- `ruff format --check world-model/src world-model/tests`: pass
- `ruff check world-model/src world-model/tests`: pass, 0 findings
- `ruff check world-model/tools/analyze_m5_stage4_validation.py` (individually, per convention):
  clean except the same pre-existing repo-wide `EXE001` non-executable-shebang finding every other
  `tools/*.py` script carries
- `mypy --strict world-model/src world-model/tests`: pass (55 source files)
- `mypy --strict world-model/tools/analyze_m5_stage4_validation.py` (individually): pass
- `pytest world-model/tests -q`: pass (139 passed, up from 138)
