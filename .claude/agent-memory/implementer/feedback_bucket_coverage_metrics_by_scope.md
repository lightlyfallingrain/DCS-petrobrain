---
name: feedback-bucket-coverage-metrics-by-scope
description: A single blended coverage percentage across a mixed-relevance fixture hides the gap in the subset that actually matters; bucket by scope and assert a floor per bucket instead.
metadata:
  type: feedback
---

`test_object_model.py::test_coverage_floor_against_real_type_sample` originally asserted one
floor (0.8) across a fixture mixing ships, armor/truck/infantry/SAM, and deliberately-out-of-
scope aircraft/WWII/building entries. The user explicitly flagged this as the mechanism that hid
`object_model.py`'s real problem: overall fallback looked like "88% -> 78%, mostly fixed" while
the metric that actually mattered — modern ground units, the channel's whole purpose — was still
~21% covered, buried under a denominator dominated by types the module never targets.

**Why:** aggregate/blended metrics over a fixture with mixed relevance always risk this — a
healthy-looking overall number can coexist with a badly-covered subset if the subset is a
minority of the denominator. This isn't specific to DCS/object_model.py; it applies to any
coverage-floor-style regression test built over a fixture that includes both in-scope and
legitimately-out-of-scope entries.

**How to apply:** when building or extending a fixture-driven coverage-floor test, tag each
entry with *why* it's in the fixture (a `bucket` field: the in-scope category the floor should
apply to, plus separate buckets for "already covered elsewhere," "deliberately deferred," and
"deliberately excluded"). Assert the floor only on the in-scope bucket; assert the others
separately (100% for already-covered, exactly 0% for deferred/excluded — the latter catching a
keyword that's too broad and leaking into the wrong bucket). Report the buckets separately in
the plan/implementation.md, not as one number. Confirmed by the user's explicit request this
session ("the metric that matters," "report the other buckets separately, or exclude them
explicitly") — treat this as the default shape for any future coverage-floor test in this
project, not just this one module.
