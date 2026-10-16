---
name: feedback_worktree_no_venv
description: An isolated worktree has no subproject .venv of its own — run the main checkout's venv binaries with cwd inside the worktree's subproject dir rather than treating a missing .venv as a blocker.
metadata:
  type: feedback
---

A fresh `isolation: "worktree"` checkout does not get its own `<subproject>/.venv` — it is
gitignored, so the worktree starts without one. `body-layer/.venv/bin/python` (or any
subproject's) does not exist inside the worktree at all (BL-B77, 2026-10-16).

**What works:** invoke the *main checkout's* venv binary directly, with `cwd` set inside the
*worktree's* subproject directory — e.g.
`cd <worktree>/body-layer && /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python -m mypy src`.
mypy's CWD-only config discovery (root `CLAUDE.md`, "Subprojects") still resolves against the
worktree's own `pyproject.toml`/`mypy_path`, since that is a property of the current working
directory, not of which `site-packages` the interpreter was built against. Same for `ruff`/
`pytest` via `-m`.

**Why not create a venv in the worktree instead:** slower (full reinstall per worktree) and this
project's own Bash sandboxing already makes long-running installs awkward; the cross-checkout
invocation is immediate and costs nothing extra, since the two trees share the same dependency
versions by construction (same repo, same `pyproject.toml` at the base commit).

**How to apply:** before reporting a venv/tool as "not on PATH" and escalating, try the sibling
checkout's `.venv/bin/<tool>` with `cwd` inside the worktree first — it is very likely to just
work, and is far cheaper than standing up a parallel venv.
