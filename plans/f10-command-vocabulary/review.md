### Review Summary

Reviewed `feature/f10-command-vocabulary` (4 commits: `9f1b8e3` plan, `e023a6a` stages 1-5,
`f93bb3d` stages 6-7, `7c85ea1` D4a scoping record) against `plans/f10-command-vocabulary/plan.md`
(D1-D5, D4a) and `implementation.md`. Both subprojects' gates re-run and confirmed green:
body-layer 520 passed / ruff format+check clean / `mypy src --strict` (run from `body-layer/`)
clean; aircraft-layer 109 passed / ruff format+check clean / `mypy src --strict` clean.

The relative-sector geometry itself (D1-D3) is correct: `_RELATIVE_SECTOR_WEDGE_DEG` matches the
plan's o'clock table exactly, `project_relative_area`'s wraparound is right (`_angular_delta_deg`'s
`(a - b + 180) % 360 - 180` formula), `area_contains` genuinely stays pure absolute geometry with
no ownship parameter, and `reproject_relative_areas` is wired into `logger.py`'s `run_once` at
exactly the D2-specified point (after `last_ownship_state` is set, before `ingest`/`tick`). D5's
register-then-trigger ordering in `crew_console._handle_scan` is correct and its failure path is
correctly non-destructive. The mutual-exclusion `ValueError` in `ContactStore.add_area` is
correctly raised and every caller (bearing-scan and relative-scan token paths) respects it.

However, there is one real correctness bug in how the moving-area design connects to task
completion (below), and it slipped past the new test suite because no test exercises a task's
sector filter across a reprojection.

### Required Fixes

- **A `scan_*` task's sector filter never actually gates task completion for relative-sector
  scans — the sector constraint is silently void for the task's entire life.**
  `belief.tasks.PendingIntent.area` is, by that dataclass's own docstring, "the same object, not a
  copy" captured at `tools.scan_area`/`ContactStore.add_area` creation time. A freshly-created
  relative-sector `AttentionArea` has `wedge_deg=None` (unprojected — `project_relative_area` only
  runs on `logger.py`'s *next* telemetry tick). `ContactStore.reproject_relative_areas` then
  updates the *store's* dict entry via `dataclasses.replace` (frozen dataclass → a new object),
  but nothing ever re-syncs `task.area` to that new object — I confirmed this directly: after
  calling `reproject_relative_areas`, `task.area is store.areas[...]` is `False` and
  `task.area.wedge_deg` is still `None`. Since `area_wedge_deg`'s documented precedence treats
  `wedge_deg=None` + no `sector` literal as "no angular filter, permissive until projected,"
  `TaskStore.tick`'s success check (`area_contains(task.area, contact.last_position)`) evaluates a
  relative-sector scan task against an unbounded circle of radius `F10_SCAN_RADIUS_M` centered on
  ownship's position *at scan-request time* — never the moving, sector-narrowed wedge the whole
  D1-D3 design exists to produce. `console.py`'s attention-display path (`effective_attention`,
  called with the live `self.areas` property) is unaffected and correctly tracks the projection —
  this bug is specific to `TaskStore.tick`'s captured reference. Concretely: "Scan Left" will
  report the task `succeeded` even if the only contact detected the whole time was dead ahead or
  to the right, because the sector was never enforced. This is exactly the kind of small-looking
  gap that's still a required fix regardless of apparent magnitude — it violates D1-D3's own
  stated invariant (an ownship-anchored area tracks the nose) for the one consumer (task
  completion) the plan's Risks section specifically flagged as needing attention. No test in the
  added suite catches it because `test_reproject_relative_areas_updates_only_relative_areas` and
  `test_console_runner_reprojects_relative_areas_before_ingest` both check the *store's* area, and
  the `_handle_scan` tests only assert `task.area.relative_sector == "ahead"`, never that the
  sector actually constrains `tick`'s success check across a reprojection.
  Fix needs `TaskStore.tick` (or its caller) to resolve the task's area from the live `ContactStore`
  by id rather than trusting the captured reference — plus a test that plants a contact outside
  the projected sector but inside the unprojected radius and asserts the task does *not* succeed.

