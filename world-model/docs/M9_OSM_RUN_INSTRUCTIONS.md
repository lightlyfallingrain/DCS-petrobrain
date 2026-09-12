# M9 OSM (Geofabrik) full-theatre build — run instructions

Per `plans/m9-osm-geofabrik/plan.md`'s Design Decision 1 and this project's standing rule
against running large external processing/full-theatre builds in an agent session: nobody but
the user runs `osmium-tool`'s clip+merge over the multi-hundred-MB country extracts, or the
resulting full `syria-full` rebuild. The implementer/reviewer/DoD verify `osm/pbf.py` against a
small in-test fixture only (`tests/test_osm_pbf.py`) and against the already-present, already
theatre-sized `syria-260911.osm.pbf` (82 MB, one country, no clip needed — see Stage 4 below);
the real 7-country clip+merge and its resulting feature counts are the user's own result. This
mirrors `M7_RUN_INSTRUCTIONS.md`'s execution-boundary precedent.

## 0. Prerequisite: raw extracts already staged

All 7 Geofabrik country `.osm.pbf` extracts (`data/raw/osm/*-260911.osm.pbf`) are already
downloaded and gitignored — confirmed present during M9 implementation:

```
cyprus-260911.osm.pbf                37 MB
jordan-260911.osm.pbf                31 MB
lebanon-260911.osm.pbf               52 MB
syria-260911.osm.pbf                 82 MB
iraq-260911.osm.pbf                  90 MB
israel-and-palestine-260911.osm.pbf  119 MB
turkey-260911.osm.pbf                646 MB
```

If any are missing, re-download from `download.geofabrik.de/asia/<country>-latest.osm.pbf` (see
`research/2026-09-06-m8-geofabrik-osm-recon.md` for the original source recon).

## 1. Install `osmium-tool`

```sh
brew install osmium-tool
```

