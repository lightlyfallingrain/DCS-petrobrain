---
name: feedback_coverage_floor_fixture_check
description: How to check a "coverage floor" test isn't vacuous when its fixture was built by curating only-passing real examples
metadata:
  type: feedback
---

When a test asserts a coverage/pass-rate floor over a committed fixture (e.g. "at least 90% of
the 'ground' bucket must classify"), don't just check the fixture uses real, non-fabricated
identifiers (see [[feedback_keyword_vocabulary_domain_check]] for that check) — also check
whether the floor can *ever independently fail*, i.e. whether it's doing more work than a
per-entry regression assertion sitting right next to it.

**Concrete case found (PB-1.5, `object_model.py`'s reporting-name lookup, 2026-09-09):** a
restructured "coverage floor" test computed `ground_classified / ground_total >= 0.9` after an
`assert not mismatches` over the same entries. Every entry in the fixture's "ground" bucket had a
non-null `expected_op_class` — the bucket was built exclusively from types already known to
classify correctly, not a representative sample of the true population (real measured coverage
was 64.5%, not the ~100% the fixture implied). Since the per-entry mismatches check already fails
before the floor is computed, `ground_classified == ground_total` was mathematically guaranteed
whenever the test reached that line — the floor was dead code dressed up as a coverage metric.
This is the same "test can't fail even if the thing it claims to guard regresses" failure mode as
a fabricated-string unit test, just one level up: fabricate the *sample*, not the string.

**How to check**: for any coverage/floor assertion, ask whether the fixture's positive-bucket
entries were drawn as an honest/random sample of the real population (including genuine misses,
with `expected: null`/fallback for them) or curated to already-classifying examples only. If
every entry in the floor's bucket has a non-fallback expected value, the floor is very likely
redundant with whatever per-entry equality check runs before it — verify by checking assertion
order (does the per-entry check run and would it already catch everything the floor claims to
catch?).

**The honest fix** is usually to rebuild the bucket to include a fair share of real,
currently-unclassified members of the population (with the correct expected fallback), and set
the floor below the currently-measured real rate so it can move — not just to lower the floor
number or add more passing examples.
