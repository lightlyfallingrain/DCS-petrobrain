---
name: project_bl3_world_enrichment
description: BL-3 world enrichment implementation — bearing/range recovery gap, fixture schema mismatch, float**float mypy quirk.
metadata:
  type: project
---

Implemented `plans/bl3-world-enrichment/plan.md` on `feature/bl3-world-enrichment`
(`body-layer/src/belief/enrichment.py` new, plus additive changes to `geometry.py`/`decay.py`/
`tools.py`/`console.py`/`logger.py`). 243 tests pass (210 baseline + 33 new).

**Contact stores no bearing/range, only the flattened `last_position`.** Any future work that
needs to re-derive geometry from a `Contact` (not a `Percept`) must walk
`contact.contributing_observation_ids` back through `ContactStore.observations` to recover the
original `Percept`, the same pattern `belief.enrichment._terrain_aware_world_position`/
`motion_when_seen` both use. The plan's prose assumed this was trivial; it isn't — document the
resolution, don't just wing it.

**`float ** float` returns `Any` under `mypy --strict`** (typeshed's `pow` overloads admit
`complex`). Use `math.pow(a, b)` instead whenever exponentiating two known floats — bit `belief/
decay.py`'s `position_confidence` once already.

**Local world-model fixture `.sqlite`s are not interchangeable for live sanity passes.**
`world-model/data/world-model/latakia-20km.sqlite` predates the M7 Stage 2 `grid.provenance`
schema bump and fails `describe_position` outright (`no such column: provenance`) — a pre-existing
gap on `main`, not something a feature branch introduces. `syria-full.sqlite` has the current
schema but its `feature` table only has `airfield`/`named_place`/`navaid`/`road`/`runway` rows —
no `settlement`/`water`/`ridge`/`valley` (see [[project_m7_stage2_srtm_provenance]]). Check both
before assuming either is usable for a live/offline sanity check.

**`project_terrain_aware`'s `max_iterations=1` only corrects altitude, not horizontal position** —
it samples terrain at the *flat* projection's horizontal spot and reports that elevation; the
horizontal position itself only starts moving from iteration 2 onward, once the corrected altitude
feeds back into a smaller horizontal range. Easy to misread as "single-shot does nothing."

**`WorldEnrichmentCache` cache-hit staleness**: keyed only on `Contact.last_position` match, so a
cached `SemanticFact.confidence` (which folds in `position_confidence`) does not re-decay between
position changes — a deliberate, documented perf/staleness tradeoff, not a bug.
