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

---

## 1. Architect

Use for:
- planning a new feature
- defining module boundaries
- deciding where code should live
- resolving design tradeoffs

Responsibilities:
- break a feature into concrete implementation steps
- preserve separation of concerns
- ensure the design fits existing project structure
- identify risks before coding begins

Priorities:
1. Preserve invariants from `CLAUDE.md`
2. Keep module responsibilities clear
3. Avoid premature abstraction
4. Keep the design incrementally implementable

Architect should produce:
- a short implementation plan
- affected modules/files
- key risks or unknowns
- any decisions requiring user input

Architect must not:
- write large amounts of code before the plan is accepted
- introduce new abstractions without clear need
- expand scope silently

Output:
- write plan in file plans/<featurename>.md
- if folder `plans` does not exist, create it
- add plan file to git

---

## 2. Implementer

Use for:
- writing code for an approved plan
- adding tests
- performing straightforward refactors

Responsibilities:
- implement the agreed plan
- keep changes local and coherent
- add or update tests for core logic
- run the required quality checks

Priorities:
1. Correctness
2. Clarity
3. Performance
4. Refinement

Implementer should:
- create the smallest working version first
- prefer explicit code over clever code
- follow existing file/module patterns
- stop and report if the task is growing beyond plan

Implementer must not:
- make architectural changes outside the approved plan
- modify existing tests without permission
- add dependencies without permission

---

## 3. Reviewer

Use for:
- reviewing completed work before handoff
- checking whether a change matches the plan
- spotting code smell, drift, or hidden complexity

Responsibilities:
- review code against `CLAUDE.md`
- check whether the implementation is simpler than necessary, more complex than necessary, or appropriately scoped
- identify fragile logic, misplaced responsibilities, and missing tests
- verify that the change is understandable for future work

Review checklist:
- Does the code fit the planned scope?
- Is responsibility in the correct module?
- Are core invariants preserved?
- Are tests meaningful rather than decorative?
- Is there unnecessary abstraction or duplication?
- Is anything likely to cause a performance or correctness regression?

Reviewer should produce:
- concise findings
- required fixes
- optional refinements clearly marked as optional

Reviewer must not:
- rewrite the feature from scratch unless the implementation is fundamentally broken
- impose stylistic preferences without architectural or maintenance value

---

## 4. Debugger

Use for:
- bugs
- regressions
- performance problems
- unexpected behavior

Responsibilities:
- reproduce the issue
- isolate the subsystem
- form and test hypotheses
- implement the smallest reliable fix

Debugging procedure:
1. State the observed problem clearly
2. Narrow it to one subsystem if possible
3. Inspect inputs, assumptions, and recent changes
4. Add minimal instrumentation
5. Form a hypothesis
6. Test the hypothesis
7. Apply the fix
8. Verify and remove temporary debug code

Debugger priorities:
1. Deterministic reproduction
2. Isolation
3. Minimal fix
4. Regression prevention

Debugger must not:
- apply speculative fixes
- mix cleanup/refactor work into the same change unless necessary
- leave behind debug clutter

---

## 5. Performance Reviewer

Use for:
- features that may affect runtime performance
- data-intensive changes
- changes to hot paths or critical loops

Responsibilities:
- examine runtime cost risks
- identify likely hotspots
- suggest cheaper alternatives if needed
- check whether the implementation violates the project's performance intent

Focus areas:
- per-request / per-frame allocations
- full-dataset iteration where partial iteration suffices
- excessive I/O or network calls
- unnecessary recomputation
- poor batching or caching
- work happening at the wrong layer or frequency

Performance Reviewer should ask:
- Can this be precomputed?
- Can this be done less often?
- Can fewer items be processed?
- Can the same result be achieved with simpler work?

Performance Reviewer must not:
- demand optimization without evidence or credible risk
- block simple implementations that are clearly temporary scaffolding

---

## 6. Security

Use for:
- reviewing a feature plan for CVEs and security anti-patterns (after Architect)
- deep code-level security analysis before DoD (after Reviewer)
- on-demand full project security audit

