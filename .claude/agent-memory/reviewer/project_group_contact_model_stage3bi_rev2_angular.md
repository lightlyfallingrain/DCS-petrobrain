---
name: group-contact-model-stage3bi-rev2-angular
description: Stage 3b-i rev.2 (angular separability, 88e493a) reviewed, minor fixes — gate revert and cancellation claims verified genuine.
metadata:
  type: project
---

Reviewed `88e493a` (angular separability replacing the Stage 3b-i ellipse,
`plans/group-contact-model/plan.md`'s "Stage 3b-i rev.2"). Verdict: APPROVED WITH MINOR FIXES.

**What held up under direct verification, not just re-reading the design:**
- The `M` (`BINOCULAR_RANGE_MULTIPLIER`) cancellation claim is true of the code as written
  (`_separable` in `clustering.py`) — `M` appears only in the (A) floor, never in the (S) merge
  test.
- The gate-revert claim ("`association_over_time.py` byte-identical to pre-`c625299`") is real:
  `git diff c625299^:... 88e493a:...` shows zero diff on `spatial_gate_radius_m`/`passes_gate`,
  only docstring changes elsewhere.
- `test_two_real_objects_stay_two_contacts` genuinely doesn't exist under that name — traced via
  full `git log -p` history to its real origin: folded into `test_mock_flight_chain_single_
  threaded_reaches_expected_contact_state` by an *earlier*, unrelated commit (`de5e7eb`) that
  predates this whole ellipse/angular saga. Not a silent deletion within this rework.

**Found by inspection, not caught by tests:** a stale/self-contradictory fixture comment in
`test_naked_eye_source.py` (`test_a_cluster_splitting_gives_the_majority_child_continuity`) —
two "moved to lat 100" comments left over from before the split geometry was changed to lat 600
during this same rework, directly contradicted by an adjacent line in the same comment block.
Functionally harmless (code is correct) but misleading to a future reader. Pattern to watch for:
when a rework moves a fixture value, grep the surrounding comment block for the old value too —
narrative comments don't get flagged by ruff/mypy/pytest.

See [[feedback_bounded_magnitude_isnt_optional_severity]] for the general principle this review
leaned on when judging whether "geometry decides, not range" (a plan-level behavior inversion the
user explicitly accepted) needed re-litigating — it didn't; that was a Settled Decision, not this
review's job to second-guess.
