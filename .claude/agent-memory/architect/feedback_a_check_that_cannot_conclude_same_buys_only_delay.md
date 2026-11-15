---
name: a-check-that-cannot-conclude-same-buys-only-delay
description: Before designing a "hold the callout until a verification look" feature, enumerate the verdicts the look can honestly reach -- if every reachable verdict produces the same pilot-audible outcome, the look and hold buy only delay (BL-B110, 2026-11-01)
metadata:
  type: feedback
---

When a design holds an output until a check resolves, first list the verdicts the check can
**honestly** reach with what Petrovich can perceive, and what the pilot hears for each. If every
reachable verdict produces the same audible result, the check plus hold is pure latency.

**Why:** BL-B110 (expected-area check). The look at a remembered group A's expected area can only
conclude "A seen there -> B different" or "couldn't tell -> B new (user Q3)". Both call B out as
new. "A's area seen empty -> B is A" needs knowing the empty patch of ground was *visible*. Nothing
in body-layer answers that: DCS LOS is per-object (the Hook), world-model LOS is testing-only by
user direction 2026-10-05, and the forest model covers trees only. So the expensive part of the
feature was a terrain-visibility source, not the look. The cheap part ("never fold an ambiguous
memory-only match, found B new") delivered most of the pilot value. A 200-realisation probe on
BL-B108's sweep harness showed it, and the plan was staged on it.

**How to apply:**
- For any "verify before speaking" design, write the verdict -> pilot-hears table first.
- Absence-of-detection evidence needs a visibility source for an *empty* place. Check one exists
  before planning a verdict that rests on absence.
- Measure the cheap variant on the existing harness before planning the expensive one. See
  [[noise-field-sweeps-need-an-ensemble]] and [[project-correlated-range-error-gate-and-fold]].
- Also from this pass: `body.py` passed `SCAN_CYCLE_PERIOD_S` unconditionally to
  `optic_policy.decide`. A docstring claim ("commanded sectors bring binoculars round faster") had
  been unit-tested at `decide` level and never wired. Read the call site, not the docstring.
