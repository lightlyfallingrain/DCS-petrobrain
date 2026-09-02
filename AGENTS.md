## General Rules

- Follow `CLAUDE.md` as the primary project contract.
- Prefer the simplest solution that satisfies correctness, performance, and architectural clarity.
- Do not switch roles unnecessarily mid-task.
- For small features, one role may handle the whole task.
- For complex features, use the appropriate role sequence:
  1. Architect
  2. Implementer
  3. Reviewer
  4. Debugger (if needed)

Full per-role responsibilities, priorities, checklists, and output-style detail: `docs/AGENT_ROLES.md` (read when tuning a role or unsure what it should/must not do).

---

## Roles (one-liners)

1. **Architect** — plan new features, module boundaries, design tradeoffs. Writes `plans/<featurename>.md`.
2. **Implementer** — writes code for an approved plan, adds tests, straightforward refactors.
3. **Reviewer** — reviews completed work against the plan and `CLAUDE.md` before handoff.
4. **Debugger** — bugs, regressions, unexpected behavior. Reproduce → isolate → fix → verify.
5. **Performance Reviewer** — runtime cost risk on hot paths / data-intensive changes.
6. **Security** — plan review (after Architect) and deep analysis (after Reviewer, before DoD); on-demand full audits.
7. **Definition of Done** — final gate: checks pass, acceptance testing with user, harvest NOTES.md.

---

## Recommended Role Sequences

- **New feature**: Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance-sensitive feature**: Architect → Security (plan review) → Implementer → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Bug fix**: Debugger → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance issue**: Debugger → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Refactor**: Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**

---

## Escalation Rules

Stop and ask the user when:
- two reasonable architectural approaches exist and `CLAUDE.md` does not decide between them
- a new dependency seems necessary
- the feature is much larger or smaller than expected
- existing tests must be rewritten rather than extended
- the requested change conflicts with project invariants

---

## Final Principle

Roles are there to improve judgment, not to simulate a company org chart.
If a role does not add clarity, do not invoke it explicitly.
