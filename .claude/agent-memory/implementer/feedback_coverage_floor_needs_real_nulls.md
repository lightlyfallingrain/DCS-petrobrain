---
name: feedback-coverage-floor-needs-real-nulls
description: A coverage-floor test whose fixture entries are all pre-selected to pass is structurally pinned at 100% and can never fail, regardless of the floor value.
metadata:
  type: feedback
---

`test_object_model.py::test_coverage_floor_against_real_type_sample`'s `"ground"` bucket was
built entirely from real types that already classified correctly (0/100 entries had
`expected_op_class: null`). Because the test's `assert not mismatches` runs before the coverage
computation and enforces `actual == expected` per entry, `ground_classified == ground_total` was
true by construction whenever the test reached the coverage line at all — `_MIN_GROUND_COVERAGE_
FRACTION = 0.9` could never independently fail no matter what value it held. This is the *same*
masking-test shape as a fabricated-string regression test (see
[[feedback_verify_keyword_vocab_against_real_strings]]), reappearing after that first fix: this
time via a curated-to-pass sample instead of a fabricated string.

**Why:** any coverage/percentage assertion computed from a fixture where every entry's expected
outcome is "success" is mathematically pinned at 1.0 (or whatever the fixture's own inherent
ratio is) — the floor constant is decoration unless the fixture's population genuinely spans
both outcomes, in proportions that reflect the real underlying data.

**How to apply:** when building or fixing a coverage-floor fixture, prefer a **full enumeration**
of the real population over a curated/random sample where the population is small enough to
enumerate (a few hundred rows is fine) — it sidesteps sampling-bias arguments entirely and
reproduces the true measured rate exactly, not an approximation of it. Categorize each real item
into the fixture's buckets independently of what the code under test currently returns for it
(script-driven, not hand-picked), so the null/non-null split falls out of actual current
behavior rather than a pre-filtered list. Before trusting a new categorization script's output,
diff it against every entry in the fixture it's replacing as a subset invariant — this project's
already-vetted `"ship"`/`"wwii"`/`"air"` bucket entries caught a real bug in the categorization
script itself (see [[project_pb1_5_coverage_floor_word_boundary_bug]]).
