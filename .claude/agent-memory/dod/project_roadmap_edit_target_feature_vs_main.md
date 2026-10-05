---
name: roadmap-edit-target-feature-vs-main
description: Before editing a roadmap/backlog file at DoD time, check whether that specific file is part of the feature branch's own diff — it decides whether the edit belongs on the feature branch or on main.
metadata:
  type: project
---

When a DoD gate needs to update roadmap/backlog bookkeeping (marking a milestone done, adding a
live-acceptance-debt entry), `main` has usually moved on since the feature branch forked — new
unrelated commits can touch the very same files (`todo/backlog.md`, a subproject `ROADMAP.md`).
Editing "the current version" of such a file without checking which branch it diverged from risks
either duplicating content the feature branch's own Architect/Implementer already added, or
writing bookkeeping that then has to be reconciled at merge time.

**Check first**: `git diff <fork-point> <feature-tip> -- <file>` — if non-empty, that file's
feature-relevant content (e.g. a new backlog entry an Architect pass already wrote) lives on the
feature branch, not on `main`, and any DoD-time edit to it belongs on a branch built off the
*feature tip* (not `main`), so it rides along with the eventual merge. If the diff is empty, the
file is untouched by this feature and cross-cutting bookkeeping edits are safe to make on `main`
directly per `CLAUDE.md`'s "non-code, cross-cutting updates... commit them on main" rule.

Concretely on `X-B29`/`feature/dcs-driven-los` (2026-10-05): `world-model/ROADMAP.md`'s `WM-B7`
rejection/`WM-B8` creation only existed on the feature branch (Architect had already written it
there); `aircraft-layer/ROADMAP.md` and `todo/backlog.md`'s `X-B29`/`X-B30` entries were untouched
by the feature, so main's current version was the right edit target. Mixing the two up would have
meant either silently duplicating the `WM-B7`/`WM-B8` text on `main` or losing the DoD's own
bookkeeping when the feature branch eventually merges over it.

Since the dispatching DoD agent's worktree usually lands on `main` (the feature branch is checked
out elsewhere — see [[feedback_dod_worktree_pythonpath_trap_applies_here_too]]), the practical move
is: create a new local branch pointed at the feature tip (`git checkout -b dod-check-<name>
<tip-sha>`) for any edit that must land on the feature branch, and make bookkeeping-only edits
separately on whatever branch the worktree actually started on.
