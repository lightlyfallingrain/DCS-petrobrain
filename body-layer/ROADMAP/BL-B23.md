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
  1379/4, +5 new tests), `ruff`/`mypy --strict` clean. [[BL-B24]] filed alongside (a pre-existing,
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

**Two records, both kept.** This entry file was created by the Stage 2 conversion from
`body-layer/ROADMAP.md`'s own `BL-B23` row (the block above). Stage 3 then converted
`body-layer/BACKLOG.md`, which carried its own `BL-B23` entry (the block below) — the backlog's
copy, written when the item was filed and updated when it was fixed. The two agree on every
fact: `[x]`, fixed on `fix/contact-store-pruning`, merged 2026-10-02, the same mechanism, and the
same 403 ms → 1.4 ms result. They are not duplicates to pick between, because each carries
material the other does not: the roadmap's copy has the sign-off trail, the acceptance-boundary
reasoning and the milestone-completion answer; the backlog's copy has the full pre-fix measurement
sweep, the fix-shape reasoning as it was written before the fix, and the player-bubble interaction
note. Both are reproduced verbatim rather than merged into a single paraphrase.

- [x] **BL-B23 — `ContactStore` is never pruned, so clustering cost grows with every contact ever
  seen.** #status/done Fixed `fix/contact-store-pruning` (2026-10-02, `plans/contact-store-pruning/
  implementation.md`): `ContactStore.tick`'s eighth block now filters its `reconcile` input to
  `belief.decay.certainty_of(contact, now_sim) != "lost"` — the existing lifecycle ladder, no new
  field — rather than passing the full historical `_contacts` set. `_contacts` itself is untouched
  (a `lost` contact stays full memory, still answerable by `describe_contact`); only clustering's
  input is filtered. Re-measured at the same scale sweep: `GroupStore.reconcile` alone still costs
  0.15-403 ms across 22-1200 *total* contacts (confirms the old number), but `ContactStore.tick()`
  end to end, given 20 live contacts plus up to 1200 total (the rest long-lost), now costs
  0.15-1.4 ms flat — clustering cost tracks the live picture, not sortie length. Found by the
  Performance Reviewer during the group-cohesion pass (2026-10-01), and
  **pre-existing** — `fix/group-undermerging` only added a few per-pair dict lookups on top of a
  growth path group-reporting Stage 2 already created. `ContactStore._contacts` has no delete path
  anywhere in the class, and `tick()` passes `list(self._contacts.values())` to
  `GroupStore.reconcile`, i.e. every contact ever folded rather than the live set. So
  `_cluster_contacts`'s O(n²) pairing scales with total-ever-seen, not with how many contacts are
  actually out there.

  Measured, same pass: 22 contacts 0.17 ms, 50 0.72 ms, 100 2.96 ms, 300 24.75 ms, 500 70 ms, 800
  180 ms, 1200 406 ms — clean quadratic from 100 up. Trivial today (the 2026-10-01 sortie had 22
  objects admitted), and the point is that it is **the sortie length that drives it, not the
  threat picture**: a 90-minute mission accumulating long-LOST records reaches the 70-180 ms band
  on a 5 Hz loop, where it starts costing the pilot latency.

  Fix shape: filter `reconcile`'s input by lifecycle or age before clustering, rather than pruning
  the store itself — a LOST contact is still memory Petrovich should have, so dropping the record
  is the wrong move; excluding it from *clustering* is the right one.

  **Player-bubble interaction (`plans/player-bubble/performance.md`, 2026-10-02, MONITOR):** the
  10 km player bubble filters the *candidate* pool, not admitted contacts, and nothing beyond
  `NAKED_EYE_RANGE_CAP_M` (10 km, same value as the bubble today) could ever have reached
  `ContactStore` before the bubble existed either — so the bubble **does not reduce the rate at
  which `ContactStore` accumulates**. Whoever measures this backlog item should not assume the
  bubble changed the baseline; it will only start doing so once `NAKED_EYE_RANGE_CAP_M` and
  `PLAYER_BUBBLE_RADIUS_M` diverge (9K113 sight).
