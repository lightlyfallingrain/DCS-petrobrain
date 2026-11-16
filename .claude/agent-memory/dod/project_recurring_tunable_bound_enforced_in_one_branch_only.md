---
name: project_recurring_tunable_bound_enforced_in_one_branch_only
description: Third occurrence (X-T26, BL-B85, BL-B118) of a tunable's docstring claiming an unconditional/cross-key bound that per-key lo/hi validation cannot see, caught each time only by Reviewer reading every branch by hand -- process debt, not code debt.
metadata:
  type: project
---

**Three features in two months have shipped a tunable constant whose docstring states a bound
that the code does not actually enforce everywhere the docstring claims, and all three were caught
only by Reviewer, never earlier:**

1. **X-T26** (`plans/configurable-constants/plan.md`) — `belief/decay.py`'s module-level
   `assert OBSERVED_WINDOW_S < POSITION_HALF_LIFE_S` crashed the process on an in-bounds
   combination of three independently-tunable keys; "a bad value warns and continues" was the
   feature's whole premise.
2. **`9k113-narrow-search`/BL-B85** — a reviewer-suggested "mirror `decay.py`'s pattern" fix added
   only the bare assert, not the coupling-check that makes `decay.py`'s own assert safe; reproduced
   the identical import-time crash from one in-bounds key.
3. **BL-B118** (`plans/bl16-qnh-mission-start/review.md`) — `ALTIMETER_QNH_MAX_STEP`'s docstring
   claimed to bound "any single write regardless of a bad gain estimate," but the clamp was wired
   into only one branch of an if/else; the sibling constant's own declared `lo`/`hi` range (not
   just its default) could invert the intended ordering.

**Why this is a DoD-relevant signal, not just a reviewer-skill one**: every instance was invisible
to every test in the file, because every test ran at code defaults — the one combination that
masks the gap. Per-key bounds validation (`tuning.py`'s whole mechanism) structurally cannot see a
cross-branch or cross-key claim; only reading every call site of the value the docstring describes
against the prose, by hand, catches it, and that has fallen to Reviewer three times running.

**Process recommendation, not yet acted on**: a plan or implementation that introduces (or
extends) a tunable whose prose states a cross-branch/cross-key ordering ("must be well under",
"regardless of X", "bounds any single Y") should be required — at Architect (stating the
coupling as a named invariant, the way `_check_scan_decay_coupling`'s own precedent already
documents) or at Implementer (wiring the coupling check or inline clamp before claiming the
docstring is true) — to close the gap at the point the claim is written, not leave it for Reviewer
to find by reading every branch. Worth raising with the user as a candidate addition to
`.claude/agents/architect.md` or `implementer.md`'s own checklist if a fourth instance occurs.

See also `notes/planning-and-process-lessons.md`'s own entry on this (same three instances, written
for a general audience) and `.claude/agent-memory/reviewer/project_configurable_constants_crosskey_assert_gap.md`
/ `feedback_tuning_clamp_covers_one_branch_not_both.md` (the reviewer-side originals).
