### Goal

Assess and scope whether world-model's *content* — ridge/valley/flat terrain, settlement
extent, road intersections, and other air-recognizable landmarks — is rich enough to be a
useful tactical-narrative source for Mission Interpreter's MI-2 world-enrichment stage, and
produce a concrete, prioritized implementation plan for closing the real gaps without
blocking MI-2.

### Investigation findings this plan rests on

Two DCS-internals claims were unverified before this plan and have now been resolved
(`world-model/research/2026-09-12-m9-tactical-landmarks-recon.md`):

1. **Settlement extent: no DCS-native source exists.** `towns.lua` has exactly three keys
   (`latitude`, `longitude`, `display_name`) theatre-wide — verified by a full-file key scan.
   A full grep of the Syria file listing for zone/city/settlement/boundary/polygon/region/
   admin-shaped filenames turned up nothing beyond `towns.lua` itself. **OSM is the only path
   to settlement boundary polygons** — this was suspected, now confirmed rather than assumed.
2. **Road junctions: derivable purely geometrically, at bit-exact tolerance, no new
   DCS decode needed.** Querying the existing `latakia-20km.sqlite` store's 3,266 road
   features directly (not re-walking the 2.25 GB raw `.routes` file) found 1,315
   endpoint-endpoint pairs at exactly 0.0 m and 3,700 endpoint-on-interior-vertex matches
   (T-junctions), with a clean gap before the next-nearest band (85 near-misses, all
   1.4–5 m). DCS's road-authoring tool snaps junction vertices to bit-identical coordinates.
   Junction detection needs zero new dependency and does not need the unresolved `.rn4`
   trailer field once speculated as "is-intersection".

### Per-ask assessment

