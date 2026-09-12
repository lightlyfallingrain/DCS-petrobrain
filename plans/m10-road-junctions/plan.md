### Goal

Derive road-junction landmarks purely from the geometry of the already-ingested `road`
feature layer (endpoint/interior-vertex coordinate clustering), store them as a new
`junction` `Point` feature using the existing `feature`/`feature_bbox` schema unchanged,
and expose them through `describe_position` — zero new dependency, zero new data source,
per `plans/world-model-tactical-landmarks/plan.md`'s M10 scoping and the confirmed
derivability findings in `world-model/research/2026-09-12-m9-tactical-landmarks-recon.md`.

No unresolved DCS-internals claim is in this plan's critical path — the recon already
verified the core fact (junction vertices are bit-identical or near-identical across
distinct `.routes` polylines) empirically against the real `latakia-20km` store. The
investigator is not invoked for this plan.

### Read-first findings that shape this design

- **Road features already carry everything junction detection needs.** `roadnet/
  ingest_roadnet.py` writes each route as a `StoredFeature(kind="road", geom_type=
  "LineString", geometry=[(x,z),...])`; `store.reader.all_features(conn, ["road"])`
  (or `features_in_bbox`) reads them back with no format work needed. No new parser.
- **No generic "layers=" selector mechanism exists in `build/pipeline.py`.** The parent
  plan's Affected-Modules note ("selectable under M8's `layers=` mechanism") does not
  match current code — `build_region` instead takes one explicit optional path parameter
  per layer (`routes_path`, `probe_output_path`, `srtm_tile_paths`, ...), each independently
  None/absent-guarded with a `*_skipped` flag on `BuildReport`. M10 follows this existing
  convention instead: junction ingest is unconditional whenever `road` features exist in
  the store from this same build (no new path parameter needed — it reads back what
  `ingest_roadnet` just wrote, the same pattern M6's terrain stage uses to read back the
  probe grid it just wrote).
- **The store schema needs no change.** `kind` is a free-text column; `junction` is simply
  a new value, exactly how `ridge`/`valley` were added in M6 with no schema migration.
- **Recon's two match types are structurally different and both matter.** 1,315
  endpoint-endpoint bit-exact pairs, and 3,700 endpoint-interior-vertex pairs (T-junctions
  — one route's endpoint lands mid-span on a *different*, unsplit route's polyline). A
  design that only clusters endpoints-against-endpoints would miss every T-junction in
  that second population, which the parent plan's own Stage 1 wording ("group road-segment
  endpoints by proximity") does not clearly account for — resolved below.

### Design decision: what "degree" counts (resolves the parent plan's open question)

The parent plan's recon left this open ("Architect should decide whether degree-2
endpoint coincidences count as junctions"). Two distinct match shapes exist and they are
not comparable by raw feature-id count:

- **Endpoint-endpoint**: N distinct road features' endpoints coincide. Each contributes
  one "arm". A plain 2-road endpoint coincidence is very likely one physical road split
  into two `.routes` polylines continuing through the same point, not a landmark — this
  matches the parent plan's own reasoning for the ≥3 threshold.
- **Endpoint-interior (T-junction)**: one road's endpoint lands on a second road's
  interior vertex. The second road does *not* terminate there — it continues through the
  point in both directions, i.e. structurally contributes **two** arms (in + out), while
  the terminating road contributes **one**. This is the "T-junction's third route counts
  as 3" framing already present in the parent plan, made precise: a T-junction is degree 3
  (2 arms from the through-road + 1 from the branch) even though only **two distinct
  `road` feature ids** are involved.

**Junction degree = sum of arms at a clustered coordinate**, where every endpoint
contributes 1 arm and every interior-vertex attachment contributes 2 arms. A junction
feature is emitted only where degree ≥ 3 (first-guess threshold, per the parent plan,
tuned in Stage 2). This makes a plain two-road endpoint meeting (degree 2) correctly
excluded as route continuation, and a genuine T-junction (degree 3, only 2 road ids)
correctly included — resolving the ambiguity the raw "≥3 distinct road ids" phrasing left
in the parent plan without silently picking a definition that would either drop every
T-junction or falsely admit every route-split.

Interior-vertex-to-interior-vertex matches (two roads crossing mid-span with neither
having an endpoint there — a true grade crossing) are **out of scope for this pass**: the
recon never tested for this case, and it is a materially different geometric signature
(no arm terminates at the point at all). Flagged in Risks, not attempted.

### Affected Modules / Files

