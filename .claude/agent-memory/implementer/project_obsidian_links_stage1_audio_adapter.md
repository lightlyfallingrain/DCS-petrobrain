---
name: obsidian-links-stage1-audio-adapter
description: Stage 0/1 of obsidian-links-and-tags plan applied to audio-adapter -- what the plan got wrong against real content
metadata:
  type: project
---

Limited-scale test (user direction 2026-10-06): converted `audio-adapter/ROADMAP.md` (22 entries)
per `plans/obsidian-links-and-tags/plan.md` Stages 0-1, minting IDs fresh rather than reusing the
`obsidian-test` spike's numbering (explicitly forbidden by the dispatcher). Branch
`worktree-agent-a0bda12a39cb43b86`, commits `ac6f008` (Stage 0) and `a6056b2` (Stage 1).

**What the plan's own worked examples predicted, confirmed:** document-order top-to-bottom minting
from the *same, unchanged* source document deterministically reproduces the spike's numbering
(`AA-4.7` really is "Press-to-readback latency" independently derived) — not a coincidence, a
property of the rule. Re-deriving fresh is safe precisely because it is deterministic.

**Found mid-task, not anticipated by the dispatching prompt:** `.obsidian/` was tracked at the
**repo root** (not `audio-adapter/.obsidian/`, which the prompt predicted), 12 files/892K
including two plugin `main.js` blobs, swept in by a parallel session's broad `git add` on the
same base commit this branch sits on. Untracked it (`git rm -r --cached`), kept the files on disk
(it's the user's real configured vault). The dispatcher independently caught and corrected this
mid-run — worth noting that two different diagnoses converged on the same fix.

**Index "never carries status" vs. plan prose's "Open/Done tables" tension:** the plan's own
"Grooming" section describes moving entries between an index's Open/Done tables, which reads as
the index carrying status. The dispatching prompt's Step 4 explicitly overrode this: "index
carries links and titles, never status — status lives on the entry." Followed the explicit
instruction over the base plan's residual ambiguity. If this surfaces again in a later stage,
flag it rather than re-deciding silently.

**Tag-regex false positive, real and would have shipped wrong:** `#[A-Za-z0-9/_-]+` matches
ordinal references like "RECOMMENDED #1" or "Decisions requiring user input #1" in ordinary prose
— neither is a tag. Fixed by requiring a leading letter (`#[A-Za-z][A-Za-z0-9/_-]*`) in both the
vocabulary gate and the TOC helper. Any future `#tag`-scanning script needs the same guard, or it
will flag real prose as an unlisted tag.

**Corpus math checked out exactly:** 173 → 198 files (+25 = 22 entries + 1 index + TAGS.md +
DOC_CONVENTIONS.md), under the 200 ceiling, no raise needed. The plan's projected "172" pre-count
was stale by one file (a research note landed via an intervening merge) — worth re-measuring the
baseline rather than trusting a plan's recorded count when the branch has moved since it was
written.

**No venv in this worktree, for any subproject** (not audio-adapter-specific — checked all six).
Ran audio-adapter's ruff/mypy/pytest against the **main checkout's** `.venv` instead
(`/Users/sg/Code/DCS-petrobrain/audio-adapter/.venv/bin/{ruff,mypy,pytest}`, cwd still in the
worktree's `audio-adapter/`) — all four green, as expected since no `src`/`tests` files changed.
This is a reusable pattern for isolated-worktree Implementer runs that touch no source: a sibling
venv in the main checkout is safe to borrow for read-only tool invocations.
