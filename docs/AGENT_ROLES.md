# Agent Role Details

Full per-role guidance for the AGENTS.md workflow. AGENTS.md keeps only the sequence table and escalation rules; read this file when tuning a role's behavior or unsure what a role should/must not do. Actual role system prompts live in `.claude/agents/*.md` — this doc is human-facing detail, not loaded automatically.

---

## 1. Architect

Use for: planning a new feature, defining module boundaries, deciding where code should live, resolving design tradeoffs.

Responsibilities:
- break a feature into concrete implementation steps
- preserve separation of concerns
- ensure the design fits existing project structure
- identify risks before coding begins

Priorities: 1. Preserve invariants from `CLAUDE.md` 2. Keep module responsibilities clear 3. Avoid premature abstraction 4. Keep the design incrementally implementable

Should produce: short implementation plan, affected modules/files, key risks/unknowns, decisions requiring user input, and at least one second-order effect this feature has on later milestones (if any — state "none identified" if truly isolated).

Must not: write large amounts of code before the plan is accepted; introduce new abstractions without clear need; expand scope silently.

Output: write plan in `plans/<featurename>.md` (create `plans/` if missing), add plan file to git.

---

## 2. Implementer

Use for: writing code for an approved plan, adding tests, straightforward refactors.

Responsibilities: implement the agreed plan; keep changes local and coherent; add/update tests for core logic; run required quality checks.

Priorities: 1. Correctness 2. Clarity 3. Performance 4. Refinement

Should: create smallest working version first; prefer explicit over clever code; follow existing file/module patterns; stop and report if task grows beyond plan.

Must not: make architectural changes outside the approved plan; modify existing tests without permission; add dependencies without permission.

---

## 3. Reviewer

Use for: reviewing completed work before handoff, checking whether a change matches the plan, spotting code smell/drift/hidden complexity.

Responsibilities: review code against `CLAUDE.md`; check whether implementation is appropriately scoped; identify fragile logic, misplaced responsibilities, missing tests; verify understandability for future work.

Checklist:
- Does the code fit the planned scope?
- Is responsibility in the correct module?
- Are core invariants preserved?
- Are tests meaningful rather than decorative?
- Is there unnecessary abstraction or duplication?
- Is anything likely to cause a performance or correctness regression?

Should produce: concise findings, required fixes first, optional refinements marked separately.

Must not: rewrite the feature from scratch unless fundamentally broken; impose stylistic preferences without architectural/maintenance value.

---

## 4. Debugger

Use for: bugs, regressions, performance problems, unexpected behavior.

Responsibilities: reproduce the issue; isolate the subsystem; form and test hypotheses; implement the smallest reliable fix.

Procedure: 1. State the observed problem clearly 2. Narrow to one subsystem if possible 3. Inspect inputs, assumptions, recent changes 4. Add minimal instrumentation 5. Form a hypothesis 6. Test it 7. Apply the fix 8. Verify and remove temporary debug code.

Priorities: 1. Deterministic reproduction 2. Isolation 3. Minimal fix 4. Regression prevention

Must not: apply speculative fixes; mix cleanup/refactor into the same change unless necessary; leave behind debug clutter.

---

## 5. Performance Reviewer

Check the project's `CLAUDE.md` "Agents" section before invoking — it may currently exempt
this role for the project's phase (e.g. no hot path exists yet). That exemption overrides the
"use for" guidance below.

Use for: features that may affect runtime performance, data-intensive changes, changes to hot paths/critical loops.

Responsibilities: examine runtime cost risks; identify likely hotspots; suggest cheaper alternatives; check whether implementation violates the project's performance intent.

Focus areas: per-request/per-frame allocations; full-dataset iteration where partial suffices; excessive I/O or network calls; unnecessary recomputation; poor batching/caching; work at the wrong layer or frequency.

Should ask: Can this be precomputed? Done less often? Fewer items processed? Same result with simpler work?

Must not: demand optimization without evidence or credible risk; block simple implementations that are clearly temporary scaffolding.

---

## 6. Security

Check the project's `CLAUDE.md` "Agents" section before invoking — it may currently exempt
this role for the project's phase (e.g. no untrusted-input surface yet). That exemption
overrides the "use for" guidance below, except for user-requested on-demand full audits, which
always run regardless of exemption.

Use for: reviewing a feature plan for CVEs/security anti-patterns (after Architect); deep code-level security analysis before DoD (after Reviewer); on-demand full project security audit.

Responsibilities: extract new dependencies and check for known vulnerabilities; reason about the plan/diff like a white-hat hacker; run scripted scans (audit-report, security-grep, extract-feature-diff) and interpret output; classify findings block/warn/note.

Plan review should: reject if a new dep has a known CVE in the version the project would use; warn about design-level risks with a risk matrix; approve cleanly if no issues found.

Deep analysis should: confirm no exploitable vulnerability was introduced by the feature diff; assess grep hits in context; ensure SBOM is up to date.

Must not: block for theoretical risks with no realistic attack path; flag pre-existing issues as blockers for the current feature; silently accept any risk — always surface and let the user decide.

Output: `plans/<featurename>/security-plan-review.md` (APPROVED/REJECTED), `plans/<featurename>/security-review.md` (APPROVED/NEEDS FIXES), `security-full-audit-<date>.md` (on-demand mode only).

---

## 7. Definition of Done

Use for: final quality gate before merging any feature; running acceptance testing with the user; capturing session knowledge into NOTES.md.

Responsibilities: verify all DoD criteria pass (fmt, clippy, tests, scope, invariants); present a concrete acceptance testing plan; collect/record user feedback if acceptance testing fails; harvest non-obvious insights into NOTES.md on success.

Checklist:
- Format, lint, and test commands all pass (run `/dod-check <feature>`)
- No debug output or TODO markers left in committed code
- No error suppression in critical paths
- Implementation matches the approved plan
- All new files staged with `git add`
- Tests are present and meaningful
- All Reviewer required fixes addressed
- `security-plan-review.md` exists and is APPROVED
- `security-review.md` exists and is APPROVED (or all findings resolved)

Must not: merge or push (belongs to the user); skip acceptance testing even when the automated check passes; add NOTES.md entries obvious from code or already in CLAUDE.md.

Output: `plans/<featurename>/dod-check.md`, `plans/<featurename>/acceptance-feedback.md` (if rejected), update `NOTES.md` on success.

---

## Output Style by Role

- **Architect**: concise plan, affected modules, risks and open decisions.
- **Implementer**: what was changed, tests added, checks run, anything notable discovered.
- **Reviewer**: findings ordered by severity, required fixes first, optional refinements separately.
- **Debugger**: observed issue, hypothesis, evidence, fix applied, verification.
- **Performance Reviewer**: likely hotspot, why it matters, whether action is required now or later, suggested mitigation.
- **Security**: plan review — dependencies checked, design findings, verdict; deep analysis — CVE table, code findings, SBOM status, verdict; risk matrix (probability × impact, options) for low-risk findings.
- **Definition of Done**: DoD check result (PASS/FAIL per criterion), acceptance testing plan, acceptance feedback, NOTES.md entries added, merge readiness verdict.
