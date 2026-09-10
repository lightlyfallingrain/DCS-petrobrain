---
name: concurrent-session-race-verification
description: How to verify an implementer's "no content was lost" claim after a concurrent-session git mishap without worktree isolation.
metadata:
  type: project
---

When an implementer's log flags that a concurrent session (no worktree isolation) briefly swept
its staged changes into an unrelated commit and then reset/recommitted, verify by:
1. `git reflog` to find the exact commit sequence (the sweep commit, the `reset: moving to
   HEAD~1`, and the clean recommit).
2. `git diff <sweep-commit> <final-recommit> -- <affected files>` — should be empty (byte-
   identical) if truly no content was lost/duplicated.
3. `git show <intermediate-recommit> --stat` for the other session's own commit — confirm it now
   touches only its own files, not the swept-in ones.

Confirmed working example: BL-5 (`plans/bl5-tool-api/review.md`, 2026-09-10) — 176fa2c (sweep) vs
561de10 (final) diffed empty for console.py/test_console.py; 68c455b (other session's recommit)
touched only `.claude/skills/merge.md`. Verdict: no corruption, claim accurate.

Don't just trust the implementer's log narrative — this reconstruction is cheap (a few git
commands) and catches exactly the silent-corruption risk the coordinating session itself flagged
as a concern.
