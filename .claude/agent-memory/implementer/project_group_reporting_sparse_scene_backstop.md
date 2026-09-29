---
name: group-reporting-sparse-scene-backstop
description: n=2 cohesion tautology fix in belief.groups; two lookalike test workarounds resolved oppositely
metadata:
  type: project
---

`belief.groups._cluster_contacts`'s relative-gap cohesion (median nearest-neighbour gap × ratio)
is mathematically tautological at exactly two tracked contacts total: with only two points, each
is the other's sole candidate neighbour, so the median always equals their own separation and the
threshold is always some multiple of the very distance being tested. Fixed by capping the
threshold at `GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M` (300.0 m, stated assumption) whenever
`len(contacts) < 3` (the whole tracked set, not the candidate cluster size) — at 3+ tracked
contacts at least one point's nearest-neighbour distance comes from a genuinely different pair, so
the median is not self-referential and the fix must not touch that case.

**Two `store._groups._groups = {}` test workarounds that looked identical resolved oppositely**,
and only instrumenting the actual fixture caught it:
- `test_crew_console.py`'s `_observation_at` derives `Contact.position` from
  `ownship_x`/`ownship_z` via an identity terrain-projection stub — two different ownship
  positions really do produce two distant contacts, so the backstop fix legitimately un-groups
  them and the workaround could be removed.
- `test_callouts.py`'s `_observation` looks parallel (`dwp_x`/`dwp_z` "50 km apart") but those
  fields drive spatial-gate matching only; `Contact.position` there comes from
  `bearing_deg`/`range_m` against `ownship_at_observation`, which two observations can share even
  with wildly different `dwp_x`/`dwp_z` — so that pair is actually co-located (same fused
  position) and legitimately coheres. Removing its workaround broke the test. Lesson: when two
  fixtures use different helper functions with similarly-named position-driving parameters, don't
  assume the parameter that reads like "world position" actually is one — print/instrument
  `Contact.position` directly before trusting a docstring's claim about what drives it.

See [[feedback_verify_rebuild_row_counts]] and [[feedback_verify_state_not_the_account_of_it]]-style
lesson: verify by running, not by pattern-matching two similar-looking test comments.
