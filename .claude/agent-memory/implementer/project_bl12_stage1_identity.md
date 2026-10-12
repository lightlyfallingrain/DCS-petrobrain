---
name: bl12-stage1-identity
description: BL-12 Stage 1 (group identity survives member-id replacement) -- narrowing a store's public "current" view breaks fixtures that inject state directly and bypass the mechanism that maintains that view; grep for the bypass before trusting the plan's test-impact list.
metadata:
  type: project
---

BL-12 Stage 1 split `GroupStore`'s single `_groups` dict into a semantic distinction: `groups`
(currently observed -- a cluster matched it *this* reconcile) vs. `remembered_groups` (the full
retained set, including groups merely kept through the `GROUP_REIDENTIFY_WINDOW_S` expiry window).
`group_for_contact` was narrowed to read only `groups`, per the plan's own warning that this is
"the sharpest silent-failure surface."

**The transferable finding: narrowing a filtered "current" view breaks whatever bypasses the
mechanism that populates it.** `test_callouts.py::test_group_of_already_reported_and_merge_echo_
suppressed_members_is_silent` injects a hand-built `Group` directly into
`store._groups._groups[id] = group`, then polls in a loop that never calls `store.tick()` again --
so `GroupStore.reconcile` never re-examines it, and its `last_observed_sim` stays at the unset
default. Under the OLD (unfiltered) `.groups` property this was invisible; under the new
"currently observed only" semantics it correctly reads as *not* observed, and `store.groups[0]`
raised `IndexError`. This was **not named in the plan's test-impact list** (which was written for
Stages 2-3, not Stage 1) and not named in the task prompt either -- it surfaced only from
`grep -rn "_groups\._groups\[" tests/`, the direct-injection bypass pattern.

**How to apply:** whenever a change narrows what a store's existing public accessor returns (adds
a filter it didn't have before), grep for every place a test constructs the underlying object
directly and injects it into the store's private dict, bypassing the method that would normally
populate/validate it. Those are exactly the fixtures a filter change can silently break, and they
are invisible to a test-impact list built from reading the plan, because the plan describes the
*mechanism's* intended consumers, not test-only backdoors into private state. The fix in this case
was to read the correct accessor (`remembered_groups`, the unfiltered superset) rather than to
weaken the new filter -- the property the test actually cares about (never marked spoken) was
unaffected by which accessor read it.

See also [[bl12-stage0-cohesion]] (same role, same milestone, same general shape: a change that
narrows what a predicate/view includes finds its casualties in fixtures that depended on the old,
looser behaviour -- there it was a cohesion predicate producing fewer groups; here it is a store
accessor exposing fewer of them).
