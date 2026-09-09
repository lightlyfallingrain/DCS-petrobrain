---
name: feedback_regression_test_empirical_check
description: Empirically disable the fix under test and re-run the new regression tests — don't just reason about whether they'd catch the bug
metadata:
  type: feedback
---

This project's review history has now hit the "test passes but not because of the fix it claims to
test" failure mode three times in one feature (PB-1.5): a fabricated-string fixture (Pass 1), a
coverage-floor fixture built only from already-passing entries (Pass 2 — see
[[feedback_coverage_floor_fixture_check]]), and a multi-candidate association test rescued by an
unrelated pre-existing filter (Pass 3, ownship-echo fix review).

**Pass 3 concrete case:** `test_hybrid_source.py::test_ownship_echo_does_not_prevent_a_real_
candidate_from_associating` gave the ownship-echo candidate `object_type="Mi-24P"` and the real
target `object_type="Ural-4320"` against detection text `"Ural truck"`. The test's own comment
claims it verifies "ownship echo does not prevent a real candidate from associating." But
`associate()`'s pre-existing `_type_match_score` tie-break already discards a
zero-keyword-overlap candidate whenever a second, better-matching candidate is present — so this
test passed identically whether or not the new `exclude_ownship()` fix ran at all. Its sibling
single-candidate test (no second candidate to trigger type-match scoring) genuinely depended on
the fix.

**How to check, going forward:** when a new regression test is added alongside a bug fix, don't
just read the assertion and reason about whether it would fail without the fix — actually verify
it. Temporarily strip the fix (comment out the call, or revert the function to a no-op) and
re-run just the new tests. Restore immediately after and confirm a clean tree + full suite pass.
This is cheap (a few minutes) and catches exactly this failure class, which static reading alone
has now missed being caught by the *author* three times running — the pattern is that a fixture
with two candidates handed to a multi-stage filter/scorer can be "rescued" by a later, unrelated
stage (a type-match tie-break, a coverage floor computed after a stronger per-entry check, etc.)
even when the earlier stage under test does nothing. Prefer doing this empirical check whenever a
test's discriminating power is not immediately obvious from a single read — not just when
something already looks suspicious.
