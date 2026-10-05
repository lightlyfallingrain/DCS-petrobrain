# World-model performance review

**Date:** 2026-10-05. Whole-subproject pass (not a feature diff), requested after
`aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` named world-model's
offline LOS fallback as the number-one suspect for body-layer's poll loop running at ~0.7 Hz
against a specified 5 Hz. Reviewed at `main` tip `19143fa`.

**What was measured and what was not.** The two halves of this review rest on different evidence,
and conflating them would be misleading:

- **The live-tick half (findings 1–6) is benchmarked.** There is no built `.sqlite` store in the
  repo (`*.sqlite` is gitignored) and none on this machine, so those figures come from a
  **synthetic store built to syria-full's own measured shape** — the real counts from `ROADMAP.md`'s
  2026-09-15/16 build (`landcover=44811, settlement=26182, named_place=23044, road=14833,
  water=5119, coastline=1269, airfield=35, runway=27, ridge=12, valley=12`, 2.01 M vertices) over
  the real `syria-full` footprint (827.3 × 771.2 km), plus a 639,216-cell elevation grid at 92.6 %
  fill. Benchmarks lived in the scratchpad and are **not** committed into `src/`.
- **The offline-build half (findings 7–18) rests on the real build logs**, chiefly
  `research/2026-10-05-afghanistan-theatre-build.md`'s per-stage timings for an ~82-minute
  full-theatre run, plus arithmetic against them and direct code reading. Only findings 15 and 17
  carry benchmark numbers of my own.

**A correction that lands on this review's own setup:** the 639,216-cell grid above is `syria-full`
at **1000 m** spacing, which is what M7 measured. The current default is
`DEFAULT_SRTM_GRID_SPACING_M = 500.0` (`src/build/pipeline.py:158`) — **2,555,208 cells, 4×** — so
my LOS benchmark ran against a grid a quarter the size of what the forced rebuild will produce. It
does not change finding 1's conclusion, because `grid_sample` lookups are O(1) primary-key seeks
(`EXPLAIN QUERY PLAN` confirms it) and the cost is statement count, not table size. It does change
the resident-grid figure: **~20 MB rather than 5.1 MB**, still trivially affordable. See finding 7
for the full baseline correction.

Two honesty notes, because they bound every number here:

- **The synthetic store is less clustered than the real one.** My dense-area `describe_position`
  measures 40.8 ms; M7 measured **136.8 ms mean / 497.7 ms p95** on the real store. So real
  Syria's hot spots are roughly 3–12× denser than my synthetic ones. **Where a figure below and
  M7's own measurement disagree, M7's is the real one** — mine establish the *shape* of the cost
  and the *ratio* a fix would buy, not its absolute value. This is the synthetic-terrain
  calibration trap and it is why no recommendation here rests on an absolute synthetic number
  alone.
- **The knowledge graph could not be queried** (`graphify-out/` is gitignored and absent from the
  worktree), so the "query before writing a research note" step could not run. Existing `WM-B` IDs
  and `research/` notes were read directly instead.

---

## The headline, and it is not in world-model

**The poll loop is not running slowly. It is configured to run at 1 Hz.**

`body-layer/src/logger.py:997`:

```python
_DEFAULT_POLL_INTERVAL_S = 1.0
```

…and it is the default for `--poll-interval-s` (`logger.py:1679-1682`). Meanwhile the code around
it reasons in terms of 5 Hz — `logger.py:1448` says a skipped poll *"costs one cycle at 5 Hz"*, and
`logger.py:993-996` calls 1.0 s *"the default one-second poll interval"* in the same file. The two
statements have coexisted without either being wrong about its own line.

That single constant accounts for most of the sortie's 7× gap:

| | |
|---|---|
| specified cadence (sortie note) | 0.2 s |
| configured default | **1.0 s** |
| observed consumer median | 1.44 s |
| → attributable to the configured interval | **~5×** |
| → attributable to per-poll work on top | **~1.4×** |

So the question "what does world-model's query layer cost on the live tick" has a real answer worth
acting on (it is the ~1.4×, and findings 1–3 below quantify it), but **the ~0.7 Hz symptom is
primarily a body-layer configuration fact, not a world-model cost.** Whoever picks up the poll-loop
instrumentation named as next step 2 in the sortie note should start by deciding whether 1.0 s or
0.2 s is the intended default, because no amount of optimisation here closes a 5× gap that a
constant opens.

**This is a body-layer finding surfaced by a world-model review — it is outside this review's remit
to fix, and it is stated first because it reorders the sortie note's own priority list.**

---

## Findings — live tick path (ranked first)

### 1. `sample_grid` issues 5 SQLite queries per sampled point; one LOS check issues 95

- **Location:** `world-model/src/store/reader.py:477` `sample_grid` →
  `reader.py:467` `_grid_cell_value` (×4) and `reader.py:408` `_load_grid_meta` (×1), called from
  `world-model/src/query/line_of_sight.py:160-168`.
- **Mechanism:** `line_of_sight_clear` loops `range(1, samples)` = **19 interior points**. Each
  calls `sample_grid`, which calls `_load_grid_meta` (1 query) and then `_grid_cell_value` four
  times for the bilinear corners (4 queries). **5 queries per sample point, 95 per LOS check**,
  measured exactly by wrapping `Connection.execute`:

  ```
  one CLEAR candidate -> True: 95 statement executions
  71 clear candidates (one poll):   6,745 statement executions
  ```

  The 19 `_load_grid_meta` calls per check are **pure redundancy** — same `grid_kind`, same
  connection, same row, 19 times, and `EXPLAIN QUERY PLAN` shows it as `SCAN grid` (no index on
  `grid.kind`; the table is tiny so the scan is cheap, but the statement execution is not free).
