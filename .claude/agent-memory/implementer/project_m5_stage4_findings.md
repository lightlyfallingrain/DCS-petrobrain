---
name: m5-stage4-findings
description: Two real findings from M5 Stage 4 validation against the live Latakia store — a confirmed roadnet resync corruption instance and a surprising-but-explained OSM displacement result.
metadata:
  type: project
---

Stage 4 validation (`world-model/research/2026-09-04-m5-stage4-validation.md`,
`world-model/tools/analyze_m5_stage4_validation.py`) against the real `latakia-20km.sqlite`
surfaced two things worth knowing before touching `roadnet`/`ingest_roadnet` or displacement
numbers again:

1. **A real, confirmed instance of [[project_m5_roadnet_stage2]]'s `sync_loss_events` risk made
   it into the live store.** Feature `id=3711` (`route:3311@464953201`) is a corrupted `.routes`
   parse: subnormal-float garbage points followed by `(0.0, 0.0)` padding, included because one
   garbage point's near-zero z coincidentally fell inside the Latakia bbox. Not fixed (Stage 4 is
   validation-only) — flagged for whoever next touches `roadnet.container.find_next_point_block`
   or `build.ingest_roadnet` (needs a plausibility/subnormal-value filter). Downstream effect is
   real, not theoretical: `describe_position(conn, "Syria", 0.0, 0.0)` returns a misleading
   `nearest_road` distance of exactly `0.0 m` sourced from this feature.

2. **DCS-vs-OSM road-centerline displacement is ~5-50 m (median/p90), not the ~1.0-1.3 km M1's
   ARP placement-error figure predicted.** Two orders of magnitude tighter. Investigated, not a
   bug: an unfiltered sample first showed a wide, misleading spread because DCS road features
   keep untruncated geometry outside the region bbox while OSM ingest only fetches inside it —
   fixed by restricting the sample to in-bbox DCS road vertices. The remaining tight number is
   plausible: M1's figure is one hand-placed point object's error; road centerlines in both DCS
   and OSM are likely digitized from similar satellite/aerial reference imagery, so they agree far
   more closely than a point-placement error would suggest. Don't assume M1's ~1-1.3km figure
   applies to road-vs-road comparisons in future milestones — it's a point-object figure only.

**Why this matters for future sessions:** when computing any aggregate stat over "all DCS road
features" in this store, filter out `id=3711`-style corruption first (check for subnormal
floats/degenerate padding), or the fix already applied in `analyze_m5_stage4_validation.py`'s
`_is_subnormal_point`/`_clean_dcs_road_polylines` needs to be ported into the fix location.
