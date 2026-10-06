---
name: keeper-election-per-contact-vs-per-event
description: A "elect one survivor, consume the peers" filter goes silent whenever the elected member has no event — check the election's granularity against the drop reasons', not just its predicate
metadata:
  type: project
---

`belief.callouts.tick`'s `_WATCHED_ONLY_KINDS` suppression elects one keeper per **group** and
permanently `_consumed`s the peers. Review rounds 2 and 3 each found a silence bug in it, and both
have the same root cause: **the election is per-contact and per-group, while every reason the filter
drops an event is per-event.**

- Round 2: keeper elected without checking whether it was *watched* → filter dropped the keeper,
  peers already consumed, nothing spoke. Fixed by `may_be_callout_keeper` (a `(store, contact)`
  predicate).
- Round 3 (mine): keeper watched **and** eligible, but simply has **no event of that kind this
  tick** → same total silence. The predicate cannot close this: "does this contact have an event?"
  is not expressible in `(store, contact)`.
- Post-merge with `fix/callout-observability-gate`: an *unobservable* keeper → same silence again.
  And `and observable` **cannot** go in the predicate either — `callout_observable` needs `now_sim`,
  and the gate's exemption is `event.kind in _OBSERVABILITY_EXEMPT_KINDS and event.engaged is True`,
  per-event.

**How to apply.** Whenever a filter elects a survivor and irreversibly discards its peers, do not
stop at "does the election use the same predicate the consumer gates on?" (round 2's question, and a
good one). Also ask **"can the elected survivor fail to produce output for a reason the election
cannot see?"** If the drop reasons are per-event and the election is per-contact, there is a silence
bug, and no amount of predicate-strengthening removes it — the election itself has to move to the
finer granularity.

Corollary worth keeping: a docstring that names itself as "the single place X is decided" and says
"extend this predicate rather than adding a gate beside it" is a **claim to verify**, not guidance to
accept. Here it was wrong for the one gate it named by signature alone. See
[[feedback_rendered_english_assertions_too_weak]] for the sibling habit of reading a claim literally.

Proving it took one probe: build the group, give the peers an event and the keeper none, tick a
`CalloutScheduler` three times, read `spoken == []`. Reading the filter loop did not reveal it —
the `_consumed.add` looks locally correct, because it is.
