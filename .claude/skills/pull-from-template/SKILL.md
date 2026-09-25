---
name: pull-from-template
description: Check claude-template repo for upstream changes and pull relevant updates into this project. Propose, get approval, apply project-specific adaptation, then summarize.
---

# pull-from-template

Purpose: `claude-template` (`/Users/sg/Code/claude-template`) evolves from other projects pushing
generic improvements back to it (see `update-template` skill, the reverse direction). This skill
checks what changed there since last sync and pulls what's valuable into this project.

**Never edit files without user approval of the specific change first.**

## Steps

1. **Locate template repo and check sync state.**
   - `git -C /Users/sg/Code/claude-template status` — confirm it exists, is clean/up to date.
   - Check whether `.claude/template.lock` exists in this project, and say which case you are in
     rather than assuming — step 6 can create it, so the answer changes over time.
   - **With a lock file**: diff by commit range from the watermark SHA it holds.
   - **Without one**: fall back to a **structural comparison** — diff each template file against
     this project's corresponding file by content, not by commit range. Absence of a lock means the
     config was copied ad hoc rather than adopted through
     `claude-template/todo/use-template.md`'s symlink flow, so there is no watermark to diff from.
     If the user wants one established going forward (recommended, see step 6), create it at the end.

2. **Enumerate template changes to consider.**
   - `git -C /Users/sg/Code/claude-template log --oneline -20` for recent history/context.
   - Walk `.claude/agents/*.md`, `.claude/skills/**`, `.claude/docs/agents.template.md`,
     `.claude/scripts/*.sh`, `CLAUDE.template.md`, `.claude/settings.json`, `README.md`,
     `todo/use-template.md` in the template.
   - For each, check whether an equivalent exists in this project
     (`.claude/agents/`, `.claude/skills/`, `docs/AGENT_ROLES.md`, `AGENTS.md`, `CLAUDE.md`,
     `.claude/settings.json`) and diff.

3. **Classify each candidate pull.**
   - **New in template, missing here, valuable**: e.g. a new generic skill, a hook improvement,
     a clearer agent-role phrasing. Propose adopting it.
   - **New in template but redundant/conflicting** with something this project already does
     differently on purpose — a role the template does not have, this project's own todo-state
     scheme, subproject-`CLAUDE.md` layering, its `docs/PROCESS.md` split. Which divergences stand
     is read from this project's own `CLAUDE.md`/`AGENTS.md` at run time, not from a list here.
     Do not propose wholesale replacement; note the conflict instead.
   - **Template changed a file this project has heavily customized** (agent files, settings.json,
     CLAUDE.md structure) — propose a **merge**, never a raw overwrite. Show both versions.
   - Skip anything clearly template-scaffolding-only with no relevance (e.g. placeholder-only
     files with no project analog).

4. **Write the proposal, do not touch project files yet.** Present to the user:
   - List of candidate pulls, each tagged adopt/merge/skip-conflict, with a one-line reason.
   - For each "adopt" or "merge," show what would change (diff-style) and how it'd be adapted
     to this project's specifics. Establish those by comparing the two sides at run time — the
     agent roster on each side (`.claude/agents/` in both repos), whatever scoping root
     `CLAUDE.md`'s "Agents" section currently applies to the default role sequences, and the
     project-specific paths/placeholders already filled in here rather than left as `{{...}}`.

5. **Get approval.** Ask which changes to apply — all / specific ones / none. Use
   AskUserQuestion for a short, clear-cut list; otherwise state the proposal and wait.

6. **Apply only approved changes, then reconcile local specifics:**
   - Copy/adapt the approved template content into the project's corresponding file(s).
   - Re-apply any project-specific overrides that must survive the pull. Root `CLAUDE.md`'s
     "Agents" section documents this project's own overrides of `AGENTS.md`'s default role
     sequences — read what it currently says and preserve it, so a template pull cannot silently
     replace a deliberate local scoping decision with the template's default.
   - If this is the first pull ever done this way, offer to write
     `.claude/template.lock` with the current template SHA
     (`git -C /Users/sg/Code/claude-template rev-parse HEAD`) so future pulls can SHA-diff instead
     of doing a full structural comparison. Ask before creating it rather than doing it silently —
     it changes how every future pull is computed.
   - Run this project's format/lint/type/test commands if any pulled file is code-adjacent
     (skills/agents are markdown/config, so usually just confirm `.claude/settings.json` is still
     valid JSON and hooks still fire).
   - Stage the changed files (do not commit unless asked, per project workflow rules).

7. **Report to the user**: what was pulled, what was adapted and how, what was skipped and why,
   and whether `template.lock` was created/updated.

## Notes

- This is the reverse direction of `update-template` (project → template). Together they form the
  sync loop described in `claude-template/todo/use-template.md`'s "Keeping the Template Updated"
  section — but that section assumes the symlink-based adoption flow. Where step 1 finds this
  project did not adopt it that way, treat those instructions as guidance to adapt, not commands to
  run verbatim.
- Prefer several small approved pulls over one big merge — same rationale as `update-template`.
