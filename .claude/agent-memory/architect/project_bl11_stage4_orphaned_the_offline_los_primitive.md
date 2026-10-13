---
name: bl11-stage4-orphaned-the-offline-los-primitive
description: BL-11 Stage 4 removed world-model's line_of_sight_clear from the live path, so any backlog item that proposes adding occluders to query/line_of_sight.py now targets dead code in flight — check this before planning one.
metadata:
  type: project
---

`world-model/src/query/line_of_sight.py`'s `line_of_sight_clear` **is never called in flight.**
`plans/bl11-stage4-fail-closed/plan.md` made `check_visibility`'s gate 4 consult
`candidate.live_los_clear` (the DCS-driven verdict) and nothing else, with a test asserting the
negative. Its own words: *"any future work on that primitive … is now purely an offline/
fixture-correctness concern with no runtime consequence."*

**Why:** the live LOS verdict comes from DCS over the bridge, and `X-B4` settled that DCS's LOS
calls are terrain-and-scenery only. So anything DCS cannot see — trees, above all — can only enter
the live path as a **separate Mac-side gate**, never as an occluder inside that primitive.

**How to apply:** any backlog item whose shape is *"add X as an occluder along the sightline in
`query/line_of_sight.py`"* was written before Stage 4 and is now pointed at a path with no in-flight
effect. `X-B31` ("the occluder layer: buildings from DCS, trees from OSM") is the live example —
its trees half was re-framed as a target-position gate in `perception/visibility.py`
(`plans/forest-occlusion/plan.md`, 2026-10-13) for exactly this reason, and building it as written
would have meant either zero behaviour change or reversing a just-merged decision.

Corollary worth keeping: `check_visibility` still takes `conn: sqlite3.Connection` and
`theatre: str` and, as of `f444370`, **uses neither** — Stage 4 left them behind. A new world-model-
reading gate needs no signature plumbing, but should take its own connection-holding object rather
than silently reviving those dead parameters.

Related: [[find-n-in-the-repo-before-accepting-n-is-more-than-we-need]],
[[verify-the-briefs-status-claims-before-planning-around-them]].