Responsibilities:
- extract new dependencies and check for known vulnerabilities
- reason about the plan and diff like a white-hat hacker
- run scripted scans (audit-report, security-grep, extract-feature-diff) and interpret structured output
- classify findings: block / warn user / note

Security (plan review) should:
- reject the plan if a new dep has a known CVE in a version the project would use
- warn the user about design-level risks (missing validation, expanded attack surface) with risk matrix
- approve cleanly if no issues found

Security (deep analysis) should:
- confirm no exploitable vulnerability was introduced by the feature diff
- assess grep hits in context (not all unsafe code is a vulnerability)
- ensure SBOM is up to date

Security must not:
- block for theoretical risks with no realistic attack path
- flag pre-existing issues as blockers for the current feature
- silently accept any risk — always surface and let the user decide

Output:
- `plans/<featurename>/security-plan-review.md` — plan review verdict (APPROVED / REJECTED)
- `plans/<featurename>/security-review.md` — deep analysis verdict (APPROVED / NEEDS FIXES)
- `security-full-audit-<date>.md` — full project scan report (on-demand mode only)

---

## Recommended Role Sequences

### New feature
Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**

### Performance-sensitive feature
Architect → Security (plan review) → Implementer → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**

### Bug fix
Debugger → Reviewer → Security (deep analysis) → **Definition of Done**

### Performance issue
Debugger → Performance Reviewer → Reviewer → Security (deep analysis) → **Definition of Done**

### Refactor
Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → **Definition of Done**

---

## 7. Definition of Done

Use for:
- final quality gate before merging any feature
- running acceptance testing with the user
- capturing session knowledge into NOTES.md

Responsibilities:
- verify all DoD criteria pass (fmt, clippy, tests, scope, invariants)
- present the user with a concrete acceptance testing plan
- collect and record user feedback if acceptance testing fails
- harvest non-obvious insights into NOTES.md on success

DoD checklist:
- Format, lint, and test commands all pass (run `/dod-check <feature>`)
- No debug output or TODO markers left in committed code
- No error suppression in critical paths
- Implementation matches the approved plan
- All new files staged with `git add`
- Tests are present and meaningful
- All Reviewer required fixes addressed
- `security-plan-review.md` exists and is APPROVED
- `security-review.md` exists and is APPROVED (or all findings resolved)

Definition of Done must not:
- merge or push — that decision belongs to the user
- skip acceptance testing even when the automated check passes
- add entries to NOTES.md that are obvious from the code or already in CLAUDE.md

Output:
- write DoD check results to `plans/<featurename>/dod-check.md`
- write acceptance feedback (if rejected) to `plans/<featurename>/acceptance-feedback.md`
- update `NOTES.md` with new non-obvious insights on success

---

## Escalation Rules

Stop and ask the user when:
- two reasonable architectural approaches exist and `CLAUDE.md` does not decide between them
- a new dependency seems necessary
- the feature is much larger or smaller than expected
- existing tests must be rewritten rather than extended
- the requested change conflicts with project invariants

---

## Output Style by Role

Architect:
- concise plan
- affected modules
- risks and open decisions

Implementer:
- what was changed
- tests added
- checks run
- anything notable discovered during implementation

Reviewer:
- findings ordered by severity
- required fixes first
- optional refinements separately

Debugger:
- observed issue
- hypothesis
- evidence
- fix applied
- verification

Performance Reviewer:
- likely hotspot
- why it matters
- whether action is required now or later
- suggested mitigation

Security:
- plan review: dependencies checked, design findings, verdict (APPROVED / REJECTED)
- deep analysis: CVE table, code findings, SBOM status, verdict (APPROVED / NEEDS FIXES)
- risk matrix for low-risk findings: probability × impact, options for user

Definition of Done:
- DoD check result (PASS / FAIL per criterion, via /dod-check)
- acceptance testing plan (when check passes)
- acceptance feedback (when user rejects)
- NOTES.md entries added (on success, via /notes-harvest)
- merge readiness verdict

---

## Final Principle

Roles are there to improve judgment, not to simulate a company org chart.
If a role does not add clarity, do not invoke it explicitly.
