---
name: bl11-round4-degrade-guard-review
description: BL-11 round 4 (feature/bl11-tick-cost) - NEEDS FIXES; brute-forcing a parent-equality claim over 840 paths, and splitting a two-assertion test to prove both halves load-bearing.
metadata:
  type: project
---

Round 4 of `feature/bl11-tick-cost` (tip `8fa2ad6`): Security findings 1 and 2 on
`logger._per_run_log_paths.resolve`. Verdict **NEEDS FIXES** — see
[[guard-widening-check-every-statement]] for the defect and why the two per-fix
counterfactuals could not see it.

Two verification techniques that paid off here and generalise:

**1. A "these are byte-identical" claim is cheap to brute-force, so brute-force it.**
The implementer swapped `stamped.parent` for `expanded.parent` in a stderr message,
claiming identity "in every pre-existing case" because `with_name` rewrites only the
final component. Rather than reason about it, I generated 780 paths from
`itertools.product({"", ".", "..", "a", "b.c", "~", "/", " ", "x."}, repeat=1..3)` joined
by `/`, plus 60 hand-picked adversarial spellings, and compared the two parents on every
one that did not raise. Zero differences — and the *reason* checked out too
(`with_name` is `self.parent / newname`). Ten lines of script, and it converts "sounds
right" into a number. Do this whenever a review asks "is X always equal to Y".

**2. A test with two assertions needs each one run alone to know which is load-bearing.**
The tilde test asserted both `trace == home/...` and `list(cwd.iterdir()) == []`. Under
the counterfactual the *first* trips, so the second never executes and looks decorative.
Copying the test into a temp file with only the second assertion showed it fails on its
own with `[PosixPath('.../cwd/~')]` — i.e. it directly observes the defect rather than
proxying for it. The temp-file split is what distinguishes "defensive and unreached" from
"load-bearing", and `-k` cannot tell you.

Also worth keeping: the brute-force probe simultaneously *found* the required fix, because
`~nosuchuser12345/a` was in the candidate list and raised `RuntimeError` out of
`expanduser()` while everything else raised from `with_name`. The probe was written to
check an equality claim and surfaced an unhandled exception for free — adversarial inputs
in a correctness probe earn their keep twice.

Environment note for this branch's worktrees: there is no `body-layer/.venv` in an agent
worktree. Borrowing `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/{ruff,mypy,pytest}`
by absolute path with `cwd` inside the worktree's `body-layer/` resolves imports to the
worktree's own `src` **via pytest only** — `pyproject.toml`'s `pythonpath` is rootdir-
relative, so a bare `python -c "import logger"` does not work even with `PYTHONPATH` set
(it fails on world-model's `query`). Prove it with a throwaway test that prints
`logger.__file__`, which is also what catches the wrong-base-commit trap.
