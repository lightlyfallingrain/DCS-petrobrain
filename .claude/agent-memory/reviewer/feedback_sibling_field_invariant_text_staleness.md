---
name: sibling-field-invariant-text-staleness
description: When a plan adds a second field under an existing grep-fenced boundary (same files, new name), check whether the CLAUDE.md/STRUCTURE.md prose describing that boundary was updated too -- the test fence can be correctly widened while the human-readable invariant text still names only the original field.
metadata:
  type: feedback
---

Found reviewing BL-B67 Stage 2 (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md`): `aim_unit_direction`
joined `Percept.relative_direction`'s exact two-file fence (`percept.py`/`attack_run.py`), and the
*test* (`test_attack_run.py`'s grep fence) was correctly widened to cover both names, with a
docstring saying so in almost these words ("the same ownship-relative boundary's second field, not
a second exception"). But `body-layer/CLAUDE.md`'s invariant bullet ("The ownship-relative channel
has exactly two consumers...") and `body-layer/docs/STRUCTURE.md`'s matching module entries still
named only `relative_direction` -- not false, just incomplete, and silently so.

**Why this is easy to miss:** the test passes, mypy passes, the code is correct. Nothing mechanical
catches a prose invariant falling one field behind its own fence. The plan itself did not list
CLAUDE.md/STRUCTURE.md updates as a task (they weren't in "Affected Modules"), so an implementer
following the plan's own task list has no prompt to touch them either.

**How to apply:** whenever a diff adds a second (or Nth) field/name to an existing grep-fenced
module boundary, grep `body-layer/CLAUDE.md` and `body-layer/docs/STRUCTURE.md` (or the equivalent
in whichever subproject) for the *old* field's name and check whether the new one appears beside
it. Treat a gap here as a required fix (doc-only, cheap, no need to loop back through Implementer)
rather than optional polish -- this project's recurring failure mode is exactly written claims
about the world going stale while reading as settled.

See also [[verify-by-mutation-per-entry]] (not yet written) -- the same review mutated the
grep-fence file list and the sight-lock-vs-OBSERV-off branch order, both confirmed real rather than
decorative, which is the complementary check to this one: mutation proves the *test* still works;
this proves the *prose describing the test's intent* didn't fall behind it.
