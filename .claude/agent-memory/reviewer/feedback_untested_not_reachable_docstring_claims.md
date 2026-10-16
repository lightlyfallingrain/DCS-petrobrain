---
name: feedback_untested_not_reachable_docstring_claims
description: When a docstring says a code-path combination "is not reachable in practice," check whether the feature under review is exactly the change that makes the stated reason false -- it was, on BL-B71, and no test covered the combination either way.
metadata:
  type: feedback
---

A docstring claim of the form "X and Y together is not reachable in practice, because Z" is a claim
about the *current* system, pinned to whatever makes Z true. If the feature being reviewed changes
anything Z depends on, the claim can go stale the moment the feature ships — and because the claim
says "not reachable," nobody wrote a test for the combination, so nothing catches it.

**Why:** On `BL-B71` (`body-layer/src/belief/attack_run.py`'s `decide`), the docstring asserted
`tier == 1` with `cause == "too_far"` is unreachable because "a fresh relative percept implies
naked_eye_source already admitted it within presence range" — true only while the admitting optic is
fixed at `UNAIDED_OPTIC`. `BL-B71` is precisely the feature that stops that optic being fixed
(`logger.py` feeds the granted guidance optic back into the perception gate), so the claim became
false the moment the feature it was reviewed alongside landed. `_no_look_cause`'s own `TOO_FAR` test
still hardcoded `UNAIDED_OPTIC`, so the combination became reachable and produced wrong speech (a
"losing sight / last I saw" callout while the contact was being actively tracked through the granted
optic) — directly undermining the feature's own stated purpose. The implementer had flagged the
hardcoded optic as "out of scope," correctly describing the diff's boundary but not re-checking the
docstring's own unreachability claim against the new code it sits beside. `test_attack_run.py`'s
`_contact_at` helper is deliberately tier-2-only ("these cause-taxonomy tests are about
`_no_look_cause`, not tier selection"), so no test exercised the combination from either side.

**How to apply:** When a changed function's own docstring (or a neighbouring function it reads from)
asserts two states "cannot co-occur" or "X implies not-Y," treat that as a claim to re-derive against
the diff, not a fact to take on trust — especially when the diff touches a value the claim's "because"
clause depends on (here: which optic admits a percept). If the claim's premise moved, the claim is
now untested in the literal sense (no fixture constructs it) and often wrong. Grep for the function
the claim depends on and trace whether the new code changed what feeds it, the same way `[[feedback_verify_state_not_the_account_of_it]]`-style checks apply to code assumptions, not just project state.
