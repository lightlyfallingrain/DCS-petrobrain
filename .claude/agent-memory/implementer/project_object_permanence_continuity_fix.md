---
name: object-permanence-continuity-fix
description: Implementation notes for the object_id continuity fix to the association-gate ambiguity runaway (fix/association-gate-ambiguity-runaway branch)
metadata:
  type: project
---

Implemented `plans/contact-duplication-ambiguity-runaway/plan.md` in full (7 commits): a
persistent, never-cleared `object_id -> last Observation.id` map in both `naked_eye_source.py`
and `hybrid_source.py` (hybrid was a scope reversal from the plan's earlier draft), a
`continues_observation_id` field threaded through `Observation`/`Percept`, a
`belief/decay.OBJECT_ID_MEMORY_S`/`object_id_continuity_valid` expiry check, and
`ContactStore.ingest`'s new `_resolve_continuity` shortcut that skips `passes_gate` entirely
when continuity resolves and hasn't expired.

Key discovery: **two objects with genuinely overlapping founding-poll gates merge cleanly, they
do not ambiguously spawn.** Stage 1's decision rule only fires "two-or-more candidates -> new
contact" when 2+ *existing* contacts both pass the gate — a second object's very first percept
sees only one existing contact (the first object's), so it's a clean one-candidate merge, not an
ambiguity. The debugger's live reproduction (`debug.md`, 874m separation, random-sweep numbers)
must have relied on quantisation noise causing early percepts to sometimes miss each other's gate
(founding two separate contacts) before a later percept fell into both simultaneously. Could not
be reproduced byte-for-byte from debug.md's summary alone — see
[[feedback_verify_mission_probe_pattern_claims]] for the general principle this is an instance
of (a plan's/report's prose isn't proof of the underlying mechanism's exact trigger conditions).
Fixed by reusing `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s own
already-verified overlapping-gate geometry (founds 2 separate contacts explicitly, then proves a
midpoint percept is genuinely ambiguous) and re-observing both objects at that midpoint via
`continues_observation_id` chaining for 58 more polls with a mid-session gap.

Verified the re-trace test actually exercises the fix (not vacuous) by temporarily monkeypatching
`ContactStore._resolve_continuity` to return `None` and confirming the test then fails —
recommend this "verify by disabling the fix" step whenever a regression test's own mechanism is
this indirect.
