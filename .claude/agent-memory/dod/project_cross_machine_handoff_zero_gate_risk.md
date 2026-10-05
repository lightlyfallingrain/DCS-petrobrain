---
name: cross-machine-handoff-zero-gate-risk
description: A branch whose Architect/Implementer ran on another machine/session can arrive with literally zero quality-gate runs ever performed on it.
metadata:
  type: project
---

`feature/spu8-intercom` (audio-adapter Slice 2, 2026-10-05): Architect and Implementer both ran on
another machine, in a different Claude session, and the branch was handed to this repo's normal
Reviewer/DoD chain with no mechanical check having ever run on it. The first gate run anywhere on
the branch (a mechanical fix pass before Reviewer round 1) found the implementer had never run the
test suite at all — a shadowed test helper (a name already bound elsewhere in the test file) was
silently breaking 80 pre-existing, unrelated tests.

**Why this is worth flagging rather than assuming a normal implementer pass**: a branch produced
entirely outside this repo's own Implementer→Reviewer loop has no guarantee any of the usual
early-warning steps ever happened — not "format/lint clean" (the normal bar), but literally
"has `pytest` ever been invoked on this tree." A clean-looking diff is not evidence of that.

**How to apply**: when a DoD or Reviewer task names a feature whose plan/implementation notes say
it was built cross-machine or in a separate session handoff, treat "run the full test suite once,
expect surprises" as step zero before trusting anything else about the branch's state — don't
assume the diff's apparent quality implies the suite was ever green. See
[DoD worktree pytest/PYTHONPATH trap](feedback_dod_worktree_pythonpath_trap_applies_here_too.md)
for the separate, unrelated trap about verifying the right commit at all in this situation.
