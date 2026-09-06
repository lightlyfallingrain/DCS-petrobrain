### Goal

Re-introduce OpenStreetMap as an augmentation layer over the DCS-native world model, sourced
from manually-downloaded offline geofabrik.de per-country extracts instead of M3's live
Overpass API queries — filling the `nearest_settlement` / `nearest_water` /
`inside_settlement` fields that M7's full-theatre build leaves `null` theatre-wide.

> **Status: not yet scheduled.** Split out of the original combined M8 plan on 2026-09-06 at
> the user's direction; M8 is now incremental-store work only
> (`plans/m8-incremental-store/plan.md`). This plan is carried over as written and has **not**
> been re-validated since the split — in particular its central open dependency question is
> still unresolved, and the reconnaissance behind it carries an explicit unverified caveat
> (below). Re-run an Architect pass before starting work; do not implement from this file
> as-is.

Reconnaissance: `world-model/research/2026-09-06-m8-geofabrik-osm-recon.md`. **Read its
caveat first** — `download.geofabrik.de` was unreachable during that pass (5/5 fetch
failures), so its format/size claims are search-snippet-derived rather than read off the
site. Stage 0 below exists to close that gap, and nothing downstream of it should be treated
as settled.

### Why OSM is back in scope

OSM was dropped from M7 because of its *live-query dependency* (Overpass API: rate limits,
availability, non-reproducibility), not because of the data. Geofabrik removes that
dependency — pre-packaged files the user downloads once, offline thereafter. The role stays
exactly as `WORLD_MODEL_BUILDER.md`'s "Data Fusion and Provenance" defines it: **DCS answers
"where is it in the simulation", OSM answers "what is it"**, never collapsed into one
undocumented fact.

### What already survives the source change (most of it)

`src/osm/features.py`'s `OsmNode` / `OsmWay` / `OsmFeatureSet` are source-format-agnostic:
id, tags, and lat/lon. `build/ingest_osm.py` consumes `OsmFeatureSet` and nothing else, and
`query/describe.py` already has `nearest_road_osm` / `nearest_settlement` /
`inside_settlement` / `nearest_water` wired and returning `None` purely because the ingest
never ran. So the whole downstream path — dataclasses, classification rules, clipping,
provenance stamping, storage, query — is reusable **unchanged**. What must be replaced is
exactly one function: `load_features(cache_path)`, the Overpass-JSON parser.

The one genuine structural difference is upstream of it: Overpass's `out geom;` inlined each
way's geometry, whereas a `.pbf` way carries only **node ID references**, so the new path
needs a node-ID → (lat, lon) resolution pass the Overpass path never needed. This single
fact drives the design below.

### Affected Modules / Files

- `world-model/src/osm/pbf.py` *(new)* — `.osm.pbf` → `OsmFeatureSet`. The only new parsing
  code; deliberately terminates at the existing dataclasses.
- `world-model/src/osm/features.py` — unchanged dataclasses; `load_features` gains a
  docstring noting it is the Overpass-era path.
- `world-model/src/osm/overpass.py` — no longer on the pipeline path. Keep it for M3
  diagnostic-tool continuity, marked superseded, rather than deleting working code that
  `tools/inspect_osm_overlay.py` still uses.
- `world-model/src/build/ingest_osm.py` — mostly unchanged; the `source` record it is given
  changes (Geofabrik extract list + clip bbox + download date, not an Overpass URL), and
  `_classify_way`'s rules get revisited against real extract tags rather than Overpass
  query-filtered ones (see Risks).
- `world-model/src/build/pipeline.py` — the OSM stage reads a `.pbf` path instead of a JSON
  cache path; becomes a selectable layer under M8's `layers=` mechanism.
- `world-model/docs/M9_OSM_RUN_INSTRUCTIONS.md` *(new)* — which extracts to download and the
  exact `osmium` merge/clip commands, mirroring `M7_RUN_INSTRUCTIONS.md`'s
  execution-boundary precedent. Downloading and clipping is a **user-run step**, not
  something the pipeline fetches.
- `world-model/tests/test_osm_pbf.py` *(new)* — parser tests against a tiny committed
  fixture `.pbf`; `test_osm_features.py` / `test_ingest_osm.py` extended.

### Design decisions

**1. bbox-clipping with `osmium-tool` is mandatory, not an optimization.**
The node-resolution requirement makes this load-bearing. Resolving way geometry needs every
referenced node's coordinates; over a raw ~612 MB Turkey extract that is tens of millions of
nodes — a memory blowup, or a complex two-pass design. If the user clips and merges first,
the Python side only ever sees a single theatre-sized `.pbf` and an in-memory node dict is
entirely reasonable. So the pipeline's contract is: **input is one pre-clipped, pre-merged
`.osm.pbf` covering the theatre envelope.** `osmium-tool` is GPLv3 but is a separately
invoked CLI, never linked or redistributed — a documented user prerequisite like DCS itself,
not a project dependency.

**2. OSM never overwrites DCS-sourced rows.** M7's store already has `road` and
`named_place` from DCS-native sources. OSM features keep
`provenance={"geometry": "osm", "name": "osm"}` and the ~1,300 m M1 uncertainty, and land
*beside* the DCS rows — `describe_position` already reports `nearest_road` and
`nearest_road_osm` as separate fields precisely so the disagreement stays visible.

**3. Provenance must record the extract set and the clip.** The `source` row needs the list
of Geofabrik files merged, their download dates, the clip bbox, and the exact `osmium`
command — otherwise an OSM feature's origin is unreproducible. ODbL attribution is already
carried; extract identity is the new part.

