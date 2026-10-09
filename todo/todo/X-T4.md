# X-T4 — Grouping is the priority — every unit gets its own callout

- [ ] **Grouping is the priority: every unit gets its own callout and it is far too much noise.** #status/open
  User's words: *"we badly need grouping, currently all units get single call outs and it's way too
  much noise. Fixing this is priority."* This is **[[X-B6]]** (`todo/backlog.md`), diagnosed
  2026-09-25 from a `--belief-truth-log` and never fixed — an outpost fragmenting into 18 contacts,
  the same *"ground, 11 o'clock, 1 kilometre"* heard four times. Full analysis:
  `plans/contact-fragmentation-at-range/debug.md`.

  **The diagnosis is counter-intuitive and worth not re-deriving**: it is not clustering (the
  contacts are founded across different polls, so per-poll clustering never sees them together) and
  the association gate is not too *tight* at range but too **loose** — `naked_eye_sigma_m` scales
  with range, so at 4 km the 3-sigma gate accepts a ~2.9 km down-range discrepancy, several
  existing contacts pass, `ingest`'s anti-guessing rule reads "2+ candidates" as ambiguous and
  founds a *new* contact, which makes the next look ambiguous against one more candidate. A
  recurrence of `plans/contact-duplication-ambiguity-runaway/`'s runaway with a new trigger.

  **CORRECTION, same day, from reading the actual log** (`plans/contact-fragmentation-at-range/
  2026-09-28-log-analysis.md`): **this is not X-B6.** The attribution above was made before anyone
  opened `~/dcs-belief-truth.jsonl` and it is wrong. In the longest run, **3 of 52 contacts were
  ever plural**, and two other runs had none at all — against 62 distinct real objects, which is
  close to 1:1 and the *opposite* of [[X-B6]]'s one-outpost-becomes-18 signature. Clustering and
  cardinality are working; they are correctly concluding that vehicles tens of metres apart at
  2 km are individually resolvable.

  The noise is the **callout policy**: one resolvable vehicle produces one callout, roughly one
  every eleven seconds for half an hour, and 4310 of 5996 belief rows sit at `PRESENCE`/
  `OP_GROUPSOMETHING`, so nearly every line is the same words. Speech-time aggregation exists
  (`belief.callouts.group_candidates`) but needs members pending *simultaneously* and sharing the
  same range *word* — detections trickle in one per poll, and `"2 kilometres"` versus
  `"2.5 kilometres"` are different buckets, so it almost never fires.

  So the lever is how long Petrovich waits before speaking and how coarse the buckets are, not the
  association gate. **[[X-B6]] stays open and unfixed** — a genuinely separate defect from a different
  sortie shape, whose 3 → 5 mitigation was never re-flown — but it is not what made this flight
  loud.

  **Needs the user's judgement before any plan**: what a crew member should *say* when sixteen
  individually-resolvable vehicles sit in one sector. The 2026-09-19 vocabulary decisions do not
  cover it — they assumed the plural case arrives as one plural contact, not as sixteen singular
  ones.
