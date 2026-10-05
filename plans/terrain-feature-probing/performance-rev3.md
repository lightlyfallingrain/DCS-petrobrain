### Performance Review

**Verified against:** `feature/terrain-callout-stages-345` tip `3a9acf8` (matches the dispatching
prompt's expected sha; confirmed `3a9acf8` is `feature/terrain-callout-stages-345`'s own HEAD via
`git log`). This worktree landed on its own scratch branch (`worktree-agent-a07338d307204b593` at
`0a8c86c`, an unrelated audio-adapter commit), so all code read and measured came from
`git archive feature/terrain-callout-stages-345 | tar -x -C <scratch>`, run from
`<scratch>/world-model` and `<scratch>/body-layer` using the main checkout's
`world-model/.venv/bin/python3` (the snapshot carries no venv of its own). Read-only queries only,
against the real `world-model/data/world-model/syria-full.sqlite` (234,799 feature rows,
122,567 of them `ridge`) — no theatre build was run.

### Findings

#### `divides_between` per-call cost (the new query)

- **Location:** `world-model/src/query/divides.py:divides_between`, called from
  `body-layer/src/belief/enrichment.py:terrain_divide_qualifier`.
- **Measured against the real store:** sampled the 8 densest 5 km ridge cells in
  `syria-full.sqlite` (max 31 ridge features per 5 km × 5 km cell; at 1 km granularity the
  densest cell holds 6 ridge features, vertex count median 5, p99 19, max 51 across all 122,567
  ridge rows — there is no pathological fragmentation in the real data today). A 5 km corridor
  through these cells returned 0–5 candidate ridges (plan's claim: "~5 lines at Baalbek
  density" — confirmed, measured, not extrapolated); a 10 km corridor (the full
  `PLAYER_BUBBLE_RADIUS_M` span) returned 3–7. Per-call cost: **0.02–0.11 ms**, R*Tree-bounded
  (`store.reader.features_in_bbox` queries `feature_bbox`, an indexed table — candidate count
  scales with corridor bbox area, not theatre size).
- **Synthetic pathological-fragmentation bound** (Security's deferred item — a crest stored as
  many short fragments rather than one polyline): monkey-patched `features_in_bbox` to hand
  `divides_between` 10/50/100/500/1000/5000 short zigzag fragments across one 5 km sightline,
  bypassing SQL to isolate the intersection+dedup loop's own complexity. Measured, in-process,
  **linear**: 0.01 ms at 10 fragments, 0.5 ms at 500, 1.06 ms at 1000, 5.35 ms at 5000. The
  dedup step (sort + single pass, `DIVIDE_MERGE_M` merge) never produces the blowup Security
  asked about to be ruled out — it is O(m log m) in crossing count `m`, and `m` is bounded by
  candidates in the bbox, which is bounded by corridor area, not by theatre size. **5000
  fragments in one 5 km corridor is ~170× denser than anything the current store contains**
  (worst real measurement: 6 features / 1 km cell ≈ 30 / 5 km corridor) and still costs 5.35 ms.
  Both the SQL-bound real-store path and the SQL-independent synthetic path confirm the same
  thing: this query's cost is bounded by corridor geometry, not by store size, and the plan's
  claim holds under measurement.
- **Risk:** none credible at current or plausible future data density.
- **Action:** MONITOR. If a future terrain-data revision (a different DEM source, a changed
  `clip, don't merge` policy) ever produces genuinely fragmented crests at the hundreds-per-
  corridor scale, re-measure — the arithmetic bound above says it would still cost single-digit
  milliseconds, not a blowup, but it's worth re-confirming against whatever new data shape
  appears rather than trusting this extrapolation indefinitely.

#### `PLAYER_BUBBLE_RADIUS_M` as the claimed upstream bound

- **Location:** `body-layer/src/perception/association.py:PLAYER_BUBBLE_RADIUS_M` (10 km).
- **Check:** this bounds *contact creation* (a candidate detection further than 10 km from
  ownship is dropped before a `Contact` is ever minted — `association.py:272-285`). It does
  **not** bound `divides_between`'s own corridor length directly; `divides_between` is always
  called with `observer = ownship`, `target = <a contact's believed position>`, and any contact
  that exists at all is, by construction, within 10 km of ownship at the moment it was created.
  So the corridor length `divides_between` ever sees is bounded by 10 km **at creation**, and
  stays bounded in practice because a contact that drifts past the bubble either loses
  `certainty_of == "observed"` or ages out via the lifecycle ticker — this review did not trace
  that aging path exhaustively, but nothing in `divides.py`/`enrichment.py` re-checks range
  before calling `divides_between`, so a contact whose *believed* position has drifted well
  past 10 km (stale dead-reckoning, operator error) would get an uncapped corridor. Given the
  measured linear-in-candidates cost above, even a worst-case full-theatre-width corridor
  (~1.4 Mm element of the extent measured: ridge features span roughly 1.37M m in X) would still
  be bounded by candidate count in that bbox, and bbox area grows, so this is a real, if
  low-probability, unbounded-input case.
