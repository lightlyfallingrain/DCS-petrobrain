---
name: feedback_decouple_fixtures_from_tuned_defaults
description: unit-test fixtures for a tunable-threshold algorithm should pass an explicit test-only threshold, never rely on the production default
metadata:
  type: feedback
---

When a module exposes a `DEFAULT_X_THRESHOLD` that a later stage (Stage 2/4 real-data tuning) is
expected to keep adjusting, synthetic unit tests must call the function with an explicit,
hardcoded test threshold — never omit it and rely on the module's current default.

**Why**: in M6 (`world-model/src/terrain/curvature.py`), the Stage 1 synthetic fixture's
curvature magnitude was sized to comfortably exceed the Stage 1 first-guess default (3.0). When
Stage 2's real-data tuning raised the default to 20.0 — which happened to exactly equal the
fixture's magnitude — the strict `<`/`>` threshold comparison silently reclassified every
fixture cell from RIDGE/VALLEY to NEITHER, breaking `test_terrain_curvature.py`,
`test_terrain_features.py`, and `test_ingest_terrain.py` all at once, well after the fixtures
were written and reviewed as correct.

**How to apply**: any time a plan says a threshold/parameter is a "first guess, tuned
empirically" against real output (a strong signal in Petrobrain's plans — see
[[project_m6_terrain_semantics]]), give the unit tests their own `_TEST_THRESHOLD_M`-style
constant, pass it explicitly at every call site, and pick a fixture magnitude with comfortable
headroom either side of that test constant (not the production default). This keeps
"does the algorithm work" tests stable independent of "what value works on real data" tuning.
