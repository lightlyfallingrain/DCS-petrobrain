---
name: merge
description: Merge a feature branch to main following the project workflow
type: user-invocable
---

Merge a feature branch into main. Usage: `/merge <branch-name>` or `/merge feature/<branch-name>`

If no branch name is given, ask the user which branch to merge.

Steps (execute in order, stop and report on any failure):
1. Confirm the full branch name — prefix `feature/` if the user omitted it
2. `git checkout main`
3. `git rebase feature/<name>` — never `--squash`, never `-i`
4. `git branch -d feature/<name>`
5. Read `todo.md` and mark all `[~]` items associated with this branch as `[x]`
6. Show the updated milestone section of `todo.md`

Rules:
- Never force-push main
- If the rebase produces a conflict, stop immediately and describe the conflict; do not resolve it automatically
- After a successful merge, re-enter plan mode, re-read `todo.md`, show the full updated To Do list, and ask the user which feature to work on next
