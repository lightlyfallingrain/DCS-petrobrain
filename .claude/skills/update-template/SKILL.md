---
name: update-template
description: Push generally-useful Claude Code setup improvements from this project back to the claude-template repo. Analyse diff, propose, get user approval before touching template.
---

# update-template

Purpose: this project's `.claude/` setup (agents, skills, CLAUDE.md/AGENTS.md structure) has
evolved beyond `claude-template` (`../claude-template` relative to this repo, i.e.
`/Users/sg/Code/claude-template`). Some of that evolution is generally useful to any project built
from the template; most is DCS-Petrobrain-specific. This skill finds the useful part, proposes it,
and — only after explicit approval — applies it to the template repo.

**Never edit files under `/Users/sg/Code/claude-template` without prior user approval of the
specific change.** This is a separate git repo other projects depend on.

## Steps

1. **Locate template repo.** Default `/Users/sg/Code/claude-template`. Confirm it exists and is a
   git repo (`git -C <path> status`). If this project has `.claude/template.lock`, read it for the
   last-synced SHA — but note this repo currently has no symlinks and no `template.lock`
   (config was copied, not adopted via the symlink flow in `claude-template/todo/use-template.md`),
   so a clean SHA-diff isn't available. Treat this as a **structural** comparison (file-by-file),
   not a SHA-range diff.

2. **Inventory both sides.**
   - Template: `.claude/agents/*.md`, `.claude/skills/**`, `.claude/docs/*.md`,
     `.claude/scripts/*.sh`, `CLAUDE.template.md`, `AGENTS.md`, `.claude/settings.json`,
     `todo/use-template.md`.
   - This project: `.claude/agents/*.md`, `.claude/skills/**`, `CLAUDE.md`, `AGENTS.md`,
     `docs/AGENT_ROLES.md`, `.claude/settings.json`.
   Diff by filename where names match (e.g. `dependency-audit-update`, `check.md`, `compile.md`,
   `test.md`, `done.md`/`dod-check.md`, agent role files). For files that exist only in this
   project, judge each on genericity (see step 3).

3. **Classify each candidate change.** For every skill, agent tweak, hook, or doc pattern that
   differs or is new here, decide:
   - **Generic — propose for template**: applies to any software project, not DCS/Petrobrain-specific.
     Examples of the kind of thing that qualifies: a new skill like `integrity-audit` (auditing
     Claude config for drift — applicable anywhere), `nudge-agent.md`, `stage-commit.md`, structural
     fixes to agent role sequencing, a hook improvement, a clearer phrasing of an existing
     convention.
   - **Project-specific — do not propose**: anything naming DCS, Petrobrain, world-model,
     body-layer, aircraft-layer, or encoding this project's own milestone/subproject structure
     (e.g. `investigator` agent, `dcs-log-recon`, subproject-CLAUDE.md conventions, the
     `[?]`/`[>]` todo-state scheme if the template already has its own).
   - **Ambiguous**: could go either way — flag explicitly for the user to decide, don't silently
     bucket it.
   Placeholder-strip generic content mentally as you classify: a project-specific value inside an
   otherwise generic skill (e.g. a hardcoded path) doesn't disqualify it — it means the proposal
   should re-introduce a `{{PLACEHOLDER}}` when porting.

4. **Write the proposal, do not touch the template yet.** Present to the user:
   - A short table/list: file → generic/project-specific/ambiguous → one-line reason.
   - For each "generic" candidate, a concrete diff/preview of what would land in the template
     (adapted to remove DCS-Petrobrain-specific names/paths, restoring `{{PLACEHOLDER}}` tokens
     per the template's existing convention in that file, if applicable).
   - Note any template file whose existing content this would need to merge with (not overwrite).

5. **Get approval.** Ask the user to approve all / a subset / none. Do not proceed on silence.
   Use AskUserQuestion if the set is small and choices are clear-cut; otherwise state the proposal
   in chat and wait for a reply.

6. **Apply only approved changes**, in the template repo:
   - New skill: add file(s) under `.claude/skills/`, update `README.md`'s skill list.
   - Agent/doc change: edit the corresponding template file directly (these are copied, not
     symlinked, into consumer projects, so template edits alone don't propagate — that's expected;
     `pull-from-template` is the other half of this loop for other projects, including this one on
     its next pull).
   - Keep placeholders (`{{...}}`) consistent with README.md's placeholder table — add new rows
     there if a new placeholder is introduced.
   - Commit in the template repo with a clear message. **Ask before pushing** if the template repo
     has a remote — do not push without explicit confirmation.
   - **Update this project's own `.claude/template.lock`** to the new template HEAD SHA
     (`git -C ../claude-template rev-parse HEAD`), but only if this project's lock was already
     at the template's pre-update SHA (i.e. this project was in sync before the push — check
     `git -C ../claude-template log --oneline <old-lock-sha>..HEAD~N` shows nothing unexpected).
     This project authored the change, so it's trivially in sync with it — no pull-from-template
     round trip needed for content this project itself just wrote. If the lock was already behind
     for unrelated reasons (other template commits this project hasn't pulled yet), don't
     silently fast-forward past those — flag it and run `pull-from-template` first instead.

7. **Report.** Summarize what was ported, what was left out and why, and what's still open
   (ambiguous items not decided, or approved-but-deferred items).

## Notes

- This is a one-way push (project → template). The companion skill `pull-from-template` handles
  the reverse direction.
- Because this project didn't adopt the template via symlinks, "port to template" here always
  means write/adapt a new or edited file in the template repo — never means "the project's file IS
  already the template's file."
- Bias toward small, reviewable proposals over one giant sync — propose per-file or per-skill,
  not as a single monolithic patch, so the user can approve some and reject others.
