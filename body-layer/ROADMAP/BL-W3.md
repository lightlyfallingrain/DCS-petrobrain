# BL-W3 — Sortie refinements (2026-10-05 debrief, items 2/3/4)

- [~] **`feature/sortie-refinements` (sortie 2026-10-05 debrief, items 2/3/4) — DoD PASSED on
  fixtures and bench probes 2026-10-06, unflown; not yet merged at DoD time.** #status/in-progress Three pilot-reported
  refinements, each independently motivated by the 2026-10-05 debrief: (2) **`describe` is now a
  voice synonym for `report`** — `"describe"`/`"describe contacts"` added to
  `PHRASES["report_all"]` in `audio-adapter`, which is the exact phrase the pilot spoke at t_sim 258
  and that fell through unrecognised; (3) **`follow`/`watch nearest` tags every member of the
  resolved contact's `belief.groups.Group` watched**, once and statically (user: *"Tag once,
  static."*), with a new `render_watch_group_readback` speaking the count — **the count actually
  marked, not the intended one**, so a group that lost members since its last reconcile falls back
  to the single-contact wording rather than overstating (Security's one required fix); (4)
  **`scan ahead` sweeps `11, 12, 1`** instead of a static `(12,)`, one clock hour at a time at 2.0 s
  dwell — a 6 s revisit per hour, with the gaze cone unchanged at ±15° and the DCS LOS query cone
  untouched (the user's own load-bearing correction: *"still one clock hour at a time"*).
  Reviewer APPROVED then two further rounds; Security APPROVED WITH REQUIRED FIXES (one, fixed);
  Performance a change request (watch-tagging multiplied `describe_position` by group size — ~820 ms
  added to one tick — fixed by speaking one watched-only line per group rather than one per member)
  plus two MONITOR items. **The one performance item carried forward unfixed, deliberately:** a
  commanded `scan ahead` now pushes `look_direction` on ~66% of polls instead of ~1%, which does not
  change per-poll CPU but makes `aircraft_client`'s 2.0 s HTTP timeout tail reachable ~66× more
  often; bounded because free scan already pushes on ~50% and the 2026-10-05 timings were taken
  under free scan. **Known limitation shipped knowingly: `BL-B41`** — the watched-group callout
  keeper is elected per *contact* while the suppression is per *event*, so a watched group whose
  keeper has no event of a given kind that tick loses that kind's report. Eligibility cannot close
  it (a `(store, contact)` predicate cannot answer a per-event question); the fix is a per-event
  election, filed together with the merged observability gate's identical silence mode because they
  need the same redesign. **For debrief triage: the observable is not silence** — the group's own
  disclosure line may still fire for an unrelated reason, so "the group said something" is not
  evidence the movement report survived. Acceptance card:
  `docs/acceptance/2026-10-06-sortie-refinements-sortie.md`, published as
  https://claude.ai/artifact/RueFQ6R3BZB7vZgfEugorQ. Full record:
  `plans/sortie-2026-10-05-refinements/{plan.md, implementation.md, review.md, review-round2.md,
  review-round3.md, security-review.md, performance-review.md, dod-check.md}`. **Batches onto one
  sortie with the two other 2026-10-06 cards** (`2026-10-06-callout-observability-sortie.md`,
  `2026-10-06-bl11-tick-cost-sortie.md`) — all three change what the pilot hears in the same
  cockpit, so one flight settles them; fly merged `main` rather than this branch, which predates
  both.

  **Milestone completion question**: does not change what the next milestone should be. It does
  **sharpen one downstream assumption**: `BL-B41` and the merged observability gate's matching
  silence mode are **one** piece of work, not two — both are the per-contact-vs-per-event
  granularity mismatch in the same election, and designing them separately means designing the
  per-event election twice. They are filed together on `BL-B41` for that reason. Nothing else
  downstream is invalidated: items 2 and 4 are self-contained table/constant changes, and item 3
  adds no new state.

