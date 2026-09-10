---
name: project_object_permanence_continuity_review
description: Object-permanence continuity-of-track fix (fix/association-gate-ambiguity-runaway) reviewed APPROVED, 370 tests, no required fixes.
metadata:
  type: project
---

`ContactStore._resolve_continuity` (belief/contacts.py) now checks index resolution +
`decay.object_id_continuity_valid` + `class_compatibility` (all three) before skipping
`passes_gate` — verified as the only added path, no third code path, gate/ambiguity logic
byte-identical to pre-fix. `OBJECT_ID_MEMORY_S = IDENTITY_HALF_LIFE_S` (600s) is a literal reuse,
not re-derived. Both `naked_eye_source.py` and `hybrid_source.py` carry a persistent
(never-cleared, survives `world_objects is None`) `object_id -> last Observation.id` map — this
is the load-bearing state; if a future change resets either map per-poll it silently degrades
back to zero-gap-only behavior with no test failure elsewhere (only the multi-poll-gap tests in
test_naked_eye_source.py/test_hybrid_source.py would catch it).

**Why the debugger's exact repro numbers (874m/60-poll) couldn't be replayed**: with only 2
contacts in the store, the second founding percept always sees exactly 1 overlapping candidate
(clean merge, not ambiguity) — genuine ambiguity needs 2+ *existing* contacts already founded.
Re-trace test reused `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s
proven-ambiguous-midpoint geometry instead and chained 116 re-observations through it. This is a
faithful mechanism re-trace, not a weaker test — verified by reading that every re-observation
sits at the proven-ambiguous point (implementer's monkeypatch-disable-and-confirm-failure step
was scratch-only, never committed, so nothing to independently re-run).

**Why**: this is the third revision of the plan (zero-gap -> object permanence -> decay/expiry);
reviewing against an earlier revision would have missed the expiry requirement entirely.
**How to apply**: for any future body-layer plan with multiple dated revisions in one plan.md,
always confirm which revision's language ("Revision 2026-09-10 (second pass...)") governs
before checking code against it — grep for "Revision" headers first.
