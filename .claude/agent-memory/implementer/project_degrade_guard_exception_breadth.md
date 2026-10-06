---
name: degrade-guard-exception-breadth
description: A stated degrade policy is only as wide as its except clause and as what sits inside the try — check both, and probe the degenerate inputs.
metadata:
  type: project
---

A "this degrades rather than crashing" guarantee in a docstring is two separate
claims about the code: **which exceptions the `except` names**, and **which
statements are inside the `try`**. BL-11 Stage 5 got both wrong in one closure —
`per_run_log_path` was called on the line *above* the `try:`, and the guard was
`except OSError`, while `Path.with_name` raises **`ValueError`** for an empty
final component. `--detection-trace .` therefore killed `main()` with a
traceback, through the exact path a docstring promised would cost "the sortie
its trace, not its crew".

**Why:** Security found it by probing the degenerate inputs directly rather than
reading the guard, which is the only thing that would have found it — the code
reads correctly if you assume `pathlib` raises `OSError` family errors, and it
mostly does.

**How to apply:** whenever a function's contract is "degrade, never raise", list
the degenerate inputs explicitly (for a path: `.`, `/`, `""`, a trailing slash,
`~`) and run them. Then check that the call that can raise is actually *inside*
the `try` — a raise one line above the guard is invisible when reading the
guard. When widening a guard, also check whether any name used in the handler's
own message is bound only by the statement that raised (`stamped.parent` was);
reach for a value computed before the `try` instead.

Related: [[feedback_verify_state_not_the_account_of_it]] is the general form —
here the "account" was the docstring and the "state" was the except clause.
Three `pathlib` facts worth not re-deriving: `Path` never expands `~`,
`Path("logs/").name` is `"logs"` (a trailing slash is *not* an empty name), and
`with_name` rewrites the last component whatever it is, so `logs/` becomes a
*file* `logs-<stamp>` beside the directory.
