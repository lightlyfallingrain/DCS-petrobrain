---
name: feedback_agent_memory_path
description: Always write implementer agent memory to the top-level .claude/agent-memory/implementer/ path, never a world-model/-nested copy.
metadata:
  type: feedback
---

Implementer agent memory lives at the repo-root
`/Users/sg/Code/DCS-petrobrain/.claude/agent-memory/implementer/` — never at a
`world-model/.claude/agent-memory/implementer/` path, even though most implementer work in
this project happens inside `world-model/`.

**Why:** This exact mistake (writing memory into a `world-model/`-nested `.claude/agent-memory/`
directory instead of the top-level one) happened twice during the M5 milestone — once in a
Stage-3-era commit and again in Stage 5 — and both times it was caught and fixed by the
orchestrating session, not by the implementer agent itself.

**How to apply:** Before writing any memory file, sanity-check the path starts with
`/Users/sg/Code/DCS-petrobrain/.claude/agent-memory/implementer/`, not a subproject-relative
variant. This is easy to get wrong specifically because the *code* work is scoped to
`world-model/` (cwd habits, mypy/pytest invocation paths documented in
`project_worldmodel_mypy_path_cwd.md`), but agent memory is repo-root-scoped regardless of
which subproject the task touches.
