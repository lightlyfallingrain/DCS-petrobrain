---
name: feedback-agent-memory-path-recurrence
description: implementer has written agent-memory files under world-model/.claude/agent-memory/ instead of top-level .claude/agent-memory/ at least twice (f7a7ec1, M5 Stage 5) — flag this explicitly in future reviews rather than treating each occurrence as a one-off
metadata:
  type: feedback
---

The repo's agent-memory convention is top-level `.claude/agent-memory/<role>/`, not
`<subproject>/.claude/agent-memory/<role>/`. The implementer has written to the wrong
(subproject-relative) path at least twice: commit `f7a7ec1` ("Relocate reviewer/implementer
memory written to wrong path") and again in M5 Stage 5 (fixed by the orchestrator in
`ac6768c`/`63760b1`). Both times the fix itself was clean (files relocated, index folded in, no
stray directory left behind) — the problem is the mistake recurring, not the fix quality.

**Why:** subproject working directories (`world-model/`) each ship their own nested `CLAUDE.md`,
and an agent operating with cwd inside `world-model/` can plausibly infer "write relative to
here" for anything without an absolute-path convention stated at the point of use. Agent-memory
path is exactly this kind of thing — stated once at the top level, easy to lose track of from
inside a subproject.

**How to apply:** when reviewing any commit that touches `.claude/agent-memory/`, check the
actual path prefix is `.claude/agent-memory/<role>/` (repo root), not
`world-model/.claude/agent-memory/<role>/` or any other subproject-relative variant. If it
recurs a third time, recommend escalating beyond a per-incident fix — e.g. a stated path line in
the implementer role definition itself, or a pre-commit check that rejects a
`*/.claude/agent-memory/` path that isn't rooted at the repo top level.
