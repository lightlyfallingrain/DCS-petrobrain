---
name: aspect-aware-profiles
description: Implementation notes for the aspect-aware object profiles feature (S-300 tall-mast fix)
metadata:
  type: project
---

Implemented `plans/aspect-aware-profiles/plan.md` in full: `ObjectTypeProfile` gained optional
`length_m`/`width_m`/`height_m` (default `None`, `size_m` unchanged/required), `apparent_extent_m`
formula, real sourced S-300 dimensions on exactly two rows, `WorldObjectCandidate.heading_true_deg`
(tri-state, `None` default, follows `is_ownship`'s precedent), and `visibility.check_visibility`
wired to use aspect for both the range-threshold gate and `_achieved_tier`. 3 commits + an
implementation-notes commit on `feature/aspect-aware-profiles`. 769/769 tests pass (24 new),
`test_vision_calibration.py` confirmed unedited/passing as the plan predicted.

**Key correctness point, worth restating for any future touch of this formula**: `None` on any of
`length_m`/`width_m`/`height_m` means "shape unknown," never "equal-sided." A prior draft of this
plan defaulted unmigrated rows to a cube (`length=width=height=size_m`) and was caught in review —
`|sin|+|cos|` ranges `[1, √2]`, so a cube silently raises detection range up to 41% at 45° while
looking identical to old behaviour at 0°/90°. Any test of a trig-based formula in this codebase
must include a non-axis-aligned angle or it can't distinguish a correct formula from this bug.

S-300 dimension sourcing: 40B6M mast height 24 m is solidly sourced (ausairpower.net / Air Power
Australia, corroborated by an independent Armorama citation of 23.8 m); 64H6E length/width
13.2m/3.0m sourced (Army Recognition). Two figures were NOT found despite real search effort and
were explicitly flagged as rough estimates in the research doc rather than invented silently: the
40B6M mast trailer's own stowed footprint, and the 64H6E antenna's erected (not stowed) height —
the latter uses the 2026-09-21 sortie's own in-game visual estimate (~10 m) per the plan's explicit
fallback instruction. Both estimates are low-consequence since height dominates `apparent_extent_m`
at every realistic aspect for these tall/thin objects.

See [[feedback_decouple_fixtures_from_tuned_defaults]] and
[[project_m6_terrain_semantics]] for related "don't let a test accidentally prove a degenerate
case" lessons — this task's mandated-45°-test rule is the same family of defect.
