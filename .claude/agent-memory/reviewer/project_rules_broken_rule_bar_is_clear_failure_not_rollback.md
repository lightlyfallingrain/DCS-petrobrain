---
name: rules-broken-rule-bar-is-clear-failure-not-rollback
description: User direction (2026-11-17, mid BL-17 Stage 4 review) -- for the Lua rule engine, a broken/erroring rule is fixed, not recovered from. Do not require rollback/undo refinements for rule-dispatch errors; the review bar is "failure is clear (logged with file/rule, Action file error spoken) and body-layer does not crash," nothing more.
metadata:
  type: project
---

Verbatim: *"rules are to be written so they are correct. Error in rule needs to be fixed. Do not
spend effort on recovery from broken rule, just make failure clear, then it needs fixing instead
of reverting back switches."*

**Context it was given in:** mid-review of BL-17 Stage 4 (`plans/speech-rules/review-stage4.md`),
right after `38dcd6a1` closed `review-stage3d.md`'s buffer-then-commit race (a real, demonstrated
race between the poll thread's drain and a dispatch's own rollback). The user's direction landed
*after* that fix, confirming it stays as built -- this is not a reason to undo it -- but drawing a
line under the whole line of work: no further required fixes asking for a rollback/undo
refinement on a rule-dispatch error, even a real one.

**How to apply, for this Reviewer role, on any future BL-17/rules work:**
- A broken rule (Lua syntax error, a runtime error mid-dispatch, a bare Python exception escaping
  an action) is reviewed against exactly two bars: (1) the failure is **clear** -- `logger.error`
  names the rule id and its file (not just "a rule failed"), and the pilot hears "Action file
  error." (D6's existing shape); (2) body-layer **does not crash** -- no unhandled exception
  reaches the poll loop (`run_rule`'s `except Exception` catch-all, `[[BL-17]]` Stage 4, is the
  mechanism; see `rules/engine.py`).
- Do **not** raise a required fix asking for partial-effect rollback, an undo mechanism, or
  "what if this specific write already landed before the error" refinements, once those two bars
  are met -- the project's own answer is "the rule gets fixed," not "the engine recovers
  gracefully from a wrong one." This is a deliberate narrowing of scope from where
  `review-stage3d.md`'s own line of fixes was heading (token-based rollback, then buffer-then-
  commit to close a race in that rollback) -- useful to know so a future reviewer does not restart
  that line of effort on the next rule-dispatch defect.
- This does not relax D16's gate (preconditions are still checked *before* a handler runs, so a
  gated command never reaches the broken-rule case for a precondition it could have refused
  cleanly) or D6's existing one-shot-transition clearing on error -- both stay. It specifically
  caps effort on *recovering partial side effects a rule already caused before erroring*.
