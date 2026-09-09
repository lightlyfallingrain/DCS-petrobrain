# Reviewer Memory Index

- [Keyword vocabulary domain check](feedback_keyword_vocabulary_domain_check.md) — separate thin-coverage (plan-licensed) from domain-mismatch (real bug) in hand-authored object_type keyword tables; check tests use real-shaped identifiers.
- [body-layer research dir convention](project_body_layer_research_dir_convention.md) — DCS-internals findings for body-layer/aircraft-layer go in `aircraft-layer/research/`, not `world-model/research/`.
- [Coverage-floor fixture check](feedback_coverage_floor_fixture_check.md) — a "coverage floor" test is vacuous if its fixture is curated to only-passing entries; check assertion order and whether the bucket includes real misses.
- [Empirically disable-and-rerun regression tests](feedback_regression_test_empirical_check.md) — don't just read new regression tests, actually strip the fix and re-run them; a multi-candidate fixture can be rescued by an unrelated later filter stage.
