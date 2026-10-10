---
name: feedback-guard-fixture-must-not-pick-a-degenerate-case
description: A test whose fixture picks a case where the two branches produce the same value passes whichever branch runs — pick a fixture where the branches differ, and derive the set from the table.
metadata:
  type: feedback
---

**When a test guards a choice between two values, its fixture must be a case where those two values
differ.** If they coincide, the test passes whichever branch runs and certifies nothing.

**Why:** `speech.render_report_summary` substituted `_OP_CLASS_DISPLAY_PLURAL`'s word into the count
clause unconditionally, so a single truck spoke *"One trucks"* — through TTS, on the commonest scene
a `report` answers. Three tests asserted that fold and all three passed, because every one used
`OP_ARMORED` or `OP_INFANTRY`, whose plural display word **equals** its singular (`"armor"`,
`"infantry"` are mass nouns). `test_render_report_summary_collapses_a_single_hour` asserted
`"One armor"` and was green under the defect *and* under the fix — measured both ways. Six of the ten
display classes genuinely inflect; the fixtures had picked from the four that do not.

This is the same failure shape as [[feedback-coverage-floor-needs-real-nulls]] (a fixture
pre-selected to pass) and a sibling of
[[feedback_equivalence_test_must_own_its_reference_arithmetic]]: the lever and the subject coincide,
so the test cannot move.

**How to apply:**

- **Pick the fixture where the branches diverge**, and say in the docstring *why that choice is
  load-bearing* — otherwise the next person renames the case to something tidier and the guard dies
  silently.
- **Derive the candidate set from the table, not by hand**, and assert the derived set equals the
  parametrised one. Here: every class whose plural entry differs from its singular, computed from the
  two display dicts, pinned against the case table — so a class added later fails that membership
  test instead of escaping the guard.
- **Do not filter an awkward member out of the derived set — give it its own expectation.**
  `OP_GROUPSOMETHING` never reaches the fold (its upstream resolver treats the default bucket and an
  unresolved classification as the same answer), so it speaks the generic noun. Filtered out, it is a
  class nobody is watching; named with `"One unit"` expected, it is covered and the reason is written
  down.
- **The counterfactual is what proves it.** Force the pre-fix branch and confirm the new cases go red
  with the exact expected diff, restore by `shasum`. The pre-existing mass-noun test stayed green
  throughout — which is the whole finding.