This is a GPLv3 CLI invoked via `subprocess`-equivalent shell commands below, never
imported/linked into the Python pipeline — same category as DCS itself, not a `pyproject.toml`
dependency (see the plan's "What changed from the deferred plan").

## 2. Clip each country extract to the theatre bbox

The clip bbox was derived once from `syria-full`'s own padded DCS-space region corners
(`build.region.REGIONS["syria-full"]`, itself already padded +30 km/side against DCS's own
point-cloud extent uncertainty — see that registry entry's comment) via
`coordinates.dcs_to_wgs84`, plus a further +0.3 degree pad (~30-33 km at these latitudes) so the
extract's own edge is never flush with the region it needs to cover. Reproducible with
`tools/derive_m9_osm_clip_bbox.py`; the fixed numbers from that run are:

- `syria-full` envelope (south, west, north, east): `30.8157, 31.7701, 38.4353, 40.5808`
- Padded clip bbox (south, west, north, east): **`30.5157, 31.4701, 38.7353, 40.8808`**

Run `osmium extract` per country, in `data/raw/osm/`:

```sh
cd world-model/data/raw/osm

for country in cyprus jordan lebanon syria iraq israel-and-palestine turkey; do
  osmium extract -b 31.4701,30.5157,40.8808,38.7353 \
      --strategy=smart \
      -o "${country}-clipped.osm.pbf" \
      "${country}-260911.osm.pbf"
done
```

`--strategy=smart` matters: it completes ways whose nodes straddle the bbox edge, avoiding the
"way references a node the location index never saw" failure mode a naive bbox cut would hit at
the Turkey/Syria border specifically (the theatre's most bbox-edge-heavy country by
construction, since Turkey's own extract is nationwide and only its southern strip is
theatre-relevant). If `osm.pbf.load_features`'s `ways_skipped_unresolved_nodes` stat comes back
non-zero after the full build (Stage 5 below), that is the first thing to re-check.

## 3. Merge the clipped extracts into one file

```sh
osmium merge cyprus-clipped.osm.pbf jordan-clipped.osm.pbf lebanon-clipped.osm.pbf \
    syria-clipped.osm.pbf iraq-clipped.osm.pbf israel-and-palestine-clipped.osm.pbf \
    turkey-clipped.osm.pbf \
    -o syria-theatre.osm.pbf
```

This produces `data/raw/osm/syria-theatre.osm.pbf` — the single pre-clipped, pre-merged file
`osm.pbf.load_features` expects (Design Decision 2: the Python side never juggles multiple
country files itself).

## 4. Validate the real Syria-only extract first (already done in this session)

Before running the full merge, M9 implementation validated `osm/pbf.py` directly against the
already-present `syria-260911.osm.pbf` (82 MB, one country, no clip needed since it is already
theatre-relevant and small enough to parse whole):

- **Parse**: 260,101 tagged nodes, 1,865,289 ways, 2,818 relations (all counted-skipped),
  **0** `ways_skipped_unresolved_nodes`. Parse time ~60s on the dev machine.
- **Ingest** (clipped to the existing `latakia-20km` region, ~20x20 km): 3,136 `road`,
  338 `settlement`, 117 `water`, 106 `named_place` features; `ways_skipped_unclassified`
  1,439,259 (dominated by `building` tags — 1,377,796 of them — which are out of scope by
  design, not a missed rule; see the plan's "Design decisions" 3-4).
- **`_classify_way` real-tag audit**: the next-largest unclassified tag groups were `source`,
  `barrier`, `power`, `amenity`, `natural` (non-`water` values like `coastline`), `man_made`,
  `leisure` — none of which map to `road`/`water`/`settlement`/`named_place` under this
  project's scope, confirming the four rules are not missing an obviously-common case.
  `boundary=administrative` ways (1,228 total) were sampled and are exclusively national/
  governorate-level borders (`admin_level` 2/4/6, e.g. the Syria-Turkey and Syria-Lebanon
  national boundaries) — correctly *not* settlement extents, so `_classify_way` correctly
  leaves them unclassified rather than needing a new rule.
- **Control-point check**: `describe_position` against the real Latakia airport-area point
  (`latakia-20km`'s region centre) returned a real `nearest_settlement`
  (`distance_m≈70.2`, `provenance="osm"`) and `nearest_road_osm`
  (`distance_m≈39.7`) sourced from this extract — the query surface (already unchanged per
  Design Decision 3) works against real polygon data, not just the fixture.
- Checked whether Latakia *city centre* itself (not the airport) falls inside a settlement
  polygon: it does not (`inside_settlement=None`), and a direct scan of the full extract found
  1,635 settlement-classified ways within ~15 km of the city centre (cemeteries, parks,
  `village_green` parcels) but no way covering the city's own administrative extent — real-world
  large-city boundaries are relation-mapped in this extract, exactly Design Decision 5's
  documented, expected gap, not a bug.

No changes were needed to `build/ingest_osm.py`'s `_classify_way` as a result of this
validation.

## 5. Full merged-theatre build

Once Steps 2-3 above have produced `data/raw/osm/syria-theatre.osm.pbf`, run:

```sh
.venv/bin/python tools/build_world_model.py syria-full \
    --towns data/raw/dcs/syria/map/towns.lua \
    --beacons data/raw/dcs/syria/map/beacons.lua \
    --routes data/raw/dcs/syria/roads/Syria.routes \
    --srtm-dir data/raw/dem/syria-full/ \
    --osm-pbf data/raw/osm/syria-theatre.osm.pbf
```

(Include whichever of `--routes`/`--srtm-dir` your existing `syria-full.sqlite` build already
uses — `--osm-pbf` is additive to M7's existing invocation, per `build.pipeline.build_region`'s
`osm_pbf_path` parameter taking precedence over `osm_cache_path` when both are given.)

Expect a substantially longer OSM stage than the single-country Stage 4 run above (~60s parse +
~6s ingest for Syria alone at 82 MB) — the merged file is dominated by Turkey's clipped
southern-strip share of its 646 MB nationwide extract.

**What "still working" looks like, and what a real stall looks like.** This stage logs progress
periodically (`osm.pbf: N elements seen...`) — steady lines every ~10-20s at this scale are
normal, not a problem, even though the interval between lines can vary (a slow batch is not
necessarily a stall). Memory is now bounded by batching (`stream_features`'s `batch_size`,
`osm-streaming-ingest` fix) rather than growing with the whole file, so this stage should no
longer exhaust memory the way an earlier build attempt did (a real `syria-full` run stalled
after ~8.6M ways / high memory usage before this fix, confirmed and killed after 22 minutes of
total silence). If you genuinely see **no new progress line for several minutes** on a build
built from this fix, that is worth reporting as a new issue, not assumed to be "just slow" —
but a `syria-full`-scale OSM stage taking many minutes total, with steady incremental progress
throughout, is expected, not a bug.

Measure and record:

- Feature counts by `kind` (the CLI prints these), especially `settlement`/`water`/`named_place`
  deltas versus M7's OSM-absent baseline (M7 dropped OSM from scope entirely).
- `syria-full.sqlite` file size delta vs. M7's 461 MB baseline.
- `osm.pbf.load_features`'s `ways_skipped_unresolved_nodes` count — should be 0 or very small;
  a large number would mean `--strategy=smart` did not fully protect the Turkey/Syria border
  (see Step 2's note).
- `describe_position` p99 latency delta vs. M7's already-flagged 803 ms tail (`tests/
  test_measure_m7_stage4_perf.py`'s measurement approach) — a real risk this milestone carries
  forward, not a formality.

## 6. Record the result

Write a dated `world-model/research/` note (extract coverage, skip counts, store growth,
query-latency delta) mirroring M5/M7's convention, and update `world-model/ROADMAP.md`'s M9
entry to done — see the plan's "Implementation Plan" step 6 and the root `CLAUDE.md`'s
"Milestone Completion" checkpoint question (does this change what the next milestone,
Mission Interpreter's MI-2, should assume — see the plan's "Second-order effect").
