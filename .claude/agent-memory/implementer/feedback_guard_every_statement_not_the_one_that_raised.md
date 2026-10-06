---
name: guard-every-statement-not-the-one-that-raised
description: When a review reports an unhandled exception, enumerate what every statement in that block can raise and guard all of them — fixing only the reported type is how the same block gets reviewed five times.
metadata:
  type: feedback
---

When a review reports an unhandled exception from a block, do not fix only the
reported exception type. **Enumerate what every statement in that block can
raise, write the enumeration down next to the guard, and make the guard cover
all of it.** Prefer a structural shape — one `try:` over the whole block, with
the caught types in a named tuple — over a second adjacent `except` clause, so
that a statement added later is inside the guard by default rather than by the
next author remembering a comment.

**Why:** `BL-11` Stage 5's eight-line `logger._per_run_log_paths.resolve` took
**five** review rounds. Round 3 guarded `OSError` from `mkdir`. Round 4 added
`ValueError` from `Path.with_name` — and in the same commit added
`path.expanduser()` *above* the `try:`, which raises `RuntimeError`, so round 5
existed solely to fix the fix. Each round's fix passed its own counterfactual.
Round 5's enumeration then found a fourth site nobody had counted
(`time.localtime` inside a helper the closure calls → `OverflowError` and
`ValueError`). Three adjacent `pathlib` calls raised three unrelated types;
nothing about reading them suggests that.

**How to apply:** the moment a fix is "add type T to this `except`", stop and
list the block's statements and each one's raises — including through helper
calls, which is where the uncounted one hid. Two signals that you are in this
situation: the docstring you are about to write states a *total* contract ("a
path that cannot be resolved degrades to `None`"), or the block is short enough
that it looks obviously complete. If the handler's message needs a value that a
guarded statement binds, bind a fallback before the `try:` and re-point it as
the body progresses — needing that value is what pushes a statement outside the
guard, which was round 4's whole defect. See
[[verify_full_suite_not_just_new_files]] and
[[feedback_revert_test_scratch_copy]].
