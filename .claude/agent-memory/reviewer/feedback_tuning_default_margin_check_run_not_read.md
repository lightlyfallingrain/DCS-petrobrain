---
name: tuning-default-margin-check-run-not-read
description: when a tunable's default is justified against one named scenario's required value with "almost no margin," run the real code against nearby/declared geometries rather than accepting the comment's own narrative -- a default can look defensible by inspection and still fail the plan's own stated baseline case
metadata:
  type: feedback
---

Found reviewing `BL-B108` (`relative-distance-grouping`) round 2. The dispatch asked specifically
whether `CROSS_OPTIC_RANGE_SHARE`'s default (0.6, needed ~0.57) was "fitted to the one scenario"
and whether the fix held for other geometries the plan names (2-5 km spacings). Reading the
source comment and `implementation.md`'s own "worked by hand... confirmed by probing" account was
not enough to answer that -- the comment is honest about *how the default was derived*, not about
*where else it fails*.

Ran the actual scenario-suite helpers (`_observation`/`_ownship` from `test_relative_distance_
scenarios.py`) directly against `ContactStore`, sweeping geometries beyond the one shipped
regression test. Result: the shipped geometry (far 4.6 km/near 2.4 km, ~2.2 km separation) is
robust across 20 bias draws, but the *plan's own declared baseline* ("clear case, 1.5 km apart at
~3 km, always two" -- `plan.md`'s own worked-numbers table) folds to one contact in 10/10 draws at
the shipped default, and still folds in 5/5 draws at the tunable's own declared `hi` bound (0.75)
-- there is no value in the allowed range that closes this. The same-optic baseline at the
identical geometry stays two 10/10, confirming the regression is specific to the cross-optic
share, not the geometry itself.

**How to apply:** when a review task names a specific "is this fitted to one scenario" concern
about a tunable's default, that is a request to *run* a small sweep of the geometries the plan
itself claims to cover (its own worked-numbers table, its own named E-numbered cases), not to
re-derive the margin arithmetic by reading the comment more carefully. A default that reproduces
the one scenario it was built against, and even sits a plausible-looking distance from the
computed threshold, can still fail a case the plan explicitly promises elsewhere -- the margin that
matters is margin against the plan's *other* stated guarantees, not margin against the one number
the implementer back-solved for. This generalises `[[feedback_zero_vs_partial_correlation_
conflation]]`'s lesson (check what the "independent across X" argument actually forbids) one layer
further: even once independence is correctly relaxed to a bounded partial correlation, the *size*
of that bound still needs checking against the plan's declared cases, not just against the one
case that motivated building it.
