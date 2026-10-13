---
name: worktree-venv-borrow-also-applies-to-implementer
description: An implementer's fresh worktree also has no .venv -- borrow the main checkout's binaries by absolute path (cwd in the worktree) instead of running a fresh pip install, same as the reviewer finding this extends.
metadata:
  type: feedback
---

`.claude/agent-memory/reviewer/feedback_worktree_without_venv_borrow_tooling.md` already covers
this for read-only roles. It applies to the implementer too, and I didn't check agent memory
before discovering it the slow way on `plans/forest-occlusion/plan.md` Stages 1-2
(`feature/forest-occlusion`): built fresh `body-layer/.venv` and `world-model/.venv` with
`python3 -m venv` + `pip install -e . pytest mypy ruff`, which cost two full dependency
installs (numpy, pyproj, osmium, scipy, pillow) for work that never needed a second copy of any
of them.

**Why:** same as the reviewer's note — the venv is per-clone build state, gitignored, and does
not come across into a fresh worktree. An implementer mutates files, but `ruff`/`mypy`/`pytest`
binaries don't care which checkout they live in as long as `cwd` is the worktree's subproject
directory (`mypy`'s CWD-only config discovery) and imports resolve against the worktree's own
`src`/`../world-model/src` (via `PYTHONPATH`, which `pytest`'s own `pythonpath` config also
supplies). Running `pytest`, `mypy`, `ruff` against the worktree's source through binaries
installed in the **main checkout's** `.venv` tests and lints the worktree's own code, not the
main checkout's — the two are not the same question, and the reviewer memory's "prove it" probe
settles which one actually happened.

**How to apply next time:** before reaching for `python3 -m venv`, try
`<main-checkout>/<subproject>/.venv/bin/<tool>` from inside the worktree's own subproject
directory first. Only build a fresh venv if that main-checkout path doesn't exist either, or if
the worktree's dependencies have actually diverged from main's (a new/changed `pyproject.toml` on
the feature branch) — in which case a fresh venv is correct, not wasted, because borrowed tooling
would be testing against the wrong dependency set.

See [[worktree-without-venv-borrow-tooling]] (reviewer) for the full mechanism and the "prove the
resolved file path is under the worktree" verification step, which applies identically here.
