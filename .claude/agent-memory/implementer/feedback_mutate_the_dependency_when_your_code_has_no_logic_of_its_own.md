---
name: mutate-the-dependency-when-your-code-has-no-logic-of-its-own
description: When a required test case (e.g. "inner-ring holes honoured") is actually guaranteed by a function you call rather than code you wrote, mutate the dependency to prove the test is not vacuous -- don't skip it or fake a mutation in your own file.
metadata:
  type: feedback
---

On `plans/forest-occlusion/plan.md` Stage 1, the plan called for a test proving "a clearing inside
a wood is not forest" (inner-ring holes honoured). `perception.forest.ForestOcclusion.occluded`
has no hole-handling code at all -- it delegates entirely to world-model's
`store.reader.containing_polygons`, which already honours `inner_rings`. There was nothing in
*my* file to mutate that would exercise that specific guarantee.

**Why this matters:** the Implementer role instructions require every new test be verified by
mutation (break the code, confirm red, revert). The naive move is to skip verification for a test
like this ("there's nothing to break") or to mutate something unrelated in my own file and call it
done -- both leave the test's real claim (hole-honouring) unverified.

**How to apply:** mutate the *dependency* the test actually relies on, even though it lives in a
different subproject. Here: temporarily changed `world-model/src/store/reader.py`'s
`containing_polygons` to pass `[]` instead of `_inner_rings(feature)` to `polygon_contains`, ran
the body-layer test, watched it go red for the stated reason, then reverted the world-model file
(checked via `shasum` before/after, same as every other mutation). This is still "mutating the
code the test covers" -- the test covers the *behaviour*, which happens to be implemented one
module layer down, and a test that can't fail when that behaviour breaks is not evidence either
way.

Don't conflate this with touching a dependency's logic permanently, or with skipping verification
because the logic is "someone else's" -- temporary, reverted, checksum-verified mutation of the
actual code path is the point, regardless of which file it lives in.
