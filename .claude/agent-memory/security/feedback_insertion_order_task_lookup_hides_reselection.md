---
name: insertion-order-task-lookup-hides-reselection
description: a "find the active task of kind X" helper that does next(t for t in tasks if t.kind==X and not cancelled) returns the OLDEST match in an insertion-ordered store -- re-selecting a different target without cancelling the old one silently keeps operating on stale state while readbacks confirm the new one
metadata:
  type: feedback
---

Found in `plans/attack-run/plan.md` (BL-14) deep security review, 2026-10-14.
`belief.tasks.TaskStore.tasks` is explicitly "every task, insertion order," and helpers like
`CrewConsole._active_attack_target_task` resolve "the current X" via
`next(task for task in tasks if task.kind == "X" and task.status != "cancelled")`. Any command
handler that mints a *new* same-kind task without first cancelling the existing one (e.g.
`_handle_select_target`/`_handle_engage`'s descriptor branch calling `tools.attack_target_task`
unconditionally) leaves two active tasks of the same kind, and every reader of "the active one"
silently keeps resolving to the **older** task — not the one the player just selected, even though
the readback for the new selection already spoke as if it had taken effect.

This is a real, reachable defect (no malicious input needed, just two ordinary voice commands with
no intervening cancel) whenever a "standing singular selection" concept (only one of kind X should
ever be meaningfully active) is implemented on a store designed for "many simultaneous X" (e.g.
`watch_contact`, where multiple active watches are intentional). The store's shape is correct for
the many-at-once case; it silently breaks the singular case unless the creating code explicitly
cancels/supersedes the prior one, or mutates the existing task's fields in place (the way
`_handle_step` already does: `target_task.contact_id = next_id`) rather than minting a new task.

**How to apply:** whenever a plan introduces a new standing/singular-selection concept (task,
mode, mark) built on an existing append-only or insertion-ordered store that other kinds already
use for a many-at-once concept, check every creation path for that new kind: does it cancel/replace
the prior active one, or does repeated selection leave two (or more) simultaneously "active" by the
store's own status field? A missing test exercising "select X, then select Y without cancelling"
is the tell — if the plan's or implementation's own test file has no such case, assume it was never
exercised.
