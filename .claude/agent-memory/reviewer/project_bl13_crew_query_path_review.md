---
name: bl13-crew-query-path-review
description: BL-13 Stages 1-3 review — CHANGES REQUIRED on a singular/plural fold masked because every fold test used a class whose plural equals its singular; plus infantry EAGER cohesion bridging non-infantry contacts across 6 km.
metadata:
  type: project
---

`feature/bl13-crew-query-path`, `e2e2164..5f73925`. Verdict CHANGES REQUIRED, one required fix.

**The fix, and why reading did not find it.** `speech.render_report_summary` folds a single in-scope
class into the count clause by `count_clause.replace(" units", plural).replace(" unit", plural)` —
unconditionally plural, so a count of one speaks *"One trucks"*, *"One short range SAMs"*,
*"One ships"*. The open-ended branch has the same defect without the fold (*"At least one units"*).
**Every existing fold test used `OP_ARMORED` or `OP_INFANTRY`, whose `_OP_CLASS_DISPLAY_PLURAL`
value equals the singular**, so `"One armor"` asserted true and passed incidentally. The same
function's air-defence clause already gets it right, using `_OP_CLASS_DISPLAY` for its `count == 1`
branch — one function, correct in one clause and wrong in the other.

**Transferable:** when a renderer has a singular/plural table, **enumerate the whole table through
the renderer** rather than reading the branch. One loop over `_OP_CLASS_DISPLAY_PLURAL` printing the
rendered string found it in seconds; the diff reads correct. This is
[[feedback_rendered_english_assertions_too_weak]] and
[[feedback_boundary_only_tested_via_fixture]] arriving together — the mass-noun fixture is the
boundary that was only incidentally tested.

**Out-of-scope finding worth the file, measured not reasoned.** `belief.groups`'
`_OP_CLASS_COHESION_BACKSTOP` marks `OP_INFANTRY` `EAGER`, dropping the absolute backstop to
`math.inf` for a pair where **either** member is infantry. So infantry is an *unbounded bridge*
between non-infantry contacts:

```
armor@1km + truck@3km                -> 0 groups
armor@1km + infantry@7km             -> 1 group of 2   (6 km apart)
armor@1km + truck@3km + infantry@7km -> 1 group of 3
```

The user's direction was *"ok to merge infantry too eagerly"*; merging **armour** into infantry's
group across 6 km is broader than that grants, and it hits the live push path's
`render_group_full_disclosure` today. The implementer called this "erratic cohesion at fixture
scales" — it is not erratic, it is deterministic and explained, which is a better finding.

**Also confirmed:** `object_model.profile_for("OP_SRSAM")` returns the default bucket
(`OP_GROUPSOMETHING`), so `speech._is_air_defence` misses a *class*-level SAM belief; its two
callers compute `is_air_defence_repeat` on the push path. `classification.parent_class_of` is the
only lookup resolving both a type string and an `OP_*` value — the pair is not interchangeable and
anything reading a class-level belief must use `parent_class_of`.

**What was well done, worth not re-litigating.** Six tests were rewritten because Decision C changed
the command's output contract; each kept a real property and two got *stronger* (the group test now
also asserts `render_group_full_disclosure` still speaks the full roster, so "the pull path changed"
cannot be confused with "the renderer broke"). A rewrite is only a lost test when the property goes
with it — check the property, not the rename. See [[project_pb2_review_log_append_only]] for where
the verdict lives.
