---
name: side-quest-commits-on-feature-branch
description: Check feature-branch commit history, not just the diff, for bundled non-scope skill/docs/research commits
type: feedback
---

Reviewing only `git diff main...feature-branch --stat` for scope fit can miss commits that are
technically on the branch but predate/interleave with the feature's own commits and touch nothing
in the plan's Affected Modules — e.g. a `.claude/skills/` addition, a `docs/PROCESS.md` edit, or an
unrelated `research/` note. `git log --oneline main...feature-branch` (or diff each commit's own
`--stat`) surfaces these; the stat-only diff against `main` does not distinguish "feature work" from
"side quest bundled in."

**Why:** `AGENTS.md`'s "Side quests" rule explicitly requires skill/config edits and cross-cutting
docs/research bookkeeping to go through a disposable `git worktree` on `main`, not the active
feature branch — both to keep feature-branch history scoped and to avoid racing a
background Architect/Implementer/Reviewer/DoD agent running in that same checkout. Found in BL-9
(`feature/bl9-detection-trace`, 2026-09-20): 4 of 12 commits were unrelated (two `research/` notes,
a `docs/PROCESS.md` rule, and the `/test-card` skill addition) — content was all fine, but they
should have landed on `main` independently.

**How to apply:** When reviewing a feature branch, run `git log --oneline main...HEAD` early and
check each commit's own `--stat` against the plan's Affected Modules list, not just the aggregate
diff. Flag any commit that touches `.claude/`, `docs/PROCESS.md`, or a `research/` note unrelated to
the feature as a required fix (extract via worktree cherry-pick before merge) even when the content
itself is unobjectionable — this is a branch-hygiene/process violation, not a code-quality one.
