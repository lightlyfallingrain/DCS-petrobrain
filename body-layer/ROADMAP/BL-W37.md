# BL-W37 — Player bubble — 10 km computation-scope limit

- [x] **Player bubble — 10 km computation-scope limit on ground/air detection. DONE, merged
  2026-10-02. ACCEPTED by the user 2026-10-09** #status/done, in the strongest form this item can receive:

  > *"seems to work, though I can't verify by flying. Accepted."*

  **That caveat is the item's own design, not a gap in the acceptance.** Its DoD recorded *no live
  acceptance owed* as a deliberate waiver rather than deferred debt, because the bubble has **no
  in-cockpit observable**: `PLAYER_BUBBLE_RADIUS_M` (10 000 m) and `NAKED_EYE_RANGE_CAP_M` are the
  same distance today, so nothing the pilot can hear changes whether the bound is enforced early or
  late. The first moment it becomes observable is when the 9K113 sight's 20 km cone makes the two
  diverge. So "can't verify by flying" is the correct and permanent state of affairs until then, and
  accepting on that basis closes it honestly rather than leaving an entry open against a
  confirmation that cannot exist.
 `feature/player-bubble` (merge commit, see below), implementing `todo/todo.md`'s
  "Player bubble: 10 km, settled 2026-09-28" item — the user's own already-complete spec was the
  authoritative source, so no separate Architect `plan.md` was written for this one.
  `perception.association.filter_player_bubble()` (`PLAYER_BUBBLE_RADIUS_M`, 10 000 m, ownship-
  relative, omnidirectional, equal-to-radius kept), called by both `NakedEyePerceptionSource.poll()`
  and `HybridPerceptionSource.poll()` immediately after `filter_ownship()` — the earliest point
  either channel's own candidate pool becomes work. Kept structurally independent of
  `visibility.NAKED_EYE_RANGE_CAP_M` (two `dir()`-namespace tests guard against either module
  importing the other's constant by name — a value-equality test can't catch aliasing since both
  constants legitimately equal 10 000 today). Ground/air only; world-model geography/enrichment is
  untouched and has no seam into the bubble (`test_enrichment_module_never_references_the_player_
  bubble`); a contact that drifts outside the radius stays remembered, only detection *computation*
  stops (`test_contact_that_drifts_outside_the_bubble_is_not_forgotten`, real `ContactStore` across
  two polls). New `GateOutcome.PLAYER_BUBBLE` detection-trace row records what the bubble excluded;
  fixed a latent bug in `tools/summarize_detection_trace.py` the new outcome exposed (it would have
  misreported a bubble-dropped candidate as "cleared the cockpit mask"). Reviewer (full read,
  required fixes: none), Security (deep analysis, APPROVED — fails closed on `nan`-valued input,
  no belief-state path for the new trace row), and Performance (APPROVED — MONITOR) all signed off;
  1379 passed/4 xfailed (up from `main`'s 1367/4, +12 new tests, no regressions), `ruff`/`mypy
  --strict` clean.

  **Measured finding, recorded precisely so it isn't later over-cited**: the bubble excludes 76.6%
  of raw candidates in a real sortie trace, but the measured end-to-end saving is only ~1.4%
  (0.955 ms/tick) — both channels' own pre-existing range gates (`NAKED_EYE_RANGE_CAP_M` = 10 000 m,
  `associate()`'s `RANGE_CAP_M` = 5 000 m, stricter) already bounded LOS/association reachability
  at or below the bubble radius, so the expensive work those candidates would have reached was
  already unreachable before this feature existed. This is not a defect — the real payoff is
  structural and arrives once the 9K113 sight (20 km cone) makes the two constants diverge, which
  is exactly why keeping them independent mattered more than the number does today.

  **Milestone completion question**: does not change what's next. `BL-B23` (`ContactStore` never
  pruned) is queued next, and the same Performance review found the bubble does **not** reduce
  `ContactStore`'s accumulation rate today, for the identical gate-duplication reason — noted on
  `BL-B23` itself (`body-layer/BACKLOG.md`) so its future measurement doesn't assume a baseline
  change that didn't happen.

  **Acceptance boundary, stated plainly rather than deferred as debt**: this feature changes
  nothing a sortie can hear or see — no candidate that would have been admitted, spoken, or
  remembered before this branch is excluded now, and none that was excluded is now admitted
  (confirmed by the Performance measurement above, not assumed). **No live acceptance is owed, and
  this is a waiver, not deferred debt** — unlike the live-acceptance-debt list above, there is no
  in-cockpit observable here for a flight to confirm or refute. The condition that will create one
  is already named in the spec: the 9K113 sight's 20 km cone, which makes `PLAYER_BUBBLE_RADIUS_M`
  and `NAKED_EYE_RANGE_CAP_M` diverge and gives the bubble a real, flight-observable effect for the
  first time. Full DoD report: `plans/player-bubble/dod-check.md`.

