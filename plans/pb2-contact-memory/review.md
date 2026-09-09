### Review Summary

Reviewed branch `feature/aircraft-layer-ownship-flag` (3 commits: `b75a5cd`, `513809b`,
`6579f83`) against `plans/pb2-contact-memory/plan.md`'s "Stage -1" section (read via
`git show feature/pb2-contact-memory:...`) and `todo/todo.md`'s Backlog spec, which the two
agree on in substance.

- Aircraft layer: `Export.lua` calls `safe_call(LoGetPlayerPlaneId)` once per poll, compares
  each object's `pairs()` key (the same numeric id `LoGetWorldObjects` iterates with) against it,
  and emits `is_ownship: true/false/null`. Ownship's entry stays in the snapshot — flag, not
  omit. `WorldObjectSample.is_ownship: bool | None` parses/serializes correctly in
  `from_dict`/`to_dict`, tri-state (JSON `null` handled distinctly from `false`), matching the
  `altitude_radar_m` nullable-field convention as claimed.
- Body layer: `association.exclude_ownship` and `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` are deleted
  outright (not deprecated, no shim). New `filter_ownship(candidates)` drops only
  `is_ownship is True`; `None` and `False` are both kept. Both call sites
  (`hybrid_source.py`, `naked_eye_source.py`) switched cleanly, no leftover `ownship_state`
  plumbing into the filter call.
- Ran all four subproject check commands myself (not just trusting the implementer's claim):
  `ruff format --check`, `ruff check`, `mypy --strict` (aircraft-layer `mypy src`, body-layer
  `cd body-layer && mypy src` per its CWD-only config quirk), `pytest` — all green, 57 + 104
  tests passing, matching `implementation.md`'s claim exactly.
- **Empirically verified the regression tests are real, not decorative**: temporarily
  no-op'd `filter_ownship` (`return list(candidates)`) and reran the ownship-related test files.
  5 tests failed as expected (`test_filter_ownship_drops_a_candidate_flagged_true`,
  both `test_ownship_echo_*` tests in `test_hybrid_source.py`, both in
  `test_naked_eye_source.py`), confirming they'd catch a regression of the actual fix. Reverted
  cleanly afterward (`git checkout -- body-layer/src/perception/association.py`).
- The `test_ownship_echo_does_not_prevent_a_real_candidate_from_associating` test deliberately
  ties the echo's `object_type` to the real target's, closing the exact confound a prior review
  pass (referenced in its own comment) found in the old proximity-based version of this test —
  good, self-aware regression coverage.
- `test_filter_ownship_keeps_a_candidate_even_when_co_located_with_ownship` and the naked-eye
  equivalent directly prove the troop-insertion false-negative window (the whole reason for this
  stage) is closed: a real object a few metres from ownship now survives.
- Doc updates (`aircraft-layer/CLAUDE.md`, `WORKFLOW.md`) accurately describe the tri-state
  contract and match the code; no stale references to the deleted proximity heuristic found
  anywhere else in the tree (`body-layer/CLAUDE.md`, `docs/concept/`, `plans/body-layer/plan.md`
  grepped clean).
- Working tree is clean, all files committed, nothing under `world-model/data/` touched, no DCS
  writes (`safe_call`-guarded reads only), coordinate math untouched/not duplicated.

### Required Fixes

- None.

### Optional Refinements

- `todo/todo.md`'s Backlog item ("Aircraft layer should flag the ownship...") is still `[ ]`
  though this branch fully implements it. The implementer flagged this explicitly in
  `implementation.md`'s "Notable Discoveries" rather than silently leaving it stale, which is the
  right call absent write access to a shared file mid-review-loop — but whoever merges this
  branch should flip it to `[x]` (or fold it into DoD's harvest step) so the backlog doesn't drift.
  (optional — bookkeeping, not a code defect)
- `implementation.md` correctly notes `plans/pb2-contact-memory/plan.md` doesn't exist on this
  branch (it lives on `feature/pb2-contact-memory` only, per the task's own framing) and used
  `todo/todo.md`'s Backlog entry as the approved spec instead. Worth writing that plan file before
  BL-2 proper starts, per the implementer's own note — not this branch's job to fix. (optional)

### Verdict
APPROVED

### Review Confidence
Full read — read every changed file in the diff (`Export.lua`, `world_objects.py`,
`association.py`, both source modules, all touched test files, both doc files,
`implementation.md`), ran all four verification commands per subproject myself, and empirically
disabled-and-reran the regression tests rather than only reading them. Live-sortie acceptance
(Stage -1's own acceptance criterion, and DCS-internals correctness of `LoGetPlayerPlaneId()`
itself) is explicitly out of scope for this review per project convention — flagged by the
implementer as user-only and unverified by fixtures, consistent with the plan's own acceptance
criteria.
