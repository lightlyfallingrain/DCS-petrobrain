---
name: new-feature
description: Create a feature branch and register it in todo.md
type: user-invocable
---

Start a new feature. Usage: `/new-feature <name>`

If no name is given, ask the user for one.

Steps:
1. Normalize the name to kebab-case (e.g. "User Auth" → "user-auth")
2. Run `git status --short` — if there are uncommitted changes, stop and warn the user to commit or stash them first
3. Branch from the repo's default branch, per root `CLAUDE.md`'s Workflow rules — checkout that
   branch first (the *local* one, never `origin/`), then `git checkout -b feature/<name>`
4. Register the feature where this project tracks in-progress work. Root `CLAUDE.md` says which
   file that is and what the state markers mean — read it rather than assuming, since milestone
   tracking has moved between files before. The entry takes the form:
   `- [~] <short description> (feature/<name>)`
5. Confirm: print the active branch and the new tracking line

Then enter plan mode and present a concrete implementation plan for the feature for the user to review before any code is written.
