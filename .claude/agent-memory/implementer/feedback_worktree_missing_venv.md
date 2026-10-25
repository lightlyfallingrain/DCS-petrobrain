---
name: worktree-missing-venv
description: a fresh git worktree has no .venv (gitignored, not shared) -- invoke the main checkout's venv by absolute path rather than symlinking
type: feedback
---

A git worktree created for an agent (e.g. `.claude/worktrees/agent-<id>/<subproject>/`) has no
`.venv` -- each subproject's venv is gitignored and lives only in the checkout it was created in,
so a fresh worktree is missing it entirely. `ruff`/`mypy`/`pytest` commands that assume
`.venv/bin/<tool>` exists will fail with "no such file or directory".

**Do not symlink `.venv` into the worktree.** `git check-ignore` does not match a symlink against
a trailing-slash gitignore pattern (`.venv/`), even when the pattern is present and would match a
real directory -- so a symlinked `.venv` shows up as an untracked, non-ignored path and risks being
swept into a commit by a broad `git add`.

**How to apply:** invoke the main checkout's venv binaries by absolute path instead, e.g.
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python -m pytest tests/ -q` run with `cwd` set
to the worktree's own subproject directory (so `pyproject.toml`'s `pythonpath`/`mypy_path` resolve
correctly against the worktree's own source tree, not the main checkout's). Confirmed this works
cleanly for `pytest`/`python -c` against a real venv (python3.14, pyproj/numpy importable) without
creating any new file in the worktree. The main checkout's venv path is stable for the session;
mint it by substituting the worktree's subproject dir for the main repo root's subproject dir.
