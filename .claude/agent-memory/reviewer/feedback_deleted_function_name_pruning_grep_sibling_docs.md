---
name: deleted-function-name-pruning-grep-sibling-docs
description: when a required fix is "doc X still names deleted function Y as current," grep for Y across every doc that documents the same module (STRUCTURE.md, other CLAUDE.md files, inline comments), not just the one doc the plan named -- the implementer's own fix round is scoped to what the plan listed, and siblings go unfixed silently.
metadata:
  type: feedback
---

On BL-16 desired-state Stage 3's review-fix round (`plans/flight-desired-state/review-s3.md`
Required Fix 4, re-reviewed 2026-11-20), the original review correctly caught
`body-layer/CLAUDE.md`'s module-map entry still describing a deleted function
(`decide_flight_control`) as current, because the plan's own "Affected modules/files" list named
that file specifically. The implementer fixed exactly that file and, in "Notable Discoveries,"
self-flagged two more sites with the same stale name (`flight_control.lua`'s own comments,
`body-layer/docs/STRUCTURE.md`) as out of the round's named scope. The re-review ran
`grep -n "decide_flight_control"` across the repo and found `STRUCTURE.md` had **two** hits
describing the deleted function as current, in a file the project's own `CLAUDE.md` says is
"expected to [be read] ... before modifying" the module in question -- the same risk class as the
fix just made two paragraphs above it in a sibling doc. Listed as a new required fix in the
re-review (two sentences, cheap); the Lua inline comment was left optional (not a doc anyone reads
as a map before touching the module).

**Why this is easy to miss:** a plan's "Affected modules/files" list names the doc it expects
touched, and both the implementer and the first-pass reviewer anchor to that list. A grep for the
deleted name across the whole repo, run once, finds every sibling in one shot and costs nothing;
reading the plan's own file list does not.

**How to apply:** whenever a required fix is "doc X still names deleted/replaced mechanism Y,"
before approving the fix, run `grep -rn "Y" --include="*.md" --include="*.py" --include="*.lua"`
(or similarly scoped) across the touched subproject(s) and classify every hit: inside a file that
is read deliberately before modifying the module (a `CLAUDE.md`, a `STRUCTURE.md`, a per-module
reference doc) is a required fix at the same cost as the one just made; inside a comment attached
to code nobody is currently touching is optional, per the comment-pruning rule's own "not in
scope" carve-out. The implementer's own self-disclosure (if present, as it was here) is a strong
signal to check, not a reason to skip the grep.
