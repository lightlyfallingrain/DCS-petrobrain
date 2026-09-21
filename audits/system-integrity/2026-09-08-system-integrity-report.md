# System Integrity Audit — 2026-09-08

Diagnostic only. No config/docs/memory edited as part of this audit.

## Definite integrity problems

### 1. Root CLAUDE.md "Current priority" and body-layer status stale — two milestones behind

- `CLAUDE.md:21-23` ("Current priority"): "Priority now: build out the rest of the chain (aircraft layer first...)".
- `CLAUDE.md:30`: "`body-layer/CLAUDE.md` ... Currently at BL-0/BL-1 tier-independent perception scaffolding only".
- `body-layer/CLAUDE.md:17`: "Currently at BL-0/BL-1: the tier-independent perception scaffolding".
- But `todo/todo.md:14`: aircraft layer — **done, merged to main 2026-09-07** (`51654ec`); PB-1 (BL-0+BL-1) — **done, ready to merge 2026-09-08**.
- `todo/todo.md:16`: **"Next milestone: PB-2 (BL-2: contact memory and data association over time)."**
- Why it matters: three files (root CLAUDE.md twice, body-layer/CLAUDE.md once) still point at a target that's already shipped. A session reading Session-Start (root CLAUDE.md → todo.md) will see the contradiction, but anyone reading CLAUDE.md alone gets stale direction, and body-layer/CLAUDE.md's own self-description is wrong about its own status.
- Fix: update CLAUDE.md's "Current priority" to point at PB-2/BL-2, and body-layer/CLAUDE.md's status line to reflect BL-0/BL-1 complete, BL-2 in progress.

### 2. "Skip performance-reviewer and security" exception stated once, contradicted in three other places

- `CLAUDE.md:36`: "**Skip `performance-reviewer` and `security` for now**... Do not insert them into the default role sequence from `AGENTS.md`."
- `AGENTS.md:31-35` "Recommended Role Sequences" lists Security unconditionally in every sequence (e.g. "Architect → Security (plan review) → Implementer → Reviewer → Security (deep analysis) → DoD").
- `docs/AGENT_ROLES.md` §6 (Security) describes it as a standard phase-gated role, no exception noted.
- The `UserPromptSubmit` hook's injected `additionalContext` (`.claude/settings.json`) independently hand-maintains its own sequence list — it omits Security/Performance Reviewer entirely, diverging in the *opposite* direction from AGENTS.md.
- Why it matters: four independent statements of the same rule, no two matching. A future edit to any one of them (e.g. lifting the exception once security-relevant surface appears) won't propagate to the other three.
- Fix: state the exception once in CLAUDE.md (already "primary contract" per AGENTS.md), cross-reference from AGENTS.md/AGENT_ROLES.md instead of restating, and make the hook's injected string derive from — or explicitly defer to — CLAUDE.md rather than being a separately hand-maintained copy.

### 3. Commit-time quality gate and `/dod-check`, `/check`, `/compile`, `/test` skills only cover world-model — aircraft-layer and body-layer have zero automated enforcement

- `.claude/settings.json` PreToolUse `git commit` hook runs exactly `ruff format --check world-model/src world-model/tests && ruff check ... && mypy world-model/src && pytest world-model/tests -q` — scoped only to world-model.
- `.claude/skills/check/SKILL.md`, `compile.md`, `test.md`, and `dod-check.md` all hardcode `world-model/src`/`world-model/tests` (`dod-check.md` sets `SRC="world-model/src"` for every gate: format/lint/mypy/pytest, debug-output scan, TODO scan, error-suppression scan, file-size scan).
- But aircraft-layer/CLAUDE.md and body-layer/CLAUDE.md each define their own real Commands block (own ruff/mypy/pytest scoped to their own src/tests), with real test suites (aircraft-layer: 52 tests; body-layer: 47 tests per `plans/pb1-perception-logger/dod-check.md`).
- `docs/AGENT_ROLES.md` §7 tells DoD to run `/dod-check <feature>` as its mechanical check — for aircraft-layer or body-layer features this would silently report false PASSes on code it never inspected.
- Confirmed no incident yet only because the PB-1 DoD check bypassed the broken script and ran the correct scoped commands by hand (`plans/pb1-perception-logger/dod-check.md`).
- Why it matters: a commit touching only aircraft-layer or body-layer can land with broken tests/types and both the git hook and `/dod-check` will say nothing (or wrongly PASS). This is discipline currently substituting for enforcement.
- Fix: parameterize the hook and the four skills by subproject — detect which subproject(s) the staged diff touches (or which the user names) and run the matching Commands block(s), or run all three unconditionally.

