---
name: divides-between-and-group-tick-multiplicity
description: divides_between cost is bounded and cheap even under synthetic pathological fragmentation; CalloutScheduler.tick's real cost multiplier is calling _group_member_facts up to 3x/group/tick regardless of change.
metadata:
  type: project
---

Measured 2026-10-05 against `feature/terrain-callout-stages-345` (tip `3a9acf8`), real store
`world-model/data/world-model/syria-full.sqlite` (234,799 rows, 122,567 ridge).

`world-model/src/query/divides.py:divides_between` (new in terrain-feature-probing Rev3 Stage
1-2): real-store corridor cost 0.02-0.11 ms (5-10 km corridor, densest real cells). Synthetic
pathological-fragmentation microbenchmark (bypassing SQL, feeding `features_in_bbox` fake
fragments directly) confirms the intersection+dedup loop is linear in candidate count: 0.01 ms
at 10 fragments, 5.35 ms at 5000 — and 5000 fragments/5km corridor is ~170x denser than the
densest real measurement (6 ridge features/1km cell, max 51 vertices/feature, p99 19). Bounded by
corridor bbox area via the `feature_bbox` R*Tree index, not by theatre size. No credible risk;
Security's deferred "pathologically fragmented crest" concern is answered by this bound.

The real per-tick cost risk in this area is NOT `divides_between` itself but
`body-layer/src/belief/callouts.py:CalloutScheduler.tick`'s pre-existing (group-reporting Stage 4)
shape: it calls `speech.py:_group_member_facts` (one `describe_contact`/`divides_between` call per
group member) up to 3x per group per tick -- scoring gather, candidate re-render gather,
`group_membership_state`'s own re-gather for the winner -- regardless of whether the group's
content actually changed (the content-signature "nothing changed, skip" check happens *after* the
full gather, not before). Each terrain-feature-probing Stage adds one more SQL query to every one
of those redundant gathers. Not a new defect introduced by terrain work, but terrain work makes
each redundant gather measurably pricier. Flagged LATER/escalate-to-Architect, not blocking --
see [[project_contact_store_never_pruned]] and [[project_group_reporting_cohesion_scale]] for the
related pre-existing group/contact-store cost patterns this compounds with.

Also confirmed: `get_contacts()` (iterates the whole never-pruned `store.contacts`) is NOT on the
5Hz hot path -- it's only called from `crew_console.py`'s player-triggered F10/speech-command
handlers (nearest-contact, follow-target resolver, sector "report"), not from
`CalloutScheduler.tick`. Worth re-checking this boundary if `tick()` is ever refactored to call
`get_contacts` directly.
