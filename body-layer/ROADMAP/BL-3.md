# BL-3 — World enrichment (= PB-3)

- [x] **BL-3 — World enrichment (= PB-3, done, merged 2026-09-10, `8df2791`).** #status/done
  `feature/bl3-world-enrichment`. Filled the four still-empty `describe_contact` fields
  (`position.confidence`, `relative_now`, `semantic`, `motion_when_seen`) without touching BL-2's
  contact/classification logic. New `belief/enrichment.py`: `SemanticFact` + a placeholder
  string→numeric confidence table, `semantic_facts_for` (one `query.describe_position` call per
  contact), `WorldEnrichmentCache` (keyed by `contact_id`, recomputes only when `last_position`
  changes), `relative_geometry`, `motion_when_seen` (direction from the two most recent distinct
  implied positions, unsmoothed). `geometry.py` gained `project_terrain_aware` (iterative
  fixed-point terrain-fit) alongside the existing `project_from_bearing_range`; gating is single-shot
  by default, iterative only when `range_m ≤ PROJECTION_ITERATIVE_RANGE_M` (placeholder `2000`) or
  `contact.attention == "watch"`. Fixture-tested only; no live sortie required by plan scope. DoD
  passed, zero required fixes. **Load-bearing placeholders inherited by BL-4**: the confidence
  table, unsmoothed motion derivation, position-keyed (not time-keyed) semantic cache staleness —
  first-guess constants, not tuned. Full history: `plans/bl3-world-enrichment/`.