### 4. Same recurring "agent-memory written to wrong path" lesson captured independently 3 times instead of promoted to a rule

- `.claude/agent-memory/implementer/feedback_agent_memory_path.md`, `.claude/agent-memory/reviewer/feedback_agent_memory_path_recurrence.md`, `.claude/agent-memory/reviewer/feedback_check_agent_memory_staged.md` all describe the same problem: implementer agents writing `.claude/agent-memory/` files to a subproject-relative path instead of repo-root, recurring at least twice (commit `f7a7ec1`, M5 Stage 5), caught only by a human/reviewer each time.
- `feedback_agent_memory_path_recurrence.md` itself says: "If it recurs a third time, recommend escalating beyond a per-incident fix — e.g. a stated path line in the implementer role definition itself, or a pre-commit check." That escalation hasn't happened — no line in `.claude/agents/implementer.md`, AGENTS.md, or CLAUDE.md, and no hook checks for a stray `*/.claude/agent-memory/` path.
- Why it matters: exactly the "pattern of correction repeated across sessions" this audit's memory-hygiene phase exists to catch — three memory files re-teaching one lesson instead of one enforced rule.
- Fix: add the absolute-path requirement to `.claude/agents/implementer.md`, and/or extend hook machinery to reject a non-root `.claude/agent-memory/` path.

### 5. Stale auto-memory: "Aircraft-layer stage3 paused"

- Auto-memory index still lists: "Aircraft-layer stage3 paused — 2026-09-07, mid live-DCS-test, resume via `plans/aircraft-layer/implementation.md` last entry."
- `plans/aircraft-layer/implementation.md`'s tail shows Stage 5 (parts 1 and 2) fully completed plus a post-stage-5 scope decision, also completed. `todo/todo.md` confirms: aircraft layer — **done, merged to main 2026-09-07**.
- Why it matters: directly actionable-sounding memory ("resume via...") that would misdirect a future session into thinking there's paused work when the feature shipped and merged.
- Fix: delete/update the memory entry — plain staleness, not a design problem.

## Possible improvements

### 6. `docs/M8_PROBE_STORE.md` "Drift protection" section describes a mechanism that no longer matches the code

`.claude/agent-memory/reviewer/m8-probe-store-read-path-drift-gap.md` notes the doc says the drift check runs on "every subsequent `open_probe_store` call," but `describe_position`'s ATTACH-based read path never calls `open_probe_store` — the actual fix (`check_probe_paired_with_base`) was added and verified; only the doc's stated mechanism is now imprecise. Low urgency — worth a one-line correction next time M8 docs are touched.

### 7. Unconfirmed whether `world-model/pyproject.toml` ever got the isort `known-first-party` fix

`.claude/agent-memory/reviewer/project_ruff_cwd_dependent_isort.md` documents a cwd-dependent `ruff check` I001 flip recurring across M2 Stages 2-4, with its Stage 4 note recommending the config fix as required rather than optional going forward. Worth a quick grep of `world-model/pyproject.toml` for `[tool.ruff.lint.isort]` before the next ruff-touching review; if still absent, promote from "known gotcha" to "fix the root config."

### 8. `.claude/agent-memory/skill-candidates.md` — checked, currently empty (no `##` entries)

No backlog-hygiene problem here; noted only because Phase 5 asks to check it.

## Not flagged (checked, clean)

- `.claude/agents/*.md` vs their AGENTS.md one-liners vs the agent-listing descriptions: responsibilities, tool access, and triggers matched cleanly on comparison (architect/implementer/reviewer/debugger/dod/investigator all consistent across all three sources).
- `docs/PROCESS.md` and the `.claude/agents/*.md` templates: read as domain-neutral, no Petrobrain-specific leakage found beyond the world-model-hardcoded skills already flagged in #3.
