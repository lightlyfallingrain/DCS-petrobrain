---
name: redundant-group-disclosure-approved
description: Group-first-disclosure silencing fix (callouts.py/speech.py) checked clean for omniscience, suppression-chain cycles, and per-tick cost
metadata:
  type: project
---

`fix/redundant-group-disclosure` (sha `fa59ef6`) silences a group's never-spoken first disclosure
when every current member's own content already reached the pilot (individually spoken, or
merge-echo-suppressed against an earlier live contact), and speaks only the unreported part
otherwise. Reviewed 2026-10-05, APPROVED.

Two things worth re-checking the same way on the next "speak less" fix in this area:

1. **Suppression-chain composition is per-member, not per-group.** The risk with composing two
   silencing mechanisms (yesterday's merge-echo `CONTACT_DETECTED` suppression + this one's
   "already reported" group gate) is a cycle where A silences B, B counts as reported, and a
   group {B, C} then silences C too by accident. It doesn't, because `_already_reported_member_ids`
   evaluates each member independently — C is only ever counted reported on its *own* history/
   echo status, never by virtue of being grouped with B. Confirmed by a direct test
   (`test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent`) built on the
   same fixture chain the flood fix used, not just by reading the code.
2. **The shared predicate was extracted, not duplicated.** `_is_merge_echo_of_earlier_contact` is
   now one function called from both `_render_event`'s `CONTACT_DETECTED` branch and the new
   `_already_reported_member_ids` — so the two can't silently drift apart. When two suppression
   mechanisms need the same condition, factoring it out this way is itself a security-positive
   move (removes a drift risk) rather than something to re-derive clean each time.

No new dependency. Cost is per-group-disclosure-candidate (two call sites, both per-candidate not
per-tick), same shape already priced for the flood fix's own O(n)-per-event check — no set
persists across ticks.

See [[project_contact_report_flood_class_gate_permissive_by_design]] for the predecessor fix this
one composes with, and [[project_bl_b23_memory_vs_clustering_filter_pattern]] for the general
"does a filter feeding a downstream consumer create a silent-starvation path" check this reuses.
