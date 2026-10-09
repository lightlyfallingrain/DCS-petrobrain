# BL-B41 — Callout keeper elected per contact, suppressing per event

- [ ] **BL-B41 — The watched-group callout keeper is elected per *contact*, while what it suppresses
  is per *event*.** #status/open Found by review round 3 of `feature/sortie-refinements`, 2026-10-06, and
  reproduced independently by the main loop.

  `belief.speech.may_be_callout_keeper` picks one member of a group and `CalloutScheduler.tick`
  `_consumed`s the rest's `_WATCHED_ONLY_KINDS` events. When every member is watched and eligible
  **but the keeper happens to have no event of that kind this tick**, the peers' events are already
  consumed and the kind goes unreported for the group. Reproduced with three cohering watched members
  and motion events on the two non-keepers: nothing about movement spoken across three ticks.

  **Eligibility cannot close it** — a `(store, contact)` predicate cannot express a per-event
  question, which is why round 3's fix is correct within its remit. The answer is a **per-event
  election**.

  **Bounded, and narrower than either failure it sits between**: `CONTACT_RANGE_CROSSED`
  self-corrects when the keeper crosses the same kilometre mark a poll later, and where envelopes
  exist the widest-envelope member — the most dangerous, and the one most likely to emit
  `CONTACT_ENGAGEMENT_CHANGED` — is always the keeper, so engagement is largely self-protecting. It
  is strictly less bad than the flood it replaced (N lines per group) and than the round-2 silence it
  fixed (nothing at all, for any kind).

  **One refinement to the review's account, from the reproduction:** the observable is not
  necessarily silence. In a construction where all three members were newly watched, the group's own
  disclosure line fired for an unrelated reason, so what is actually lost is *that kind's content*,
  not every utterance. A triage reading "the group said something" is not evidence the motion report
  survived.

  **Do this together with the observability-gate interaction**, which needs the same redesign:
  `fix/callout-observability-gate` (merged, `24746f5`) skips an unobservable keeper with a bare
  `continue` while its peers are already consumed — the identical silence mode by a second trigger.
  Doing them apart means designing the per-event election twice.
