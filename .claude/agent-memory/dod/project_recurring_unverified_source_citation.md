---
name: recurring-unverified-source-citation
description: an implementer's comment/docstring/implementation.md citing "the plan's own wording" or "plans/<feature>/plan.md" has now been wrong twice across two different features -- both caught by Reviewer re-grepping the cited source, neither caught earlier in the pipeline
metadata:
  type: project
---

Two independent occurrences, caught by Reviewer, not by Architect or the dispatching main loop:

1. `fix/taking-fire-visible-shooter` (reviewed 2026-10-20): 17 new code comments cited
   `plans/taking-fire-visible-shooter/plan.md`, which never existed — that feature was a
   Debugger→Reviewer flow (`debug.md`/`review.md` only, no Architect step at all). See Reviewer
   memory `project_bugfix_comments_citing_nonexistent_plan_md.md`.
2. BL-16's takeover revision (`feature/bl16-takeover-fix`, reviewed 2026-11-16): the implementer's
   justification for skipping a tolerance re-check cited "the plan's own 'then go on to step 6's
   checks'" — that exact phrase is not in `plan.md`, current or in history. It turned out to come
   from the **main loop's own dispatch brief**, misattributed to the plan. See Reviewer memory
   `project_bl16_quick_path_misattributed_brief_quote.md`.

**Why this is a category, not two unrelated slips**: both are an implementer treating a citation
to a planning artifact as self-evidently true without grepping it, in a codebase whose convention
(`plans/<feature>/plan.md` as the canonical source of sanctioned decisions) makes that citation
carry real weight — a reviewer or a future reader has no reason to doubt "the plan says X" unless
they check. Both were caught only at Reviewer, by someone re-deriving the claim from the primary
source rather than trusting the implementer's account — the same discipline this role's own
"verify state, not the account of it" rule names, applied to a different artifact (a quoted
source, not a system state).

**Process signal, not just a one-off fix**: this is the second occurrence. If a third shows up,
it is worth moving the check earlier than Reviewer — e.g., a grep-based pre-commit or
Reviewer-checklist line ("any new comment/implementation.md citation to `plan.md` or a dispatch
brief: grep the cited phrase against the actual file before accepting it") rather than relying on
each Reviewer pass to catch it ad hoc by habit. Flagged to the user in the BL-16 takeover-revision
DoD report as a process-debt signal, per root `CLAUDE.md`'s own instruction to raise this rather
than only noting it in memory.

**How to apply** (at DoD, since this role runs last): when a review's required fixes include a
"citation didn't check out" finding, don't just confirm the required fix landed — check whether
this is the Nth time this category has recurred (`memory-search.py` across all roles, not just
DoD) and say so in the DoD report if N ≥ 2, even though the specific fix is small each time.
