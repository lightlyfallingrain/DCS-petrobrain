---
name: done
description: Run the Definition of Done checklist for the project
type: user-invocable
---

Run the full Definition of Done quality gate. Ask the user for the feature name if not provided,
then:

1. Run `/dod-check <feature-name>` — executes every mechanical check (per-subproject ruff format,
   ruff check, mypy `--strict`, pytest, staging state) and outputs a structured pass/fail report.
2. Check the working tree: `git status --short` must be clean, with every new or modified file
   committed. Root `CLAUDE.md`'s Definition of Done makes this explicit — no task, bug or feature is
   complete with uncommitted work, and build artifacts or gitignored output must never be staged.

Read the report. Then:

- **All pass** — declare the feature complete, name the branch the user should test, and point at
  its acceptance card (`docs/acceptance/`) before merging with `/merge <branch>`.
- **Any FAIL** — stop, list each failure, and do not proceed.

Print the verdict as **PASS** (all criteria met) or **FAIL** followed by the failing items only.

**There is no separate build step, and that is not an omission.** The template had one
(`{{BUILD_COMMAND}}`: `cargo build --release`, `npm run build`); Python has no build artifact this
project ships, so the compile-equivalent is `mypy --strict`, which step 1 already runs per
subproject. The one thing a Python-only gate would miss is the Lua that runs inside DCS —
`commit-quality-gate.sh` syntax-checks staged `aircraft-layer` Lua with `luac5.1 -p`, so it is
covered at commit time rather than here.

**Verification runs from inside each subproject**, never from the repo root: each keeps its own
`.venv` and `ruff`/`mypy`/`pytest` are generally not on `PATH`, and mypy's config discovery is
CWD-only, so `mypy body-layer/src` from the root silently drops `strict` and reports phantom import
errors. `/dod-check` resolves `<subproject>/.venv/bin/<tool>` for this reason.

**If this runs in a worktree, check what is actually checked out first.** A worktree based on `main`
while the branch under gate sits in the main checkout will test `main`'s code and report a plausible
pass — it has happened, with pytest reporting exactly `main`'s baseline count. `git rev-parse HEAD`
against the tip the task named, before anything else.
