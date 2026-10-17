---
name: project_bl8_review_fix_round
description: BL-8 mission-memory Reviewer fixes -- theatre="Syria" is the existing registered-theatre fixture pattern for dcs_to_wgs84 tests; mutation-testing an except ValueError guard by deleting it is the cheap, decisive counterfactual for "never raises past the poll loop" claims.
metadata:
  type: project
---

Fixing BL-8's three Reviewer-required fixes (`plans/bl8-mission-memory/review.md`,
`plans/bl8-mission-memory/implementation.md`'s final section) surfaced two reusable points:

1. **`theatre="Syria"` is this codebase's standing registered-theatre test fixture.** It appears
   already in `test_tools.py` (for `EnrichmentContext.theatre`, a different parameter of the same
   name) and is registered in `coordinates.projections.THEATRE_PROJECTIONS` with a confirmed
   live-DCS-verified projection. Any test needing a real (non-`None`) theatre for
   `coordinates.dcs_to_wgs84` should reuse `"Syria"` rather than inventing a new one -- it is
   already load-bearing elsewhere and its correctness is independently confirmed.

2. **The decisive counterfactual for a "catches X, never lets it propagate" claim is to delete the
   catch, not to feed in different input.** Both `admission._build_entry_position` and
   `marks._mark_position` wrap `dcs_to_wgs84` in `try/except ValueError: lat, lon = None, None`.
   To prove a new "unregistered theatre never raises" test actually exercises that branch (and
   isn't accidentally passing for an unrelated reason), temporarily remove the `try/except` and
   confirm the test goes red with the real `ValueError` from `coordinates/__init__.py`'s
   `_theatre_crs`, then restore and confirm the `shasum` matches the pre-mutation file exactly.
   This is the project's "show the red" rule (`.claude/agents/implementer.md`) applied to an
   exception-suppression guard specifically -- the guard is itself a negative-space claim ("this
   never raises"), so the only test of whether a new test can tell the difference is removing the
   guard and watching it fail for the stated reason.

See also [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]] (same "run the
actual counterfactual" family, different failure mode -- that one is about not perturbing a
constant the test itself derives its expectation from; this one is about deleting a guard rather
than varying an input).
