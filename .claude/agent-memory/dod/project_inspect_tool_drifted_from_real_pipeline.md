---
name: inspect-tool-drifted-from-real-pipeline
description: tools/inspect_terrain.py rendered raw traced skeletons for weeks, not what the pipeline actually stored — a DoD-relevant verification-tool trap
metadata:
  type: project
---

`world-model/tools/inspect_terrain.py` drew `comp.points` (the raw traced skeleton) instead of
calling `to_stored_features` and drawing `feature.geometry` — every terrain render this project
judged landforms by before `fix/landform-relief-gate` (2026-10-04), including the 2026-10-01
"choose geomorphons" decision and the 2026-10-02 acceptance renders, showed something other than
what the store held. Only surfaced when the relief-gate fix needed a render matching real output.

**Why:** a hand-maintained inspection/dev tool that reimplements "roughly what the pipeline does"
instead of calling the pipeline's own functions drifts silently, and each use builds more
confidence in the wrong picture rather than less.

**How to apply:** when a DoD pass reviews a feature that ships or relies on a `tools/` inspection
script, check whether that script actually calls the production code path it claims to visualize
(diff it against the real pipeline function names), not just whether its output "looks
plausible." Flag drift as a finding even if it isn't the branch's own named defect — see also
[[feedback_verify_roadmap_prose_claims]] for the related habit of checking claims against the
artifact rather than its plausibility.
