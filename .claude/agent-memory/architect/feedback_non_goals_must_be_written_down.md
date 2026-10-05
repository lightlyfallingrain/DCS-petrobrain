---
name: non-goals-must-be-written-down
description: When a user relaxation turns a constraint into a non-goal, write the non-goal AND the shape of the machinery you dropped — otherwise the next reader rebuilds it as a defect fix
metadata:
  type: feedback
---

When a user relaxes a requirement so that two things no longer need to agree, state the non-goal
explicitly in the plan, and record what reconciliation machinery was dropped and why.

**Why:** 2026-10-05, mid-pass on `plans/dcs-driven-los/plan.md`, the user relaxed offline LOS to
"we only need it for testing" — which dissolved a question I had just answered with a
cross-implementation contract test, a recorded disagreement rate and a docstring carrying the last
measured figure. The user's own instruction was that *"replacing a real constraint with an explicit
non-goal is worth a paragraph, because the next reader will otherwise re-derive it as a defect."*
A plan that silently stops mentioning divergence reads as an oversight; a plan that says
"divergence here is expected and correct, and here is the machinery we deliberately did not build"
cannot be misread.

**How to apply:** two paragraphs, not one. First the non-goal in a table or a sentence naming what
each side is authoritative *for*. Then the dropped machinery, by name, so nobody rebuilds it
believing it was forgotten. Also check what *else* was filed to serve the retired constraint —
here `WM-B7` had been created that same morning to feed the offline primitive at theatre scale, and
its rationale largely evaporated; flagging that (without redesigning it) is how a milestone avoids
being built to a requirement that was retired while it waited.

Related: [[amend-plans-when-ground-shifts]] — same reflex, one level up.
