---
name: terrain-feature-probing-rev3-stages345
description: Rev3 Stages 3a-5 (divide callout) implementation gotchas -- nearest_feature shape, test-fixture latent trap, commit-split technique
metadata:
  type: project
---

Implemented `plans/terrain-feature-probing/plan.md` Revision 3, Stages 3a-5 (2026-10-05) on
`feature/terrain-callout-stages-345`, five commits.

**`nearest_feature`'s return shape cannot change, despite the plan's own prose.** Decision 4 says
"`nearest_feature` returns it [closest point] alongside the distance," but 7 of `describe.py`'s own
info-builders unpack it as `feature, distance = match` (2-tuple). Widening it would break every one
silently (`ValueError` at the next call). Added a separate public `store.reader.
closest_point_on_feature(x, z, feature)` instead -- same `Point`/`LineString`/`Polygon` handling as
`_distance_to_feature`, called directly on a feature already in hand. The same Affected-Files
entry's own second sentence ("existing callers keep their shape") is the real constraint; trust
that over the first sentence's prose when they conflict.

**A new direct-query call path inside an existing enrichment function breaks every test fixture that
monkeypatches only the higher-level function it used to go through.** `terrain_divide_qualifier`
calls `store.reader.features_in_bbox`/`nearest_feature` directly (deliberately, to avoid a second
full `describe_position` call) -- but five `body-layer` test fixtures only monkeypatch
`enrichment.describe_position` against a schema-less `sqlite3.connect(":memory:")`. Two of the five
(`test_tools.py`, `test_console.py`) happened not to fail because their ownship/target coincide,
hitting `divides_between`'s zero-length early return by luck. Grep every file matching the pattern
the plan's own test-impact list doesn't scope to (here: every `_enrichment_context` helper across
`test_*.py`), not just the files that actually failed -- a passing-by-coincidence fixture is exactly
the silent-coverage-loss case `[[verify_full_suite_not_just_new_files]]` warns about, one level up.

**Technique for "mechanism and calibration never share a commit" when the two interleave in one
file's diff**: save a scratch copy of the final file content first (`cp` to `/tmp`, **not**
`git stash`/`git checkout --`, per `[[feedback_revert_test_scratch_copy]]`), then use `Edit` to
strip back to the earlier commit's intended state (re-add the old constant, remove the
not-yet-existing function/imports), run the full test+mypy+ruff gate on that intermediate state,
commit, then restore from the scratch copy for the next commit. **Caveat that bit me**: a
multi-file `cp` loop across several test files got refused by the worktree's "too complex to
verify it stays inside the worktree" guard (`AGENTS.md`'s own documented friction for heredocs/
`>>` in a worktree extends to chained `cp`/`git show` commands too) -- the refusal silently skipped
the whole loop with no partial effect, so the "final" scratch copies for those five files were
never actually written. Re-derive from memory if this happens; always `ls` the scratch directory
immediately after writing to it to confirm the files actually landed, one command at a time if a
chained one gets refused.

See also: `[[feedback_decouple_fixtures_from_tuned_defaults]]` -- Stage 3a's dominance rule made a
pre-existing fixture test (`test_semantic_facts_for_includes_every_present_field`) assert two
mutually-exclusive outcomes (both ridge and valley present and dominant) at once; had to drop one
kind from that fixture rather than retune distances, since the rule is now exclusionary by
construction, not just threshold-gated.
