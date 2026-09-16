---
name: f10-command-vocabulary-review-fix
description: Fixed TaskStore.tick's stale-captured-area bug from the f10-command-vocabulary review; the recurring "two views of one object drift apart" class.
metadata:
  type: project
---

`plans/f10-command-vocabulary/plan.md`'s review found `belief.tasks.PendingIntent.area` (captured
once at task-creation time, per its own docstring "the same object, not a copy") going stale the
moment `ContactStore.reproject_relative_areas` replaces the store's entry via `dataclasses.replace`
(a new frozen object) on a relative-sector area — silently voiding the sector filter for
`scan_ahead`/`left`/`right`/`full` tasks for their whole life, because `area_wedge_deg` treats an
unprojected `wedge_deg=None` as permissive.

Fix: added `ContactStore.get_area(area_id) -> AttentionArea | None` (plain dict lookup, mirrors
`remove_area`'s existing "unknown id" shape) and had `TaskStore.tick` resolve
`store.get_area(task.area.id) or task.area` before every `area_contains` check, instead of reading
`task.area` directly — keeps `belief/contacts.py` with zero import of `belief/tasks.py` (layering
inversion was explicitly ruled out). The `or task.area` fallback only matters if a still-`pending`
task's area id is missing from the store, which `tools.cancel_task`'s own ordering (cancel task,
then remove area) should make unreachable — documented as a safety net for an invariant violation,
not a relied-on path, and tested directly by removing an area out from under a task without going
through `cancel_task`.

This is (per the review) at least the second time this project has hit "two views of the same
object silently drift apart" — worth checking for the same shape (a captured reference to a
frozen/replaceable object, held across a mutation that swaps rather than mutates) whenever a task,
event, or cache holds an object minted by a store that later replaces entries via
`dataclasses.replace`.

See [[feedback_verify_mission_probe_pattern_claims]] for the same "read the actual code, not the
docstring's claim" discipline that caught this class of bug.
