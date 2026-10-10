---
name: fixing-a-defect-falsifies-the-prose-that-documented-it
description: Before fixing a known defect, grep for its name/symptom — every docstring that explains a workaround asserts the defect in the present tense and becomes false on commit.
metadata:
  type: feedback
---

**Before fixing a documented defect, grep for the defect's ID and for the name of the broken symbol.
Every docstring that explains why something is worked around is a present-tense assertion that the
defect exists, and it becomes false the moment you fix it.**

**Why:** `BL-B47` (2026-10-10) was a one-line predicate fix. Three docstrings — two in
`belief/speech.py`, one in `tests/test_speech.py` — said in the present tense that
`_is_air_defence` "resolves through `object_model.profile_for`" and so "does **not** recognise a
class-level SAM". Each was correct when written and each was a lie after the commit. **None was in
the task's own list of what the fix touches**, because the task described the code to change, and
these were files explaining why they had routed *around* that code.

This is the mirror image of [[project_bl11_round3_fixes]]: there, *deleting* a function dangled
prose that named it. Here, *repairing* a function invalidated prose that praised avoiding it. The
trigger differs — a fix, not a deletion — so the grep has to be prompted by the fix itself.

**How to apply:** after `grep`-ing for the broken symbol, sort hits into two piles with opposite
treatment, same split as the deletion case:

- **Dated records (research notes, review docs, implementation logs, roadmap entries,
  agent-memory): leave alone.** The defect really did exist when they were written.
- **Live prose (source and test docstrings): correct it**, and prefer rewriting the claim as a
  dated historical note over deleting it. *"This was originally written as X, because <defect>;
  `BL-B47` fixed it on <date>, so <current state>"* preserves the reason the code is shaped that way
  — which is usually the part worth keeping — while removing the false present-tense claim.

**The tell that a docstring is in the blast radius:** it names the broken symbol in order to say it
is *not* being used. That sentence has no purpose once the symbol works.
