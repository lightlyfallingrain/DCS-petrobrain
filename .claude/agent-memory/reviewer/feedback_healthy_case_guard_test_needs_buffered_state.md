---
name: healthy-case-guard-test-needs-buffered-state
description: A "guard isn't hiding an ordinary-path failure" test is decorative unless the guarded call is the only thing that can produce the observable
metadata:
  type: feedback
---

When a fix wraps a teardown call in a suppression (`contextlib.suppress(OSError)` around
`file.close()`), the paired *healthy-case* test is the one that proves the guard is not hiding an
ordinary failure. **Check it by deleting the whole guarded body, not by reading it.**

**Why:** BL-11 round 2 (`feature/bl11-tick-cost`, 2026-10-06) added four close() tests — a
raises-case and a healthy-case per writer — and the healthy pair asserted
`path.read_text().strip() != ""` after `close()`. Replacing the entire body of `close()` with
`return` in both writers left **all four passing**. The rows were already on disk: the
detection-trace test used `flush_every_n_polls=1`, and `BeliefTruthLogWriter.write_speech` flushes
eagerly by design. So `close()` was not load-bearing for either assertion and the docstring's
claim ("the guard must not be hiding a failure on the ordinary path") was false.

**How to apply:** for any teardown-path guard, the healthy test must leave state that *only*
the guarded call can externalise — buffered-but-unflushed data, an unreleased lock, an unsent
queue. Concretely here: a poll write with `flush_every_n_polls > 1`, assert the file is empty
before `close()` and non-empty after. The mutation check is one `sed` and a `pytest -k`; do it
rather than trusting the pairing.

Same shape as [[feedback_regression_test_empirical_check]] and
[[feedback_boundary_only_tested_via_fixture]] — the test is correct about *something*, just not
about the thing its name claims.

Also from this review, worth reusing: when a test file keeps a **local copy** of a pre-change body
as its reference, verify fidelity by parsing both and comparing `ast.unparse`d bodies rather than
by eye. It took one short script to establish that all three reference constructs were identical
to the pre-change commit, and it covered the union-find loop as well as the two predicates — the
part an eye-diff skips. See [[project_bl11_tick_cost_round2_review]].
