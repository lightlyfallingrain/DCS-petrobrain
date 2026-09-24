---
name: watch-reporting-stage1-5
description: watch-reporting full implementation (5 stages) — watched-only speech gating gotchas, follow-resolver ordering, and belief.threat design
metadata:
  type: project
---

Implemented all 5 stages of `plans/watch-reporting/plan.md` on `feature/watch-reporting` (body-layer
+ audio-adapter). Full details: `plans/watch-reporting/implementation.md`. Key non-obvious findings
worth remembering for future work in this area:

- **Any new "watched-only" event kind that renders via `_contact_report_text`'s `lead`/
  `event_clause` affixes must be added to `belief.callouts._WATCHED_ONLY_KINDS` for TWO reasons, not
  one**: (1) the obvious speech-layer/emission gating, and (2) forcing it to always be a singleton
  group in `group_candidates` — `render_group_report` has no concept of those affixes, so merging
  such a kind into a multi-contact group silently drops the fact the event exists to report. The
  plan's own prose only names reason (1); (2) was found during implementation, not specified.

- **Testing any watched-only kind against a real `ContactStore.tick()` needs "move the observer, not
  the target" fixtures.** Re-ingesting a new observation to simulate a contact moving a large
  distance gets rejected by the percept-gate (founds a second contact instead of updating the
  first), silently invalidating the test. Always found the contact once, then vary only the
  `ownship=` argument across successive `tick()` calls.

- **A new watched-only kind will very likely fire on the *same tick* as an existing one** (e.g.
  `CONTACT_RANGE_CROSSED` and `CONTACT_ENGAGEMENT_CHANGED` both fire when ownship closes distance in
  one jump) — since the scheduler speaks at most one per call and ties on identical priority tuples
  by insertion order, tests need a multi-tick fixture that drains each colliding kind on its own
  tick (via a throwaway `CalloutScheduler`) before the tick under test, or the assertion will pick up
  whichever kind happens to sort first rather than the one intended.

- **`belief.threat`'s class-level rollup (`perception.object_model.profile_for` joined against
  `threat_envelopes.json`'s `threat` names) only actually resolves ~3 of ~19 SAM/AAA rows on the
  real data** — `object_model`'s keyword table was authored against DCS names, not the Hoggit wiki's
  own naming, so most rows share no matching substring. Type-level lookup is unaffected (same table,
  direct match). Not a defect in the join *mechanism* (the plan explicitly forbids hand-writing a
  per-class number); the fix belongs in `object_model.py`'s keyword coverage, a different module.

- **A resolver's scoring weights need a self-consistency check, not just "pick reasonable numbers"**:
  for `_resolve_follow_target`, `W_FOLLOW_CLOCK * max_clock_delta` must exceed `FOLLOW_MATCH_FLOOR`
  or a clock-only mismatch can *never* be refused regardless of how wrong it is. Caught by a test
  built around the worst-case input, not an arbitrary one.

- **A new parsed "slot" family for a fuzzy verb (like `follow`'s descriptor/clock/range) must be
  tried *before* the generic phrase-table match, not after as a naive fallback** — a slot-bearing
  utterance can score deceptively well against an unrelated existing phrase that shares most of its
  words (here: `"follow two o'clock"` vs. `"report two o'clock"`/`"scan two o'clock"`, differing only
  in the verb). Gate the early slot-attempt on the verb itself fuzzy-matching the new verb, and let
  utterances that produce zero slots fall through unchanged.
