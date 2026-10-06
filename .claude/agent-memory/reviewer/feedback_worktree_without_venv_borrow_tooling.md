---
name: worktree-without-venv-borrow-tooling
description: An agent worktree has no .venv; borrow the main checkout's tool binaries but keep cwd in the worktree, then prove imports resolve to the worktree's own src.
metadata:
  type: feedback
---

A fresh agent worktree contains no `<subproject>/.venv` — it is gitignored, so it does not come
across. `.venv/bin/ruff` etc. simply do not exist there, which reads at first glance like "the checks
cannot be run from here".

**Why:** the venv is per-clone build state, not tracked content. Creating one costs a full dependency
install for a read-only review.

**How to apply:** invoke the **main checkout's** binaries by absolute path while keeping `cwd` inside
the **worktree's** subproject directory, e.g. from
`<worktree>/body-layer/`: `/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/mypy src`. `mypy`'s
CWD-only config discovery then finds the worktree's own config, `ruff` reads the worktree's own
`pyproject.toml`, and `pytest`'s `[tool.pytest.ini_options] pythonpath` resolves against the
worktree's rootdir.

**But prove it, every time, because this is precisely AGENTS.md rule 4's trap wearing a different
hat** — borrowed tooling from another checkout is exactly how you end up verifying the wrong tree.
One command settles it:

```sh
<main>/body-layer/.venv/bin/python -c "import sys; sys.path.insert(0,'src'); \
import belief.contacts as m; print(m.__file__)"
```

The path printed must be under the worktree. (Expect a `ModuleNotFoundError: query` from that bare
invocation — body-layer needs `../world-model/src` on the path too, which pytest adds and this probe
does not. The traceback still prints the resolved file paths, which is all the probe is for.)

Two further notes: a compound command that builds a tool path in a shell variable is **refused** in a
worktree ("name computed at runtime … cannot be shown not to be git") — write the absolute path
literally, one command per call. And `git show <ref>:<path>` to read a file from another ref is also
refused here as a shared-resource modification; read from the working tree instead, which is fine
when the branch is based on current `main`.
