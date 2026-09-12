---
name: mi5-reviewed-approved
description: MI-5 (player questions) reviewed and approved with no required fixes; disclosed choice-path gap verified against source, not taken on faith.
metadata:
  type: project
---

MI-5 (`plans/mi5-player-questions/plan.md`, locked commit `9947c93`) reviewed 2026-09-12 on
`feature/mi5-player-questions` and approved with zero required fixes — only two cosmetic optional
notes (a "93 unit tests" ROADMAP wording that's actually the whole-suite total, and a permanently-
no-op `_ownship_candidates()` placeholder).

**Why:** Implementer's own disclosure ("the `choice` path is currently unreachable because
`_build_ownship`'s `UNKNOWN` `basis` only ever carries a match-count string") checked out exactly
against `schema/build.py::_build_ownship` — and, more importantly, the code doesn't just happen to
fall back to `free_text` by accident of empty `basis`; `_detect_ownship_question` explicitly checks
`if candidates:` and chooses the fallback deliberately, with a docstring pointing at the real
follow-up. This is the bar to hold future "known gap, deferred on purpose" disclosures to — verify
the claim against the actual producing code, and check whether the deferral is structurally
deliberate (an explicit branch) vs. an accident of current data shape.

**How to apply:** When an implementer discloses "path X is unreachable today because upstream
field Y doesn't carry the data yet," don't just confirm Y's current shape — check whether the
consuming code has an explicit branch for the empty case or is silently relying on it. See
[[project_mi4_reviewed_minor_fixes]] for the precedent this continues (verify quoted/disclosed
claims against the file, don't trust the report).
