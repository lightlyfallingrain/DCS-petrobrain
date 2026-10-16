---
name: project_fix_answers_review_wording_not_user_direction
description: BL-B71's first review-fix round answered the review's own narrower wording ("the granted optic") rather than the user's actual direction behind the finding ("actual behavior must measure by used optic") -- a correct-sounding narrower target standing in for the thing actually asked about. First occurrence under this exact shape; watch for a second.
metadata:
  type: project
---

On `BL-B71` (the least-capable-optic guidance ladder), the Reviewer's required fix named
`OpticState.guidance_optic` as the fix target -- a specific, plausible, named field. The
implementer wired exactly that. It was wrong: `guidance_optic` is `None` through ordinary
glassing with no guidance grant standing, so the fix reintroduced the original defect (a live,
resolvable look reported `"too_far"`) for the ordinary-glassing case, just narrower than before.
Only when the user was asked directly whether this was a test artefact or real behaviour did the
actual requirement surface: **"actual behavior must measure by used optic"** -- `runner.optic`,
the value that actually admitted the tick's percept, not any single named field that usually
tracks it.

**Why this is worth a memory on its own, separate from
`[[recurring_correct_conclusion_unearned_reason]]`:** that pattern is about a review *approving* a
conclusion with an unearned reason. This is about a review's *own finding* naming a target that
turns out to be a correct-sounding proxy for the real one, and the fix implementing the named
target faithfully and still missing the point -- the defect survives the fix because the fix
answered the review's wording, not the direction the wording was trying to capture. The tell, in
hindsight: the review said "the granted optic" where the actual requirement was "the optic in use"
-- two things that agree in the common case (hence passing fixtures) and diverge in exactly the
case (ordinary glassing, no standing grant) that triggered the bug a second time.

**How to apply:** when a Reviewer's required fix names a specific field/variable as *the* fix
target, treat that name as the reviewer's best current guess at the real requirement, not as the
requirement itself -- especially when the field's own semantics are narrower than the English
description of the defect ("the optic in use" vs. "the optic the guidance ladder happens to have
granted"). Before approving a fix that targets the named field, ask whether there is a case where
the named field and the broader English description diverge, and if the defect's own user-facing
description used more general language than the fix's target, that divergence is worth surfacing
to the user directly rather than assuming the two are interchangeable.

**Occurrence count: 1.** Not yet a confirmed recurring category -- filed so a second instance (on
a different feature) can be matched against this one rather than treated as a fresh discovery.
