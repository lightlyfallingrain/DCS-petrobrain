---
name: contact-report-flood-same-poll-trap
description: CalloutScheduler suppression checks must exclude same-poll peers, or mutually-close simultaneous foundings all silence each other
metadata:
  type: project
---

`plans/contact-report-flood/plan.md` Stage 1 added a `CONTACT_DETECTED` suppression in
`CalloutScheduler._render_event`: suppress a freshly-founded contact's line if any other, not-yet-
`lost`, `contacts_plausibly_same` contact already exists. Implemented exactly as specified, this
has a real failure mode found only by testing against the real `sortie-1004` snapshot (not caught
by any synthetic fixture, nor by the plan's own analysis): `CalloutScheduler.tick()`'s `for _,
candidate in scored` loop tries every scored candidate in priority order until one succeeds, but
if N contacts are founded in the *same poll* and are pairwise plausibly-same each other, all N
already exist by the time any of them is first attempted -- every one sees the other N-1 as live
peers and suppresses. Confirmed directly: `debug.md`'s own named six-vehicle cluster
(`CONTACT_3/4/5/7`, founded simultaneously, pairwise plausibly-same by their real recorded believed
positions) produces **zero** spoken lines under the literal plan, violating the plan's own "at most
2, not 6" bound on its own example.

Fix: add `other.first_seen_sim < this_contact.first_seen_sim` to the suppression condition. A
same-poll peer is a simultaneous, independent sighting, never a merge-echo of an abandoned identity
(the mechanism this check targets always has the abandoned identity surviving from a *strictly
earlier* poll) -- so excluding it costs nothing against the real mechanism while fixing the
regression. After the fix, two pre-existing fixtures that happened to found their contacts in one
same-poll `ingest()` call (`test_2c_transcript_fixture_renders_four_lines_not_seven`,
`test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken`) reverted to their exact
original behaviour -- no lasting edits needed to either.

**General lesson for any "does another live X already exist" suppression/dedup check scored once
per tick with "try candidates until one succeeds": always exclude peers from the *same batch/poll*
unless the mechanism being guarded against can actually originate within one batch.** A synthetic
test with two contacts founded on two *different* polls will never catch this -- it only shows up
when multiple real, same-poll candidates are mutually close, which a live sortie produces routinely
(several vehicles entering view in one scan) but a hand-picked fixture usually doesn't.

See [[feedback_decouple_fixtures_from_tuned_defaults]] for a related but distinct lesson (fixtures
vs. tuned thresholds); this one is about *batch/poll boundaries* in a scored-candidate scheduler.
