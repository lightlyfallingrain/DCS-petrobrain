---
name: integrity-audit
description: Audit this project's Claude Code operating environment (CLAUDE.md files, AGENTS.md, docs/AGENT_ROLES.md, .claude/agents, .claude/skills, .claude/settings.json hooks, agent-memory, auto-memory, todo/todo.md, NOTES.md) as a whole system for contradiction, staleness, drift, and gaps. Diagnostic and advisory only — never edits config itself. Use when the user asks for a system/config/process integrity audit, or to check whether the Claude setup has drifted from how the project actually works.
---

# System Integrity Audit

Audits Petrobrain's Claude Code operating environment for internal coherence — not any one
file in isolation, but whether the system as a whole (instructions, agents, skills, hooks,
docs, memory) still agrees with itself and with how the project actually works.

This is diagnostic. **Never edit CLAUDE.md/AGENTS.md/agents/skills/hooks/memory as part of
running this skill.** Produce a report; let the user decide what to change.

## Phase 0 — Inventory (discover, don't assume)

Rebuild the file list fresh each run — don't rely on a hardcoded list, since the whole
point is catching drift since the last audit. Enumerate:

- `CLAUDE.md` at repo root and every subproject (`glob **/CLAUDE.md`)
- `AGENTS.md`, `docs/AGENT_ROLES.md`, `docs/PROCESS.md`, `docs/concept/*.md`
- `.claude/agents/*.md` (role system prompts)
- `.claude/skills/**` (both loose `.md` skills and skill directories with `SKILL.md`)
- `.claude/settings.json` and `.claude/settings.local.json` (hooks, permissions) + any
  scripts they invoke under `.claude/scripts/`
- `.claude/agent-memory/**` (per-role memory) and the auto-memory dir for this project
  (`~/.claude/projects/<sanitized-cwd>/memory/`, indexed by its `MEMORY.md`)
- `todo/todo.md`, `todo/backlog.md`, `NOTES.md`, and each subproject's own `NOTES.md`/`ROADMAP.md`/`BACKLOG.md` if present
- `plans/**` directory names (to sanity-check milestone/feature references elsewhere)

Skim each, don't deep-read yet — this pass is just "what exists and what does it claim to
govern."

## Phase 1 — Cross-file consistency

For each rule, convention, or workflow that appears to be stated in more than one place,
compare the statements word-for-word in intent, not just topic:

- Role sequences and escalation rules: `AGENTS.md` vs `docs/AGENT_ROLES.md` vs the
  `UserPromptSubmit` hook's injected `additionalContext` text in `.claude/settings.json`
  vs any restating in `CLAUDE.md`. Flag divergence, not just duplication — two statements
  of the same rule that could drift apart over independent edits are a latent problem
  even if they currently agree.
- Per-subproject `CLAUDE.md` overrides vs the root `CLAUDE.md` — do they actually override
  cleanly, or silently contradict (e.g. a subproject command list that no longer matches
  root's "Verification" section)?
- Agent role definitions (`.claude/agents/*.md`) vs their one-liners in `AGENTS.md` vs
  their descriptions in the agent listing — do responsibilities, tool access, and
  invocation triggers actually match across all three?
- Root `CLAUDE.md`'s explicit exceptions to a general rule (read the current ones there —
  which roles or steps are narrowed or exempted changes by user direction) vs `AGENTS.md`'s
  "Recommended Role Sequences" and anywhere else the general rule appears unconditionally.
  An exception stated once and not threaded through every place the general rule appears is
  exactly the kind of drift this audit exists to catch — and so is an exception whose premise
  has lapsed while its wording stands.

## Phase 2 — Staleness against actual project state

Claims about project structure age fast. For each file/path/command/tool/agent name
mentioned in CLAUDE.md, AGENTS.md, skills, or hooks, verify it still exists or is still
accurate:

- Do referenced paths, scripts, and commands (`ruff format world-model/src`, hook script
  paths, etc.) still exist and match current structure?
