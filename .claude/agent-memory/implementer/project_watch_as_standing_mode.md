---
name: watch-as-standing-mode
description: Watch became a second cancellable TaskKind alongside scan; TaskStore.create's positional area param, cancel-per-kind semantics
metadata:
  type: project
---

`plans/watch-as-standing-mode` (no plan.md -- direct orchestrator fix task) closed the
2026-09-21 sortie finding: `crew_console._handle_watch_nearest` called
`belief.tools.set_attention` directly, never creating a `belief.tasks.PendingIntent`, so
"Cancel Task" had nothing to find. Root-cause claim in the brief was verified correct by
reading the code first, not assumed.

**Shape used**: added a second `TaskKind`, `"watch_contact"`, to the *existing*
`TaskStore`/`PendingIntent` machinery rather than a parallel mechanism -- `TaskStore` already
supported multiple concurrent tasks (dict keyed by minted id); the gap was narrower than it
looked. `PendingIntent.area` became `AttentionArea | None` (`None` for watch, which has no
spatial area, only `contact_id: str | None`, new field). `TaskStore.tick` skips any task with
`area is None` -- a watch task has no success/timeout lifecycle, it just persists until
cancelled.

**Gotcha: `TaskStore.create`'s `area` param could not be given a default and reordered.**
Dozens of call sites across `tools.py`, `logger.py`, and 3 test files call it positionally as
`create(kind, area, created_sim=..., ...)`. Giving `area` a default and moving it after
`created_sim` would have silently miscompiled those into passing an `AttentionArea` object as
`created_sim`. Fix: keep `area: AttentionArea | None` as a **required positional** 2nd arg (no
default), add `contact_id` as a new trailing keyword-default param instead. Caught by
re-grepping call sites before running tests, not by a failure -- worth doing before any
"add an optional param and reorder" edit to a widely-called constructor/factory in this repo.

**Gotcha: a structural test enforces `console.py` (the debug REPL) references every public
`belief.tools` function** (`test_console.py::test_console_module_contains_no_belief_logic`,
same family as the `derived_world_position` grep trap in
[[project_pb2_stage4_tools_console]]). Adding a new public `tools.py` function
(`watch_contact_task`) without a `console.py` command broke it immediately. Fix: add the
matching debug command (`watch-task <id>`), don't just rename the function private -- it has a
real cross-module caller (`crew_console.py`).

**Cancel-per-kind design decision** (documented, not dictated by the brief): one F10 "Cancel
Task" item, no vocabulary to say "cancel the watch" specifically -> `_handle_cancel_task`
cancels every currently-*governing* kind at once (`_active_tasks_by_kind`, new helper
generalizing `logger._active_gaze`'s own "most-recent-non-cancelled-per-kind" selection),
naming each in the readback ("Copy, stopping the scan ahead and the watch."). Deliberately
narrower than "every non-cancelled task ever created" -- superseded scan_area tasks already
accumulate across a session without being cancelled (only `_active_gaze`'s tie-break stops
honouring them), so "cancel everything non-cancelled" would sweep up stale history.

Full suite stayed at baseline 877 passed/4 xfailed with zero existing tests touched; 10 new
tests added (887 passed/4 xfailed).
