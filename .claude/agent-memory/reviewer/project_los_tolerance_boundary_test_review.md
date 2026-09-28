---
name: project_los_tolerance_boundary_test_review
description: fix/los-elevation-tolerance (missed-aaa-detection) reviewed APPROVED — a wide guard-test margin can look adversarial while not pinning the exact moved boundary
metadata:
  type: project
---

`fix/los-elevation-tolerance` (world-model's `_TERRAIN_TOLERANCE_M = 12.0` on terrain LOS) reviewed
APPROVED clean, both subprojects' baselines re-run and matched exactly (world-model 473/3 skipped,
body-layer 1313/4 xfailed). Cross-subproject blast radius through body-layer's thin
`perception.geometry.line_of_sight_clear` wrapper was verified directly by grepping every test file
touching `line_of_sight`/`sample_grid` — all either monkeypatch wholesale or use a flat 50 m
elevation fixture hundreds of metres from the boundary. No gap found (contrast
[[project_precise_position_belief_hybrid_gap]], where the same kind of grep *did* find a channel
never wired up — the technique paid off both ways here: confirmed clean rather than assumed clean).

**New pattern worth carrying forward**: a guard test whose margin is *some* multiple of the moved
boundary (here 50 m vs. a 12 m tolerance, ~4x) can still pass "trivially" in the sense that it
would pass identically across a wide range of miscalibrated tolerance values (0–49 m here) — it
only proves "still blocked well beyond tolerance," not the exact `>`/`>=` edge at the calibrated
number. Worth checking, when a plan/implementation frames a test as "deliberately not the huge
fixture, so it exercises the real boundary": compute what range of the constant's value the test
would actually still pass for. If that range is wide, the test is weaker than its own docstring
claims, even though it isn't literally vacuous (a 10x-scale miscalibration would still be caught).
Classified this one as optional, not required, because the constant's correct derivation is
otherwise fully documented in its own comment and the mechanism itself is simple enough (single
comparison) that this is a low-probability gap — but flag the reasoning explicitly next time rather
than accepting "not the trivial 2000 m fixture" as proof the boundary is pinned.
