---
name: project-association-gate-fragility
description: belief/association_over_time.py's spatial gate is a live trade-off zone -- widening it to fix one bug reliably reopens duplicate-contact risk from another angle
metadata:
  type: project
---

`body-layer/src/belief/association_over_time.py`'s `spatial_gate_radius_m` and
`belief/contacts.py`'s `ContactStore.ingest` "two-or-more candidates -> always spawn a new
contact, never a best-match merge" policy are in permanent tension:

- **Too narrow a gate** -> a single real object's own bucket-requantisation jitter (naked-eye's
  clock/range buckets re-anchor to current ownship heading every poll) misses its own prior
  contact and spawns a duplicate. Fixed once (commit `7581928`, 2026-09-09/10,
  `plans/classification-refinement/debug.md`) by summing both the incoming percept's and the
  contact's own stored uncertainty.
- **Too wide a gate** (which the above fix necessarily produces -- summing both sides roughly
  doubles it) -> any two *distinct* real objects within about a kilometer of each other (a common
  DCS multi-unit spacing: convoys, escorted vehicles, dismounted infantry near their carrier) have
  overlapping gates from the first poll. Because `ContactStore.ingest`'s ambiguity rule never
  prunes or merges once ambiguity fires, this becomes an *unbounded* runaway -- one new contact
  per percept, forever, for the rest of the session, not a one-time miscount. Found live during
  BL-5a acceptance testing (2026-09-10), `plans/contact-duplication-ambiguity-runaway/debug.md`.
  This second failure mode was explicitly flagged as an unaddressed risk in
  `plans/classification-refinement/review.md` at the time of the first fix, and was never
  mitigated.

**Neither direction has a mechanical/local fix.** Shrinking the gate reopens the first bug;
making the ambiguity policy self-limiting changes a deliberately-designed invariant
(`plans/pb2-contact-memory/plan.md` Stage 1's "never a guessed merge" decision). Any future work
touching this gate's sizing, or `ContactStore.ingest`'s decision rule, needs Architect-level
design first, not a Debugger patch -- see [[feedback_escalate_gate_policy_changes]].

**Test coverage gap worth closing whenever this is finally addressed**: existing tests
(`test_two_well_separated_objects_produce_two_contacts`,
`test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`) only check a single poll or
extreme separation. Nothing drives *multiple* polls with two *moderately* (a few hundred to ~1km)
separated real objects the way
`test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` does for one object --
that's the shape of test that would have caught the second failure mode.
