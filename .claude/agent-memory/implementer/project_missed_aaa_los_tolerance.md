---
name: missed-aaa-los-tolerance
description: LOS terrain-tolerance fix (option 1) split into mechanism-then-calibration commits; airframe-tactics lapse condition belongs in the constant's comment
metadata:
  type: project
---

world-model's `query.line_of_sight.line_of_sight_clear` gained `_TERRAIN_TOLERANCE_M` (12.0 m,
derived from M7's own SRTM-vs-DCS stddev of 11.52 m) to fix a real defect: an elevation grid cell
that overestimates ground height by roughly its own measured error can place a unit permanently
"underground" relative to the model, blocking terrain LOS from every angle regardless of true
visibility. See `plans/missed-aaa-detection/debug.md` for the full diagnosis and reproduction.

Two things worth remembering for similar work:

1. **Mechanism/calibration split, done for real, not just claimed.** Committed the tolerance
   mechanism first with the constant at `0.0` (behaviour-preserving no-op, verified with a full
   pytest run before committing) and the two calibration-dependent regression tests temporarily
   removed, then a second commit bumped the value to 12.0, restored the tests, and expanded the
   comment. This is more faithful than writing the final code once and describing it as "two
   commits" after the fact — the mechanism commit is independently revertible and its own tests
   still pass.

2. **A tolerance's cost depends on how the *thing being modeled* behaves, not just on the data
   source's error budget.** The user added, mid-task, that 12 m is acceptable specifically because
   the Mi-24P attacks in a run rather than hiding-and-popping-up — a Ka-50/Apache flying that
   tactic would sit exactly inside the margin the tolerance opens. This became an explicit "lapse
   condition" paragraph in the constant's own comment (not just a footnote), same pattern as this
   project's other standing-decision lapse conditions (see [[project_m2_raster_open_questions]] and
   AGENTS.md's own security/performance cadence history for the general shape). When a tolerance or
   threshold is being justified by one data property, check whether it also depends on a *behavior*
   assumption that could change under a different consumer.
