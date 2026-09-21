### Implementation Summary

Fixes the 2026-09-21 sortie finding: `_handle_watch_nearest` in
`body-layer/src/belief/crew_console.py` called `belief.tools.set_attention`
directly and never created a `belief.tasks.PendingIntent`, so "Cancel Task"
had nothing to find regardless of the earlier scan-side standing-mode fix
(`plans/detection-cones-slice2/implementation.md`'s note). This closes that
gap: watch is now a cancellable standing mode that coexists with scan, and
"Cancel Task" ends every currently-governing mode (not just one) since
there is no vocabulary to say "cancel the watch" specifically.

No `plans/watch-as-standing-mode/plan.md` exists — this came directly from
the orchestrator with an investigation brief, not an Architect plan, so
there was no test-impact list to check against Stage 0. The investigation
step (reading `belief/tasks.py`, `belief/tools.py`, `belief/crew_console.py`,
`logger.py`'s `_active_gaze`) confirmed the finding's stated root cause was
correct for the watch half, and additionally found the multiplicity gap
described below, which the finding's "check what TaskStore/`_active_gaze`
assume about multiplicity" pointer anticipated but did not fully specify.

### Design decisions

**`PendingIntent` gains a second `TaskKind`, `"watch_contact"`, rather than
a parallel mechanism.** `TaskStore`, `PendingIntent`, `cancel_task`, and
`logger._active_gaze` already existed and already handled multiple
concurrent tasks (a dict keyed by minted id) — the gap was narrower than a
new store: `_handle_watch_nearest` never called into any of it.
`PendingIntent.area` becomes `AttentionArea | None` (`None` for
`watch_contact` — a watch has no spatial area, only a `contact_id`) and
gained a new `contact_id: str | None` field. `TaskStore.tick` skips any
task whose `area is None` — a `watch_contact` task has no success/timeout
lifecycle at all; watching does not "succeed" or "time out," it just
persists until explicitly cancelled. `TaskStore.create`'s `area` parameter
stays a **required, positional** second argument (not given a default)
specifically because dozens of existing call sites across `tools.py`,
`logger.py`, and the test suite already call it positionally as
`create(kind, area, ...)`; `contact_id` was added as a new trailing keyword
default instead, so no existing call site needed touching.

**`belief.tools.watch_contact_task`** composes `set_attention` +
`tasks.create`, mirroring `scan_area`'s own "one command, two existing
registries" pattern. `belief.tools.cancel_task` now also returns a
`watch_contact` task's contact to `"normal"` attention on cancel (parallel
to how it already removed a `scan_area` task's `AttentionArea`).

**Cancel semantics: "Cancel Task" cancels every currently-governing kind at
once, one cancel per kind, never a bare "most recent overall."** There is
exactly one F10 "Cancel Task" item and no voice vocabulary to disambiguate
"cancel the scan" from "cancel the watch," so guessing which one kind the
player meant (or picking the single most-recently-created task across
kinds, which could silently leave the other running) seemed less
predictable than ending everything currently commanded and naming each
thing stopped in the readback. "Currently governing" is deliberately
narrower than "every non-cancelled task ever created": `scan_area` tasks
already accumulate in `TaskStore` across a session without being
cancelled when superseded (only `logger._active_gaze`'s own "most recent
wins" tie-break stops honouring the old one for gaze) — treating every
merely-superseded task as "active" would make one Cancel Task press
cancel a whole session's worth of stale scans. `_active_tasks_by_kind`
(new, in `crew_console.py`) generalises `_active_gaze`'s own
"most-recent-non-cancelled-per-kind" selection to any kind, and
`_handle_cancel_task` cancels exactly that set. This is a designed choice,
not something the finding dictated outright — flagged here per the task's
own "decide and document" instruction.

A `watch_contact` task's cancel readback is always the fixed phrase "the
watch" (never the contact's id or type), matching `render_cancel_readback`'s
existing "no ids in speech" rule and the terseness of the scan fallback's
own bare "the scan". Multiple cancelled kinds join with a plain "and"
(`_join_task_descriptions`) — e.g. "Copy, stopping the scan ahead and the
watch."

**`logger._active_gaze` is unaffected by `watch_contact` tasks** — it
already filtered on `kind == "scan_area"`; only a `task.area is not None`
null-check was added since `area` is now optional in the type.

### Files Changed

- `body-layer/src/belief/tasks.py` — `TaskKind` gains `"watch_contact"`;
  `PendingIntent.area` becomes `AttentionArea | None`, gains `contact_id:
  str | None`; `TaskStore.tick` skips any task with no `area`.
- `body-layer/src/belief/tools.py` — new `watch_contact_task` (composes
  `set_attention` + `tasks.create`); `cancel_task` now also clears a
  `watch_contact` task's attention mark, guarded for `area is None`.
- `body-layer/src/belief/crew_console.py` — `_handle_watch_nearest` now
  registers a `watch_contact` task via `watch_contact_task` when
  `self.tasks` is configured (falls back to the old direct `set_attention`
  call otherwise, same graceful-degradation shape as a missing
  `enrichment`); `_describe_task_for_speech` gains a `"watch_contact"` ->
  `"the watch"` branch; `_handle_cancel_task` rewritten to cancel every
  currently-governing kind (`_active_tasks_by_kind`, new module-level
  helper) instead of only the single most-recently-created task; new
  `_join_task_descriptions` helper for the multi-kind readback.
- `body-layer/src/belief/console.py` — new debug command `watch-task <id>`
  -> `tools.watch_contact_task`, added so the structural test
  (`test_console_module_contains_no_belief_logic`, which asserts every
  public `tools.py` function is referenced from `console.py`) stays
  satisfied; `_format_task_line` now branches on `area`/`contact_id`
  depending on which is populated.
- `body-layer/src/logger.py` — `_active_gaze` gains a `task.area is not
  None` guard (docstring note only; behaviour unchanged, `kind ==
  "scan_area"` already excluded `watch_contact` tasks).
- `body-layer/tests/test_tasks.py` — two new tests for the `watch_contact`
  kind's tick/cancel behaviour.
- `body-layer/tests/test_tools.py` — three new tests for
  `watch_contact_task`/`cancel_task`'s composing behaviour.
- `body-layer/tests/test_crew_console.py` — six new tests: the sortie's
  root-cause regression, the graceful-degradation fallback, scan+watch
  coexistence, and multi-kind cancel (including that a superseded scan is
  not swept up alongside a genuinely active one).

### Tests Added

- `test_tasks.py::test_watch_contact_task_never_resolves_via_tick` —
  `tick` leaves a `watch_contact` task `"pending"` regardless of contacts
  appearing or the deadline passing.
- `test_tasks.py::test_watch_contact_task_is_cancellable` — baseline
  cancel behaviour for the new kind.
- `test_tools.py::test_watch_contact_task_marks_watched_and_registers_a_task`
  — the composing function's happy path.
- `test_tools.py::test_watch_contact_task_returns_none_for_unknown_contact`
  — no task registered for a nonexistent contact.
- `test_tools.py::test_cancel_task_on_a_watch_contact_task_returns_attention_to_normal`
  — cancel undoes the watch mark.
- `test_crew_console.py::test_watch_nearest_registers_a_cancellable_task` —
  the finding's stated root cause, fixed.
- `test_crew_console.py::test_watch_then_cancel_task_stops_the_watch` —
  the sortie's own scripted sequence, now working.
- `test_crew_console.py::test_watch_nearest_without_tasks_still_falls_back_to_a_bare_mark`
  — graceful degradation without a `TaskStore` configured.
- `test_crew_console.py::test_scan_and_watch_coexist_and_cancel_task_stops_both`
  — the full finding: scan ahead + watch closest both active, one Cancel
  Task ends both and names both.
- `test_crew_console.py::test_cancel_task_only_cancels_the_newest_task_per_kind`
  — a superseded scan is left untouched (`status == "pending"`) while the
  newest scan and the watch are both cancelled.

### Checks

(body-layer/, the only subproject touched)

- ruff format --check: pass
- ruff check: pass
- mypy src (`--strict`, run from `body-layer/`): pass, 0 errors
- pytest -q: pass, 887 passed, 4 xfailed (baseline was 877 passed, 4
  xfailed; 10 new tests added, no existing test modified)

### Notable Discoveries

- The finding's root-cause claim for the watch half was correct as stated:
  `_handle_watch_nearest` really did call `set_attention` directly with no
  `PendingIntent` at all, confirmed by reading the code before designing
  anything.
- `TaskStore.create`'s `area` parameter could not simply be given a
  default and reordered — every existing call site across `tools.py`,
  `logger.py`, and three test files calls it positionally as `(kind, area,
  ...)`. The first attempt (moving `area` to a trailing keyword-with-
  default) would have silently miscompiled several of those calls into
  passing an `AttentionArea` object as `created_sim`. Caught by re-checking
  call sites before running tests, not by a test failure.
- A structural test in `test_console.py`
  (`test_console_module_contains_no_belief_logic`) asserts every public
  `belief.tools` function is referenced somewhere in `console.py`'s
  source — adding `watch_contact_task` to `tools.py` without a
  corresponding `console.py` command failed that test. Fixed by adding a
  `watch-task <id>` debug command to `console.py`, which also gives a
  developer a way to exercise the new machinery from the debug REPL
  without going through F10/crew-text.
- `body-layer/CLAUDE.md`'s `belief/tasks.py`/`belief/tools.py`/
  `belief/crew_console.py`/`belief/console.py` Structure entries describe
  the pre-fix shape (`TaskKind` as a single-value `Literal`, `cancel_task`
  as "most-recently-created" rather than per-kind) and were not updated as
  part of this change — that file is very large and its own convention is
  hand-maintained prose describing the code as of the last touching
  change; flagging as a known follow-up rather than doing a large doc
  rewrite outside this task's stated scope.
