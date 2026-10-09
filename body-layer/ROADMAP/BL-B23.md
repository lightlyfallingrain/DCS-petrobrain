# BL-B23 — `ContactStore` never pruned

- [x] **BL-B23 — `ContactStore` never pruned, so clustering cost grew with every contact ever seen.
  DONE, merged 2026-10-02.** #status/done `fix/contact-store-pruning`. `ContactStore.tick`'s eighth block now
  filters `GroupStore.reconcile`'s input to `belief.decay.certainty_of(contact, now_sim) != "lost"`
  — reusing the existing lifecycle ladder, no new field. `_contacts` itself is untouched: nothing is
  deleted, a `lost` contact stays full memory and remains answerable via `describe_contact`. Fixes
  the total-ever-seen quadratic growth the Performance Reviewer found during the group-cohesion pass
  (2026-10-01): 403 ms -> 1.4 ms at 1200 total contacts (20 live, rest long-lost), independently
  reproduced by both Reviewer and Performance. Reviewer (full read, required fixes: none), Security
  (deep analysis, APPROVED — pure in-memory filter, no new narration path, memory invariant holds),
  and Performance (APPROVED — MONITOR) all signed off; 1384 passed/4 xfailed (up from `main`'s
  1379/4, +5 new tests), `ruff`/`mypy --strict` clean. `BL-B24` filed alongside (a pre-existing,
  unrelated `association_over_time` long-gap reacquisition ambiguity found while writing this fix's
  tests — see Backlog).

  **The fix is bounded, not complete, and that distinction matters for the next reader.** Performance
  confirmed the *total-ever-seen* axis is fixed, but the *live-count* axis is exactly as quadratic as
  before, by design — clustering's input is now the live set, and `_cluster_contacts` is still O(n²)
  over whatever it's given. Measured with all contacts simultaneously live: 20 -> 0.15 ms, 300 ->
  25 ms, 500 -> 70 ms (35% of a 200 ms 5 Hz tick budget). Performance deliberately kept this under
  the existing `group-cohesion-redesign` MONITOR finding rather than filing a new backlog item — it's
  the same risk that review already named, just confirmed to survive this fix unchanged — and framed
  whether a mission can realistically put 300-500 *simultaneously live* contacts inside the 10 km
  player bubble as a scenario-design question, not a code defect, today.

  **Acceptance boundary, stated plainly rather than left implicit**: every number above is a
  standalone microbenchmark against synthetic fixtures, independently reproduced three times
  (implementer, Reviewer, Performance) within single-digit-percent noise of each other and of the
  original group-cohesion-redesign measurement. That is exactly what a fixture can settle — "does
  clustering cost stop scaling with sortie length" is a closed, timing question with no cockpit
  observable, unlike e.g. the F10-vocabulary precedent where only a flight could reveal the wrong
  subsystem driving a command. **No dedicated acceptance card is warranted.** A long sortie already
  pending for the group-cohesion-redesign work exercises this same `tick`/`reconcile` path
  end-to-end and will confirm the fix incidentally; this rides along on that flight rather than
  generating its own. DoD report: `plans/contact-store-pruning/dod-check.md`.

  **Milestone completion question**: does not change what's next, and does not invalidate a
  downstream assumption. It does narrow the live-count MONITOR already on file: that risk is now
  confirmed to be exactly as large post-fix as pre-fix, so whoever next touches `group-cohesion-
  redesign`'s MONITOR item should treat BL-B23 as having tested, not changed, that number.

