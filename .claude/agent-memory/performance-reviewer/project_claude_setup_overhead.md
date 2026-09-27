---
name: claude-setup-overhead
description: Measured hook/context cost baseline for the Claude Code operating environment itself (not project source), as of 2026-09-27
metadata:
  type: project
---

Measured 2026-09-27 (worktree had no subproject venvs, so mypy/ruff/pytest costs are estimated
from file counts, not timed — noted per item):

- **`posttooluse-mypy.sh` (PostToolUse, `.py` Edit/Write) runs whole-subproject `mypy`, not the
  touched file** — est. 1–8s per edit depending on subproject size (aircraft-layer 46 files vs
  body-layer/world-model 116–126 files).
  **CORRECTED 2026-09-27, same day, by measurement: that estimate was ~30-70x too high.** Timed with
  the real venv, whole-of-`body-layer/src` (52 files) with a warm `.mypy_cache` is **110ms**, and a
  single-file invocation is **also 110ms** — mypy's incremental cache sets the price, not the file
  count, so narrowing the check to the edited file saves nothing and would lose errors in files that
  import it. The recommendation to scope it was therefore dropped rather than applied.
  **The lesson is about method, not mypy:** the estimate was derived from file counts because no venv
  was available, was labeled "estimated", and was still wrong by more than an order of magnitude —
  file count does not predict cost for any incrementally-cached tool. When a venv is missing, the
  cheap move is to ask for one or say the number is unavailable, not to model it from what can be
  counted. Also only covers world-model/aircraft-layer/body-layer —
  audio-adapter, brain-layer, mission-interpreter get zero post-edit mypy signal (same
  hardcoded-three-of-six staleness pattern root CLAUDE.md already documents elsewhere;
  `commit-quality-gate.sh` already fixed this via `[ -d src ] && [ -d tests ]` discovery,
  `posttooluse-mypy.sh` and `push-roadmap-gate.sh` did not).
- **Inline PreToolUse Bash safety checks (reset-hard/graphify-query/branch-rule) + `build-filter.sh`**
  measured 8–14ms each via bash+jq spawn; ~35–55ms per Bash call combined. Cheap relative to a
  turn; not worth consolidating (each guards a distinct documented incident).
- **`body-layer/CLAUDE.md` is 96,947 bytes (~24.2K tokens)** — larger than root CLAUDE.md+AGENTS.md
  combined (36,194B) and larger than the other five subproject CLAUDE.md files combined. Largest
  single fixed-context contributor found in the whole setup. Worth a content pass by whoever owns
  it, not a mechanical trim — did not assess what's cuttable.
- **UserPromptSubmit role-sequence reminder hook has no session-marker gate** (unlike
  `session-start.sh`, which does) — injects ~170 tokens identically on every single turn, pure
  duplication of AGENTS.md content already in context after turn 1.
- Agent-dispatch fixed overhead (root CLAUDE.md+AGENTS.md + subproject CLAUDE.md + role file + role's
  own MEMORY.md) is roughly 20K–40K tokens per dispatch before any task reading — structural cost of
  the worktree-isolated role-sequence model, ×5–6 dispatches for a full "new feature" sequence. No
  cheaper alternative without weakening isolation; not a finding, just a sizing note for next time.
- `commit-quality-gate.sh` already discovers subprojects dynamically (`[ -d src ] && [ -d tests ]`)
  — confirmed correctly scoped, not a hot-path cost (gated to `git commit` only via jq `if`).
  **But "correctly scoped" was not the same as "works", and this pass missed that it did not.**
  Verified 2026-09-27 in the main checkout: it invoked bare `ruff`/`mypy`/`pytest`, none of which are
  on `PATH` (each subproject keeps its own `.venv`), so every check exited **127 command not found**
  → `FAIL=1` → the gate blocked any commit touching a subproject's code, with noise instead of a
  result. It was invisible because the loop skips unless the staged diff matches a subproject prefix,
  and recent commits touched only `.claude/`, `docs/` and `todo/`. Measured cost now that it runs:
  **~12s** for body-layer (ruff+mypy+pytest, 1292 tests) — real but commit-time, so acceptable.
- **Timing a script is not the same as running it.** Both of this pass's misses on these two scripts
  share one cause: cost was reasoned about from the source text while the scripts were never executed
  against a real input. Executing `posttooluse-mypy.sh` once would have shown the 110ms; executing
  `commit-quality-gate.sh` once with a subproject path staged would have shown the 127s. For a hook,
  "run it with a synthetic payload" is the first step, not the last.
- Tool resolution is a standing trap in this repo: `ruff`/`mypy`/`pytest` live only in
  `<subproject>/.venv/bin/`, and `mypy`'s config discovery is **CWD-only** (run from repo root it
  silently drops `strict` and `mypy_path` and reports phantom import errors — reproduced on
  body-layer: 6 errors from root vs. clean from inside). `check` and `dod-check` already handled both;
  `commit-quality-gate.sh` and `posttooluse-mypy.sh` did not until 2026-09-27. Now recorded in root
  CLAUDE.md's "Subprojects" section so it is findable without reading four scripts.
