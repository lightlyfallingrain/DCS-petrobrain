---
name: equivalence-test-must-own-its-reference-arithmetic
description: An equivalence/refactor test must copy the pre-change predicate locally, never import it — importing shares the mechanism and makes the test tautological; share only tuning constants.
metadata:
  type: feedback
---

When writing an "output is identical before and after the refactor" test, the
reference implementation must contain its **own copies** of the pre-change
predicates and gates. Importing them from the module under test looks like
rigour ("the real old function, verbatim") and is the opposite: if the refactor
rewrote those functions — even into thin wrappers — both sides of the comparison
now run the new code and move together under any change to it.

**Share the tuning constants, copy the arithmetic.** Constants are calibration;
a second copy of them makes the test fail whenever a threshold is legitimately
retuned, which is noise. The gate and the formula are mechanism; sharing those
is what destroys the test.

**Why:** BL-11 Stage 2 hoisted per-candidate terms out of `group_salience`'s
O(n²) loop and shipped `test_group_salience_equivalence.py` importing `_cohesive`
and `_resolvable`. Stage 2 had turned `_resolvable` into a wrapper over
`_resolvable_terms` and made `_cohesive` delegate to `_cohesive_from_terms` —
both used by production's own loop. Deleting `* optic.presence_range_mult` from
the resolvability gate, a real behaviour change, left the file passing **15/15**
and the whole suite at 1506/4. One test's docstring explicitly claimed it would
catch exactly that.

**How to apply:**

- Write the reference's predicate inline in the test module, from
  `git show <refactor-commit>^:<path>`.
- **Prove it by counterfactual before reporting done**: mutate the production
  gate, confirm the test *fails*, restore, and `shasum` the file before and
  after to prove the restore was byte-identical.
- Expect a side effect: the originals may end up with no caller at all. Say so
  rather than deleting them, and fix any docstring claiming they are tested.
- Watch which parametrised cases can actually detect the mutation — here the 14
  `UNAIDED_OPTIC` cases could not (its multiplier is 1.0); only the raised-optic
  case could. A test file's pass count is not its coverage.

Related: [[project_bl11_perf_stages]].
