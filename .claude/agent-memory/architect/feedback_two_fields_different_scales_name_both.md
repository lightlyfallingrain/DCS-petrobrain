---
name: two-fields-different-scales-name-both
description: When a plan introduces a validity/clip gate against "the field", check there isn't already a differently-scaled bound of the same name in scope (gimbal field-of-regard vs. ASP-17 readable window, BL-B80 v2->v3) -- name both explicitly with distinct constants rather than letting one get reused for the other's job.
metadata:
  type: feedback
---

BL-B80 v2's `run_sight_servo` had exactly one concept called "the field" in its own comments:
`GIMBAL_AZ_HALF_DEG`/`GIMBAL_EL_*_DEG` (±60°/+20°/−15°, the sight's full mechanical slew envelope).
When v2 needed a second, much narrower bound -- whether the ASP-17 mark reading can be trusted
(the reticle's own readable window, measured ≈±4.3° azimuth) -- it reused the same comment
language ("how far inside the field...") and the same gimbal constants to gate it, instead of
introducing a second, differently-named bound. The result passed every unit test (none of them
exercised a setpoint between ~5° and ~58° off boresight against a live mark) and reproduced live,
flown, as the pilot watching the ASP-17 mark drift while the simulated sight pointed "clearly to
the side" -- occurrence 5 of this subsystem's own recurring field-of-regard-enforcement defect
(`.claude/agent-memory/dod/project_recurring_field_of_regard_enforcement_gap.md`, occurrences 1-4).

**Why:** a bound that is correctly *named* ("field", "regard", "limit") does not mean it is the
*right* bound for a new gate reusing that name. Two physically distinct bounds sharing a casual
English name (both are "the field" in prose) is exactly the shape that lets one quietly stand in
for the other across a design, each use locally reasonable, the mismatch visible only by reading
both call sites side by side -- which no single review pass naturally does.

**How to apply:** whenever a plan adds a new validity/clip/saturation gate on a value that already
has *some* bound in scope (a gimbal limit, a field of regard, a sensor's own clip range), stop and
ask explicitly: is this gate's bound the *same physical thing* as the existing one, or a different,
differently-scaled thing that happens to share a name in the surrounding prose? If different, give
it its own constant with its own name (`ASP17_FIELD_AZ_HALF_DEG`, not a reused `FIELD_MARGIN_DEG`)
even when the two bounds are nested (the ASP-17 window sits entirely inside the gimbal envelope) --
nesting is exactly what makes the confusion easy, since a value inside the narrower bound is also,
trivially, inside the wider one, so the wrong gate "passes" far more often than it fails. The
`sight_elevation_deg_to_raw`/`sight_elevation_raw_to_deg` command-vs-readback-domain confusion in
this same subsystem (`implementation.md`, "Notable Discoveries") is the same root cause one level
down: two things that share a unit and a casual name but are not the same thing.

Related: [[check-setpoint-frame-before-blaming-the-loop]] (same family: before trusting a measured
error or a validity gate, check what the reference value actually represents, not just what it is
called).
