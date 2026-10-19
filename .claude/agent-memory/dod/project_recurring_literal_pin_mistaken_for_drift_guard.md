---
name: recurring-literal-pin-mistaken-for-drift-guard
description: 2nd occurrence of a hand-synced vocabulary/constant set getting a `== frozenset({literals})` test on one or both copies, read as a bidirectional drift guard when it is only a one-sided change detector -- raise at Architect/plan stage when a plan introduces a second hand-synced copy of a set.
metadata:
  type: project
---

**Second occurrence of this shape, in a different context from the first.**

1. `BL-B47` (reviewer finding, 2026-10-10, `[[feedback_a_literal_pin_is_not_a_drift_guard]]`,
   reviewer's own memory store) — `belief.groups.AIR_DEFENSE_OP_CLASSES` is pinned by
   `assert AIR_DEFENSE_OP_CLASSES == frozenset({...})`, a change detector that goes red only when
   *this* set changes, never when the module it was copied from grows. A sibling copy in
   `crew_console.py` had the real guard (`<=` against a derived set); the literal-pin copy quietly
   lagged it for months.
2. `radio-check` (`BL-B81`/`BL-B82`, reviewer required fix, 2026-10-19,
   `plans/radio-check/review.md`) — the *cross-subproject* version of the same shape:
   `audio-adapter/src/vocabulary.py`'s `TIME_OF_DAY_WORDS` and
   `body-layer/src/belief/crew_console.py`'s `_GREETING_TIMES_OF_DAY` are two independent literal
   sets (module independence forbids importing one from the other), and only the audio-adapter
   side had a test pinning its own membership — body-layer had none, despite a docstring on the
   audio-adapter test *claiming* the body-layer side asserted the same membership. The claim was
   aspirational, not true, until the review's required fix added the missing body-layer test.

**Why this is a distinct flavour from `BL-B47`'s, though the same underlying mistake:** `BL-B47`'s
case is a single set copied *within* one subproject, with a derivable "real" source to check
`<=` against (`object_model`'s own keyword tables). The radio-check case has **no single source
of truth at all** — both sides are genuinely independent hand-authored literals by design (module
independence across subprojects), so the fix there isn't "derive one side from the other," it's
"make both sides' literal pins actually name and depend on each other" (each test's docstring now
names the other's test function), so a one-sided change at least fails loudly on whichever side
drifted, even though neither can structurally prevent the drift.

**How to apply:** whenever a plan introduces a second hand-synced copy of a vocabulary/constant set
(same list of strings/values asserted to match on both sides of a module-independence boundary, or
a derived-vs-literal boundary within one subproject), check **both** directions before approving:
does a change to side A get caught by side B's tests, and vice versa? A `== frozenset({literals})`
test on only one side, or on both sides with no cross-reference, is not yet a guard — it is two
separate unlinked assertions that happen to currently agree. Raise this as an explicit
Architect/plan-stage question for any new hand-synced pair, the same way
`[[project_recurring_air_defence_vocabulary_resolution_gap]]` is raised for `profile_for`
lookups, rather than letting Reviewer keep finding it per-feature.
