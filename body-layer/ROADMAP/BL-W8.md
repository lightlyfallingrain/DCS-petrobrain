# BL-W8 — Position-belief-runaway fix

- [x] **Position-belief-runaway fix — FLOWN AND CLOSED 2026-09-25** #status/done (user direction).
  `docs/acceptance/2026-09-25-position-belief-sortie.md` is closed. No range beyond the cap was
  reported back; the belief-truth log from the same sortie is what exposed the separate
  fragmentation defect instead. Merged 2026-09-25 (`bfbcf8d`).**
  (`fix/position-belief-runaway`, 2026-09-25). Corrects the range-runaway defect above (see the
  Status entry for the four fixes). Card: `docs/acceptance/2026-09-25-position-belief-sortie.md`
  — its own headline check (no naked-eye range beyond 10 km) is checkable by ear in one flight;
  whether the underlying believed position is now *correct*, not just *bounded*, and whether
  hold-recovery timing (~7-10 s predicted) matches a real sortie, are both harder to judge and the
  card says so explicitly. Clears when a real flight exercises it post-merge.


**Original entry, kept for the record (written before the flight closed above):**

- [x] **Position-belief-runaway fix — merged 2026-09-25 (merge `bfbcf8d`,
  `fix/position-belief-runaway`). Merged before flying, deliberately, so any correction the sortie
  produces lands on `main`; live acceptance remains outstanding.**
  (branch head was `0465290` at the DoD gate; plan/review paper trail:
  `plans/position-belief-runaway/`). Corrects a live defect the sortie the day after
  `precise-position-belief` merged actually found: `"couple contacts, 4 o'clock, 87.5
  kilometres"` against a 10 km naked-eye cap. Four distinct fixes under one report:

  1. **`FUSION_SANITY_SIGMA` residual guard in `fold_position`** — the root-cause fix for
     ill-conditioned triangulation (near-parallel disagreeing looks intersecting arbitrarily far
     from either input). Rejects a fused mean unless it sits within 5 sigma of at least one input's
     own covariance; holds the prior (inflated for elapsed motion) otherwise.
  2. **`clamp_to_detection_envelope`, a new function** — the gate that was entirely missing:
     nothing previously checked a fused position against what a channel could physically detect.
     This is the mechanism that actually caught the reported live defect (a slow directional drift,
     individually plausible at every step) — the ill-conditioning guard above addresses a real but
     separately-unreachable mechanism, since the pre-existing association gate already rejects a
     single large-residual jump before it reaches fusion. **This distinction — the user's own
     one-line diagnosis ("position uncertainty needs a gate, cannot be further than detection
     range") named the reachable path; the orchestrator's own ill-conditioning hypothesis, though
     real, did not** — see `NOTES.md`.
  3. **A scale-relative determinant floor** (`Covariance2D.inverse()`'s `_MIN_DETERMINANT_RATIO`,
     replacing an absolute `1e-9`) — found by Reviewer, not planned: the absolute floor was
     calibrated for covariance-scale determinants but silently corrupted the fused *mean* (not
     just reported uncertainty) for any same-bearing repeated naked-eye look beyond ~2.7 km, and
     made the new guard itself misfire on a legitimate residual. Required fix, re-reviewed
     APPROVED.
  4. **Hold-recovery timing decoupled from poll interval** (`PositionEstimate.fused_at_sim`/
     `fused_covariance`, new) — found by Security, not planned: a held position's elapsed-time
     inflation was compounding once per poll rather than once per real gap, so recovery time
     scaled as `O(1/poll_interval_s)` — ~47 s at the project's own 1.0 s default poll interval,
     not the ~20 s the merged review's approval had rested on (measured for a single-gap
     re-acquisition, not continuous disagreeing-look polling). Fixed by tracking "last genuinely
     fused" time separately from "last poll" time. Required fix, re-reviewed APPROVED.

  Also fixed: the doubled unit-type callout (`"truck ... is KrAZ truck"`, `belief/speech.py`'s
  `_identification_lead` stutter guard, an exact-string match that missed a class word appearing
  inside a longer type name) — an independent speech defect reported alongside the position bug,
  unrelated in mechanism.

  DoD gate run 2026-09-25: format/lint/type/test all green (1192 passed / 4 xfailed, +15 over
  main's 1177/4 — verified against an isolated `git archive` of the branch tip, not the working
  checkout, per the standing pytest/PYTHONPATH trap memory). Reviewer and Security both APPROVED
  after their respective required fixes were applied and re-reviewed. **Live acceptance
  outstanding** — card at `docs/acceptance/2026-09-25-position-belief-sortie.md`.

