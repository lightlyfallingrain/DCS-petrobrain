---
name: sortie-0926-fixes-observability-gate-review
description: sortie-2026-09-26-fixes (fix/sortie-2026-09-26, 195085f) reviewed APPROVED WITH MINOR FIXES — deliberate plan deviation verified correct by empirical patch-and-rerun, one required doc fix found
metadata:
  type: project
---

Reviewed `fix/sortie-2026-09-26` (commit `195085f`, merged as `f1feb5b`). Verdict: APPROVED WITH
MINOR FIXES.

**Technique worth repeating: when a task brief flags "verify this reasoning from the code, not the
report," the fastest real verification is to patch the rejected alternative back in and rerun the
tests, not just re-derive the argument by reading.** Here the implementer deviated from the plan's
literal `unobservable_since_sim` ("elapsed since it started failing") formula, using
`last_observable_sim` ("time last confirmed observable") instead, arguing the literal formula
fails the plan's own committed test. I copied `contacts.py` to a scratch file, patched in a literal
implementation of the rejected formula, and reran just the two range-crossing tests: the rejected
formula passed the grace-window companion test (coincidentally — both models agree on "recently
seen, briefly masked") but failed the primary defect test (a contact masked continuously since
founding got a full grace window on its first tick). Five minutes of patch-and-rerun settled a
question that reading the argument alone would have left as "plausible."

**Lesson for future review of "committed/pending split" or "field renamed to fix a scenario the
literal plan didn't handle" changes**: the discriminating test is usually the *original* committed
defect test, not a new companion test added alongside it — a companion test written to prove the
*other* half of a behavior (here, "does still get grace within the window") will often pass under
both the correct and the naive model, since it wasn't written to distinguish them.

**Doc-drift pattern found here, worth checking on every future field-rename-mid-implementation
case**: `decay.py`'s constant docstring (the *other* file, not the one with the renamed field)
still named the old field (`Contact.unobservable_since_sim`) and its old, now-empirically-wrong
semantics ("how long the mask check has failed continuously"), while the field's own docstring in
`contacts.py` was updated correctly. When an implementer discovers mid-task that the plan's
literal field semantics don't work and substitutes something else, check *every* file that
documents the old field's meaning, not just the file where the field itself lives — a constant's
own docstring in a different module is an easy miss.

See `plans/sortie-2026-09-26-fixes/review.md` for the full write-up, including confirmation that
Fix A's gate is cockpit-mask-only (not gaze-cone, correctly avoiding regressing
`plans/callout-outside-gaze/debug.md`'s shipped wording fix), Fix C's scope is exactly the
diagnosed one-line move, and sector coverage (Decision 2a) is genuinely untouched.