- **`belief/tasks.py`'s docstring was never updated**, despite the plan's own Risks section
  explicitly calling this out: "An ownship-anchored area whose centre tracks ownship changes what
  'area' means... needs saying in `tasks.py`'s docstring." `implementation.md`'s "Files Changed"
  list does not include `tasks.py`, and no deliberate-deferral note explains the omission. This
  should be fixed alongside the bug above, since the correct semantics (once fixed) still need
  stating at the site the plan named.

### Optional Refinements

- `plans/f10-command-vocabulary/plan.md`'s own "Menu tree (D4)" ASCII diagram and "Sector bounds"
  table only enumerate 6 leaves (4 relative scans + Watch Nearest + Cancel Task), with no mention
  of the 8 `scan_bearing_*` compass items or the nested `Bearing` submenu that were actually built
  — yet D4a's prose two paragraphs later calls it "the 14-token vocabulary below," an internal
  inconsistency in the plan document itself (not introduced by the implementer, who built to match
  the "14-token" figure and the pre-existing absolute `Sector` literal, and who documented the
  actual tree correctly everywhere else: `ALLOWED_COMMANDS`, the Hook script's own added comment
  block, `body-layer/CLAUDE.md`, and `body-layer/ROADMAP.md` all correctly show 14 tokens with the
  Bearing submenu). Worth reconciling `plan.md`'s Menu tree/Sector bounds sections to match what
  was actually built and documented elsewhere, so a future reader of the plan alone isn't misled
  by the stale 6-leaf diagram. (Optional: the actually-shipped behavior and every other doc are
  already correct and consistent with each other; only the plan's own tree diagram is stale.)

### Verdict (original round)
NEEDS REVISION

### Review Confidence (original round)
Full read — read the complete diff for every touched file, reran both subprojects' format/lint/
type/test gates directly rather than trusting the reported numbers, and reproduced the task/area
staleness bug with a standalone repro script against the actual code rather than inferring it from
reading alone.

---

## Re-review (`eac1000`, `ece3c94`)

Re-read both new commits in full, re-ran both subprojects' gates independently, and reproduced the
fix's claimed behavior with a standalone repro script rather than trusting the commit message.

**Required fix 1 (stale captured area voiding the sector filter) — confirmed fixed.**
`ContactStore.get_area(area_id)` is a straight dict lookup against the live `self._areas`.
`TaskStore.tick` now does `area = store.get_area(task.area.id) or task.area` before the containment
check, replacing the old `area_contains(task.area, ...)`. I reproduced it directly: after
`reproject_relative_areas` on a `left`-sector task with heading 0, `store.get_area(task.area.id)`
has `wedge_deg=(300.0, 30.0)` while `task.area.wedge_deg` is still `None`; `area_contains` against
the live area correctly returns `False` for a dead-ahead contact that the stale captured area would
have wrongly accepted (`True`) — matching the coordinator's report exactly.

*Checked every other reader of a task's `area`, not just `tick`* — this was the first thing asked
to verify, since a captured-reference bug fixed in one spot but not another is the same class of
bug one level over. Grepped `tools.py`/`crew_console.py`/`console.py`/`tasks.py` for every
`task.area`/`.area.` access: `tools.cancel_task` reads only `task.area.id` (to call
`store.remove_area`, itself id-based, not geometry-based); `console.py`'s `_handle_task_status`
and `_handle_scan_area`'s readback print only `task.area.id`, never `.center`/`.sector`/
`.wedge_deg`; `tools.get_task_status` returns the `PendingIntent` unchanged but nothing downstream
reads its area's geometry. `tick`'s containment check was the only geometry-reading site — the fix
is complete, not partial.

**Required fix 2 (tasks.py docstring) — confirmed done and accurate.** The new module-docstring
section ("Ownship-anchored areas are a moving patch of view, not ground") and the tightened
`PendingIntent.area` docstring ("only `.id` is safe to read directly") both match the actual
mechanism now in place — verified against the code above line by line, not just read as prose.

**Optional fix 3 (plan.md menu-tree diagram) — confirmed done**, redrawn to 14 leaves with the
`Bearing` submenu and a note reconciling it with D4a's "14-token" prose.

**The `or task.area` fallback's "should not happen" claim — reachable, but by a pre-existing,
out-of-scope path, and the fix already handles it gracefully.** The docstring says the fallback
should never trigger for a pending task "since `tools.cancel_task` always cancels the task before
removing its area" — but `cancel_task` is not the only path that can remove an `AttentionArea`.
`belief.console.Console`'s pre-existing `unwatch-area <id>` debug command (`tools.unwatch_area` →
`store.remove_area`) removes any area by id directly, with no awareness of `TaskStore` at all. If a
`--console` operator runs `unwatch-area` on the id printed by a still-pending scan task's own
`_handle_scan_area` readback (`"scan task {id} created (area {area.id})"`), the area vanishes while
the task stays `pending`, and the next `tick` genuinely hits the fallback branch — not merely a
hypothetical invariant violation. That said: (1) this is unreachable from the F10 path this
milestone actually built — `unwatch-area` is `--console`-only, pre-dates this milestone, and no F10
token or `_handle_scan` code path calls it; (2) the fallback's actual behavior when triggered is
exactly what `test_tick_falls_back_to_captured_area_when_the_live_area_is_gone` already exercises
and asserts — it degrades gracefully (uses the stale-but-present captured geometry, doesn't raise,
doesn't drop the task) rather than crashing or silently discarding the task; that test would have
passed identically before this fix too, since `tick` always used `task.area` directly pre-fix, so it's
confirming the new code path's graceful-degradation shape, not a behavior change. Net: the
docstring's "should not happen" is a slight overstatement of the invariant's actual scope (it holds
for every path this milestone touches, not for the pre-existing `unwatch-area` command), but the
runtime behavior is already correct and tested for the case where it's wrong. Recording this as
optional, not required — narrow the docstring's claim to name `cancel_task` as "the only
task-lifecycle path that removes an area" rather than implying no path can, whenever `tasks.py` is
next touched.

**Test quality — both new tests would genuinely have failed/behaved differently pre-fix.**
`test_tick_resolves_relative_scan_area_against_its_live_projection`: under the old
`area_contains(task.area, ...)` code, `task.area.wedge_deg` is `None` at the point `tick` runs (the
captured reference is never projected), so the dead-ahead contact at bearing 0 would have matched
the permissive full-circle fallback and the task would have wrongly reported `succeeded` after the
*first* `ingest`/`tick` — the test's first assertion (`status == "pending"`) is a genuine regression
guard, not incidental. `test_tick_falls_back_to_captured_area_when_the_live_area_is_gone` exercises
the new `get_area`-miss branch specifically (confirmed above it wouldn't have distinguished old vs.
new code, since old code always used the captured reference) — legitimate coverage of the new
fallback branch's shape, correctly not claimed as a regression test for the original bug.

Gates re-confirmed independently: body-layer 522 passed (520 → +2, matching the two new
`test_tasks.py` cases), ruff format/check clean, `mypy src --strict` (from `body-layer/`) clean;
aircraft-layer 109 passed unchanged, ruff format/check clean, `mypy src --strict` clean.

### Final Verdict
APPROVED

### Review Confidence (re-review)
Full read of both new commits' diffs, independent gate re-run, and independent reproduction of
both the fix (live vs. captured wedge divergence) and the fallback path's reachability via
`unwatch-area` (traced, not executed against a live console session) — not a re-read of the
commit message alone.
