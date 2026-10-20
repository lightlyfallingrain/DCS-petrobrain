---
name: feedback-single-member-cluster-tests-dont-exercise-unanimity-folds
description: a cluster-fold that checks set-unanimity (member_emitter_kinds == {x}, member_targets_ownship == {True}) is only trivially exercised by a test with one candidate -- len({x}) == 1 is true whether or not real aggregation happened. Build a genuine 2+-member cluster to test it.
metadata:
  type: feedback
---

Reviewing `fix/taking-fire-visible-shooter` (`6029f184`, `body-layer/src/perception/
naked_eye_source.py`'s `_build_observation`): the fix changed precedence of a set-unanimity check
(`member_targets_ownship == {True}`, generalizing `Cluster.classification_raw`'s "identical keeps,
disagreement degrades" rule to the targets-ownship bit). Every committed test for this branch --
new and pre-existing, and the sibling `member_emitter_kinds` branch too -- constructs exactly one
`_world_object`, i.e. a one-member "cluster." `len({value}) == 1` is true for a singleton
regardless of whether any real set-aggregation logic ran correctly; it does not distinguish "the
unanimity check works" from "the unanimity check was never really exercised."

**Why this matters here specifically**: the whole point of `_build_observation` is cluster-level
folding -- multiple members, one Observation. A fold rule like this is exactly the kind of thing
that silently breaks (wrong operator, wrong default on `.get`, checking the wrong set) without a
genuine multi-member test ever catching it, because every existing test happens to use clusters of
one.

**How I verified instead of trusting the single-member tests**: built an ad hoc probe (not
committed, used the test module's own `_source`/`_world_object`/`_firing_active_map` fixtures) with
two genuinely clustered candidates (20 m apart at ~500 m range, inside `clustering.py`'s own
down-range merge radius) and three variants -- unanimous `targets_ownship=True`, mixed
`True`/`False`, mixed emitter kind -- and confirmed all three match the docstring's claimed rule.
Found the logic correct, but the gap is real and predates this commit (no "mixed"/"degrad"-named
cluster test exists anywhere in `test_naked_eye_source.py`, for either `member_emitter_kinds` or
`member_targets_ownship`) -- filed as an optional refinement, not a required fix, since it is a
pre-existing coverage gap in the `emitter-visibility`/`BL-B72`/`BL-B73` feature, not something this
diff introduced.

**How to apply**: when a cluster-fold or any `set(...) == {single_value}` check is in a diff under
review, check whether any committed test actually constructs 2+ members for it. If not, either ask
for one or verify the aggregation by hand (not just trust that `len(...) == 1` passing proves
anything) before approving. See also [[feedback_emitter_visibility_fix_pass_confirmed_by_mutation]]
and [[feedback_regression_test_empirical_check]] for the same "verify by mutation, don't trust the
test shape" posture applied to this feature's earlier stages.
