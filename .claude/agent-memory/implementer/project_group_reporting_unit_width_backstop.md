---
name: group_reporting_unit_width_backstop
description: Replacing a flat-metre cohesion backstop with a per-pair unit-width bound in belief/groups.py -- currency reuse, mechanism/calibration split limits, and a keyword-matching accident worth knowing about.
metadata:
  type: project
---

`belief/groups.py`'s cohesion backstop moved from a flat `GROUP_PROXIMITY_ABSOLUTE_BACKSTOP_M`
(300.0 m, applied only below 3 tracked contacts) to `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS`
(20.0), a per-pair bound scaled by the pair's own mean believed size (`perception.object_model.
size_m`), applied at every tracked-contact count. Task: 2026-09-29, `plans/group-reporting/plan.md`
+ `review.md`'s n>=3 finding.

**Borrow the currency, not the constant, when two modules solve the same class of problem at
different layers.** `perception.group_salience.GROUP_COHESION_GAP_UNIT_WIDTHS` (10.0) already
proved out "unit widths" as a range/size-correct currency for an *angular* question. This module
needed the same currency for a *world-space* question and got its own, separate, differently-valued
constant -- not a shared one. Two constants with an identical name pattern and vocabulary
("unit widths") sitting one layer apart is exactly the kind of pair a future reader could
accidentally unify; both modules' docstrings say explicitly why they must not be.

**Full behaviour preservation across a mechanism/calibration commit split is not always
achievable, even when a prior pass on the same file used the technique successfully.** The
flat-metre backstop's own two-commit precedent (`9ecedaf`/`b0f9518`) used `math.inf` as a
placeholder that changed *zero* behaviour, because it was adding a wholly new constraint to a
previously-unconstrained case. This pass reused the technique but the scope itself was the whole
point (apply the bound at every n, not just n<3), so the placeholder commit was a genuine,
temporary regression of the already-shipped n=2 protection -- two tests had to flex out and back
in across the two commits. Recorded explicitly in both commit messages and implementation.md rather
than claiming "no behaviour change" the numbers didn't support. See [[feedback_mechanism_calibration_split_scope_change]].

**`perception.object_model.profile_for`'s keyword matching against `OP_*` class-bucket strings is
inconsistent by accident, not design.** Some bucket names happen to contain a matching keyword as a
substring (`"OP_TRUCK".lower()` contains `"truck"` -> real 6.0 m match) while others don't
(`"OP_ARMORED"` matches nothing -> falls to the default profile). Any belief-layer code reading a
CLASS-level `Contact.classification.value` (which *is* the literal `OP_*` bucket string at that
level, per `belief/classification.py`) through `profile_for` should not assume it either reliably
resolves or reliably fails -- detect "no real match" via `profile.op_class ==
object_model.DEFAULT_OP_CLASS` (the same signal `belief.classification._op_class_of` and
`belief.speech._identification_lead` already use) and fall back explicitly, rather than trusting
the keyword match to behave uniformly across class buckets.

**When choosing a "no data yet" default size for an unresolvable classification, prefer an
already-established reference over inventing a new number.** Used `perception.visibility`'s own
7 m armored-vehicle calibration reference (the value its angular-radius tiers are tuned against)
rather than `object_model.DEFAULT_SIZE_M` (5.0 m) -- that constant answers a different question
(ED's "unclassified" bucket for the angular-radius range-threshold numerator), and reusing it
silently would have been the same shape of error as its own docstring already warns against
(fabricating a fact you don't have).
