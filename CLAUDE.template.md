## Template Protection

Never modify `CLAUDE.template.md` without explicit user permission for each individual edit.

---

## Phrasing Convention (for whoever fills in project-specific rules below)

State prohibitions with their positive alternative: "Don't X — use Y instead," not a bare
negative. A bare "don't use `unwrap()`" leaves the replacement unstated; "don't use `unwrap()` —
use `?` or `.expect(\"reason\")` instead" is actionable on its own.

---

## Verification

Run, in order, after every code change and always before a commit:

1. `{{FORMAT_COMMAND}}`
2. `{{LINT_COMMAND}}`
3. `{{TEST_COMMAND}}`

This is the same sequence the pre-commit hook enforces mechanically — stating it here prompts
self-verification earlier, during implementation, instead of only at commit time.

---

## Session Start

1. Read `todo/todo.md`
2. Identify the next actionable milestone (first non-completed, non-deferred section with open items)
3. Show that milestone and its subitems to the user
4. Ask what they want to work on

---

## Decision Heuristics

1. Prefer stable, predictable behavior over clever optimizations
2. Prefer simple, debuggable solutions over clever ones
3. Prefer precomputation over per-request work if it reduces runtime cost
4. Avoid new abstractions unless they remove clear duplication
5. Choose solutions that can be iterated later

---

## Implementation Strategy

Build in stages: minimal working version → validate correctness → validate performance → refine.
Do not attempt final-quality implementation first.

---

## Debugging Protocol

1. Reproduce deterministically
2. Isolate subsystem
3. Add minimal instrumentation
4. Form hypothesis
5. Apply smallest fix
6. Verify
7. Remove debug code

No speculative fixes.

---

## Code Rules

Run formatter, linter, and tests before every commit.

---

## Dependencies

Prefer the existing stack. New dependencies must be justified (purpose, safety, license). Keep dependencies minimal.

---

## Definition of Done

- Feature implemented as planned
- All checks pass (format, lint, test)
- Core logic tested
- No regressions
- **All modified files committed** — run `git status` and confirm a clean working tree before declaring any task, bug, or feature complete

---

## Workflow

- One feature at a time. Commit in small logical steps.
- **Always create and checkout a feature branch before starting any implementation task.** Name the branch after the feature using kebab-case (e.g., `feature/hyg-data-pipeline`, `fix/floating-origin-precision`). Never implement directly on `master`. **Always branch from local `master`** — checkout `master` first, then create the branch. Do not use `origin/master` as the branch point.
- Do not merge without user approval.
- Before starting, surface any ambiguous, contradicting, or missing information and ask for clarification.

---

## Git Tracking

After creating any new project file, immediately `git add <file>`.
Do NOT `git add` build artifacts, generated output, or files covered by `.gitignore`.
Before stating that a task, bug, or feature is complete or fixed, run `git status` and commit all modified files. A clean working tree is required before any completion claim.

---

## Agent Roles

Read `AGENTS.md` before starting any implementation task. Follow its role sequences and escalation rules.

---

## Autonomy

Stop and ask when: architectural tradeoff is unclear, tests require rewriting, new dependency is needed, or scope significantly changes.

---

## Engineering Notes

Maintain `NOTES.md` for non-obvious findings: bugs, perf bottlenecks, framework quirks, chosen solutions, workarounds.
- Short, factual entries — one idea per bullet, no narrative
- Add when something non-trivial is discovered; never duplicate code comments
- Consult before making decisions in areas where prior issues are recorded

---

## Backlog Management

`todo/todo.md` is the source of truth. States: `[ ]` open · `[~]` in progress · `[x]` done · `[?]` decision needed · `[>]` deferred.

- Read before starting work; prefer Current Focus tasks
- Do not start `[?]` or `[>]` tasks without instruction
- Update state as work progresses; do not delete tasks; do not exceed task scope
