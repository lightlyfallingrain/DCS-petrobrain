---
name: feedback_shared_fixture_position_becomes_load_bearing
description: a test helper's convenience default (same bearing/range for every observation) can become semantically load-bearing once a new gate/fold mechanism is sensitive to spatial coincidence, breaking unrelated tests
metadata:
  type: feedback
---

When a test-helper function (e.g. `_make_observation`) hardcodes one shared position/geometry for
every caller "by convenience" — because the test it was written for didn't care about position —
that sharing is latent coupling. It is invisible until a later feature makes position-coincidence
*mean something new*.

**Why:** BL-12 Stage 3 (`plans/group-contact-identity/plan.md`) added a within-group ambiguity
fold: when 2+ candidates pass the spatial/class gate and all belong to one `Group`, the percept
folds onto the nearest instead of founding a new contact. Two tests broke that had nothing to do
with grouping or ambiguity at all:

- `test_logger.py::test_console_runner_overlay_push_failure_is_isolated_per_push` — testing
  overlay-push failure isolation, not ambiguity. Its follow-up "Mi-8 helicopter" observation shared
  `_make_observation`'s one default bearing/range with the first poll's BMP-2/Ural-truck pair
  (which, at that shared position, formed a `Group`). "Mi-8 helicopter" is an unrecognised keyword
  (`object_model.profile_for` → default bucket), so it was class-*unknown* against both, genuinely
  ambiguous, and folded instead of founding a third contact — breaking an assertion about *push
  isolation* for a reason entirely unrelated to what the test was checking.
- `test_callouts.py::test_2c_transcript_fixture_renders_four_lines_not_seven` — a real sortie
  reproduction where a cluster's covariance, inflated by elapsed time plus the fixture's own
  undeclared-`position_uncertainty` fallback (300m isotropic), reached far enough to ambiguously
  gate against a *different*, previously-separate cluster, folding a genuinely-new real formation
  into an unrelated group.

Neither test's author anticipated that "same position, different test" would ever matter, because
until Stage 3 nothing read group membership when resolving ambiguity.

**How to apply:**
- When adding a mechanism that reads cross-contact state (group membership, cluster shape,
  anything beyond "does this one percept gate against this one contact"), run the *full* suite
  before writing any new test for the mechanism itself — the plan's named test-impact list is a
  hypothesis, not a guarantee (see [[verify_full_suite_not_just_new_files]] for the same principle
  applied to lint rather than behaviour).
- When a fixture-helper's default position is shared across unrelated calls purely for brevity,
  consider giving it an optional override (additive, default unchanged) the moment a test actually
  needs a *distinct* position — cheaper than discovering the coupling via an unrelated test
  breaking.
- Distinguish, in the fix, between "the new expectation is correct and the old one encoded the
  stale rule" (rewrite the assertion, document why) and "this test was never testing the thing that
  broke it" (decouple the fixture instead of rewriting the assertion to match an irrelevant side
  effect). Conflating the two either weakens an unrelated test's intent or hides a real behavioural
  finding inside what looks like fixture housekeeping.
