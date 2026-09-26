---
name: feedback_regression_test_verify_mechanism_not_just_hypothesis
description: A reviewer's suggested test-fix mechanism can itself be wrong; check both code paths' literal behavior before writing the assertion
metadata:
  type: feedback
---

On `audio-adapter-review-findings` round 2, the Reviewer found
`test_speak_negative_content_length_returns_400` passed against pre-fix code too (proved nothing),
and suggested the fix: spy on/mock `rfile.read` and assert it's never called with a negative count.

That suggested mechanism turned out not to actually distinguish pre-fix from post-fix for this
specific case — the pre-fix code's own `self.rfile.read(length) if length > 0 else b""` ternary
already prevented calling `read()` with a negative count, exactly like the post-fix guard does, so
a read-call spy would pass on both versions. The two versions actually differ in *which* rejection
path fires (JSON-validation fallback vs. the header guard itself), visible only in the response
body's error message.

**Why:** a reviewer's suggested fix mechanism is a hypothesis about the difference between two code
versions, not a verified fact — the review report itself hadn't checked whether its suggested spy
would actually flip red/green across the revert. Applying it uninspected would have produced a
test that still proved nothing, while looking like the required fix had been done.

**How to apply:** when a review asks for a regression test to be "strengthened" with a specific
suggested mechanism, read both code paths' literal source (old and new) before writing the
assertion, and empirically verify (as the task already requires) rather than trusting the
suggestion's mechanism to be correct just because the requirement to fail-on-old-code is correct.
The empirical revert-and-run step catches a wrong mechanism just as well as it catches a missing
fix — do it before reporting done, not after assuming the suggested approach will work.

See [[feedback_verify_mission_probe_pattern_claims]] and [[feedback_verify_state_not_the_account_of_it]]
for the same "verify, don't trust the account" pattern generalized elsewhere in this project.
