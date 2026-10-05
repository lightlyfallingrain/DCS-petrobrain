---
name: keeper-eligibility-predicate
description: Electing a "keeper" and consuming its peers turns a flood into total silence unless keeper eligibility uses the exact predicate the consumer gates on
metadata:
  type: project
---

**A suppression that elects one survivor and discards the rest must elect the survivor using the
*same predicate the downstream consumer gates on*, or it converts a flood into total silence.**

`belief.callouts.tick` suppressed `_WATCHED_ONLY_KINDS` down to one keeper per group and
`_consumed`d the peers — but elected the keeper without checking whether the keeper was *watched*.
The filter's own not-watched check then dropped the keeper with a bare `continue` while the peers
were already gone, so nothing spoke for the group at all.

**Why:** the discard is irreversible (`_consumed`, not a deferring `continue`) while the gate after
it is not, so any gate the consumer applies *after* election is a silence trigger. Here the fix was
`belief.speech.may_be_callout_keeper`, evaluating `effective_attention(...) in ("watch",
"priority")` — literally the expression the filter gates on, so the two agree by construction rather
than by coincidence.

**How to apply:** whenever you write `peers.consume(); continue` around an elected winner, ask what
can still reject the winner downstream. If anything can, that condition belongs in the election.
Express eligibility as a **named predicate over one candidate**, not an inline condition: these
gates arrive one at a time (an observability gate was already in flight on a sibling branch,
reaching the identical dead end), and a predicate extends with `and <new>` in one place while an
inline condition grows a second special case beside the first.

Also: keep "is there still a group to speak for?" counted over **all** members, and eligibility
applied only to **who speaks**. Narrowing the coherence guard to eligible members only reintroduces
the flood for a watched pair inside a mostly-unwatched group.

Related: [[feedback_decouple_fixtures_from_tuned_defaults]],
[[feedback_test_pure_function_and_its_wiring_separately]].

**Corollary that cost a measured surprise:** tightening a function's contract broke two existing
*direct unit tests* of it that the review's impact list did not name, because their fixtures relied
on a field's default (`Contact.attention == "normal"`) that the new predicate now reads. A
contract-narrowing change's impact list is every test that constructs the input, not only the tests
that assert the behaviour — grep for callers of the function, not for the behaviour's name.
