---
name: decision-quoted-figure-stale-vs-shipped-code
description: when a user's answered decision was made against an architect-prototype measurement range, re-measure the shipped code's own numbers before treating the decision as settled -- the shipped figure can be materially worse than what was quoted, even when the model is honest and the test fence is correct
metadata:
  type: feedback
---

Found reviewing `BL-B108` (`relative-distance-grouping`) round 3, the amendment implementing the
user's answered cross-optic decision ("1": accept the honest memory-only cross-optic fold-rate
limit, documented at "5-67% across the clear-case grid" in `plan.md`'s "Decision Requiring User
Input"). That range came from the architect's own monkeypatched prototype, run *before*
implementation, not from the shipped code.

Re-measuring the actual shipped code's own `_e1_fold_rate` logic (independent salts, N=300 per
cell, all 24 geometry/optic-order/temporal-order combinations) found **0%-86.3%**, not 5-67% --
the worst cells (far group founded through binoculars, near group reacquired unaided, far-first,
at 4.5-5.0 km) reach 72-86%, well above the quoted 67% maximum. The shipped test suite's own fence
table (`test_relative_distance_sweep.py::_CROSS_OPTIC_MEMORY_ONLY_FENCE`) correctly covers these
higher numbers (ceilings up to 0.95) -- the *test* is honest. The *decision document* (`plan.md`'s
amendment section and `BL-B108.md`'s roadmap entry) is not: both still quote the prototype's "5-67%"
when the user's "1" is actually standing behind a 0-86% reality.

**Root cause of the gap, traced rather than assumed a defect**: the architect's prototype table
showed one ordering ("far optic looser, near optic tighter") always worse than its mirror; the
shipped code's `passes_gate` hypothesis-scaling (multiplying the *second-observed* look's own
sigma by `hypothesis_range_m / percept.range_m`) inverts this at the largest geometries, because
when the second-observed look is already the looser optic *and* that ratio exceeds 1, an
already-loose sigma gets scaled further up, which widens the gate's effective `S` and makes it
*more* permissive rather than less. This is an emergent, explainable property of a design decision
that predates this amendment (the hypothesis-scaling fix from round 2), not an obvious coding bug --
confirmed by instrumenting `correlated_innovation`'s actual call-site values across both orderings,
not just a comparison of end rates.

**How to apply:** whenever a user decision is answered against an architect's *prototype*
measurement (monkeypatched, pre-implementation) rather than the shipped code's own numbers, treat
"the implementer later measured roughly similar numbers" claims in `implementation.md` as needing
independent verification at every cell the decision covers, not just the one or two cells the
implementer's own comparison calls out. A 7-point difference on one cited cell does not bound the
difference on the others -- here, other cells diverged by 20-45 points and even inverted which
ordering is worse. The fix in this case was not a code change (the model and fence are both
correct and already honest) -- it was flagging that the *number the user approved* needs correcting
in the decision documents before being carried forward as settled, per `CLAUDE.md`'s "Direction
before speed" and "Talking to the user" sections (a finding that changes the user's own prior
understanding is surfaced, not silently absorbed because CI is green). See
`[[project_correlated_range_error_gate_and_fold]]` for the surrounding correlation-model history
this decision sits inside.
