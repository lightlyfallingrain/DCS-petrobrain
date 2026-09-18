---
name: group-contact-model-stage3bi-rev2-angular
description: Stage 3b-i rev.2 — replaced the ellipse with a true angular predicate; supersedes project_group_contact_model_stage3bi_ellipse.md's ellipse-specific findings
metadata:
  type: project
---

Implemented Stage 3b-i rev.2 of `plans/group-contact-model/plan.md` (feature/group-contact-cardinality
branch), replacing Stage 3b-i's world-space ellipse (`c625299`) with a true 3D angular separability
predicate. **This supersedes [[project_group_contact_model_stage3bi_ellipse]]'s ellipse-specific
mechanism findings** (`EllipseRadii`, grid-binning, the acuity-derived gate) — that memory's meta-level
lesson (test geometry tied to a formula that changed underneath it) still applies and is reinforced
here, but its concrete code references are gone.

**The predicate**: `angular_separation_rad(observer, a, b)` (`atan2(|cross|, dot)` of two 3D unit
vectors) vs. `angular_size_rad(size_m, range_m)` (`size_m/range_m`). Merge when
`theta_sep < 0.5*(theta_size_a+theta_size_b)` — the two-apples criterion, derived not tuned, and the
magnification constant cancels out entirely (both sides of the inequality are angles scaled by the
same optic). This reproduces the ellipse's anisotropy *for free* because the observer has real
altitude — no world-space ellipse, no separately-tuned cross/down-range radii needed.

**Counting**: `floor(extent_rad / unit_rad) + 1`, `floor` not `round` — makes "two-member cluster
always reports `OP_1UNIT`" a *theorem* of the merge criterion, not an artefact of one test's numbers
the way grid-binning's boundary case was.

**The gate/clustering formula-sharing (Decision 7) was diagnosed as the actual defect, not a
regression needing a bigger number.** The two functions answer different questions (live-candidate
resolvability vs. quantised-report-to-remembered-position plausibility) and reverting the belief gate
to its pre-ellipse, quantisation-derived form fixed the `xfail`ed duplicate-contact regression
directly — confirmed by arithmetic (jitter-to-budget ratio is a ratio of two angles, invariant under
representation) before touching code, not by re-tuning a magnitude.

**Real, un-anticipated collateral damage: any test fixture with multiple same-bearing,
same-observer-altitude candidates is now a degenerate always-merges case**, independent of how far
apart they are down-range. Found in `test_naked_eye_source.py`'s cap/debounce fixture (5 candidates
all on bearing 0 at ownship's own altitude) and its majority/minority split test (same issue, plus a
naive split position that exceeded the cockpit mask's 22° forward depression allowance and dropped
out of visibility entirely — caught only by running the real `poll()` pipeline, not the bare
`cluster_candidates` function in isolation). Fix: add a small cross-range (`lon_deg`) offset, or use
a real altitude difference between observer and targets, or both — never assume a "wide down-range
spacing, same bearing" fixture is still safe once separability goes angular.

**The design doc named the exact test files/names it expected to be affected (§8), and one didn't
exist and one file wasn't listed at all.** `test_two_real_objects_stay_two_contacts` (named as a
strict-xfail expected to flip) does not exist under that name anywhere in the repo — the actual
fixture the design's own reasoning described was `test_mock_flight_chain.py`'s single-threaded test,
which did change exactly as predicted (merged-cluster phase across polls 0-13 disappears entirely,
observation count rises 42→56, contact count stays 2). `test_naked_eye_source.py` needed five tests
reworked and wasn't in the design's test-impact list at all. Lesson: a design's own blast-radius
section is a hypothesis to verify against `pytest`, not a checklist to trust — run the full suite
before declaring the stage's test surface complete, even when the design is unusually precise
elsewhere (this one's own worked numbers for the calibration tests matched to within rounding).

See [[decouple_fixtures_from_tuned_defaults]] and [[project_group_contact_model_stage3bi_ellipse]].
