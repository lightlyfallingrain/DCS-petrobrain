## General Rules

- Follow `CLAUDE.md` as the primary project contract.
- **"Side quests"** — a non-code or cross-cutting update that is not part of the milestone
  currently in progress on the active feature branch (skill/config edits, backlog notes,
  cross-milestone bookkeeping, workflow-doc fixes like this one) — go through a disposable
  `git worktree` checked out on `main`, commit and push there, then remove the worktree. Do not
  make them in the active feature branch's working directory. Two independent reasons converge on
  this: (1) it keeps a feature branch's history to that feature's own work, not bundled with
  unrelated bookkeeping; (2) role-sequence agents (Architect/Implementer/Reviewer/DoD) run in that
  same working directory without worktree isolation by default, so any `git` operation there while
  one is active risks racing it — a stray commit can sweep up another agent's staged-but-uncommitted
  work. See `.claude/skills/merge.md` for the same worktree pattern applied to merging a finished
  branch into `main`.
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

Full sequences below include Security and Performance Reviewer. **Check the project's
`CLAUDE.md` "Agents" section first — it may currently exempt one or both roles for this
project phase; that exemption overrides the sequences shown here rather than being restated
per-sequence.**

- **New feature**: Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance-sensitive feature**: Architect → Security (plan review) → Implementer → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Bug fix**: Debugger → Reviewer → Security (deep analysis) → **Definition of Done**
- **Performance issue**: Debugger → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**
- **Refactor**: Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**

---

## Auto-Advance

Once a role sequence starts, move to the next stage automatically — do not stop to ask "should I proceed?" between stages. Reviewer → Implementer is a loop: if Reviewer finds required fixes, hand back to Implementer and continue the loop until Reviewer approves, then proceed to DoD without asking.

Only stop and hand control to the user mid-sequence when one of the Escalation Rules below applies, or a step genuinely needs the user's own input, verification, or perception (e.g. live DCS acceptance testing, a judgment call only the user can make). Otherwise keep going through Architect → Implementer → Reviewer → (loop) → DoD in one continuous run.

---

## Escalation Rules

Stop and ask the user when:
- two reasonable architectural approaches exist and `CLAUDE.md` does not decide between them
- a new dependency seems necessary
- the feature is much larger or smaller than expected
- existing tests must be rewritten rather than extended
- the requested change conflicts with project invariants

When multiple reasonable technical approaches exist and none of the above apply, pick one and proceed — do not escalate — if the tradeoff is **local, reversible, and does not materially affect** product behavior, future architecture, dependencies, cost, or risk. State which approach was chosen and why in the plan or commit, so the user can revisit it later if needed. Escalate only when a decision is consequential, difficult to reverse, or there is genuine ambiguity about expected behavior.

---

## Final Principle

Roles are there to improve judgment, not to simulate a company org chart.
If a role does not add clarity, do not invoke it explicitly.
