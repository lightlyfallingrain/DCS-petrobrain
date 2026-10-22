---
name: feedback_mutation_value_already_held_is_a_noop
description: a "show the red" mutation that writes a value the scenario already holds is a no-op and leaves the test green -- check the pre-mutation state before blaming the test; also, a differential test needs a pinned wall clock
metadata:
  type: feedback
---

BL-B80 v2 review fix 2 (2026-10-22), widening the F4 differential no-leak test. The mutation
"the seen aim sets the looked-at contact's attention to `priority`" left the TOOL_SET identity
test green. The test was fine. The scenario's earlier `select_target` had already made that
contact `priority`, so the mutation changed nothing. Switching it to `ignore` turned the test red
at once.

**How to apply:** when a mutation leaves a test green, first check that the mutation actually
changes state in *this scenario*: print the value before and after. Only then conclude the test is
blind. A mutation that does nothing proves nothing either way.

**Second lesson, same test:** two otherwise-identical runs differed in `MissionMemory`
`Entry.t_wall` (`time.time()` in `mission_memory/store.py`). Pin it with
`monkeypatch.setattr(store_module, "time", SimpleNamespace(time=lambda: 0.0))`. That patches only
the module's own `time` reference, not the shared stdlib, as in
[[feedback_monkeypatch_module_attr_not_shared_stdlib]]. Then the comparison is about content.

Related: [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]].
