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
  body-layer/world-model 116–126 files). Also only covers world-model/aircraft-layer/body-layer —
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
- No venv was present in this worktree to actually time `mypy --strict` / `ruff` / `pytest` —
  next performance review of this same setup should try to get real timings for those rather than
  re-estimating from file counts.
