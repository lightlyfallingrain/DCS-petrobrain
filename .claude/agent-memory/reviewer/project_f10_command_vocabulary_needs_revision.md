---
name: project-f10-command-vocabulary-needs-revision
description: f10-command-vocabulary reviewed NEEDS REVISION — captured-object staleness bug where TaskStore.tick reads a frozen AttentionArea reference that reprojection never updates.
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
