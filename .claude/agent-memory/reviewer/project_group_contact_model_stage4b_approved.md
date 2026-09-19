---
name: project_group_contact_model_stage4b_approved
description: Stage 4b (speech/events) reviewed and approved — how the dead-code and structural-test claims were independently verified.
metadata:
  type: project
---

Stage 4b of group-contact-model (branch `feature/group-contact-speech`, commit `6b7cdec`) —
approved, no required fixes. First stage of this plan that changes what the user can hear.

Two claims were worth independently verifying rather than trusting the implementation log:
1. The "OP_GROUPSOMETHING is dead code at class level" claim — traced `Contact.record` directly and
   confirmed it takes `SpecificityLevel(percept.classification_level)` straight from the
   `Observation` with no `_op_class_of` resolution step, so a hand-built test fixture can construct
   a state no real resolver path produces. This made the fixture change (test asserting `"group."` →
   `"ground."`) a legitimate correction, not a masked regression.
2. The `test_console_module_contains_no_belief_logic` structural check — confirmed it filters
   `not name.startswith("_")`, so renaming the new helper to `_estimated_units_lower_bound` (private,
   matching the `_cardinality_facts` convention) genuinely preserves the test's invariant rather than
   dodging it, since the helper has no intended `console.py` caller.

**Why:** a design document's dead-code/unreachability argument is a claim about the code, not a fact
until traced; and a "test renamed to pass" resolution needs the test's actual filter logic read to
tell a legitimate fix from a dodge. See [[feedback_verify_pipeline_wiring_not_just_module]] for the
same pattern (verify the mechanism, not the summary) applied to a prior stage.

**How to apply:** for any future stage in this plan (or similar dead-code-removal / structural-test
work elsewhere), re-derive "unreachable" claims against the actual resolver/construction code path,
not the design doc's prose — a hand-built test fixture bypasses resolvers that real pipeline code
goes through.
