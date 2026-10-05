## Security Plan Review: terrain-feature-probing (Revision 3, Stages 3a–5)

Reviewed against `plans/terrain-feature-probing/plan.md`, the section headed "Revision 3
(2026-10-05)" (lines 14–268). The superseded 2026-09-29/2026-10-01 content below it (basin
adjacency, `numpy`/`scipy`) is explicitly voided by Revision 3 and out of scope for this review —
those deps were already added to `world-model/pyproject.toml` by the earlier Stages 1–2 work and
cleared at that time (`project_world_model_first_native_deps_numpy_scipy` memory).

### Dependencies Checked

- **None proposed by Revision 3.** `/extract-plan-deps` hits inside the Revision 3 range (lines
  1–268) are limited to prose uses of the word "dependency" (ownship-dependency caching risk,
  line 228) — no package name. The only dependency-bearing lines in the file (418, 428, 472, 580)
  are all inside the Superseded section and already reflected in
  `world-model/pyproject.toml`'s current `numpy>=1.26,<2.5` / `scipy>=1.11` entries (verified by
  reading the file directly). **No new dependency in this plan.**

### Design Findings

- **No-omniscience boundary — held.** `Decision 2`'s `divides_between(observer, target)` is stated
  to run in the contact-report build path on `contact.last_position` (the fused belief position),
  the same position `_terrain_aware_world_position`/`semantic_facts_for` already consume in
  `body-layer/src/belief/enrichment.py`. The observer side is `OwnshipState` — the pilot's own
  aircraft, which is not a no-omniscience boundary (the crew always knows where it is). Nothing in
  Revision 3 reaches for `Observation.derived_world_position`, a DCS object id, or any ground-truth
  channel; the plan does not introduce a second path around `belief/percept.py`'s boundary. — **No
  action.**

- **Caching mistake — explicitly guarded against, not just avoided by luck.** Decision 1 states the
  divide count is never put in `WorldEnrichmentCache` because it is ownship-relative, and the
  plan's own Risks section (line 228) calls out "the ownship dependency is an easy caching mistake"
  as a named hazard for the implementer. This mirrors the existing, correct pattern:
  `relative_geometry` in `enrichment.py` (line ~585) is already "never cached" for the identical
  reason. The plan does not create a new per-tick full-store query path — Decision 1 is explicit
  that this runs in the contact-report build path, not the per-tick enrichment path. — **No
  action**, but worth the implementer re-reading that line, since it is exactly the kind of
  one-line omission that would reintroduce a stale "next valley" after the contact has moved.

- **Hot-path cost — bounded, and the plan's own measurement is corroborated against code, not just
  asserted.** Decision 1's claim ("~5 lines at Baalbek density, ~19 at theatre average for a 5 km
  corridor") rests on `features_in_bbox`, the same R*Tree-pruned bbox query `nearest_feature` and
  `containing_polygons` already use (`world-model/src/store/reader.py` lines 177–220) — not a new
  query mechanism or an unbounded table scan. The "contact 20 km away, before the bubble filters
  it" scenario this review was asked to check does not arise: `PLAYER_BUBBLE_RADIUS_M = 10000.0`
  (`body-layer/src/perception/association.py:116`) gates which units become `Contact`s at all, well
  upstream of contact-report build, so no contact a report is ever built for can be farther than
  10 km — the corridor Decision 1's bbox query spans is bounded by that, not by contact range in
  general. — **No action.**

- **Resource exhaustion from pathological geometry — low risk, non-blocking, no new surface.** A
  crest fragmented into hundreds of short lines inside one 10 km-bounded bbox query is a real
  degenerate case for the segment-crossing count and the `DIVIDE_MERGE_M` dedup pass, but:
  (a) the candidate set is still bounded by the same bbox query every other `nearest_feature` caller
  already relies on, not a new unbounded scan; (b) the data source is the offline-built,
  user-controlled `syria-full.sqlite` — a local build artifact, not untrusted network input, per
  this project's own threat model (LAN-only, single-user); and (c) the plan's own
  Effort/Value section already treats query-time cost as "argued from density, not timed" and
  names a documented fallback (a per-report memo). This is a performance-tuning question for the
  Performance Reviewer pass that is scheduled at this same feature boundary, not a security finding
  on its own.

  **Finding:** worst-case segment-crossing/dedup cost over a pathologically fragmented crest inside
  a bounded bbox is untimed.
  **Location:** `world-model/src/query/divides.py` (new, not yet written).
  **Probability:** low — the plan's own measured line density (234,799 rows theatre-wide, median
  5–6 vertices) does not show this pattern occurring at scale, and the data is offline/trusted.
  **Impact:** low — bounded by the existing bbox mechanism and the 10 km player bubble; at worst a
  slower poll, not a crash or a wrong result (the plan's own ≥2 ⇒ silence rule fails safe toward
  saying nothing).
  **Recommended action:** no action now; let the scheduled Performance Reviewer pass (this same
  feature, before DoD) time it against the real `syria-full` store rather than adding speculative
  bounds here.

  Options:
    (A) Ignore — accepted, re-raise only if the Performance Reviewer pass finds a real cost.
    (B) Add to todo.md — not warranted at this size.
    (C) Fix now — not warranted; no mechanism to fix, only a measurement to take later.
    (D) Stop — not warranted.

  Recommendation: **(A)**.

- **Input-trust surface — no new parsing introduced.** `divides.py` is planned to read
  `geom_json` rows the same way `store/reader.py`'s existing `_row_to_feature` already does
  (`json.loads(geom_json)` → list of `[x, z]` pairs, `world-model/src/store/reader.py:94`) via the
  shared `features_in_bbox`/`nearest_feature` path, not a hand-rolled parser with different
  assumptions. Stage 4's `nearest_feature` companion (closest point on the polyline) extends an
  existing, already-parsed `StoredFeature.geom`, not raw JSON. — **No action.**

- **Scope discipline — confirmed, not assumed.** Decision 5 explicitly excludes cover/attack advice
  ("recommend an approach from the north") as out of scope, consistent with
  `CLAUDE.md`'s "whose job is whose" (pilot owns navigation). This is a product-scope point, not a
  security one, but it is worth noting the plan does not quietly grow Petrovich's authority beyond
  perception/callout, which is the invariant this review would otherwise flag as scope creep. —
  **No action.**

### Verdict

**APPROVED**

No new dependency, no CVE exposure, no omniscience-boundary violation, no new untrusted-input
parsing surface, no unbounded hot-path query. One low-risk, non-blocking item (untimed worst-case
geometry cost) is deferred to the Performance Reviewer pass already scheduled before DoD for this
feature, per `recommended action: (A)` above.