- **Measured cost** (639,216-cell / 500 m grid, warm, read-only URI connection exactly as
  `body-layer/src/perception/geometry.py:65` opens it; worst case = a *clear* sightline, which runs
  all 19 samples because a blocked one early-returns):

  | candidates/poll | poll cost | per candidate | at 5 Hz |
  |---|---|---|---|
  | 10 | 5.92 ms | 592 µs | 3.0 % of one core |
  | 43 (sortie median) | 25.41 ms | 591 µs | 12.7 % of one core |
  | 71 (sortie max) | **43.40 ms** | 611 µs | **21.7 % of one core** |

  Blocked sightlines early-exit, so a real poll sits between this and ~1/5 of it. At the ~128
  candidates the gaze gate can pass (the sortie saw >128 in 11 of 2,104 polls), extrapolate
  ~78 ms/poll.
- **Blast radius:** per candidate per poll, on the path the sortie found carrying **77 % of
  admissions**. Scales linearly with candidate count; independent of theatre size (grid lookups are
  O(1) PK seeks — `EXPLAIN QUERY PLAN` confirms
  `SEARCH grid_sample USING PRIMARY KEY (grid_id=? AND row=? AND col=?)`, which is correct and
  needs no index work).
- **Verdict on the sortie's hypothesis:** **partially exonerated.** 43 ms/poll at the observed
  maximum is real and worth removing, but it is ~4 % of a 1.0 s interval and cannot by itself
  produce 1.44 s polls. The sortie note's ordering of suspicion should be revised: the configured
  interval first, then this.
- **Mitigation, three options, measured:**

  | fix | poll cost at 71 cand | vs as-written |
  |---|---|---|
  | as written | 43.40 ms | — |
  | hoist `_load_grid_meta` out of the sample loop (95→76 queries) | 32.53 ms | 1.3× |
  | + per-poll cell memo (candidates share one observer) | 6.26 ms | **6.9×** |
  | **load the whole grid into memory once** | **0.08 ms** | **540×** |

  The per-poll memo works because candidates in one poll share an observer position, which nothing
  currently exploits: at 71 candidates a poll issues **5,396 cell lookups against 792 distinct
  cells — 6.8× redundancy** (3.2× at 10 candidates, 5.3× at 43). The redundancy *rises* with
  candidate count, so the memo gets better exactly where it is needed.

  **The in-memory option is the right one and is cheap.** `load_full_grid`
  (`reader.py:429`) already reads the whole grid in one query. The full theatre grid is
  **591,732 populated cells of 639,216** — measured at **5.1 MB** as a flat Python list, loaded in
  **263 ms, once**. Against `ROADMAP.md`'s own note that `grid_sample` is only 49 MB of
  `syria-full.sqlite`'s 608 MB, there is no memory argument against holding it resident.
- **Action: NOW** for the `_load_grid_meta` hoist (a strict improvement, no behaviour change, no
  new state). **NOW** for the in-memory grid *if* the offline fallback is staying — and per
  `line_of_sight.py`'s own docstring and `plans/dcs-driven-los/plan.md` it is: *"a real, permanent
  use, not a test-only path"*. **Escalate the shape to the Architect rather than improvising**: an
  in-memory grid is a new lifetime/ownership decision (who loads it, per-theatre, when a probe
  store is attached) and `ROADMAP.md`'s own 2026-10-01 correction says *"Re-check what still reads
  `sample_grid` before assuming it must stay"* — that re-check should happen before caching is
  built around it. The per-poll memo is the intermediate that needs no architectural decision.

### 2. `describe_position` spends ~73 % of its time proving that 86 features aren't nearby

**This is the largest and cheapest-to-fix finding in the subproject.**

- **Location:** `world-model/src/query/describe.py:713, 714, 743, 744` — `nearest_feature` for
  `ridge`, `valley`, `airfield`, `runway` → `world-model/src/store/reader.py:309`
  `nearest_feature`'s expanding-radius loop (`_EXPANDING_RADII_M = (500, 2000, 8000, 30000)`,
  `reader.py:29`).
- **Mechanism:** `nearest_feature` tries each radius until a feature's *exact* distance falls
  within it, and returns `None` only after exhausting all four. Four of the nine layers
  `describe_position` queries hold almost nothing theatre-wide — **ridge 12, valley 12, airfield
  35, runway 27, i.e. 86 features across 638,000 km²** — so for almost any position all four radii
  are exhausted, and the fourth is a **60 × 60 km bbox**.
- **Measured** (dense population centre, synthetic syria-full density):

  ```
  nearest_feature(['ridge'])     7.31 ms   (12 features theatre-wide)
  nearest_feature(['valley'])    7.33 ms   (12 features theatre-wide)
  nearest_feature(['airfield'])  7.32 ms   (35 features theatre-wide)
  nearest_feature(['runway'])    7.84 ms   (27 features theatre-wide)
  -> 29.8 ms of a 40.8 ms describe_position, on 4 layers holding 86 features
  ```

  The same four calls at a sparse desert position cost 0.23–0.25 ms each — the cost is entirely
  the *unrelated* features the R*Tree returns, not the layer being searched.
- **Where the 7.3 ms goes**, decomposing one 30 km `features_in_bbox(['ridge'])`:

  ```
  stage 1, R*Tree scan returning ALL kinds:            1.09 ms  (4,191 ids)
  stage 2, 4,191-parameter 'id IN (...)' + kind filter: 4.44 ms
  whole features_in_bbox(['ridge']):                    5.78 ms
  ```

  `features_in_bbox` (`reader.py:177`) collects **every** overlapping feature id regardless of
  `kinds`, then applies the kind filter in a second query whose SQL text embeds one `?` per
  candidate id. So searching for 12 ridges drags 4,191 landcover/settlement ids through Python and
  back into SQLite.
