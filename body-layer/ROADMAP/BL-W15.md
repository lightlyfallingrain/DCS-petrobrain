# BL-W15 — Object-permanence continuity

- [x] **Object-permanence continuity (no BL- number — a contact-memory refinement in the BL-2/2.6
  lineage; done, merged 2026-09-10, `c1af0e0`).** #status/done `fix/association-gate-ambiguity-runaway`. BL-2.6's
  symmetric-gate fix reopened a different bug: the wider gate now overlaps between genuinely
  distinct nearby real objects, and `ContactStore.ingest`'s "never guess-merge" rule had no bound on
  runaway spawning once that overlap fired (reproduced: 2 stationary objects ~874 m apart, 60 polls
  → 120 duplicate contacts). Scope grew mid-plan from "zero-gap continuity only" to full object
  *permanence*, per the user's framing: correlation now fires on any `object_id` match regardless of
  gap length, subject to a 600 s decay (`OBJECT_ID_MEMORY_S` = `IDENTITY_HALF_LIFE_S`,
  `object_id_continuity_valid`) — an expired match falls through to the ordinary spatial/class gate
  exactly like an unresolved one. `association_over_time`'s gate is now the *exception* path
  (founding observations, non-correlating reacquisitions, expired continuity), not the common case.
  Both perception sources are in scope (the scope/hybrid channel's earlier exclusion from `object_id`
  correlation no longer applies). **Live-verified**: masked-gap reacquisition (76 s behind terrain,
  correctly reacquired under the same contact id) and the original duplication scenario (mixed-unit
  cluster) no longer runs away. Full history: `plans/contact-duplication-ambiguity-runaway/`.

