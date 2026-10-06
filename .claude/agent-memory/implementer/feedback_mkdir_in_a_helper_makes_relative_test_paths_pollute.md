---
name: mkdir-in-a-helper-makes-relative-test-paths-pollute
description: Adding a mkdir to a path-resolving helper silently turns existing tests' relative paths into untracked directories in the CWD — reroot them onto tmp_path.
metadata:
  type: feedback
---

When you add a `parent.mkdir(...)` to a function that previously only *computed*
paths, re-read every existing test that calls it. Tests that passed bare relative
paths (`logs/trace.jsonl`) will now create directories in whatever directory
pytest was started from, without a single assertion changing. Reroot them onto
`tmp_path`.

**Why:** BL-11 post-review fix 2 added a `mkdir` to `logger._per_run_log_paths`
so a gitignored `logs/` could not crash the crew at startup. Two tests added two
commits earlier passed `Path("logs/trace.jsonl")`. Both still passed — and both
now deposited an untracked `logs/` at pytest's CWD. The documented command is
`pytest body-layer/tests -q` from the repo root, whose `.gitignore` does **not**
cover `logs/` (only `body-layer/.gitignore` does), so the suite would have
littered the repo root. Worse, per `AGENTS.md` rule 1 an untracked file makes
`git worktree remove` refuse — so a later, unrelated agent's harvest would have
failed for a reason nothing connected to this change. No check reports this:
format, lint, mypy and pytest all pass.

**How to apply:** any time a helper gains a filesystem side effect, grep its
test callers for relative paths before running the suite, and check
`git status --porcelain --untracked-files=all` **after** a full run rather than
only before. Also check whether the directory is gitignored at the level pytest
actually runs from, not just inside the subproject.

Related: [[feedback_verify_full_suite_not_just_new_files]] — same shape, a check
passing while the repo state quietly drifts.
