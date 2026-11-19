---
name: worktree-may-lack-venvs
description: a freshly-created agent worktree can have no .venv at all for a subproject even though other, older worktrees do -- check before assuming the dispatching instructions' venv paths exist, and build from pyproject.toml's own declared deps if missing.
metadata:
  type: feedback
---

On the BL-16 mode-1 batch dispatch, the assigned worktree
(`.claude/worktrees/agent-a590dbe227742313f`) had **no `.venv` for either `body-layer` or
`aircraft-layer`** -- `ls .venv/bin` failed outright for both, while other, older agent worktrees
created around the same time (`agent-aa23e7ed329b74376` etc.) did have them. Not something to
silently work around and not mention: it's worth flagging in the Implementer's report, since it
suggests the worktree-creation step doesn't always carry venvs forward (or copy-on-write them)
consistently.

**How to apply:** if `<subproject>/.venv/bin/python` doesn't exist, don't assume the dispatching
instructions' exact commands will work — check first (`ls <subproject>/.venv/bin`), and if
missing, build it yourself: `python3 -m venv <subproject>/.venv`, then `pip install` the exact
versions named in that subproject's own `pyproject.toml` `dependencies` list plus `mypy`/`ruff`/
`pytest` (no version pins needed for those three unless the project pins them elsewhere — check an
existing sibling worktree's `pip list --format=freeze` if one is reachable, to match versions
closely). Report that you had to do this and why, in one line, so the pattern gets noticed if it
recurs.
