---
name: mutate-the-assertion-not-just-the-accessor
description: When a store's filtered "current" view is narrowed and a direct-injection test fixture is fixed by switching to the unfiltered accessor, check whether the production code path under test still runs at all — not just whether the final assertion reads correctly.
metadata:
  type: feedback
---

BL-12 Stage 1 (`feature/bl12-group-contact-identity`) narrowed `GroupStore.groups` to mean
"currently observed" (matched by a real `reconcile` call this tick), replacing its old unfiltered
meaning. `test_callouts.py::test_group_of_already_reported_and_merge_echo_suppressed_members_is_silent`
injects a `Group` directly into `store._groups._groups[...]`, bypassing `reconcile` — so under the
new filter its `last_observed_sim` never matches `_last_reconciled_sim`, and the group vanishes from
`.groups`. The implementer fixed the resulting `IndexError` by reading `store.remembered_groups`
(the unfiltered superset) in the final assertion instead, reasoning that "the property the test
cares about was unaffected by which accessor read it."

**That reasoning checked the read side only.** `CalloutScheduler.tick`'s group-disclosure block —
the actual code this test exists to exercise — is `for belief_group in store.groups:`. With the
group invisible to `.groups`, that whole loop body (including the suppression check the test is
named for) never runs for it. Verified by mutation: replacing `_already_reported_member_ids` with
`return frozenset()` (which would defeat suppression if the loop ran) left the test green. The
rewritten test asserts something true, but for a reason that has nothing to do with the mechanism
under test — a comment, not a contract.

**How to apply:** whenever a fixture switches from a filtered accessor to the unfiltered one to
dodge a new narrowing, ask whether anything *inside production code* still reads the filtered
accessor on that same object — if so, check (by mutation, not by reading) whether the test still
exercises the logic gated behind that accessor, not just whether its final assertion is semantically
true. See also [[bl12-stage1-identity]] (implementer memory, same incident, read-side framing only)
and the reviewer role's standing instruction to verify absence-assertions by mutation rather than by
re-deriving the author's reasoning.
