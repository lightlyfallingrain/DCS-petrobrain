---
name: project-f10-command-vocabulary-review-cycle
description: f10-command-vocabulary review cycle — required fix (captured AttentionArea staleness in TaskStore.tick) found, fixed, re-reviewed and APPROVED.
metadata:
  type: project
---

Reviewed `feature/f10-command-vocabulary` (2026-09-16, `plans/f10-command-vocabulary/`). D1-D3's
relative-sector geometry (wedge table, wraparound, `area_contains` purity) and D5's
register-then-trigger ordering were all correct on inspection and reproduction. Gates green in
both subprojects.

Found one real correctness bug: `belief.tasks.PendingIntent.area` is a captured object reference
("the same object, not a copy" per its own docstring) taken at task-creation time, before
`ContactStore.reproject_relative_areas` ever runs. Reprojection replaces the *store's* dict entry
via `dataclasses.replace` (a new frozen object) but nothing re-syncs the task's own `.area`
reference — confirmed directly with a repro script (`task.area is store.areas[...]` is `False`
after reprojection, `task.area.wedge_deg` stays `None` forever). Since `area_wedge_deg` treats
`wedge_deg=None` + no `sector` literal as "no angular filter, permissive," a relative-sector
scan task's sector constraint is silently void for its entire life — `TaskStore.tick`'s success
check matches against an unbounded circle, not the moving wedge D1-D3 exists to produce. The
attention-display path (`effective_attention`, called with the live `self.areas` property) is
unaffected — only the captured-reference path (`TaskStore.tick`) is stale.

**General lesson for this codebase's pattern**: whenever a plan introduces a "live, re-projected/
re-synced" value stored in one place (here: `ContactStore._areas`) but also captured by reference
into a second, independent store (here: `PendingIntent.area`), check whether the second store's
reference gets refreshed or is frozen at capture time. Frozen dataclasses + `dataclasses.replace`
make this bug easy to introduce silently, since the old object is never mutated in place — it just
quietly stops being the canonical one. New tests added for the reprojection feature all checked
the *store's* live area, never a task's captured reference across a reprojection — a test-coverage
blind spot worth checking for on any future "value X lives in two places" design.

See also [[feedback_bounded_magnitude_isnt_optional_severity]] — this was flagged as a required
fix despite reading like a subtle edge case, because it violates the plan's own D1-D3 invariant
for the one consumer (task completion) the plan's own Risks section had flagged as needing care.

**Re-review outcome (same session, commits `eac1000`/`ece3c94`): APPROVED.** Fix was a
`ContactStore.get_area(id)` lookup + `TaskStore.tick` resolving `store.get_area(task.area.id) or
task.area` instead of trusting the captured reference. Verified the fix closes the divergence for
every reader of a task's area, not just `tick` — grepped for all `task.area.*` accesses first
before accepting the fix as complete, since a captured-reference bug fixed in one spot but not
another (same bug, one level over) is a real risk with this pattern. Also traced (did not just
accept the commit message's claim) that the docstring's "the fallback should never trigger" is
slightly overstated: `belief.console.Console`'s pre-existing, out-of-scope `unwatch-area` debug
command also removes an `AttentionArea` directly, independent of `TaskStore`, so the fallback is
reachable through that older path too — downgraded to optional since it's `--console`-only,
pre-dates this milestone, and the fallback already degrades gracefully (has its own test). Useful
process note: when a fix adds a "should not happen because X always does Y first" claim, check
whether X is genuinely the *only* path to that state, not just the path this milestone added.

**Follow-on commit `c05bbc1` (D6, "Watch -> Nearest Air Defence"), reviewed alone: APPROVED.**
User-authored, asked to be reviewed adversarially. Verified the air-defence `OP_*` class set
against `perception/object_model.py`'s actual profile table (not just the commit message) and
`parent_class_of`'s no-op-for-class/resolve-for-type behaviour against `_op_class_of`'s real body,
not its docstring. No-omniscience held (traced the whole `facts` chain back to `Contact.
classification`, never `derived_world_position`/a DCS id). Found one test-quality nuance worth
naming even in an APPROVED review: `test_..._ignores_a_presence_level_contact` would pass
identically with the level gate deleted, because `parent_class_of(PRESENCE_CLASS)` already returns
`None` on its own — the level gate is *intentionally* redundant defensive coding given the lattice's
documented value-tied-to-level invariant, not a bug, but the test's docstring overclaims which
mechanism it's isolating. Also caught a doc inconsistency `mypy`/tests can't catch: `WORKFLOW.md`
bumped "14 tokens" to "15" but left its enumerated Watch-submenu list one item short of that count,
inconsistent with the sibling sentence in `CLAUDE.md` updated correctly in the same commit —
useful reminder that a count bump and a list bump are two separate edits and both need checking
even when they're two lines apart in the same diff.