- Does "Current priority" / "Current Focus" language in CLAUDE.md and `todo/todo.md` agree
  with each other and with recent git history (`git log --oneline -20`)? A stale "next
  milestone" pointer that both files still repeat is a coherence bug, not just an oversight
  in one file.
- Do any milestone/gate statements (e.g. "gate lifted", "deferred") contradict what
  `world-model/ROADMAP.md` or other subproject roadmaps now say?

## Phase 3 — Genericity leaks

Mechanisms meant to be generic (skills without a hardcoded project domain, `docs/PROCESS.md`,
the role-agent templates in `.claude/agents/`) should work for any project. Check whether
Petrobrain-specific assumptions have crept into them — a "generic" skill that silently
assumes `world-model/src` exists, a role template that references DCS-specific concepts in
what's meant to be a domain-neutral responsibilities list, etc. Contrast against skills that
are *intentionally* project-specific (e.g. `dcs-log-recon`) — those are fine as-is; only flag
leakage into mechanisms that claim or imply generality.

## Phase 4 — Duplication and dead mechanisms

- Rules stated in two+ places that could plausibly diverge on a future edit (see Phase 1) —
  list as a "competing sources of truth" risk even where content currently matches.
- Hooks, scripts, or skills that no longer appear to serve their stated purpose: a hook
  gating on a file/command that no longer exists, a skill whose placeholders were never
  filled in, an agent-memory file that nothing references and whose content is now covered
  by a permanent rule or doc.
- Gaps: places where CLAUDE.md/AGENTS.md *say* something is enforced (a checklist item, a
  "must" rule) but no hook, script, or test actually enforces it — describe what mechanism
  would close the gap without recommending you build it unprompted.

## Phase 5 — Memory hygiene

Read `.claude/agent-memory/**/MEMORY.md` (per-role) and the auto-memory index at
`~/.claude/projects/<sanitized-cwd>/memory/MEMORY.md`, then the entries they point to. For
each memory entry:

- Is it obsolete (describes a state that has since changed, e.g. a paused task that's now
  done, a "current focus" that's moved on)?
- Is it now redundant with a permanent rule, doc section, or hook — i.e. a lesson that was
  captured as memory but has since been (or should be) promoted into `CLAUDE.md`/`AGENTS.md`/
  a skill/hook? Flag these explicitly as promotion candidates, since that's the exact kind of
  finding this audit exists to surface.
- Do multiple memory entries describe the same recurring problem independently (a pattern
  of correction repeated across sessions) that suggests it should become a durable rule
  instead of being re-taught every time?

Also check `.claude/agent-memory/skill-candidates.md` for entries that have been sitting
unreviewed — that file's own docstring says entries should be cleared once acted on or
rejected; a long-accumulating backlog there is itself a process-degradation signal worth
surfacing.

## Phase 6 — Classify and write the report

Sort findings into two tiers. Do not let tier 2 pad out tier 1 — most audits should surface
a small number of definite problems.

- **Definite integrity problems**: contradictions, stale claims, broken enforcement,
  duplicated rules with a real divergence risk, dead mechanisms. Each entry states:
  the evidence (quote or cite exact files/lines), why it matters (what could go wrong or
  already has), and a concrete corrective action.
- **Possible improvements**: things that aren't broken but could be tightened (e.g. a rule
  that's currently consistent but only lives in one place and would be safer duplicated
  with a cross-reference, or a memory-to-rule promotion candidate that's not urgent). Do
  **not** treat complexity itself as a defect, and do not recommend more automation/rules/
  agents just because they're possible — only when the audit surfaced a concrete gap they'd
  close.

Write the report to `audits/system-integrity/<YYYY-MM-DD>-system-integrity-report.md`
(create the directory if missing), then print a concise summary to the user: finding count
per tier, and the single most important finding if any definite problems exist. Point them
at the full file for details. Do not make any changes to the audited system as part of this
skill — the report is the deliverable.