**4. Per-layer append would help, but is not available.** This layer would benefit a lot from
being independently re-runnable and deletable without a ~450 s full rebuild, while tuning
classification rules against a real extract. That capability is `todo/todo.md`'s "Incremental
per-layer pipeline builds" backlog item — it was considered for M8 and **explicitly dropped**
from it, so it is *not* a dependency this plan can assume. Either schedule that backlog item
alongside this milestone, or accept full rebuilds during rule tuning. Worth deciding in the
fresh Architect pass this plan requires.

### Implementation Plan

0. **Close the format question before writing any parser.** Open
   `https://download.geofabrik.de/europe/turkey.html` and
   `https://download.geofabrik.de/asia/syria.html` and record what formats, sizes and
   sub-region links actually exist. Two claims decide the dependency question and neither is
   currently verified: (a) whether `.osm.bz2` is truly gone — if it still exists, the whole
   PBF problem evaporates into stdlib `bz2` + `xml.etree.iterparse` with zero new
   dependencies; (b) whether Turkey has a sub-national split, which decides whether the
   download is ~1.0 GB or far less. Append findings to the existing research note.
   **This stage gates the dependency decision — do not skip it.**
1. **Parsing spike, timeboxed.** Prove the chosen path against one small real extract: parse
   it, count nodes/ways, round-trip known coordinates. Success criterion is a control-point
   check per this project's testing rule — a known place (e.g. Latakia) parsed out of the
   extract must land within M1's ~1.3 km residual of its DCS position.
2. **`osm/pbf.py` → `OsmFeatureSet`,** with a committed tiny fixture and unit tests.
   Unsupported constructs (relations, and now also ways whose nodes fall outside the clip)
   must be **counted skips, not silent drops** — `OsmFeatureSet.relations_skipped` already
   sets this precedent and the new failure modes get the same treatment.
3. **Wire into the pipeline as a selectable layer,** re-validate `_classify_way` against real
   extract tags, and measure what actually lands in the store.
4. **Scale check and, if needed, filtering design.** Measure feature counts before deciding
   anything about decimation — see Risks.
5. **Write `M9_OSM_RUN_INSTRUCTIONS.md`** and hand the real build to the Windows machine.

### Risks & Unknowns

- **The pivotal fact is unverified.** `download.geofabrik.de` was unreachable during
  reconnaissance, so "`.osm.bz2` is deprecated, `.pbf` is the only full-data format" is a
  search-snippet claim, not an observed one. It is also the single claim that decides whether
  this milestone needs a new dependency at all. Hence Stage 0. Per project convention, an
  unverified community claim must not be encoded as fact.
- **Turkey dominates the download** (~612 MB of a ~1.0 GB total, with no sub-national split
  found). Note it is filed under `europe/`, not `asia/` — an easy wrong guess when writing
  the instructions.
- **Node resolution is the real complexity, and it exceeds the `.routes`/`.rn4` precedent.**
  Those parsers are forward scans over self-contained records; a `.pbf` way needs a lookup
  table built from a different part of the file. The 200-400 LOC estimate covers block/varint
  decoding and does not fully cover this.
- **Scale could be a 10x+ store growth on roads alone.** M7's store is already 461 MB with
  `describe_position` p99 at 803 ms — itself a flagged M7 follow-up. A large OSM layer could
  push the query tail from "flagged" to "blocking". Measure before designing decimation, but
  treat this as a live possibility.
- **A raw extract is not a filtered Overpass response.** M3's `_classify_way` rules ran on
  results the Overpass query had already narrowed. A raw extract contains every tagged way in
  the bbox, so `ways_skipped_unclassified` will be enormous and the rules need re-validation
  rather than reuse-on-faith.
- **OSM is not period-accurate for DCS's Syria**, and post-2011 conflict changed the real
  region substantially. Reference data for "what is it", never game truth.
- **`osmium-tool` is a new user-side prerequisite** (`brew install osmium-tool`) on whichever
  machine does the clipping.

### Decisions Requiring User Input

1. **The dependency decision** — `AGENTS.md`'s "a new dependency seems necessary → stop and
   ask" trigger. Three options, in the order Stage 0 should test them:
   - **(a) `.osm.bz2` still exists** → stdlib `bz2` + `xml.etree.iterparse`, zero new
     dependencies, simplest possible path. Verify first; if true, take it.
   - **(b) Hand-rolled stdlib `.pbf` parser** (`zlib` + `struct` + varints, no protobuf
     compiler). Zero new dependencies, consistent with the `.hgt`/`.routes`/`.rn4`
     precedent, fully inspectable. Costs ~200-400 LOC plus node-resolution work, and it is
     new binary-format code to maintain and get right.
   - **(c) `pyosmium`** (BSD-2-Clause, prebuilt wheels, no compiler needed, actively
     maintained, handles node resolution). Fastest route to working code; adds a dependency
     to a project that has so far avoided every geospatial library. (`pyrosm` is already
     ruled out — it pulls GeoPandas.)

     Architect's lean, conditional on (a) failing: **(b)**, because the mandatory
     `osmium-tool` clip means the parser only ever handles a small, well-formed input, which
     removes most of the argument for a robust general-purpose library. A real tradeoff
     between maintenance burden and dependency policy — the user's call.
2. **Scope check on fusion depth.** This plan stops at "OSM features stored beside DCS
   features, both labelled." The concept doc's richer `external_matches` / `match_score` /
   `preferred_name` model is entity resolution and belongs in its own milestone. Confirm that
   is the intended stopping point.
