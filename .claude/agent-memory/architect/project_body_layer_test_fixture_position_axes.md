---
name: body-layer-test-fixture-position-axes
description: In body-layer's test_callouts fixtures ownship_x drives Contact.position and dwp_x/dwp_z drive gate matching only — the helper's own docstring says dwp drives last_position, and that is stale.
metadata:
  type: project
---

In `body-layer/tests/test_callouts.py::_observation`, with `_enrichment_context`'s identity
`project_terrain_aware` stub:

- **`ownship_x`/`ownship_z` drive `Contact.position`** — the fused position comes out at
  `(ownship_x + 1000, ownship_z)`. This is how a probe places contacts in world space.
- **`dwp_x`/`dwp_z` drive gate matching only** and do **not** move the fused position.
  Measured: moving `dwp_x` by 100 m per tick left `position` at `(1000.0, 0.0)` unchanged.

**The helper's own docstring claims `dwp_x`/`dwp_z` drive `Contact.last_position`. That is
stale** — `last_position` is a property of `position`, which dwp does not touch.

**Why it matters:** two tracks 200 m apart in `ownship_x` **found a new pair of contacts every
tick** rather than continuing, because at the fixture's `_FALLBACK_UNCERTAINTY_RADIUS_M`
(300 m) each percept has ≥2 passing gate candidates, so `ingest` takes the ambiguous branch.
A probe that moves a contact to simulate real motion will silently produce contact-id churn
instead, and any transition count measured off it is an artifact.

**How to apply:** establish both axes with a three-tick probe before building any multi-tick
belief scenario on this fixture, and check whether the contact count grew. A clean
unambiguous re-observation is **not constructible** in this harness at the spacings where the
cohesion relative term binds — state that as a limit of the measurement rather than reasoning
past it. Worked probe: `plans/group-retention-hysteresis/scratchpad/probe_b59_axes.py`.
