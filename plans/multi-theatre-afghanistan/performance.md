### Performance Review

Reviewed `feature/multi-theatre-afghanistan` at tip `58fa966` (confirmed via `git rev-parse HEAD`
after `git checkout --detach 58fa966`). Diff base `14ca593..58fa966`. Context:
`plans/multi-theatre-afghanistan/plan.md`/`review.md`, build results in
`world-model/research/2026-10-05-afghanistan-theatre-build.md` (82 min build, road-junction stage
29.2 min, terrain-semantics stage 44.0 min).

No per-tick cost is added anywhere in this diff. The one real build-time-scaling question (3)
surfaced a pre-existing, undocumented-until-now inefficiency in the terrain-semantics stage that
is directly relevant to Kola — not introduced by this branch, flagged for a later milestone.

### Findings

#### 1. Body-layer theatre/store resolution and mismatch guard — startup only, not per-tick

- **Location:** `body-layer/src/logger.py` `main()`, lines ~1859-1908 (theatre/`world_model_db`
  resolution + `open_world_model`/`load_only_region`/`parser.error` mismatch guard);
  `belief/mission_phase.py`'s `load_mission_understanding`/`_parse_theatre`.
- **Risk:** none at runtime. Traced the call graph directly: `load_mission_understanding` is
  called exactly once in `main()` (same call site BL-7 already had, just moved earlier so Stage 5
  can read `mission_data.theatre` before resolving `world_model_db`). The resolved `theatre`/
  `world_model_db` values are plain local variables closed over by the poll-thread `args=(...)`
  tuples — nothing re-reads `args.theatre`/`args.mission_understanding` inside
  `_run_naked_eye_poll_loop`/`_run_console_repl`'s per-tick code. The mismatch guard opens a
  second short-lived `sqlite3.Connection` via `open_world_model(world_model_db)` purely to call
  `load_only_region` (a `SELECT ... FROM region LIMIT 1`, no scan) and immediately closes it
  before the real, long-lived connection used by the perception sources is opened a few lines
  later. Both the extra artifact parse and the extra connection-open/close/`LIMIT 1` cost are
  one-time, pre-poll-loop costs, independent of theatre or store size (878 MB Afghanistan vs
  589 MB Syria makes no difference to a `LIMIT 1` row read).
- **Action:** NONE — confirmed safe by reading the code, not just by the plan's own claim.

#### 2. `describe_position`/`line_of_sight_clear` cost does not scale with Afghanistan's larger feature counts

- **Location:** `world-model/src/query/describe.py:describe_position`,
  `world-model/src/query/line_of_sight.py:line_of_sight_clear` — unchanged by this diff, but the
  task asked for a direct measurement against the new, much larger Afghanistan store (878 MB,
  ridge=634,867/valley=551,657) vs `syria-full` (589 MB).
