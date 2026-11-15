---
name: feedback-worktree-use-main-checkout-venv
description: Before building a fresh .venv in a review worktree to run format/lint/type/test, check agent memory -- other roles already solved "no .venv in a fresh worktree" by invoking the main checkout's venv binaries with cwd set inside the worktree's subproject dir.
metadata:
  type: feedback
---

On the BL-B106 (async-speech) review, `body-layer/.venv` did not exist in the review worktree (git
worktrees don't get a copy of a gitignored `.venv`). I built a fresh one from scratch
(`python3.12 -m venv .venv && pip install ruff mypy pytest pyproj numpy`) to run the required
`ruff format --check`/`ruff check`/`mypy --strict`/`pytest -q` checks myself rather than trusting
the implementer's reported numbers.

**This was the slow path.** [[feedback_worktree_no_venv]] and [[worktree-missing-venv]] (both
implementer memory, found afterward via `memory-search.py venv worktree missing`) already
establish the fast one: invoke the **main checkout's** venv binaries directly by absolute path
(`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/<tool>`), with `cwd` set inside the
**worktree's** own subproject directory. mypy's CWD-only config discovery and pytest's
`pythonpath`/`mypy_path` resolve against whatever directory the process is run from, not against
which `site-packages` the interpreter was built with -- so this runs the worktree's own code
against the main checkout's already-installed dependencies, with no install step at all.

**Why:** a fresh venv-plus-pip-install costs several minutes and a background task; the
cross-checkout invocation is immediate. The two trees share the same `pyproject.toml` at the
base commit, so there is no version-skew risk worth trading for the speed.

**How to apply:** at the start of any Reviewer (or DoD/Architect/Investigator/Security/
Performance-Reviewer) worktree pass that needs to run a subproject's own checks, search agent
memory first (`memory-search.py venv worktree`) before reaching for `python -m venv` -- the answer
is almost always "use the sibling checkout's binaries, don't build a new one."