- **Risk:** a contact with a very stale/wrong believed position produces a very large bbox query
  and correspondingly more candidates (still R*Tree-selective, not a full-table scan) — slower,
  not unbounded, since `features_in_bbox` cost scales with features *in that larger bbox*, which
  for a real theatre-sized bbox is "most of the ridge table" (122,567 rows) in the worst case. No
  measurement of that specific pathological corridor was taken (constructing a contact with a
  multi-hundred-km position drift is a `body-layer` belief-system question, not a `divides.py`
  one) — sized here only by arithmetic, not timed.
- **Action:** LATER. Worth a cheap guard (clamp or skip `divides_between` when
  `distance_point_point(observer, target) > PLAYER_BUBBLE_RADIUS_M`, or some similarly generous
  cap) the next time `enrichment.py` is touched, but this is not a credible risk today — it
  requires a pre-existing belief-system defect (stale position) to trigger, not normal operation,
  and this review found no evidence such positions occur in practice.

#### Per-tick call multiplicity in `CalloutScheduler.tick` (pre-existing, amplified by this change)

- **Location:** `body-layer/src/belief/callouts.py:CalloutScheduler.tick`, via
  `belief/speech.py:_group_member_facts` → `belief/tools.py:describe_contact` →
  `_add_enrichment_facts` → `terrain_divide_qualifier` → `divides_between`.
- **What I checked:** this is the actual 5 Hz hot path (`tick()` runs every poll). It is **not**
  the unbounded `get_contacts(store, ...)` path (`belief/tools.py:get_contacts` with no filter,
  which iterates `store.contacts` — every contact ever seen this sortie, per this project's own
  prior finding that `_contacts` is never pruned) — that function is only called from
  `crew_console.py`'s on-demand F10/speech-command handlers (`_nearest_contact_id`, the
  follow-targeting resolver, the sector/clock "report" command), all player-triggered, not
  per-tick. `tick()` itself only touches `store.unacknowledged_events` (bounded by actual pending
  lifecycle changes, not total contacts) and `store.groups` (bounded by current spatial
  clusters).
  For **groups**, though, `tick()` calls `_group_member_facts` (one `describe_contact`, hence one
  `divides_between`, per member) up to **three times per group per tick**, regardless of whether
  anything about that group changed: once to score the candidate
  (`render_group_disclosure`'s own internal gather), once again if that group is re-rendered as
  the chosen candidate, and once more in `group_membership_state`'s own re-gather for the winner
  (the second and third are the same tick, same group, same reason stated in the code's own
  comments: "re-gathers the same member facts... see that function's own docstring"). This
  pattern predates Stages 3a–5 (it is `group-reporting` Stage 4 architecture); this change adds
  one more SQL-backed call (`divides_between`) to every one of those gathers, so it multiplies an
  existing redundancy rather than introducing a new one.
- **Risk:** a tick where nothing changed for any group still re-runs `describe_contact` (and now
  `divides_between`) once-to-three-times per member of every tracked group, every 200 ms. At the
  real-store per-call cost measured above (0.02–0.11 ms for `divides_between` alone;
  `describe_contact`'s other enrichment work, cached via `WorldEnrichmentCache`, adds little on
  top for a position that hasn't moved), a scenario with 5 groups of 10 members each costs on the
  order of `5 × 10 × 3 × ~0.1 ms ≈ 15 ms` of `divides_between` time alone, every tick, whether or
  not anything is said — **this group/member count is an estimate, not a measurement**: no live
  sortie log was available in this worktree to pull a real concurrent-group-size distribution
  from (the `dcs-belief-truth.jsonl` sortie logs are generated on the Windows machine during
  flight, not present here). It is bounded, not catastrophic, but it is real waste: the content-
  signature check that would tell `tick()` "nothing changed, skip" only happens *after* the full
  member-facts gather, not before.
- **Action:** LATER, escalate to Architect rather than request a Stage 3a–5 rework. This is a
  pre-existing `group-reporting` Stage 4 shape (gather member facts, then check if anything
  changed), not something introduced by the terrain work, and fixing it well (e.g. caching
  `describe_contact` facts per-tick so the three gathers inside one `tick()` call share one
  computation, or gating the gather behind a cheaper "did anything move" pre-check) is a design
  change to that scheduling loop, not a one-line fix to `divides.py` or `enrichment.py`. Flagging
  it here because this change is what makes each of those three redundant gathers measurably more
  expensive than before (one more SQL query per member, per gather) — worth folding into whatever
  future pass touches `CalloutScheduler.tick`'s caching, not worth blocking this feature on.

#### Stage 4's `closest_point_on_feature` on the `describe_position` path

- **Location:** `world-model/src/store/reader.py:closest_point_on_feature`, called from
  `query/describe.py:_bearing_from_feature`.
- **Check:** operates on one already-fetched `StoredFeature` (no new DB query) — same shape and
  cost class as the pre-existing `_distance_to_feature` it sits beside (`O(vertices)` of that one
  feature, median 5, p99 19, max 51 vertices for `ridge`; similar order for `valley`/`road`).
  `describe_position` itself is called through `WorldEnrichmentCache.get_or_compute`, which is
  keyed on `Contact.last_position` and therefore **not** recomputed every tick for a stationary
  or slow-moving contact — confirmed this is the existing cache, not bypassed by Stage 4's
  addition.
- **Risk:** none. Cheap, and on an already-cached path.
- **Action:** none.

### Verdict
APPROVED — MONITOR
