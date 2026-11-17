---
name: architecture-decision-text-vs-scoped-down-build
description: when an implementer deliberately scopes down an architect decision (a plan's "D<n>") rather than violating it outright, check whether the plan document itself still states the abandoned approach -- a scope-down disclosed in code/implementation.md but not back into plan.md leaves the decision record wrong even though the build is honest
metadata:
  type: feedback
---

Found reviewing `BL-17` Stage 1b (`plans/speech-rules/plan.md`, `feature/speech-rules`,
`e417d852`). D8 says rule literals are "scored with the existing word-sequence scorer
`_phrase_match_ratio`... The existing floors are reused" (fuzzy matching, like the legacy
matcher). What shipped (`rule_patterns.py`'s `match_pattern`) is full-consumption, exact-literal
matching with no fuzzy tolerance on a rule's own literal words -- a deliberate, reasoned,
explicitly-flagged scope-down (the implementer's own module docstring and
`implementation.md`'s "Notable Discoveries" both say so honestly), not a bug and not hidden.

**The gap was not in the code or the tests -- both were honest about the departure. The gap was
that `plan.md` itself was never updated**, so a future reader who treats the plan as the
project's decision record (which this project's conventions say it is) would believe fuzzy
scoring was built. This is the same shape as
`[[feedback_decision_quoted_figure_stale_vs_shipped_code]]` (a decision document says one thing,
the shipped reality is another) but with a different cause: there, a *measurement* went stale;
here, an *architecture decision* was deliberately not followed, correctly, but the plan was never
told.

**How to apply:** when `implementation.md` or a code docstring says "this stage deliberately
departs from `D<n>`/the plan's own text, here's why" -- that disclosure is necessary but not
sufficient. Check whether `plan.md` (or the roadmap entry, whichever this project treats as the
decision record for that feature) was updated to match, the same way a superseded decision is
marked rather than silently left stale elsewhere in this project (`docs/PROCESS.md`'s
supersession rule). If it wasn't, that is a required fix even when the code and tests are both
correct and honest -- it costs one documentation edit, and the alternative is a stale plan that
actively misleads the next reader (an Architect re-planning a later stage, a Reviewer on the next
pass, the user themselves) into thinking a design that was never built is standing.

Verifying the judgement call itself (is the scope-down actually *safe* for what ships now) is a
separate, also-necessary step -- in this case: running the real matcher against the task's own
adversarial example transcripts (`"turn left 30"`, `"Turn left, 30."`, `"turn left thirty"`)
rather than reasoning about it in the abstract, which showed the upstream filler/punctuation
stripping already absorbs most of the risk this departure looks dangerous on paper.
