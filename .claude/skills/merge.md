---
name: merge
description: Merge a feature branch to master following the project workflow
type: user-invocable
---

Merge a feature branch into master. Usage: `/merge <branch-name>` or `/merge feature/<branch-name>`

If no branch name is given, ask the user which branch to merge.

Steps (execute in order, stop and report on any failure):
1. Confirm the full branch name — prefix `feature/` if the user omitted it
2. `git checkout master`
3. `git rebase feature/<name>` — never `--squash`, never `-i`
4. `git branch -d feature/<name>`
5. Regenerate SBOM if the project has one configured: run `{{SBOM_COMMAND}}` (skip if not configured); stage with `git add sbom.json`
6. Read `todo.md` and mark all `[~]` items associated with this branch as `[x]`
7. Show the updated milestone section of `todo.md`

<!--
SBOM_COMMAND examples:
  Rust:   cargo cyclonedx --format json --output-file sbom.json
  Node:   npx @cyclonedx/cyclonedx-npm --output-file sbom.json
  any:    syft . -o cyclonedx-json=sbom.json
If no SBOM tooling is configured, remove step 5.
-->

Rules:
- Never force-push master
- If the rebase produces a conflict, stop immediately and describe the conflict; do not resolve it automatically
- After a successful merge, re-enter plan mode, re-read `todo.md`, show the full updated To Do list, and ask the user which feature to work on next
