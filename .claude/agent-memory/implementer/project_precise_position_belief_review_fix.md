---
name: precise-position-belief-review-fix
description: Fixed the milestone's central invariant gap left by two prior implementer sessions — the scope/hybrid channel never got Stage 2's perturbation
metadata:
  type: project
---

`plans/precise-position-belief/plan.md` (Stages 1-5) landed on `feature/binocular-optic`, but
Decision 2 ("does the scope/hybrid channel get Stage 2's perturbation too?") was silently never
answered — Stage 1's mechanical `PositionUncertainty(300, 300)` declaration reached
`perception/hybrid_source.py`, but nobody ever wired `perception.estimation.perturbed_bearing_range`
into it. A heavily-observed scope contact converged on exact ground truth behind a cosmetic 300m
band — on the channel the pilot actually flies with. Reviewer caught it; two prior implementer
sessions (one that ran out of budget, one scoped to stages 3-5 that reasonably assumed stage 2 was
fully done) both missed it, and nothing in commits/`implementation.md`/`ROADMAP.md` ever flagged the
gap as deliberate or open.

**Fix pattern**: mirror `naked_eye_source._build_observation`'s call shape exactly —
`perturbed_bearing_range(observation_id=..., object_id=result.candidate.object_id,
true_bearing_deg=result.bearing_deg, true_range_m=result.range_m, sigma_cross_m=SCOPE_UNCERTAINTY_M,
sigma_down_m=SCOPE_UNCERTAINTY_M)` — isotropic since this channel has no reporting bucket to derive
an anisotropic split from. `derived_world_position` stays ground truth (untouched) — it is
trace/debug-only by that field's own docstring, never crew-facing.

**Test that catches this class of bug**: poll a stationary object many times
(`emit_mode="every_poll"`) and assert the *mean* of the emitted range/bearing over many looks stays
measurably away from truth — per-look noise averages down, the per-object systematic bias does not.
A single-observation "range != truth" assertion is much weaker and can pass by the same mechanism
that let this gap ship (a reviewer/implementer eyeballing one value and calling it "close enough").

See also [[verify-full-suite-not-just-new-files]], [[agent-memory-path]] — same worktree/venv
conventions applied here (no `.venv` existed in this worktree; had to `python3 -m venv .venv && pip
install -e . mypy ruff pytest` before any check would run).
