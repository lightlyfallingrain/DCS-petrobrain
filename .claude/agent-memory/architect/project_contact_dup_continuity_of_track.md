---
name: contact-dup-continuity-of-track
description: Resolution of the BL-2.6 gate-widening vs never-guess-merge tradeoff via continuity-of-track
metadata:
  type: project
---

`plans/contact-duplication-ambiguity-runaway/plan.md` (2026-09-10) resolves a genuine
architectural tradeoff: BL-2.6's symmetric spatial-gate fix (7581928) necessarily widened
`spatial_gate_radius_m` enough that two real, moderately-separated objects (~874m) now overlap
gates, and `ContactStore.ingest`'s deliberate "two-or-more candidates → always new contact,
never guess-merge" policy (`plans/pb2-contact-memory/plan.md` Stage 1) has no self-limiting
mechanism once that fires — runaway one-contact-per-poll duplication.

**Chosen fix: continuity-of-track**, not gate re-tuning, not relaxing the ambiguity policy. Add
a `continues_observation_id: str | None` field on `Observation`/`Percept` — populated only by
`naked_eye_source.py`'s `_acquire_every_poll` when the same `object_id` (perception-internal
only, never serialized onward) appears in both the previous and current poll's visible set, with
no gap. `ContactStore.ingest` uses it to skip `passes_gate` entirely for that percept, merging
directly via an `observation_id -> contact` index — but only after a defense-in-depth
`class_compatibility` check (an incompatible class on a same-id claim falls back to the normal
gate path rather than trusting continuity blindly, since raw `object_id` stability is
high-confidence desk research, not a project-run live probe — see
`aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`).

**Boundary precedent set**: "never crossing into belief/" (the backlog item's phrasing,
`todo/todo.md`) cannot be taken literally — `belief/contacts.py` and `belief/percept.py` do
change. What actually stays true: `object_id` itself never leaves `perception/`; only an
already-legitimate field shape (`observation_id`, which `Percept` already carries as
bookkeeping, not a truth field) crosses. This is now the template for any future
perception-continuity work (e.g. extending continuity to `hybrid_source.py`, explicitly out of
scope for this fix since it has no per-object cross-poll state today).

**Residual, accepted risk**: two real nearby objects that both experience a genuine
*simultaneous* gap (masked then reappear same poll) still hit the untouched gate/ambiguity path
on reacquisition and could still reproduce the runaway shape. Deliberately not fixed — doing so
would mean touching the Stage 1 invariant. Revisit only if observed live.

See also [[project_bl2_contact_memory_design]] (the original Stage 1 invariant) and
[[project_bl26_classification_refinement]] (the 7581928 gate-widening fix this resolves the
fallout from).