**1. Ridge/valley/"flat".** M6's curvature classifier already computes a third per-cell
class, `CurvatureClass.NEITHER` (`terrain/curvature.py`) — every cell that isn't ridge/valley
is already this today. It is simply never grouped into a stored feature
(`terrain/features.py`'s `extract_components` only builds connected components for
`RIDGE`/`VALLEY`). Judgment call: **do not build a new "flat" feature class.** A ridge/valley
is meaningfully a *line* (principal-axis extraction through a component); "flat" terrain is
not a line, it's the majority of the map, and forcing it through the same line-extraction
machinery would produce meaningless geometry. The tactical fact a consumer actually wants —
"is there a ridge or valley worth mentioning near this point" — is already fully answered by
`nearby_ridges`/`nearby_valleys` both being `None`. That is "flat" under this project's
existing absence-as-absence rule; it needs a documentation update (a sentence in
`describe.py`'s module docstring and `PositionDescription`'s docstring, read by MI-2's
implementer), not new code. M6's existing `confidence: "low"` caveat is judged **acceptable
for a first Mission-Interpreter consumer** — narrative tactical framing ("ridge rises to the
west") tolerates the documented single-dominant-feature/checkerboard-noise limitation in a way
survey-grade terrain classification would not; revisit only if MI-4 synthesis output is
observed to state false relief claims with unwarranted confidence.

**2. Settlement boundaries.** Confirmed OSM-only (see above). The M9 plan
(`plans/m9-osm-geofabrik/plan.md`) already designed this path in full and most of it is
**already-working code, not new scope**: `store.reader.containing_polygons` +
`point_in_polygon` already exist and are already wired into `describe_position`'s
`inside_settlement`; `build/ingest_osm.py` already classifies closed OSM ways with
`landuse`/`place` tags into `Polygon` settlement features (M3-era code, never fed at theatre
scale). What's genuinely missing is exactly what M9 already scoped: a `.osm.pbf` parser
(`osm/pbf.py`, new) to replace M3's live-Overpass `load_features`, because Geofabrik's
`.osm.bz2` is deprecated. **M9 is reopened** — per explicit user direction, "should M9 exist"
is resolved to yes, since this scoping confirms settlement-boundary polygons need it and there
is now a real downstream consumer (Mission Interpreter). The one still-open decision M9's own
plan already flagged — `.osm.pbf` parsing: stdlib hand-roll vs `pyosmium` — remains open and is
carried into this plan's Decisions section, not resolved here.

**3. Road intersections.** Confirmed cheaply derivable, zero new dependency (see Investigation
findings). This is a straightforward addition: cluster road-feature endpoints/interior
vertices at (near-)zero tolerance across the existing `road` layer, emit one `junction`
`Point` feature per cluster with ≥3 distinct routes converging (a 2-route meeting is just a
route continuing, not a landmark; ≥3 is the geometric signature of a real junction — a
T-junction's third route counts as 3, per the T-junction match evidence found). This is the
**cheapest and highest-value-per-cost item of the four asks** — no new dependency, no new data
source, reuses the existing `feature`/`feature_bbox` schema unchanged, and directly answers
the user's own framing ("a more significant landmark than a road").

**4. Other air-recognizable landmarks.** Scoped narrowly per the user's own instruction not to
enumerate everything. **First slice: none beyond what junctions add this pass** — airfields/
runways are already exposed (M5/M7). Bridges were considered (road × water intersection,
same clustering technique as junctions) but rejected as this pass's slice: DCS has no
theatre-wide vector water layer at all today (`nearest_water` is `None` theatre-wide, same OSM
gap as settlements — `ingest_osm.py` is the only place `kind="water"` is ever produced), so a
"bridge" feature would be gated on M9's OSM water geometry landing first, not purely
DCS-native the way junctions are. The DCS-native alternative (detecting a road/`surface_type`
probe-grid crossing into `WATER`/`SHALLOW_WATER`) only has data where M8's incremental probe
store has actually been probed — not a theatre-wide guarantee, and a real design question of
its own. **Bridges, POI-tagged structures (towers, distinctive buildings — need OSM POI tags,
gated on M9), and everything else in the concept doc's "Semantic Terrain Features" list
(saddle, pass, coast, river corridor, forest/treeline, etc.) are explicit backlog**, not
attempted this pass, per the concept doc's own "do not attempt all of these initially."

### Affected Modules / Files

- `world-model/src/roadnet/junctions.py` *(new)* — endpoint/vertex proximity clustering over
  an already-ingested region's `road` features; emits `junction` `Point` `StoredFeature` rows.
  Pure geometry over existing store data, no raw-file re-parse.
- `world-model/src/build/ingest_junctions.py` *(new)* — thin build-stage wrapper: reads `road`
  features already written to the store for a region (via `store.reader.features_in_bbox` or
  equivalent whole-region read), runs the clustering, writes `junction` features. Runs *after*
  `ingest_roadnet` in `build/pipeline.py`'s stage order (needs `road` rows already committed).
- `world-model/src/build/pipeline.py` — add the junction stage; selectable under M8's
  `layers=` mechanism like other optional layers.
- `world-model/src/query/describe.py` — add `nearest_junction: JunctionInfo | None` to
  `PositionDescription`, following the exact shape of `_terrain_line_info`/`_road_info`
  (provenance `"dcs_derived"`, confidence carrying the cluster's tightness — see Stage 2).
  Also: doc-only update to the module docstring and `nearby_ridges`/`nearby_valleys`'
  docstrings noting "both `None` constitutes absence of notable relief ('flat'), not missing
  data" — the ask-1 resolution, no schema change.
- `world-model/tests/test_junctions.py` *(new)* — unit tests over synthetic road geometries
  (T-junction, 4-way, near-miss-should-not-cluster) plus a real-data regression test against
  the already-known `latakia-20km` junction counts from the investigator's recon.
- `world-model/ROADMAP.md` — new **M10 — Road-network junctions** entry (see Implementation
  Plan); **M9's entry updated from "deferred" to "reopened"** with a one-line pointer to this
  plan's ask-2 resolution as the reason.
- `plans/m9-osm-geofabrik/plan.md` — status line updated from "deferred, not scheduled" to
  "reopened — see `plans/world-model-tactical-landmarks/plan.md`"; the plan body's own content
  (Stage 0-5, decisions 1-4, risks) still stands as written and needs a fresh Architect pass
  before implementation starts, per that plan's own instruction — **this plan does not
  re-litigate M9's internals**, it only resolves the "should it exist" gate.

### Implementation Plan

1. **M10 Stage 1 — Junction clustering (minimal working version).** `roadnet/junctions.py`:
   group road endpoints/interior vertices by exact-coordinate match first (the dominant case
   per recon: 1,315 pairs), extend to a small tolerance band (recon found a clean gap at
   1.4–5 m — pick a conservative threshold below that gap, e.g. 0.5 m, and document the choice
   against the recon data rather than guessing) to catch floating-point-representation edges.
   A cluster becomes a `junction` feature only when ≥3 distinct `road` feature ids contribute a
   vertex to it (2 is route continuation, not a landmark).
2. **M10 Stage 2 — Validate correctness.** Run against `latakia-20km`'s real road layer;
   spot-check a handful of emitted junctions against the F10 map / raster overlay tooling
   already built (M2) to confirm they land on real intersections, not spurious near-parallel-
   road false positives. Tune the tolerance threshold against real output, same "first guess,
   tuned empirically" pattern M6 used for its curvature threshold — record the tuned value and
   why in the module docstring, not just the code.
3. **M10 Stage 3 — Wire into `describe_position` and the full pipeline.** Add
   `nearest_junction` to `PositionDescription`; run across `syria-full` (M7 scale) and report
   real counts + a store-size delta (junctions are `Point` features off an existing dataset,
   expected cheap relative to M9's road-heavy growth risk, but measure rather than assume).
4. **M10 Stage 4 — Documentation-only ask-1 resolution.** Update `describe.py` and
   `PositionDescription` docstrings per Affected Modules above. No code change, no new
   milestone number needed — fold into M10's own DoD or land as a same-branch small commit.
5. **M9 reopening — scope confirmation only, not full re-implementation in this plan.** Update
   `world-model/ROADMAP.md` and `plans/m9-osm-geofabrik/plan.md`'s status line per Affected
   Modules above. Actual implementation (Stage 0's format-verification, the `.pbf` parser, the
   pipeline wiring) is **out of this plan's scope** — it requires the fresh Architect pass
   M9's own plan already calls for, informed by this plan's confirmation that settlement
   polygons are the concrete, now-real consumer need driving it (not a hypothetical one).

### Scheduling relative to MI-2

**Nothing here needs to block MI-2.** `PositionDescription` gains fields additively
(`nearest_junction` now; `nearest_settlement`/`inside_settlement` going from always-`None` to
sometimes-populated once M9 lands is not a shape change either) — MI-2's `world_model_client.py`
and `world_enrich/` can be built and tested today against the current schema and will pick up
richer answers later with no client-side change required. Recommended order:

- **M10 (road junctions) — do first, in parallel with or just ahead of MI-2's own build.**
  Cheapest, zero new dependency, no open decision, direct answer to the user's own priority
  framing ("more significant landmark than a road"). Small enough to land before MI-2 needs
  its first real waypoint-enrichment test data, giving MI-2 a genuinely richer signal from day
  one rather than retrofitting later.
- **Ask-1 documentation fix — trivial, land alongside M10.**
- **M9 reopening (settlement boundaries) — parallel track, not a blocker, but the larger lift.**
  Needs its own fresh Architect pass (per that plan's existing instruction) before
  implementation, and carries a real new-dependency decision (below) plus M9's own
  already-documented risks (node-resolution complexity, potential store/query-latency growth
  on top of M7's already-flagged p99 tail). Can proceed on its own timeline; MI-2 does not need
  to wait for it, but Mission Understanding quality for settlement-heavy waypoints stays
  point-only until it lands.
- **Backlog (bridges, POI landmarks, remaining concept-doc terrain classes) — not scheduled,**
  most of it gated on M9's OSM data landing first.

### Risks & Unknowns

- **Junction false positives from near-parallel roads or duplicated route segments.** The
  0.5 m proposed threshold is a first guess informed by the recon's observed gap, not yet
  empirically tuned against the full `syria-full` scale — Stage 2 must validate before trusting
  theatre-wide counts, same caution M6's curvature threshold needed.
- **`.osm.pbf` parser choice (stdlib hand-roll vs `pyosmium`) is a real new-dependency decision**
  M9's own plan already flagged and this plan does not resolve — see Decisions below.
- **M9's already-documented risks still apply unchanged**: Geofabrik page contents were
  search-snippet-sourced, not directly fetched (M9 plan's Stage 0 still needs to run); Turkey's
  ~612 MB extract dominates the download with no confirmed sub-national split; node-ID
  resolution for way geometry is more complex than any parser this project has built so far;
  potential store growth could push `describe_position`'s already-flagged p99 tail (803 ms at
  M7 scale) further into "blocking" territory — must be measured, not assumed, per M9's own
  Stage 4.
- **Junction `confidence`/`position_uncertainty_m` need a real value, not a placeholder.**
  Because junctions are derived purely from already-DCS-authoritative road vertices (not a
  coarse probe grid like M6's ridges), a reasonable case exists for `confidence: "high"` /
  `position_uncertainty_m: 0.0` at exact-match clusters — but this should be validated against
  Stage 2's real spot-checks, not asserted here.

### Second-order effect

Reopening M9 for settlement-boundary polygons also unblocks a wider set of previously-deferred
richer semantics that ride the same OSM ingest path (road class/ref, land-use, POI tags,
`nearest_road_osm` finally getting real data instead of theatre-wide `None`) — this milestone
decision has effects well beyond MI-2's immediate settlement-boundary need, and should be
treated as reopening OSM augmentation generally, not a narrow one-field patch.

### Decisions Requiring User Input

- **`.osm.pbf` parsing — resolved 2026-09-13: `pyosmium`.** User approved world-model's first
  native-extension dependency over a stdlib hand-roll, given the node-ID-resolution complexity
  a hand-rolled parser would need to solve itself. BSD-2-Clause, prebuilt wheels on
  macOS/Linux/Windows x64 — no compiler needed on this project's supported platforms.
- **Junction minimum-degree threshold (≥3 routes) and coordinate-match tolerance (proposed
  0.5 m)** — first-guess values pending Stage 2's empirical tuning; flagging here in case the
  user has a different tactical bar in mind for what counts as a "significant" junction (e.g.
  should a 3-way meeting of three very minor tracks count the same as a major highway
  interchange — `subtype`/road classification is still `None` theatre-wide per M5 Decision 7,
  so today's junction feature cannot yet distinguish "significant" from "minor" by road class).
