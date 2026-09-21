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
3. `git checkout master && git checkout -b feature/<name>`
4. Read `todo.md`, identify the correct milestone for this feature, and add:
   `- [~] <short description> (feature/<name>)`
5. Confirm: print the active branch and the new `todo.md` line

Then enter plan mode and present a concrete implementation plan for the feature for the user to review before any code is written.