- **Measured** (fresh `world-model/.venv`, read-only `file:...?mode=ro` connections, 20-call
  average per point, warm page cache, this session's hardware):

  | call | Afghanistan (Kabul/Bagram/Jalalabad) | Syria (Damascus/Latakia/Aleppo) |
  |---|---|---|
  | `describe_position` | 552–906 ms/call | 565–1082 ms/call |
  | `line_of_sight_clear` (20 samples) | 2.8–14.5 ms/call | 5.9–53.8 ms/call |

  Afghanistan is **not** slower than Syria despite ~1.15x the ridge count and ~0.75x the valley
  count, and despite a larger store file — both land in the same range, confirming the R\*Tree
  bbox-pruned query path (`store/schema.py`'s `feature_bbox` virtual table) does what it's
  supposed to: per-call cost tracks *local* feature density near the query point, not total
  theatre-wide feature count. This answers the task's scale question directly: nothing about
  Afghanistan's larger store creates a new, Afghanistan-specific query-cost regression.
- **Pre-existing absolute cost, not new:** `describe_position`'s 550–1080 ms/call is already a
  documented, known tail — `world-model/RUN.md`'s own Troubleshooting section states
  "`describe_position` p99 is around 800 ms on the full theatre" for `syria-full`, predating this
  branch. Traced its only runtime consumers: `body-layer/src/belief/enrichment.py` (mission-
  interpreter-adjacent fact flattening, not body-layer's own per-tick perception loop) and
  `body-layer/src/perception/geometry.py:elevation_at`, which **has zero callers anywhere in
  `body-layer/src`** (grepped directly — only `tests/test_geometry.py` calls it). The
  per-tick LOS gate `NakedEyePerceptionSource` actually uses goes through
  `query.line_of_sight.line_of_sight_clear` → `store.reader.sample_grid` directly, bypassing
  `describe_position` entirely (confirmed by the module's own docstring and the measured 3–54 ms
  LOS timings above, consistent with the plan's prior finding that LOS reads a dozen-plus grid
  samples, not a full `describe_position` join). `describe_position`'s cost is real but it sits on
  mission-interpreter's offline enrichment path (one call per route waypoint/group/trigger zone,
  per `world_enrich/enrich.py`'s own docstring) and diagnostic tools, not on a hot path that gates
  anything per-sortie-tick.
- **Action:** MONITOR. Not this plan's defect (unchanged code, and the cost is theatre-size-
  independent, not scale-driven), but worth a documentation pointer next time `RUN.md`'s
  Troubleshooting section or `world_enrich/enrich.py` is touched, so a future reader isn't left
  wondering whether Afghanistan made this worse (measured here: it did not).

#### 3. Terrain-semantics stage processes every staged DEM tile, not the region's own bbox — real build-time cost, directly relevant to Kola

- **Location:** `world-model/src/build/pipeline.py` `build_region`, stage 8
  (`existing_srtm_tile_paths` gate, ~line 719) → `world-model/src/build/ingest_terrain.py:
  ingest_terrain`. **Not touched by this diff** — this is pre-existing pipeline behavior,
  already self-documented as a known, deliberately-deferred decision
  (`ingest_terrain`'s own docstring: "`region` identifies the cache (name + bbox), it does **not**
  clip the extracted geometry... see `plans/landform-geomorphons/implementation.md` for why this
  is left unaddressed"). Surfaced here because the task's build-time question (3) asked
  specifically about Caucasus/Kola scaling, and this is where that risk actually lives.
- **Risk, with real numbers from this build:** Afghanistan's `--srtm-dir` had **288** staged
  `.hgt` tiles (the research note's own staging range, 28–40°N/54–78°E — a round 12°×24° bounding
  rectangle), but the SRTM elevation grid (which *does* clip to the region's padded bbox via
  `probe_grid_for_region`) only needed **158** of them
  (`srtm stats: tiles_used=158`). The terrain-semantics stage has no such clipping: its own log
  (`afghanistan-full-build.log`) shows `"[8/8] terrain semantics (ridge/valley), 288 tile(s):
  starting"` — it processes all 288, including the ~130 tiles (45% more than needed) that fall
  entirely outside the region's own extent, and inserts whatever ridge/valley features they
  produce into the store regardless (`ingest_terrain`'s docstring again: "a region-scoped build
  therefore stores whatever ridge/valley lines its given tile(s) produce across their *whole*
  tile extent, not just the region's own smaller bbox"). This stage is already the single most
  expensive one measured (2640.2s / 44.0 min of the 82 min total, 53.6%) — the ~1.82x tile-count
  inflation plausibly explains a meaningful fraction of that, though isolating the exact split
  would need a tile-filtered rerun this review did not perform.

  **Why this specifically matters for Kola, not just as a general inefficiency:** `RegionDefinition`
  grew rectangular half-extents (M7 Kola stress-test note, `research/2026-09-05-m7-kola-square-
  vs-rectangle-stress-test.md`) precisely to stop a square-shaped region from "wasting 40-70%
  area/compute" on a theatre whose real footprint is a ~1,400×1,000 km (or, by the tighter beacon-
  derived lower bound, ~478×800 km) elongated strip. That fix reaches the SRTM grid stage (which
  reads `probe_grid_for_region`, i.e. the rectangular bbox) but **does not reach the terrain-
  semantics stage at all**, because that stage ignores the region bbox entirely and processes
  every `.hgt` file physically present in `--srtm-dir`. If Kola's raw DEM tiles are staged as a
  bounding rectangle over the theatre's full extent (the natural way to stage 1°×1° `.hgt` tiles
  for an elongated strip), the terrain-semantics stage will burn time proportional to that
  bounding rectangle's tile count, not the strip's actual area — exactly the waste the rectangular-
  half-extent work was built to avoid, just in the one stage that work never touched.
- **Action:** LATER — escalate to Architect/backlog, not a fix for this branch. This plan did not
  introduce the behavior, did not regress it, and Afghanistan's absolute cost (82 min total, one
  offline per-theatre build) is still well inside "minutes, not hours." But before a Caucasus or
  Kola build is attempted, whoever stages that theatre's raw DEM tiles should either (a) stage
  only tiles overlapping the region's own padded bbox (not a convenience bounding rectangle), or
  (b) `ingest_terrain`'s caller should filter `srtm_tile_paths` to tiles whose footprint intersects
  `region`'s bbox before stage 8 runs. Caucasus itself is not a concern either way — its real
  footprint (~700×400 km per ED's own marketing figure, smaller than Syria's ~827×771 km) is
  smaller than Afghanistan's, so even an unfiltered tile set should cost less, not more. Recording
  this as the concrete, numbers-backed version of the gap `ingest_terrain`'s docstring already
  flagged abstractly, so the next theatre's build doesn't rediscover it from a slow build instead
  of from this note.

#### 4. Road-junction stage cost tracks road-feature count/segmentation, not bbox area — no Kola-specific risk found

- **Location:** `world-model/src/build/ingest_junctions.py` (unchanged by this diff).
- **Risk:** Checked whether this stage's cost (29.2 min for Afghanistan, 1,590 roads, 196
  junctions) might scale badly with Kola's large bbox. Comparing against the retained
  `syria-full-build.log` (14,833 roads, 8,732 junctions): Syria's junction stage took **2885.1s
  (48.1 min)** — *longer* than Afghanistan's, despite Afghanistan's region having a larger bbox
  (~1,084×1,318 km padded vs Syria's ~827×771 km). This is the same chunk-bucketed, grid-pruned
  design the R\*Tree-based query path uses, and it tracks input road density (Syria's `.routes` is
  segmented into ~9.3x more, much shorter polylines than Afghanistan's, per the Reviewer's own
  investigation of the same build) rather than raw bbox area.
- **Action:** NONE. No credible Kola-specific risk found here — unlike the terrain-semantics
  stage above, this one does not appear to carry a bbox-driven blind spot. Noting the comparison
  for the record since the task asked about build time at Caucasus/Kola scale specifically.

### Verdict

**APPROVED — MONITOR**

Nothing in this diff adds per-tick/per-poll cost; the theatre/store resolution and mismatch guard
are startup-only and theatre-size-independent, confirmed by tracing the call graph rather than by
re-stating the plan's claim. `describe_position`/`line_of_sight_clear` were measured directly
against the real 878 MB Afghanistan store and show no scale-driven regression relative to
`syria-full` — the larger ridge/valley counts don't cost more per call, as expected from the
R\*Tree-pruned query path. The one real finding (#3) is a pre-existing, already-self-documented
pipeline design decision, not something this branch introduced or could reasonably be asked to
fix here — it is flagged with concrete numbers (288 vs 158 tiles, 44.0 min stage) specifically
because the task asked about Caucasus/Kola build-time risk, and this is the mechanism that would
bite Kola specifically if its DEM tiles are staged the natural way. No required fix for this
branch; recommend an Architect/backlog item before a Kola build is attempted.
