---
name: stage-commit
description: Stage a specific set of files and commit them with the project's standard message format
type: user-invocable
---

Usage: `/stage-commit <file1> [file2 ...]` — pass explicit paths, never a blanket `-A`/`.`.

Steps:

1. `git status --short` — review what's currently dirty. Confirm the files given are the ones
   intended; call out (don't silently include) any other dirty file that looks related but
   wasn't named.
2. `git add <file1> [file2 ...]` — explicit paths only, per this project's `CLAUDE.md` staging
   rule (never `git add -A`/`git add .`).
3. `git diff --cached --stat` — confirm exactly the intended files are staged, nothing more.
4. If any staged file could plausibly hold a secret (`.env`, credentials, tokens) despite an
   innocuous name, read its content before proceeding and warn the user if anything looks off.
5. Commit with a message via heredoc, ending with the project's footer:
   ```
   git commit -m "$(cat <<'EOF'
   <one-line summary of why, not what — the diff already shows what>

   <the attribution trailers for THIS session, verbatim>
   EOF
   )"
   ```
   **Take the trailers from the attribution guidance in force for the current session**, not from
   an example — the co-author model and the session URL differ every session, so a pair copied
   into this file would credit the wrong model and link to a dead session.
6. `git status --short` — confirm the working tree reflects only what's expected to remain dirty
   (nothing this commit was supposed to include).

Rules carried over from `CLAUDE.md`/`AGENTS.md`:
- Never `--amend` unless the user explicitly asks — always a new commit.
- Never skip hooks (`--no-verify`) or bypass signing.
- Only commit when the user has asked for it (directly, or via a role like `dod`/`reviewer` whose
  job includes committing its own findings) — don't commit proactively mid-investigation.
