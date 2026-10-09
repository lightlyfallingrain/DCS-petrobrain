# BL-B24 — Ambiguous reacquisition candidates after a long gap

- [ ] **BL-B24 — Two close contacts can become ambiguous reacquisition candidates for each other
  after a long gap.** #status/open Found 2026-10-02 while fixing [[BL-B23]], **pre-existing and not introduced by
  it**; the Reviewer recommended filing it for discoverability rather than leaving it only in a
  plan's "Notable Discoveries" and two test docstrings.

  `association_over_time`'s gate inflates with elapsed time since a contact was last seen — correct
  in itself, since a unit unobserved for two minutes could genuinely have moved. But two contacts
  roughly 17 m apart, both reacquired in the same poll after a 120 s+ gap, each fall inside the
  other's inflated gate. The plain spatial gate then has two candidates for one observation, and
  `ingest`'s anti-guessing rule treats "2+ candidates" as ambiguous — the same shape as
  `plans/contact-duplication-ambiguity-runaway/`, with elapsed-time inflation as the trigger rather
  than range-scaled sigma.

  Real traffic routes around it: naked-eye and hybrid observations both carry
  `continues_observation_id`, which resolves the pairing without consulting the spatial gate, and
  [[BL-B23]]'s own tests use that path for the same reason. So this is reachable mainly where an
  observation arrives *without* a continuation id. Worth establishing when that actually happens
  before sizing a fix — if it never does in production, the honest outcome is a test and a comment,
  not a change to the gate.

  Note the existing lost-and-reacquired test only ever exercised a single contact, which is why
  this had no coverage until a two-contact fixture was written.

  **Still open after `fix/contact-report-flood` (2026-10-04).** That branch muted the *audible*
  symptom of the same underlying engine — `ContactStore.ingest`'s "2+ candidates → always found a
  new contact" rule — by suppressing the spoken first-report of a merge-echo. It did not touch the
  rule, and this item's own case (two close contacts ambiguous for each other after a long gap) is
  unaffected: suppression is scoped to `CONTACT_DETECTED` and never to `CONTACT_REACQUIRED`, which
  is the path this item is about. See `plans/contact-report-flood/plan.md`.

  **Still open after `fix/redundant-group-disclosure` (2026-10-05).** That branch silences a
  `Group`'s own *first disclosure* when every current member's content already reached the pilot —
  a third, speech-layer symptom of the same underlying ambiguity, one layer up from the merge-echo
  case above. It, too, leaves `ContactStore.ingest`'s root "2+ candidates → always a new contact"
  rule untouched: nothing about which `Contact` a percept resolves to changes, only whether a
  `Group`'s opening line repeats what a member's own events already said. This item's own case
  (ambiguous reacquisition for `CONTACT_REACQUIRED`) is unaffected either way. See
  `plans/redundant-group-disclosure/implementation.md`.
