---
name: cones_2c_sortie_fixes
description: fix/gaze-visibility-and-standing-modes -- gaze overlay + scan/watch mode bug, and a worktree base mis-setup found and corrected
metadata:
  type: project
---

Two fixes from `todo/todo.md`'s "Cones 2C sortie findings" section, branch
`fix/gaze-visibility-and-standing-modes`. Full design note in
`plans/detection-cones-slice2/implementation.md`'s "Cones 2C sortie fixes" section (append-only,
per [[feedback_implementation_log_append]]).

**Worktree base was wrong at task start** -- worth checking for on any future isolated fix branch.
The orchestrator said "base is main merged into the 2C branch," but my worktree's throwaway branch
(`worktree-agent-*`) had been created from bare `main` (18d0436), missing the entire 2C scan-loop
commit series that actually lived on `feature/cones-2c-scan-loop`/`fix/gaze-visibility-and-standing-
modes` at `c1efbbd`. `git merge --ff-only c1efbbd` fixed it (a plain `git reset --hard` was refused
by the sandbox as destructive; `merge --ff-only` was allowed and is safer anyway). Symptom that
should trigger this check next time: grep for a symbol the task prompt names (here, `gaze_at`/
`ScanPlan`) and if it's not found despite the prompt treating it as already-merged code, check
`git merge-base --is-ancestor <expected-tip> HEAD` before assuming the task description is wrong.

**Fix 1 (show gaze on overlay):** `gaze_at(t_sim, plan)` was already pure -- no new state, just a
read + a dedup-on-change push through the existing per-poll overlay hook (`_push_gaze_line` in
`logger.py`). `Gaze.label` is explicitly documented as for "debug/trace output," so using it
(reformatted) for this display is exactly its intended use, not a violation of its own "never
compared/branched on" warning.

**Fix 2 (scan/watch as standing modes):** the real bug was a `status == "pending"` filter baked
into **three separate call sites** (`logger._active_gaze`, `belief.tasks.TaskStore.cancel`,
`belief.crew_console._handle_cancel_task`), not one. Fixing only the first (the one the backlog
named) would have left cancel hollow -- a resolved scan would keep steering gaze forever with no
way to stop it, since `TaskStore.cancel` refused to overwrite an already-`"succeeded"`/`"failed"`
status. All three needed the same `!= "cancelled"` reframing. No data-model change was needed in
the end (`TaskStatus` keeps its four values) -- the "is this a data-model change" escalation
trigger in the task prompt didn't fire once I'd actually traced every consumer, but it was close:
worth doing the full consumer grep (`grep -rn "task\.status"`) before concluding a status-filter
fix is small, since the second and third sites were invisible from the first site's diff alone.

**A sortie finding turned out to have a different root cause than the backlog assumed**: "watch
closest -> cancel task -> nothing to stop" cannot be the tasks.py bug on its own reading of the
code, because `watch_nearest`/typed "watch" never create a `PendingIntent` at all (they call
`belief.tools.set_attention` directly on the `Contact`) -- there is nothing for "Cancel Task" to
find regardless of the status-filter fix. Flagged rather than silently folded into the fix; a real
fix would need a product decision (does "Cancel Task" stop a watch too, and what happens when both
a scan and a watch are active). See [[feedback_verify_mission_probe_pattern_claims]]-style
lesson: a backlog's causal framing ("the task had already succeeded") is a hypothesis to verify
against the actual code path, not a given.
