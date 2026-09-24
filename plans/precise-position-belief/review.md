### Review Summary

Reviewed `plans/precise-position-belief/plan.md`'s five stages (commits `311d3d3`..`9ea9bce`,
merged from `feature/binocular-optic`) against the plan, the implementers' decision log
(`implementation.md`), and the source. All checks pass as reported: `ruff check` clean, `mypy
--strict` clean (47 files), `pytest -q` 1103 passed / 4 xfailed.

The covariance math (`belief/position_belief.py`), the 2D Mahalanobis gate
(`belief/association_over_time.py`), the `Contact.position`/read-only-property refactor
(`belief/contacts.py`), the `enrichment._terrain_aware_world_position` fix, and the naked-eye
perturbation (`perception/estimation.py`, `perception/naked_eye_source.py`) are all correctly
built, well-documented, and covered by tests that exercise the actual property under test rather
than asserting the implementation back to itself — including two tests that independently derive
and check numeric claims from the docstrings (the gate-geometry re-derivation in
`test_contacts.py`, and the down/cross-axis gate test in `test_association_over_time.py`), which I
recomputed by hand and confirmed correct.

One finding is required, and it is the invariant this milestone exists to protect.

### Required Fixes

- **`perception/hybrid_source.py` still hands belief a truth-exact, unperturbed position — the
  exact omniscience hole this plan's own diagnosis names as "today's real omniscience hole" and
  "the strongest evidence for the design," left completely unaddressed.** `hybrid_source.py:222-223`
  still writes `bearing_deg=result.bearing_deg, range_m=result.range_m` straight from
  `perception.association.associate`'s ground-truth-derived geometry — no call to
  `perturbed_bearing_range` anywhere in this file. Only Stage 1's mechanical part landed here (the
  `PositionUncertainty(sigma_cross_m=300.0, sigma_down_m=300.0)` declaration, confirmed at
  `hybrid_source.py:244-246`); Stage 2's actual replacement of quantisation-or-exactness with a
  perturbed estimate was never applied to this channel. The plan's own Decision 2 ("Does the
  scope/hybrid channel get the same treatment (Stage 2)? Recommended: yes... against: it is the
  channel driving today's live behaviour") was never recorded as answered — not in the plan file
  (no amendment after the original commit), not in either implementer's commit message or
  `implementation.md`, not in agent memory, not in `body-layer/ROADMAP.md` (which has no entry for
  this milestone at all — see below). The stage-1-2 commit message says only "stage 2 replaces
  naked_eye_source's quantisation" — hybrid is never mentioned as deferred, just silently untouched.
  Net effect: a heavily-observed contact seen exclusively (or predominantly) through the
  scope/HelperAI channel converges on **exact ground truth** with a declared-but-cosmetic 300 m
  uncertainty band around it — precisely the "precision without an error model" failure mode the
  plan's diagnosis calls out, and it sits on the channel the user actually flies with today. This
  needs an explicit decision before merge: either extend Stage 2's perturbation to
  `hybrid_source.py` (the plan's own recommendation), or get the user's explicit sign-off to defer
  it and record that decision in the plan and `ROADMAP.md` rather than leaving it silently
  unresolved.

- **No `body-layer/ROADMAP.md` entry exists for this milestone at all.** `grep -n
  "precise-position"` against the roadmap returns nothing. Per this project's own convention
  (root `CLAUDE.md` "Milestone Completion"), every milestone needs a roadmap entry stating whether
  its completion changes what the next milestone should be — this is also the place the hybrid-
  channel deferral above should have been recorded, had it been a deliberate choice rather than an
  oversight.

### Optional Refinements

- `Covariance2D.inverse()`'s `_MIN_DETERMINANT` floor (the defence against a degenerate/singular
  covariance) has no direct test — neither `test_position_belief.py` nor
  `test_association_over_time.py` constructs a near-zero-determinant covariance and checks the gate
  neither always-accepts nor always-rejects. Low risk in practice (both declared sigmas are always
  strictly positive from any real source), but it is exactly the class of defensive code path that
  silently rots. Worth one direct test of `Covariance2D.inverse()`/`mahalanobis_squared` at a
  near-degenerate input.
- `PositionEstimate.bearing_uncertainty_deg`'s behaviour under a near-isotropic (post-triangulation)
  covariance is documented and tested only implicitly, via `implementation.md`'s "Notable
  Discoveries" note and `test_optic_policy.py`'s two convergence tests (same-bearing collapses to a
  single step, no test for the crossing-bearing case explicitly *not* collapsing). Since the
  implementer already verified this numerically with a standalone script before writing the tests,
  a short comment or test pinning "crossing-bearing fusion does not reliably reach single-step" would
  turn a verified-but-undocumented-in-tests claim into a real regression guard, cheaply.
- Stage 3 (the association gate — the stage flagged as carrying the regression risk) was not flown
  live in this session, per the plan's own explicit "do not merge Stage 3 without a live sortie"
  instruction and `implementation.md`'s own admission. This is not a code defect and not something
  I can address as Reviewer, but it is an outstanding acceptance gate the user should clear before
  trusting this branch in flight, independent of the two fixes above.

### Verdict

NEEDS REVISION

The hybrid-channel gap is not a nitpick — it is the exact invariant the task brief named as "the
first thing to check," and it means the milestone's own stated goal ("no path delivers an
unperturbed, ground-truth-derived position into belief") is false as merged: `hybrid_source.py` is
that path, unchanged. Everything else reviewed (the gate, the fusion, the enrichment fix, the sweep
width, the test suite) is solid and required no changes.

### Review Confidence

Full read. Read `perception/estimation.py`, `perception/naked_eye_source.py::_build_observation`,
`perception/hybrid_source.py` (module docstring + the `Observation` construction site),
`belief/position_belief.py` in full, `belief/association_over_time.py`'s gate and covariance
helpers, `belief/contacts.py`'s `position`/`last_position`/`record`/`from_percept`,
`belief/enrichment.py::_terrain_aware_world_position`, `belief/optic_policy.py`'s sweep-width
wiring, and the new/changed test files (`test_estimation.py`, `test_position_belief.py`, the
directional gate test in `test_association_over_time.py`, the re-derived fixture and convergence
test in `test_contacts.py`, the terrain-aware regression test in `test_enrichment.py`). Hand-
verified two numeric claims (the 900 m gate radius for two isotropic 300 m-fallback sides at
`GATE_SIGMA_THRESHOLD=3`; the down/cross gate-directionality test's geometry) rather than trusting
the docstrings. Did not re-derive the `test_optic_policy.py` sweep-width numbers by hand — the
underlying `bearing_uncertainty_deg` arithmetic in `position_belief.py` was checked directly
instead, which covers the same formula.
