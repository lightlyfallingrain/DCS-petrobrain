---
name: group-cohesion-redesign-review-needs-revision
description: fix/group-undermerging @ 3d7d51c reviewed NEEDS REVISION — two rendered-English defects found by running the code
metadata:
  type: project
---

`fix/group-undermerging` (`plans/group-cohesion-redesign/plan.md`, Stages 1-3) implements the
infantry `EAGER` cohesion release, the `installation_component` kind-coherence fix (500 m cap,
correctly keyed off a new per-profile flag rather than `op_class`), and the delta taxonomy for group
re-disclosure, rebuilt against worked utterances. Mechanically clean: ruff/mypy/pytest all green
(1366 passed, 4 xfailed), `AIR_DEFENSE_OP_CLASSES` correctly uses `OP_ZU23` (verified complete
against `object_model.py`'s full `op_class` vocabulary), the `render_group_full_disclosure` split
for the pull ("report") path is a real, correctly-diagnosed and correctly-fixed gap, all six
taxonomy branches are reachable and tested, clock position never keys identity anywhere.

NEEDS REVISION for two rendered-English defects, both confirmed by actually running the code
(Write + `.venv/bin/python` throwaway scripts, deleted after — not reasoned about by eye):

1. `_group_composition_clause`'s hard-coded `"a"` article breaks on vowel-initial class words
   ("armor", "infantry") — "a armor"/"a infantry". Pinned as *expected* in the implementer's own
   new test.
2. The "first differentiation → full" branch renders a mixed differentiated/undifferentiated group
   as `"A ground and a truck."` — directly contradicting the plan's own cited worked example
   ("AAA in the group") for that exact branch. Pre-existing code (unchanged in substance, just
   moved into a new helper), but the plan explicitly claims this scenario works, and it doesn't.
   The implementer's own test for this branch only asserts negative shape conditions
   (`not startswith("Now leading")`, `"in" not in text or ...`), never the actual string — see
   [[feedback_rendered_english_assertions_too_weak]].

Full review: `plans/group-cohesion-redesign/review.md`. Optional (not blocking): a stale integration
test in `test_crew_console.py` still names/calls `render_group_disclosure` for the "report" path in
its docstring and body, even though production now routes through `render_group_full_disclosure` —
passes only because that test's group was never spoken, so it provides no regression coverage for
the already-spoken case the fix actually addresses.
