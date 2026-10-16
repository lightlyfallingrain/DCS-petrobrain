# BL-W31 — Repetition is better but not gone

- [x] **Repetition is better but not gone — CLOSED 2026-10-16, superseded by `[[X-T4]]`'s contacts
  callout.** #status/done

  **User direction:** *"BL-W31 -> close as fixed by other items."* Closing it as he asked, with one
  correction to the wording that matters for whoever reads this next: **the shipped code does not
  yet fix the run below.** What has happened is that the fix moved to a better place and a settled
  design, so tracking it here would be tracking it twice.

  **Where it went.** `[[X-T4]]`'s contacts callout (`plans/contacts-callout/plan.md`, Architect-
  passed and merged 2026-10-16, implementation not started) is **exactly** this entry's own first
  candidate rule — *"widen aggregation to a range band at presence level only"* — generalised and
  settled with the user: one line per clock hour, the hedge register for the count, classes as an
  array, range as whatever span that hour covers, delta-only cadence. The five-call run below
  collapses to *"several contacts, 12 o'clock, 2.5 to 4.5 kilometres"* and then silence.

  **Two things that genuinely did ship and reduce it**, so the closure is not purely forward-
  looking: merge-echo suppression (`[[BL-W1]]`, flown and passed 2026-10-05) silenced 17 of 34
  contact foundings on its own sortie, and the group-disclosure delta stopped groups restating known
  members. Neither addresses the presence-level range-bucket case, which is why this entry stayed
  open after both.

  **The relevant history, since it is the reason not to re-diagnose:** the push path's
  report-space aggregation (`belief.callouts.group_candidates`) was **deleted** by group reporting's
  Stage 4, so today every ungrouped contact speaks its own line and there is no aggregation left to
  widen. `[[X-T4]]` replaces that role with a coarser key rather than reviving it. Original entry
  follows.

- [>] **(original, superseded)** Repetition is better but not gone — reopened 2026-09-23 from the sortie. Aggregation
  works on same-type, same-range, adjacent-clock contacts, and the transcript shows it firing. What
  it does not catch is the run it left behind:

  ```
  ground, 12 o'clock, 2.5 kilometres.
  ground, 12 o'clock, 4.5 kilometres.
  ground, 12 o'clock, 3 kilometres.
  ground, 12 o'clock, 4 kilometres.
  ground, 12 o'clock, 4 kilometres.
  ```

  Five presence-level calls in one sector within one scan, differing only in range, two of them
  identical. They are not aggregated because the range differs, and the range is precisely the part
  that carries no information at presence level — *"ground, 12 o'clock"* five times is one fact.
  Two candidate rules, not yet chosen: widen aggregation to a range *band* at presence level only,
  or suppress re-reporting a contact already called within some window. The second is probably the
  real one, since the identical repeat suggests the same contact was called twice.

