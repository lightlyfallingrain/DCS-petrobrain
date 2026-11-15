---
name: zero-vs-partial-correlation-conflation
description: a correlated-error/no-omniscience design that zeroes correlation entirely to avoid "arithmetic omniscience" (fusing two fully-correlated unequal-sigma estimates to extrapolate past both) can quietly reopen the original bug under routine conditions, because the argument only rules out rho=1, not any rho>0
metadata:
  type: feedback
---

Found reviewing `BL-B108` (`relative-distance-grouping`, body-layer). The plan's correlated
down-range error model deliberately folds `optic_class` into each noise field's seed so a look
through a *different* optic is a fully independent draw (`rho = 0`) -- stated reason: "sharing one
field across optics would let belief infer Z exactly from two optics and recover truth... omniscience
by arithmetic." That reasoning is correct against `rho = 1` (two fully-correlated estimates of
unequal variance do extrapolate past both inputs), but the implementation jumped straight to
`rho = 0`, skipping every value in between.

**Why this matters beyond this one case:** `rho = 0` is exactly the width the whole feature exists
to narrow (the plain independent-sum gate). So whenever this model's correlation hits a path that
forces `rho = 0`, the original bug (two real things folding into one) comes back -- and here that
path (raising binoculars on something already being watched) is the crew's own *default* autonomous
behaviour (`belief/optic_policy.py`'s scan→glass cycle), not a rare or player-forced action. A
test the implementer themselves wrote (`xfail(strict=False)`) demonstrated the fold directly, and
was candidly disclosed in `implementation.md` as a discovery -- but still shipped as a known gap
without flagging to the user that it defeats the plan's own headline goal (E1) under ordinary play.

**How to apply:** when reviewing any "independent across X" correlation-boundary design (new optic,
new sensor, new observer, new time-of-day...), check whether the *reason given* for independence
only forbids `rho = 1` (full correlation / omniscience) rather than *any* `rho > 0`. If so, and if
the independent fallback reopens the bug the feature exists to fix, treat it as a required finding,
not an accepted risk -- even if the implementer's own plan or risk list seems to cover it (compare
against what the plan's "accepted risk" actually describes: geometry decorrelation after ownship
has moved, not an optic switch at unchanged geometry, are not the same trigger even though they hit
the same `rho -> 0` code path). See `[[feedback_verify_the_rendered_artifact_not_the_source_comment]]`
for the sibling habit of checking the rendered artifact rather than the stated intent.