- **Blast radius:** `describe_position` is **on the per-poll path** — `CalloutScheduler.tick`
  (`body-layer/src/belief/callouts.py:755`) → `describe_contact` → `belief/tools.py:350`
  `enrichment.cache.get_or_compute` → `belief/enrichment.py:424` `describe_position`. The
  `WorldEnrichmentCache` hit test is structural equality on `Contact.last_position`
  (`enrichment.py:644`), so **a moving contact misses the cache every poll**, and `tick` calls
  `describe_contact` several times per contact per poll (the `BL-B26` triple-gather). At M7's real
  136.8 ms mean this is far and away the dominant world-model cost on the tick — **an order of
  magnitude above finding 1**, which is what makes the sortie note's suspect list worth reordering.
- **Mitigation — load small layers once, answer `nearest` from memory:**

  ```
  nearest_mem(['ridge'])    0.027 ms
  nearest_mem(['valley'])   0.026 ms
  nearest_mem(['airfield']) 0.193 ms
  nearest_mem(['runway'])   0.049 ms
  -> 0.296 ms total (101x cheaper); one-time load 91 ms for 86 features
  ```

  **101×**, for 86 features. Any layer below roughly a couple of thousand features theatre-wide
  (that is ridge, valley, airfield, runway, and plausibly `junction`, `navaid`, `coastline`) is
  cheaper to hold resident and scan linearly than to index-search, because the R*Tree cannot prune
  by kind.

  Two cheaper-still partial alternatives, both measured and both weaker, recorded so they are not
  re-proposed as the main fix:
  - **An index on `feature(kind, id)`**: `describe_position` 40.8 → **27.8 ms** (1.5×), +2 MB on a
    129 MB store, 0.1 s to build. `EXPLAIN` confirms it becomes
    `SEARCH feature USING COVERING INDEX idx_feature_kind (kind=? AND id=?)`. **There is currently
    no index on `feature.kind` at all** (`PRAGMA index_list(feature)` → none;
    `src/store/schema.py:47` declares none). Worth doing on its own merits — it is one DDL line in
    `schema.py` and helps `all_features`, `find_place_by_name` and the build's own validation
    queries too — but it does not touch the real problem, which is the unfiltered R*Tree stage.
  - **Rewriting `features_in_bbox`' two stages as one static SQL text** (`id IN (SELECT id FROM
    feature_bbox WHERE …)`, no Python id list, no per-call bind-parameter count): only **1.1–1.3×**.
    I expected more and it is not there — worth recording so the next reviewer does not chase it.
    It does, however, remove a latent correctness hazard; see finding 4.
- **Action: NOW.** This is a self-contained change inside `store/reader.py` /
  `query/describe.py` with a 101× measured win on the dominant per-poll cost. **Flag to the
  Architect** only for where the resident-layer cache lives and how it is keyed (per-connection?
  per-theatre? invalidated how?) — the same ownership question as finding 1, and the two should be
  decided together rather than growing two independent caches.

### 3. `terrain_divide_qualifier` → `divides_between` is uncached by design, and that is fine

- **Location:** `world-model/src/query/divides.py:85` `divides_between`, one
  `features_in_bbox(conn, ["ridge"], bbox)` at `divides.py:119`; called from
  `body-layer/src/belief/enrichment.py:714`, deliberately outside `WorldEnrichmentCache`
  (rationale at `enrichment.py:690-696`: it is ownship-relative, so a contact-keyed cache cannot
  hold it).
- **Measured:** 0.06 ms at 2 km, 0.16 ms at 6 km, **0.77 ms at 12 km**.
- **Assessment:** bounded and cheap, consistent with what a previous pass recorded for this
  primitive. The `ridge` layer holding 12 features theatre-wide is exactly why — and finding 2's
  resident-layer fix makes this free as a side effect.
- **Action: MONITOR.** No change needed for its own sake. The real cost here is **multiplicity, not
  unit cost**: `CalloutScheduler.tick` reaches `describe_contact` up to three times per group
  member per poll regardless of whether anything changed, which is already filed as `BL-B26` and is
  a body-layer item. Cite it; do not re-file it.

### 4. `features_in_bbox` embeds one bind parameter per candidate id — a latent hard failure

- **Location:** `world-model/src/store/reader.py:195-199` — `placeholders = ",".join("?" for _ in
  candidate_ids)`.
- **Mechanism:** the candidate id list from the unfiltered R*Tree stage becomes one `?` each. A
  30 km bbox in my (under-clustered) synthetic store already produces **4,191 parameters**; the
  real store is 3–12× denser in its hot spots, which puts a dense-area 30 km query plausibly in the
  **10,000–50,000** parameter range.
- **Risk:** `SQLITE_LIMIT_VARIABLE_NUMBER` is **32,766** by default in modern SQLite (**999** in
  3.31 and earlier). Exceeding it is not a slowdown — it is
  `sqlite3.OperationalError: too many SQL variables`, raised from inside a per-poll perception
  call. This machine's build reports 250,000, so **the limit cannot be probed from here**; it is
  the user's Windows Python's SQLite build that decides.
- **Blast radius:** every `nearest_feature`/`containing_polygons`/`describe_position` call at its
  30 km radius, i.e. the per-poll enrichment path, in the densest parts of the theatre — the places
  the aircraft is most likely to be flying.
- **Mitigation:** the subselect rewrite from finding 2 (`id IN (SELECT id FROM feature_bbox WHERE
  …)`) removes the parameter list entirely and keeps the plan correct
  (`EXPLAIN`: `LIST SUBQUERY 1` + `SCAN feature_bbox VIRTUAL TABLE INDEX`). Its *speed* win is only
  1.1–1.3×, but its *correctness* win is the whole finding.
- **Action: NOW**, on the correctness argument rather than the performance one. It is the same edit
  finding 2 already touches.

### 5. `find_place_by_name` parses every named feature in the theatre to substring-match a name

- **Location:** `world-model/src/query/search.py:92` → `store/reader.py:113` `all_features(conn,
  search_kinds)`, with `PLACE_KINDS` defaulting to `named_place` + `settlement`.
- **Mechanism:** `all_features` has no bbox and no name filter: it selects every row of those kinds
  (**49,226** in the real store) and `_row_to_feature` (`reader.py:75`) runs **four `json.loads`
  per row** (`geom_json`, `tags_json`, `provenance_json`, `confidence_json`) and materialises the
  full vertex list — all to compare `name` against a needle and throw the geometry away for every
  non-match.
- **Measured:** **507 ms** against **26.9 ms** for a SQL-side `name LIKE` prefilter returning ids
  and names only — **19×**, and my synthetic geometries are smaller than real `settlement`
  polygons, so the real gap is wider.
- **Blast radius:** not per-poll. It is a **crew-command latency** path — `belief/tools.py:717`
  `find_place`, reached when the pilot asks about a place by name, and the `/find_place_by_name`
  API endpoint (`src/api/server.py:180`). Half a second (likely over a second on the real store)
  between the pilot's question and Petrovich starting to answer, for a string match.
- **Mitigation:** push the name filter into SQL. `_match_confidence` (`search.py:67`) only needs
  case-insensitive exact-vs-substring, which `name LIKE '%needle%' COLLATE NOCASE` expresses
  exactly; fetch full rows only for the handful that match. An index on `feature(kind, id)`
  (finding 2) removes the full-table scan from the prefilter too.
- **Action: NOW.** Small, local, no architectural question, and it is latency the pilot hears.

### 6. Things checked on the live path that are *not* findings

Recorded so a later reviewer does not re-flag them.

- **Connection handling is correct.** One long-lived read-only connection per poll thread,
  opened on the poll thread (`body-layer/src/perception/geometry.py:56`, opened at
  `logger.py:1398`), never reopened per poll, `check_same_thread` left at its safe default. **No
  lock anywhere serializes the tick** — `api/server.py:44-52`'s docstring shows the serialization
  question was already reasoned through for the HTTP path.
- **`grid_sample` lookups are optimally indexed.** `WITHOUT ROWID` with `PRIMARY KEY (grid_id, row,
  col)` (`schema.py:81-88`) gives a direct PK seek; `EXPLAIN QUERY PLAN` confirms it. There is no
  index to add here.
- **`PRAGMA` tuning buys nothing.** `mmap_size=1 GB` → 43.40 → ~40 ms (≈8 %); `cache_size=-200000`
  → no improvement. Cold-vs-warm first-poll difference was within noise. The cost is **statement
  execution count in Python**, not I/O — which is why the in-memory fix wins 540× and the pragmas
  win 8 %. Do not reach for pragmas here.
- **`pyproj` transformer construction is already cached** per theatre
  (`src/coordinates/__init__.py:40-47`, `@cache`), with the M5 regression that caused it recorded
  in-file. Still correct.
- **`sample_grid`'s bilinear path allocates nothing per call** beyond four floats. No per-request
  allocation problem exists on this path.

---

## Findings — offline build pipeline

Budget here is different and must not be confused with the tick: a whole-theatre run has to stay
**minutes, not hours**, and scale roughly linearly. `WM-B1` + `WM-B6` together force a full
`syria-full` rebuild, and both bump cache-invalidation constants (`CLASSIFIER_VERSION`,
`EXTRACTOR_VERSION`), so that rebuild pays **every** stage cold.

### 7. The 449.3 s baseline everyone is quoting is obsolete, and the two expensive stages are not the ones it names

**This reorders every other priority below, so it comes first.**

M7's `449.3 s` figure (`ROADMAP.md`, M7 entry) predates M9 (OSM), M10 (junctions) and geomorphons,
and its SRTM grid was built at **1000 m** spacing — `points_expected=639,216` is exactly
`syria-full`'s half-extents at 1000 m. The current default is
`DEFAULT_SRTM_GRID_SPACING_M = 500.0` (`src/build/pipeline.py:158`), i.e. **2,555,208 cells, 4×**.
Its *"`.routes`-walk-dominated"* characterisation is also no longer true.

The only full-theatre build at current-HEAD-equivalent code is
`research/2026-10-05-afghanistan-theatre-build.md`, **~82 minutes** end to end, with per-stage
timings from the build log:

| stage | time | share |
|---|---|---|
| **terrain semantics (ridge/valley)** | **2640.2 s (44.0 min)** | **54 %** |
| **road junctions** | **1751.1 s (29.2 min)** | **36 %** |
| `Afghanistan.routes` walk | 320.2 s | 6.5 % |
| SRTM elevation grid | 136.8 s | 2.8 % |
| OSM overlay (`.osm.pbf`, cache miss) | 85.9 s | 1.8 % |
| towns + beacons | 0.1 s | — |

**Two stages are 90 % of the build.** Neither is the `.routes` byte-scan, and neither is OSM.
**Action: NOW** — stop citing 449.3 s; it will make any rebuild estimate wrong by an order of
magnitude. `ROADMAP.md`'s M7 entry should carry a pointer to the Afghanistan note.

### 8. `ingest_junctions` re-parses every road's full geometry once per 5 km chunk its bbox overlaps

**The single biggest win per line changed in the whole subproject.**

- **Location:** `world-model/src/build/ingest_junctions.py:211` — `roads = features_in_bbox(conn,
  ["road"], padded)` inside the `for index, (ix, iz) in enumerate(chunks):` loop at
  `ingest_junctions.py:191`.
- **Mechanism:** `features_in_bbox` selects R*Tree candidates by **bbox overlap**, then
  `_row_to_feature` (`store/reader.py:94`) `json.loads`es the full `geom_json` of every road
  returned. A `.routes` polyline is stored **unclipped** (`build/ingest_roadnet.py:23`) and is
  typically 100 km+ across, so the same road is re-fetched and re-parsed in **every chunk its bbox
  touches** — not every chunk it passes through.
- **Cost:** `O(Σ_roads vertices(road) × chunks_overlapping_bbox(road))`, not `O(V)`.
- **Arithmetic against the real build**, which is what makes this a confirmed mechanism rather than
  a suspicion: Afghanistan's half-extents give `ceil(1083.9/5) × ceil(1318.5/5)` = **57,288
  chunks**; 1751.1 s / 57,288 = **30.6 ms per chunk**, to find **196 junctions from 1,590 roads**.
  Mean route size is `996,609,990 bytes / 1,590 routes / ~112 bytes per point` ≈ **5,600 points**,
  so `geom_json` ≈ 120 KB per road; a 100 × 100 km bbox spans ~400 chunks, giving ~11 road
  re-parses per chunk ⇒ ~**77 GB of `json.loads` traffic**. At 50–100 MB/s that is 770–1,540 s,
  which lands on the measured 1,751 s.
- **Blast radius:** multiplies theatre **area** (chunk count) by road **vertex** count. `syria-full`
  has 25,730 chunks but **14,833 roads — 9.3× Afghanistan's** — so the same or worse, and it is
  inside the forced rebuild.
- **Mitigation — invert the loop.** One streaming pass over `SELECT id, geom_json FROM feature
  WHERE kind='road'`, parsing each geometry exactly **once**, emitting
  `(chunk_ix, chunk_iz, x, z, feature_id, is_endpoint)` into a temp table; `CREATE INDEX` on
  `(chunk_ix, chunk_iz)` **after** the bulk insert; then run `extract_clusters` per chunk off vertex
  rows. Padding/centroid-ownership semantics survive by also emitting each vertex into the (≤8)
  neighbour chunks whose padding reaches it — padding is 10 m against a 5 km chunk, so that
  duplication is negligible. `O(V log V)` with one parse per road: expect **1751 s → tens of
  seconds**.
- **Action: NOW.** Confined to one file, output geometry unchanged.

### 9. `ingest_junctions` visits ~57,000 chunks for a 1,590-road layer, most of them empty

- **Location:** `world-model/src/build/ingest_junctions.py:191`, fed by `chunks_covering` over the
  road layer's whole **bounding rectangle**.
- **Mechanism:** even with finding 8 fixed, that is 57,288 R*Tree round-trips over a theatre whose
  roads occupy a small fraction of its cells.
- **Mitigation:** falls out of finding 8 — derive the chunk list from the vertex table's own
  `DISTINCT (chunk_ix, chunk_iz)` instead of from the bbox rectangle.
- **Action: NOW**, as part of finding 8. On its own it would be MEDIUM.

### 10. `skeleton.thin()` allocates two 8-deep int64 stacks per sub-pass, for values bounded by 8

- **Location:** `world-model/src/terrain/skeleton.py:149` and `:151` —
  `np.sum(np.stack(p).astype(np.int64), axis=0)`, inside the `while changed:` loop at
  `skeleton.py:145`.
- **Mechanism:** each materialises an `(8, rows, cols)` int64 array. For a 1°-tile window (~1.5 M
  cells with the margin at 90 m) that is **96 MB per array, ~200 MB allocated and ~400 MB of memory
  traffic per sub-pass**. The loop iterates to the maximum object half-thickness (tens of passes on
  mountainous geomorphon blobs), × 2 sub-passes, × 2 masks (ridge, valley), × 158 tiles.
  `O(cells × iterations)` with a ~25× constant factor in bytes touched that the algorithm does not
  require: **both `count` and `transitions` are bounded by 8**, so int64 is pure waste.
- **Blast radius:** linear in theatre area, and it is the largest single component of the largest
  stage (54 % of the build).
- **Mitigation**, all mechanical and behaviour-preserving:
  - accumulate into `uint8` in place (`count = p[0].copy(); for q in p[1:]: count += q`) instead of
    `stack(...).astype(int64).sum(axis=0)`;
  - better: build the 8-bit neighbourhood code once (`code |= p[i] << i`) and resolve
    `count`/`transitions`/`struct_ok` through three 256-entry `uint8` lookup tables indexed by
    `code` — the standard vectorised Zhang-Suen, ~10× less traffic;
  - shrink to the mask's own bounding box on entry, and after the first two iterations restrict
    evaluation to a dilation of the still-changing set.
- **Action: NOW.** The module docstring records that a `scikit-image` fallback *"was not needed"* —
  that judgement predates the 44-minute theatre-scale measurement and is worth re-opening
  (`skeletonize` is C and ~100× faster), **but that is a new dependency and therefore the user's
  call, not this review's.** The LUT rewrite gets most of it with no new dependency and should be
  tried first.

### 11. `_smooth_for_storage` runs the deviation check on 16× the points, before the decimation that makes it redundant

- **Location:** `world-model/src/terrain/features.py:332-334` — the
  `for point, (lo, hi) in zip(smoothed, support, …)` loop calling `distance_point_polyline` once per
  **smoothed** point, i.e. 16× the traced cell count (four Chaikin passes), for every one of
  ~1.19 M stored lines — and it runs **before** `_decimate_for_storage` at `features.py:336`.
- **Mechanism:** `_chaikin_smooth_with_support` already fixed an earlier O(n²) here (recorded in
  `ROADMAP.md`), but the surviving O(16n) Python loop still dominates per-feature cost: ~340
  `distance_point_polyline` calls per feature at ~2 µs ⇒ ~0.7 ms × 1.19 M features ≈ **800 s**,
  roughly 30 % of the terrain stage.
- **Mitigation — reorder, on the function's own documented grounds.** Its docstring
  (`features.py:322-329`) states that `_decimate_for_storage` performs *"its own independent
  deviation check against the same `cap_m`"* and that the return value *"always satisfies"* the cap
  *"whichever of smoothing/decimation ends up applied."* So on the common path — decimation
  succeeds, measured at 36.7× point reduction — the 16× loop is **redundant**. Decimate first,
  check the decimated line against the original sampled points, and fall back to the windowed
  check only if decimation is rejected. Then vectorise what survives: all original points against
  all decimated segments is one `(N, M)` numpy expression, not `N × M` Python calls.
- **Action: NOW**, paired with finding 10 — the two are the halves of the 44-minute stage.

### 12. `sample_tiles_bilinear` scans all 158 tiles per window and re-casts each to int64 per call

- **Location:** `world-model/src/terrain/resample.py:66-81`, called from
  `src/build/ingest_terrain.py:244` with **all** region-touching tiles.
- **Mechanism:** the loop evaluates five full-window boolean comparisons (~1.5 M cells each) per
  tile until `remaining` empties. Tiles are in name order, so a window's 9 covering neighbours sit
  ~24 list positions apart and the loop typically runs to the highest-indexed needed tile — about
  half the list. ~79 tiles × 1.5 M × ~6 element-ops ≈ 700 M ops per processed tile × 158 tiles,
  plausibly **300–600 s of the 2640 s stage**. Separately, `resample.py:81` does
  `np.asarray(tile.samples, dtype=np.int64).reshape(size, size)` **per call per tile** — an 11.5 MB
  allocation and cast for a 1201² SRTM3 tile, ~1,400 times across a build, at a width 4× what the
  data needs.
- **Mitigation:** pre-filter `tiles` to those whose lat/lon box intersects the window's lat/lon box
  before the loop (9 instead of 158); cache the reshaped grid on `SrtmTile`, or build it once in
  `from_file` via `np.frombuffer(raw, dtype='>i2').reshape(...)`, and keep it `int16`/`int32`.
- **Action: NOW** — it rides along with findings 10/11 in the same stage.

### 13. The SRTM grid stage is a per-cell Python loop with a per-tile linear scan and per-row inserts

- **Location:** `world-model/src/elevation/dem.py:150`, `src/build/ingest_srtm.py:105-132`,
  `src/store/writer.py:159-167`.
- **Measured:** **136.8 s for 5,721,822 cells** (`afghanistan-full` at 500 m) = **23.9 µs/cell**.
  Three compounding costs: scalar `dcs_to_wgs84` per cell; `select_tile`'s linear scan over **all
  288 staged tiles** (`pipeline.py:650` loads every staged tile, not `tiles_for_region`'s 158, so
  ~829 MB of `array('h')` is resident); and `insert_grid`'s single-row `conn.execute` per cell,
  5.72 M times.
- **Blast radius:** `syria-full` at the current 500 m default is 2,555,208 cells — **4× the 639,216
  the old 4.5 s figure was measured on.** Expect ~60 s there, not 4.5 s.
- **Mitigation:** three independent, each small — (a) call the existing
  `terrain/resample.py::resample_window` instead of the scalar loop (it already does this job
  vectorised, and `coordinates.dcs_to_wgs84_array` exists); (b) pass `tiles_for_region(...)` to
  `ingest_srtm_grid`, or bucket tiles by `(floor(lat), floor(lon))` in `select_tile`; (c)
  `executemany` the `grid_sample` rows — `probe_store/writer.py:195` **already does exactly this**,
  so the pattern exists in-repo and `store/writer.py` simply does not use it.
- **Action: LATER.** 2.8 % of the build; the (b) tile-residency part also overlaps
  `project_terrain_semantics_ignores_region_bbox`, already filed.

### 14. No SQLite build-time PRAGMA tuning anywhere in the subproject

- **Location:** `grep -rn "PRAGMA" src/` returns **nothing**. `store/writer.open_for_build`
  (`writer.py:32`) opens with defaults — `journal_mode=delete`, `synchronous=FULL`.
- **Mechanism:** every batched transaction writes and fsyncs a rollback journal, roughly doubling
  write volume for a 608 MB–8.1 GB store plus the two caches.
- **Mitigation:** `PRAGMA journal_mode=OFF; synchronous=OFF; cache_size=-262144;
  temp_store=MEMORY` in `open_for_build` / `open_osm_cache_for_populate`. Correctness-safe for the
  base store and the OSM cache by their own stated contracts (delete-and-recreate /
  `.tmp`-then-`os.replace`, so a crash is already *"start over"*). **Not for `terrain_cache`** — its
  resumability depends on real per-tile transaction durability (`terrain_cache/writer.py` module
  docstring), so that one gets `journal_mode=WAL; synchronous=NORMAL` at most.
- **Action: NOW** — cheap, low risk, and the per-stage contract difference is the part not to get
  wrong.

### 15. `feature` has no index at all beyond its implicit `id` PK

- **Location:** `world-model/src/store/schema.py:47-60` — no `CREATE INDEX`.
- **Blast radius:** both halves of the subproject. On the build side,
  `count_features(conn, ["road"])` and `feature_layer_bbox(conn, ["road"])`
  (`ingest_junctions.py:172,174`) are each a **full scan of a multi-GB table**; on the query side it
  is findings 2 and 5.
- **Measured:** `CREATE INDEX idx_feature_kind ON feature(kind, id)` — **0.1 s to build, +2 MB on a
  129 MB store**; `describe_position` 40.8 → **27.8 ms** (1.5×), `EXPLAIN` confirms a covering
  index.
- **Action: NOW**, bundled with the rebuild `WM-B1`+`WM-B6` already force. The point of a forced
  rebuild is that schema changes are free this once.

### 16. Lower-severity build items, recorded with their measured share

- **`roadnet/container.py:228-242`** — byte-by-byte Python resync scan over the whole `.routes`
  file: 320.2 s on 996 MB (Afghanistan, 321 ns/byte), 446.2 s on 2.25 GB (Syria, 198 ns/byte).
  Afghanistan is *slower per byte*, consistent with more candidate offsets surviving
  `min_n <= n <= max_n` and paying `_prefilter_plausible`. Roadnet is also the one expensive stage
  with **no cache**, so it is 100 % of a warm rebuild. Fix if it ever matters: vectorise the
  candidate mask with numpy over a `uint8` view, then run the Python prefilter only on survivors
  (10–20×). `container.py:237-240` also re-unpacks all N triples that `_full_validate` just
  unpacked — a literal 2× on the accepted-block path. **LATER**: 6.5 % of the build, and not what
  makes the forced rebuild slow. The incremental/per-layer-build backlog item at `ROADMAP.md:1197`
  is the structural answer; nothing new to file.
- **`terrain/geomorphons.py:101-118`** — 120 whole-*window* array passes (8 directions × 15 lookup
  cells), each allocating `shifted`, `angle` and two `nan_to_num` temporaries at float64: ~8.6 GB
  of churn per tile, ~160 s/build. Fix: `out=` buffer reuse and float32 (angle comparisons against
  a 1° flatness threshold do not need float64). **LATER** — real, but a fifth the size of finding 10
  in the same stage.

  **A correction worth recording, because it is the mistake this review nearly published.** An
  earlier draft of this note claimed `geomorphons` holds ~5 GB of *whole-theatre* arrays and churns
  ~151 GB, and recommended tile-wise processing with overlapping margins. **That is wrong: the
  tiling already exists.** `ingest_terrain._tile_pipeline` (`ingest_terrain.py:225-255`) builds a
  per-tile DEM window with a `margin_cells` margin and calls `geomorphons` on *that*, and
  `on_tile_features` is invoked once per tile (`ingest_terrain.py:288,417`). `ROADMAP.md`'s
  `WM-B6` entry already records the ~29 GB → ~1.75 GB fix (`b4d38cf`) that implemented it. The
  arithmetic was sound; the premise was a theatre-wide array that is never built.
- **`terrain/skeleton.py:210,214,219,240`** — a `frozenset` per edge visit in `trace`: ~3
  constructions per walk step over ~50–150k skeleton points per mask, ~70 s/build. `walk` also
  rebuilds the `turn` closure every step and calls it twice on the winner (`:232-238`). Fix:
  canonical sorted int-pair tuples keyed on `row * n_cols + col`. **LATER.**
- **`build/ingest_osm.py:474,581,589`** — scalar `wgs84_to_dcs` per OSM vertex, 8,343,864
  pre-simplify vertices on `syria-full`, while `coordinates.dcs_to_wgs84_array` proves the array
  path exists. Projection also happens **before** the region clip and before the `MIN_AREA_M2`
  gate, so dropped rings pay for every vertex. But the whole OSM stage measured **85.9 s**, so this
  is bounded small today. **MONITOR** — re-measure on the `syria-full` rebuild, whose vertex count
  is much larger.
- **`geometry/__init__.py:97`** — `point_in_polygon` calls `_point_on_segment` (a full
  `distance_point_segment`) for every edge before the ray-cast, ~tripling its cost. Hits
  `_ring_vertices_contained` (`ingest_osm.py:558`, `O(hole_verts × outer_verts)` — 127 × 13,097 ≈
  1.6 M ops for the largest real polygon) and the runtime `inside_landcover` path. Fix: bbox reject
  first, boundary test only when the ray-cast is ambiguous. **LATER.**
- **`geometry/__init__.py:211`** — Douglas-Peucker's inner loop is `O(n²)` worst case (iterative
  stack, but total work is Σ segment lengths if splits land near an endpoint). Average is
  `O(n log n)` and real geographic data behaves; the bound for the largest known ring is 13,097² =
  171 M ops. **MONITOR**, and re-check if `SIMPLIFY_TOLERANCE_M` is ever lowered.
- **`terrain_cache/hashing.py:23`** — `combined_tile_hash` SHA-256s every staged tile's full content
  on every build, including a 100 % warm cache hit: 158 × 2.88 MB ≈ 455 MB, ~1–2 s. Correct by
  design (content identity, not mtime). **MONITOR**, no action.

### 17. Things checked on the build path that are *not* findings

Recorded so nobody "fixes" them.

- **The feature/grid write path is already fast.** `store/writer.py:101-129` does two `conn.execute`
  per feature (~230,700 statements for syria-full) and `writer.py:157-166` one per cell (591,732),
  with no `executemany`. Measured against the real `grid_sample` DDL at M7's real cell count:

  ```
  per-row execute (as written), default pragmas      0.78 s  (757k rows/s)
  executemany, default pragmas                       0.55 s  (1077k rows/s)
  executemany + journal_mode=OFF, synchronous=OFF    0.55 s  (1081k rows/s)
  ```

  `executemany` saves **0.23 s** — against an 82-minute build, nothing. The pragmas save nothing
  *here* because both functions already commit **once at the end** (`writer.py:130`, `:168`), so
  there is no per-row fsync to remove; finding 14's pragma win is about journal **write volume**
  across the build, not about these two loops. The single-transaction batching, which is the part
  that matters, is already right. Across all three feature write paths
  (`store/writer.py:101,125`, `osm_cache/writer.py:55`, `terrain_cache/writer.py:73`) the estimate
  is 18–30 s at 1.19 M terrain features, ~1 % of the terrain stage. **A cheap tidy-up if someone is
  in the file; not a performance fix, and it should not be presented as one.**
- **`terrain_cache/schema.py:89`** — `CREATE INDEX feature_tile_id` exists **before** the bulk
  insert, the classic anti-pattern. It is load-bearing for per-tile resumability and
  `write_tile_features`' `DELETE … WHERE tile_id = ?`. **Correct as written.**
- **`terrain/skeleton.py:139`** — Zhang-Suen thinning is genuinely vectorised, not the pixel-by-pixel
  double loop the spike used. Finding 10 is about its dtype and allocation, not its structure.
- **`coordinates`' per-theatre `Transformer` caching** (`src/coordinates/__init__.py:40-47`) is the
  fix for a real M5 build regression (*"an OSM way's every vertex through `wgs84_to_dcs`"*) and is
  still in place.

### 18. A documented premise that no longer holds: the OSM cache protects a 1.5-minute pass

- **Location:** `world-model/CLAUDE.md` and `plans/osm-classified-cache/plan.md` justify the entire
  OSM cache layer by a *"~25-30+ minute pyosmium-parse-plus-classify pass."*
- **Why it is stale:** that figure predates the `osmium tags-filter` pre-filter (−85–87 % nodes) and
  `pbf.py`'s in-process `KeyFilter`. The real post-optimisation measurement is **85.9 s**.
- **So:** the OSM cache is now protecting a 1.5-minute pass, while the 44-minute terrain stage and
  the 29-minute junction stage are the actual rebuild cost. The cache is not *wrong* — it is simply
  not where the time is, and a reader who takes the 25–30 minute figure at face value will spend
  effort on the wrong stage.
- **Action: NOW**, as a documentation correction only. No code change implied, and **no
  recommendation to remove the cache** — that is a separate judgement with correctness and
  offline-rebuild implications this review did not examine.

### Recommended order for the forced `WM-B1`+`WM-B6` rebuild

1. **Findings 8 + 9** (junctions: ~29 min → tens of seconds). Biggest win per line changed.
2. **Findings 10 + 11** (the two halves of the 44-minute terrain stage).
3. **Finding 14** (PRAGMA) and **finding 15** (the `kind` index) — both near-free, and 15 must land
   *with* the rebuild or it costs another one.
4. **Findings 12, 13.**

That is ~90 % of an 82-minute build addressed by changes in five files, **none of which alter output
geometry** — which is what makes it worth doing inside `WM-B6` rather than after it.

---

## What could not be measured, and what it would take

| unmeasured | what is needed |
|---|---|
| Absolute `describe_position` cost at **real** syria-full clustering | the real `syria-full.sqlite` (608 MB, user's machine). M7's committed 136.8 ms mean / 497.7 ms p95 is the authoritative figure and is 3–12× my synthetic; treat mine as ratios only |
| Whether `SQLITE_LIMIT_VARIABLE_NUMBER` is actually exceeded (finding 4) | `python -c "import sqlite3; print(sqlite3.connect(':memory:').getlimit(9))"` on the **user's Windows Python**, plus one `features_in_bbox` id-count probe at a 30 km bbox centred on Damascus against the real store. This machine reports 250,000, which proves nothing about theirs |
| Real per-poll candidate count reaching gate 4's fallback | already partly in the sortie logs (43 median / 71 max units from DCS; >128 past the gaze gate in 11 of 2,104 polls). The missing piece is a timing instrument *inside* the poll loop — sortie note's own next step 2 |
| Offline LOS at **fine** grid spacing | `WM-B8` (fixture-scale fine elevation grid, LOW PRIORITY, open). Cite it; it is the right vehicle. Note that a finer grid makes finding 1 **worse**, because 19 samples over a 6 km sightline currently straddle only a handful of 500 m cells — at 100 m spacing the 6.8× cell redundancy that makes the per-poll memo work largely disappears, and the in-memory grid becomes the only fix that still holds. **A fine grid should not land before the in-memory decision is made.** |
| Peak RSS during a build | still unmeasured, as `ROADMAP.md`'s M7 entry already says — nothing in the pipeline logs it |
| Whether findings 8/10/11 deliver their estimated savings | they are reasoned from the Afghanistan build log plus arithmetic, not from a before/after run. The verification is a `syria-full` rebuild with per-stage timings, which **only the user can run** (execution-boundary rule). The command is `RUN.md`'s own full-theatre build; this review does not run it |
| `src/build/pipeline.py` / `ingest_osm.py` / the cache layers line by line | not examined at that depth. Known-unexamined: whether `osm_cache`/`terrain_cache` skip the expensive pass or re-do hashing work, and index-before-vs-after ordering in the pipeline's own sequence. Finding 18 is the one cache premise that was checked |

---

## Verdict

**NEEDS MITIGATION** — in both halves, and in neither case for the reason that prompted the review.

**Live tick, ranked by measured value:**

1. **Finding 2** — resident small layers for `ridge`/`valley`/`airfield`/`runway`. **101×** on
   ~73 % of `describe_position`, which is the dominant world-model cost on the per-poll path.
2. **Finding 5** — SQL-side name filter in `find_place_by_name`. **19×** on a latency the pilot
   hears.
3. **Finding 1** — hoist `_load_grid_meta` (1.3×, free), then the per-poll cell memo (6.9×) or the
   resident grid (540×).
4. **Finding 4** — the bind-parameter rewrite, on correctness grounds.

**Offline build, ranked by share of an 82-minute run:**

1. **Findings 8 + 9** — `ingest_junctions`' per-chunk road re-parse. **36 % of the build**, one
   file, output unchanged.
2. **Findings 10 + 11** — `skeleton.thin()`'s int64 stacks and `_smooth_for_storage`'s pre-decimation
   check. Together most of the **54 %** terrain stage.
3. **Finding 14** (PRAGMA) and **finding 15** (the `kind` index) — both near-free; **15 must land
   with the forced rebuild or it costs another one.**

**Two findings that outrank everything above and belong to other owners:**

- **`_DEFAULT_POLL_INTERVAL_S = 1.0`** in `body-layer/src/logger.py:997`, against a specification of
  5 Hz and against the same file's own comments. ~5× of the sortie's 7× gap. **body-layer's, not
  world-model's.**
- **The 449.3 s rebuild baseline is obsolete** (finding 7). The real figure is ~82 minutes with
  terrain at 54 % and junctions at 36 %. Any plan sized against 449 s is wrong by an order of
  magnitude.

**The sortie's number-one suspect is substantially exonerated.** The offline LOS fallback costs
43 ms per poll at the worst candidate count observed — real, worth fixing, and ~4 % of a 1.0 s
interval. It is not the 7×.

**One correction this review made to itself**, recorded because the near-miss is the instructive
part: an earlier draft recommended tile-wise processing for `geomorphons`, with 5 GB-resident and
151 GB-churn arithmetic behind it. The tiling already exists (`ingest_terrain._tile_pipeline`), and
`ROADMAP.md`'s `WM-B6` entry already records the fix that built it. The arithmetic was correct for a
whole-theatre array that is never allocated. See finding 16.
