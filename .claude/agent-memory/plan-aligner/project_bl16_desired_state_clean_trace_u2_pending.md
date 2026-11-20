---
name: project-bl16-desired-state-clean-trace-u2-pending
description: BL-16 flight-desired-state plan traced cleanly against all of E1-E10/C1/C3/Q1-Q6 and the mode-2-is-Mi-24-only seam; E9's full force rides on U2, still open, which the plan names itself
metadata:
  type: project
---

Plan check on `plans/flight-desired-state/plan.md` (one desired flight state, one mode authority,
BL-16): every expectation in the goal check traced to a named section/stage, no missing or
contradicted rows. Verdict ALIGNED.

**Why this one was easy:** the architect's own "Expectation trace (alignment.md)" section restated
E1–E10 against the same stages independently of my own trace, and the two agreed line for line —
same shape as [[project_bl16_mode1_u5_u10_amendment_clean]] (a plan that does the aligner's own
cross-check is not itself a finding, it's evidence the design was actually worked through).

**The one thing worth flagging without changing the verdict:** E9 ("the pilot must never see one
value held without being told") is split into two halves — the readback mechanism (`m2_flown`,
built, met) and whether Petrovich *speaks* when a value is silently reclamped across a mode change
(U2, an open decision in the same plan, recommended "yes"). The plan names this itself
("E9 → `m2_flown` readback, plus U2"), so it is not a silent drop — but if U2 comes back "no"
instead of the architect's recommendation, E9 would flip from `met` to `contradicted` for exactly
that case. **Check an E whose trace cites an open `U<n>` as part of its own row**: confirm which
way the recommendation points relative to the E's wording, and say in the report that the
verdict depends on which way the user answers it, so a later pass (or the user) doesn't read `met`
as unconditional.

Also useful as a calibration case for `docs/BEHAVIOUR_ALIGNMENT.md`: the heading-reference risk
(U3, mode 1 true heading vs. likely-magnetic HSI/overlay course) was flagged by `architect`
memory ([[project_heading_reference_true_vs_hsi_unsettled]]) before this plan, and the plan both
named it as a Risk *and* put the check on Stage 1's test card — the same "named, explained, and
on the card" pattern that separates a disclosed exception from a Finding.
