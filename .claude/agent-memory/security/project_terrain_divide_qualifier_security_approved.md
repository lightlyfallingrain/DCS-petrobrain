---
name: terrain-divide-qualifier-security-approved
description: terrain-feature-probing Rev3 Stages 3a-5 (divides_between / terrain_divide_qualifier) checked clean on no-omniscience and cache-containment; APPROVED 2026-10-05.
metadata:
  type: project
---

Deep security analysis of `feature/terrain-callout-stages-345` (sha
`b95b3c69ee284e8172f2ea5ebcd931af7ca31c5b`) — the "next valley"/"beyond the ridge" divide-crossing
callout (`world-model/src/query/divides.py`, `body-layer/src/belief/enrichment.py`'s
`terrain_divide_qualifier`).

Findings:
- `terrain_divide_qualifier`'s `target` argument is always `world_position` (the terrain-aware
  **belief** position), never `Observation.derived_world_position` — confirmed by reading the
  `_add_enrichment_facts` call site, not the docstring. `ownship` is the player's own aircraft
  state, legitimately exact, not a leak.
- `WorldEnrichmentCache`'s tuple type has no slot for the divide count, and the call site bypasses
  the cache entirely — the ownship-relative value cannot go stale via cache hit. Same pattern as
  `relative_geometry`; this is the second instance of it. If a third ownship-relative value is
  added later, check this same class of bug again.
- `divides.py` reads geometry through the same `_row_to_feature`/`json.loads(geom_json)` path as
  every other store reader — no second parser.
- Degenerate geometry (zero-length segment, single-vertex LineString, NaN/inf coords, contact at
  ownship's exact position) all fail safe to an undercount/zero, never a crash or overcount —
  verified by reading `_segment_intersection_t`'s arithmetic, not assumed.
- Hot-path cost: `PLAYER_BUBBLE_RADIUS_M = 10000.0` (`perception/association.py`) is a real,
  code-verified gate on contact existence itself, which bounds the observer→target corridor length
  `divides_between` ever sees — not just a plan claim. Worst-case cost under adversarial crest
  fragmentation stays out of scope: the `.sqlite` is a trusted local build artifact, not untrusted
  input, per this project's threat model.

Full report: `plans/terrain-feature-probing/security-deep-analysis-rev3.md`. See also
[[project_los_terrain_tolerance_accepted_omniscience_trade]] for the sibling no-omniscience pattern
on the LOS side.
