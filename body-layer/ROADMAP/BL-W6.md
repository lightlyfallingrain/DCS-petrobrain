# BL-W6 — Sortie 2026-09-26 fixes (Fix A/B1/B2/C)

- [x] **`sortie-2026-09-26-fixes` (Fix A/B1/B2/C) — merged, DoD PASSED on fixtures/console only,
  not yet flown.** #status/done #needs-flight All three fixes have real in-cockpit observables and this is deliberately
  *deferred*, not waived — the plan and DoD gate both treat a flown sortie as needed, not optional
  (unlike e.g. BL-3, waived by its own plan). Card: see the acceptance card DoD published for this
  branch. What it should clear: (1) crossing/motion callouts stop for contacts behind the cockpit
  mask or briefly occluded beyond the grace window, without regressing the already-fixed
  "sounds like a fresh sighting" wording; (2) binoculars actually get used on a watched/orbited
  contact held at constant range, not just a closing one; (3) an unrecognised utterance no longer
  interrupts an in-progress look, and `follow <target>` on the already-glassed target does not
  lower and re-raise. Sector coverage (Decision 2a, see Backlog below) is explicitly **not** in
  this branch — "all ten units to my left get identified" is still expected to fail and must not
  be read as a regression of this fix. `CALLOUT_OBSERVABILITY_GRACE_S` (10.0s) and
  `OPTIC_RETRY_INTERVAL_S` (~64s) are both starting values pending this sortie's feedback, not
  measurements — the card's own commands were run and their output verified before publishing, not
  written from reading the code (DoD role requirement).