- `world-model/src/roadnet/junctions.py` *(new)* — pure geometry, no store I/O:
  - `collect_endpoints(roads: list[StoredFeature]) -> list[Vertex]` and
    `collect_interior_vertices(roads) -> list[Vertex]`, each `Vertex = (feature_id, x, z)`.
  - Grid-bucketed clustering (reusing the recon's proven approach — bucket cells sized a
    small multiple of the tolerance, 3×3 neighbourhood scan, no naive O(n²) all-pairs at
    `syria-full` scale where a single region can carry >14,000 `road` features and
    correspondingly ~30k+ endpoints) via union-find over: (a) endpoint↔endpoint pairs
    within `tolerance_m`, and (b) endpoint↔interior-vertex pairs (different feature id)
    within `tolerance_m`. Interior↔interior pairs are never unioned (see Design decision).
  - For each resulting cluster: compute arm count per the rule above, the representative
    point (centroid of member coordinates), the max intra-cluster pairwise distance (drives
    confidence — see below), and the sorted distinct `road` feature ids contributing.
  - `to_stored_features(clusters, source_id, min_degree, position_uncertainty_m) ->
    list[StoredFeature]`: emits `kind="junction"`, `geom_type="Point"`,
    `geometry=[centroid]`, `tags={"degree": arms, "connecting_road_ids": [...]}`,
    `provenance={"geometry": "dcs_derived"}` (mirrors M6's ridge/valley — the source
    vertices are DCS-native but the junction *fact* is this module's derived analysis, not
    something DCS reports directly), `confidence={"geometry": "high"}` when the cluster's
    max intra-cluster distance is bit-exact (< 1e-6 m, matching the recon's own exact-match
    finding) else `"medium"`, `position_uncertainty_m` = that same max intra-cluster
    distance (0.0 for the bit-exact case — an honest, measured value, not a placeholder).
  - Mirrors `terrain/features.py`'s two-function shape (`extract_components` /
    `to_stored_features`) deliberately, for the same testability reason: pure-geometry
    intermediate objects (`JunctionCluster`) that tests can assert on directly, separate
    from the store-facing wrapping step.
- `world-model/src/build/ingest_junctions.py` *(new)* — thin wrapper mirroring
  `ingest_terrain.py`'s shape: takes `roads: list[StoredFeature]`, `source_id`,
  `tolerance_m`, `min_degree`; calls `roadnet.junctions`; returns
  `(list[StoredFeature], JunctionIngestStats)` (counts: endpoints scanned, interior
  vertices scanned, clusters found, clusters kept as junctions, degree histogram).
- `world-model/src/build/pipeline.py` — new stage after the roadnet stage (renumber
  `_TOTAL_STAGES` 7→8): read back `store.reader.all_features(conn, ["road"])` (only
  when `routes_path` was given and the roadnet stage actually ran — `report.
  roadnet_skipped` guards this, same pattern the terrain stage uses against
  `probe_skipped`), run `ingest_junctions`, `insert_features`, update
  `report.feature_counts["junction"]`. New `BuildReport` fields: `junction_stats:
  JunctionIngestStats | None`, `junction_skipped: bool`. `tolerance_m`/`min_degree`
  exposed as `build_region` keyword args with module-level defaults (`DEFAULT_JUNCTION_
  TOLERANCE_M`, `DEFAULT_JUNCTION_MIN_DEGREE` in `roadnet/junctions.py`), following the
  exact "first guess constant, override available, tuned value documented in the
  docstring" pattern `terrain/curvature.py`/`terrain/features.py` already established.
- `world-model/src/query/describe.py` — add `JunctionInfo` dataclass (`distance_m`,
  `degree: int`, `connecting_road_ids: list[int]`, `provenance`, `confidence`,
  `position_uncertainty_m`), a `_junction_info` helper mirroring `_terrain_line_info`,
  and `nearest_junction: JunctionInfo | None` on `PositionDescription`, answered via the
  existing `nearest_feature(conn, ["junction"], x, z)` — no new query primitive needed.
  Also: doc-only update folding in the parent plan's ask-1 resolution — a sentence on
  `nearby_ridges`/`nearby_valleys`' docstrings and the module docstring noting both being
  `None` constitutes absence of notable relief ("flat"), not missing data. No schema/field
  change for this part.
- `world-model/tests/test_junctions.py` *(new)* — synthetic fixtures: a clean 4-way
  endpoint cluster (degree 4, kept), a 3-way endpoint cluster (degree 3, kept), a plain
  2-road endpoint coincidence (degree 2, dropped — route continuation), a T-junction
  (endpoint-on-interior, degree 3, kept), a near-miss pair just outside tolerance (not
  clustered), and a real-data regression test against `latakia-20km` recording the actual
  cluster/junction counts this implementation produces there as the checked-in baseline
  (see Stage 2 — the recon's 1,315/3,700 are raw *pair* counts, not cluster/junction
  counts, so they cannot be asserted directly; Stage 2 establishes the real baseline).
- `world-model/tests/test_ingest_junctions.py` *(new)* — thin wrapper-level test mirroring
  `test_ingest_terrain.py`'s shape (stats correctness, source_id plumbing, empty-input
  behaviour).
