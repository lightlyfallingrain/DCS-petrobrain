---
name: implementation-log-append-not-overwrite
description: plans/<feature>/implementation.md is a cross-stage decision log for multi-stage features -- read it first and append, never overwrite
metadata:
  type: feedback
---

For multi-stage plans (e.g. `plans/m2-raster-understanding/plan.md` with Stage
2, Stage 3, Stage 4 as separate implementer sessions), `implementation.md` in
that plan's folder may already exist from an earlier stage's implementer
session. Read it before writing, and append a new dated/staged section rather
than replacing the whole file with just the current session's summary --
overwriting silently destroys the previous stage's decision log. Caught in
the M2 Stage 3 session (2026-09-03): a `Write` call replaced Stage 2's
implementation summary with only Stage 3's, requiring a follow-up commit to
restore it from git history and append properly.

**How to apply:** before writing `plans/<featurename>/implementation.md`, run
`git log --oneline -- plans/<featurename>/implementation.md` or just `Read`
the file first. If it already has content from a prior stage, use a
`## Stage N -- <name>` heading structure and append your session's summary
under a new heading, leaving prior stages' content intact.
