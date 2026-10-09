# X-B6 — An outpost fragments into 18 contacts at range

- [ ] **X-B6 — An outpost fragments into 18 contacts at range — diagnosed, not fixed.** #status/open Found in a real
  sortie 2026-09-25 from `--belief-truth-log`; full analysis in
  `plans/contact-fragmentation-at-range/debug.md`. The user heard the same callout four times
  (*"ground, 11 o'clock, 1 kilometre."*) and asked why they did not collapse into a group.

  **It is not clustering** — the contacts were founded across ten different polls, so per-poll
  clustering never saw them together. It is association over time, and it is a **recurrence of
  `plans/contact-duplication-ambiguity-runaway/`'s runaway with a new trigger**.

  The counter-intuitive part, and the reason it took a log to see: the association gate is not too
  *tight* at range, it is too **loose**. `naked_eye_sigma_m` scales with range, so at 4 km the
  3-sigma gate accepts a 2.9 km down-range discrepancy. In a dense outpost several existing
  contacts therefore pass, `ingest`'s deliberate anti-guessing rule reads "2+ candidates" as
  ambiguous and founds a *new* contact, and that new contact makes the next look ambiguous against
  one more candidate. Object-permanence continuity is the existing protection and still correct,
  but it needs stable cluster membership, which a sweeping gaze, a marginal gate and
  `NAKED_EYE_MAX_NEW_GROUPS_PER_POLL = 3` all churn.

  Four directions are listed in the debug note, none chosen — the anti-guessing rule is
  load-bearing and this needs a decision rather than a patch. Note also that contacts drift between
  real objects over a sortie, so any fix validated against the belief-truth join must account for
  the join re-resolving, or it measures itself.
