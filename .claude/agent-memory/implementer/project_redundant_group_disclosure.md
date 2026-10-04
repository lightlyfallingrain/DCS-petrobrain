---
name: redundant-group-disclosure
description: Group's first-disclosure redundancy fix -- where "already reported" state lives and a real test the change broke.
metadata:
  type: project
---

`fix/redundant-group-disclosure` (2026-10-05) added `render_group_disclosure`'s
`already_reported_contact_ids` keyword param (default `None` = old always-full behaviour) and
`CalloutScheduler._already_reported_member_ids`, which answers "already reported" from state the
scheduler already owns: `_last_spoken_signature` (own CONTACT_DETECTED/REACQUIRED spoken) plus the
same `contacts_plausibly_same`/`first_seen_sim`/`certainty_of` condition the merge-echo check
(`plans/contact-report-flood`) already uses for a merge-echo-suppressed member. No new field on
`Contact`/`Group` -- the fact is about what the scheduler said, not about belief state.

**This broke a real, named-correct test**: `test_2c_transcript_fixture_renders_four_lines_not_seven`
expected a 5-member group's full disclosure "Three infantry, BTR-70 and truck..." even though one
member had already been individually spoken. The fix correctly shortened it to "BTR-70 and truck,
in 1 o'clock group." -- this was the fix working as intended on a *second*, pre-existing redundant
case the plan never named, not a regression. Updated the test rather than working around it, with a
docstring explaining why. [[verify_rebuild_row_counts]]-style lesson: always grep the whole test
suite for the modules you touch, even ones the task didn't name -- `belief.groups`' cohesion gate
is measurably tighter than `belief.association_over_time`'s contact-founding gate, so two contacts
500m apart (inside the founding gate) never cohere into a Group via `reconcile()` on their own;
tests needing a 2-member group at that spacing must construct the `Group` directly.

`sortie-1004` snapshot's `belief-truth.jsonl` logs contact rows only when state changes, not a full
per-tick snapshot -- several group-disclosure instants have 0 or 1 contact rows logged at the exact
t_sim, making precise group-membership reconstruction for *every* group line infeasible from this
data alone. Only the task-named 730.9 line was independently confirmed (via the task's own given
object-id evidence); a second (1021.9) was flagged as "strongly suspected, not confirmed" from
adjacent near-identical individual-line wording. Honest partial measurement, labeled as such, beat
forcing false precision.
