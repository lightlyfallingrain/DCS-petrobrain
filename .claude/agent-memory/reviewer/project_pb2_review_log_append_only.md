---
name: pb2-review-log-append-only
description: plans/<feature>/review.md is an append-only running log across stages, not a per-review scratch file — always read it in full and append, never overwrite with Write.
metadata:
  type: project
---

`plans/pb2-contact-memory/review.md` (and likely other multi-stage features) accumulates one
`## Review: Stage N (...)` section per reviewed stage, going back to Stage -1. When reviewing a
new stage or a post-hoc fix (e.g. a Debugger patch to already-approved code), read the existing
file in full first (or `git show HEAD:<path>` if unsure of current state), then append the new
section with `---` as a separator, preserving every prior section verbatim. Using the `Write`
tool with only the new section's content destroys the prior stages' review history — caught
once (2026-09-09, PB-2 Stage 6 review) only because the file was staged before commit and
`git diff --cached` showed a 338-line deletion; recovered via `git show HEAD:<path>`. Prefer
`Edit` (targeted insertion before/after a known anchor) over `Write` for any file that is a
running log rather than a single-shot report.
