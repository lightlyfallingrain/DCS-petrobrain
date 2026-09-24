---
name: binocular-stage3b
description: Stage 3b planning — the mock-flight xfail's stated cause was wrong, and why last_position_uncertainty_m must not be read as a bearing error
metadata:
  type: project
---

Two findings from planning binocular Stage 3b (2026-09-23), both of which
a later plan would otherwise re-derive or get wrong.

**1. `test_mock_flight_chain`'s `xfail(strict=True)` names the wrong cause.**
Its reason text (and `plans/binocular-optic/plan.md` Stage 3b) says the
36 → 32 observation loss comes from aiming a single stare at a quantised
believed bearing. Replaying the fixture with `optic_policy.decide` traced
shows `OpticPhase.GLASSING` is **never entered** there: the only contact is
`type`-level from frame 0, so `improvement_window_m` returns `(0,0)` and no
look is ever chosen. The binoculars go up via `SEARCHING` (the test's
permanent `scan_area("ahead")` task makes `_search_sweep` non-empty), and
the four lost polls are search polls aimed 6.6–15.6° down at the
2333–5647 m band while the truck sat at ~1.1 km. Nearest miss ≈ 1° outside
the 4.25° cone.

**Why:** the marker was written from reasoning, not from a traced replay,
and it reads as an acceptance criterion ("when this lands the test must
turn green").

**How to apply:** when a plan's premise is an assertion inside a test
marker, replay the thing before designing to it. A scratch script that
monkeypatches the decision function and prints per-poll state took minutes
and reversed the whole framing. Same root cause as the object-permanence
revisions: trusting a stated assumption instead of reading current state.

**2. `Contact.last_position_uncertainty_m` must not be converted into a
bearing uncertainty.** It is `hypot(range·sin(15°), range_bucket_width)` —
an angular error hypot'd with a down-range error, budgeted for a spatial
*containment* gate. `asin(u/R)` therefore overstates bearing error, worse
at short range (24.9° at 300 m, 16.2° at 1000 m, against a true 15°), and
on the scope channel it is the flat placeholder `SCOPE_UNCERTAINTY_M=300`
(36.9° at 500 m) which is documented as uncalibrated.

**Why:** this is the same category error `association_over_time.py`'s own
docstring records paying for once — sharing a *derived budget* between two
questions (there: clustering acuity vs reporting quantisation).

**How to apply:** share the *measurement* (the clock bucket is 30° wide),
never the derived radius. Expose `CLOCK_BUCKET_DEG` and derive each
consumer's own figure from it.

Related: [[resolution_vs_salience_split]], [[contact_dup_continuity_of_track]].