- `world-model/ROADMAP.md` — new **M10 — Road-network junctions** entry once Stage 3/DoD
  numbers are known, following M6/M7/M8's established entry format (what was built, real
  store counts, tuned parameter values + why, confidence caveats, link to research/plan).

**Not in this plan's scope** (per the parent plan's own scoping, and per this project's
side-quest rule for non-milestone bookkeeping): the M9 reopening status-line updates to
`world-model/ROADMAP.md`'s M9 row and `plans/m9-osm-geofabrik/plan.md`. Those are a
separate cross-cutting bookkeeping edit unrelated to this feature branch's own commits —
if still wanted, they should land via a disposable worktree on `main`, not here.

### Implementation Plan

1. **Stage 1 — Junction clustering (minimal working version).** `roadnet/junctions.py`:
   endpoint/interior-vertex extraction, grid-bucketed union-find clustering at a
   first-guess `tolerance_m=0.5` (conservative, below the recon's observed clean gap at
   1.4 m), arm-counting per the Design decision above, `min_degree=3`. Unit-test the pure
   clustering functions against the synthetic fixtures listed above before touching any
   store/build code.
2. **Stage 2 — Validate & tune against real data.** Run against `latakia-20km`'s real
   `road` layer (3,266 features, matching the recon's own dataset). Record actual
   endpoint/interior counts, cluster counts, and kept-junction counts (this becomes the
   regression baseline `test_junctions.py` checks against — do not assume the recon's raw
   pair counts translate directly). Spot-check a sample of emitted junctions against the
   F10 map / raster overlay (M2 tooling) to confirm they land on real intersections, not
   false positives from near-parallel roads. Tune `tolerance_m`/`min_degree` against this
   real output if needed; record the tuned values and why in `junctions.py`'s docstring,
   same discipline M6 used for its curvature threshold.
3. **Stage 3 — Wire into the pipeline and `describe_position`.** Land `ingest_junctions.py`,
   the `build/pipeline.py` stage, `JunctionInfo`/`nearest_junction`. Run a full
   `latakia-20km` rebuild and a full `syria-full` rebuild; report real junction counts,
   store-size delta, and any `describe_position` latency change (M7 already flagged an
   803 ms p99 tail — measure, don't assume junctions are free just because they're a
   `Point` layer over existing data).
4. **Stage 4 — Documentation-only ridge/valley "flat" note.** Small same-branch commit
   per the parent plan's fold-in instruction; no code change.
5. **Stage 5 — ROADMAP.md M10 entry**, written with Stage 2/3's real numbers, following
   the existing per-milestone entry format.

### Risks & Unknowns

- **The arm-counting rule (endpoint=1, interior-attachment=2) is this plan's own
  resolution of an explicitly-open parent-plan question, not independently re-verified
  against DCS ground truth.** It is grounded in the recon's own T-junction framing but has
  not been visually spot-checked against a real T-junction in the F10 map the way Stage 2
  now commits to doing — if that spot-check disagrees, the rule (not just the threshold
  constant) may need revision, which is a larger change than a tolerance/threshold tweak.
- **Tolerance/min-degree are first-guess values pending Stage 2's empirical tuning**,
  same status as the parent plan already flagged.
- **Interior-interior crossings (no endpoint at the shared point) are excluded this pass.**
  If DCS's road-authoring tool ever produces a genuine unsplit X-crossing, this design
  will not surface it as a junction. Not tested for; flagged as backlog, not attempted.
- **Reading back `road` features via `all_features`/`features_in_bbox` after
  `insert_features` within the same `build_region` call needs the R*Tree-populated read
  path to see rows inserted earlier in the same open connection/transaction** — should be
  fine (same pattern M6's terrain stage already relies on for its own read-back of the
  probe grid it just inserted), but Stage 3 must confirm this holds for `feature`/
  `feature_bbox` specifically, not just `grid`/`grid_sample`.
- **Store growth and `describe_position` latency at `syria-full` scale are unmeasured
  until Stage 3.** Junctions are cheap in principle (a `Point` per cluster, off data
  already resident), but M7's own p99 tail is already flagged as a concern other
  milestones must not make worse without measuring.

### Second-order effect

A working, tuned junction-clustering primitive over `road` features is reusable
infrastructure beyond this milestone: the parent plan's own backlog for "bridges" (road ×
water intersection) explicitly names "same clustering technique as junctions" as its
approach once M9 lands water geometry — so this milestone's `roadnet/junctions.py`
becomes the template that unblocks that later feature, not just a one-off landmark type.

### Decisions Requiring User Input

None beyond what the parent plan already carries forward as open (tolerance/min-degree
tuning, resolved empirically in Stage 2, not requiring a user decision). The arm-counting
design resolution above is a judgment call within the parent plan's own stated ambiguity,
not a new architectural fork — proceeding on it per this project's escalation rule (local,
reversible via Stage 2's tuning pass, does not require a new dependency or conflict with
an invariant).
