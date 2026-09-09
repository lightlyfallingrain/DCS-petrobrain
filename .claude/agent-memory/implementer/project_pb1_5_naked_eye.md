---
name: project_pb1_5_naked_eye
description: PB-1.5 naked-eye (binocular) visual detection channel -- what was built, where plan text left implementation choices open
metadata:
  type: project
---

Implemented `plans/pb1.5-naked-eye-detection/plan.md` stages 1, 2, 3, 6 (stage 4 deferred per
Decision #4, stage 5 is live/user-run, stage 7 was a separately-delivered probe script, not
touched). New: `body-layer/src/perception/object_model.py`, `visibility.py`,
`naked_eye_source.py`. Changed: `source.py` (added `SOURCE_NAKED_EYE_VISUAL_FILTERED`, unusually
placed in `source.py` itself per the plan, not in `naked_eye_source.py` like Hybrid's own
constant), `logger.py` (`PerceptionLogger.source` -> `.sources: list[PerceptionSource]`, no
`CompositePerceptionSource`).

**Why:** the channel gates on `visibility.py`'s ED-`HelperAI.lua`-grounded filter (angular-radius
tier x a binocular-aided-observation multiplier, per user Decision #6 -- explicitly NOT the
unaided eye, despite the "naked_eye" module/branch name) since no real DCS detection-existence
signal for ambient spotting has been confirmed exportable yet (Investigator Session 5). This is
the first code in the repo that actually calls `geometry.line_of_sight_clear` -- it had zero real
callers before this (Hybrid never used it), so `NakedEyePerceptionSource` is also the first
`PerceptionSource` needing a `sqlite3.Connection` to a built world-model `.sqlite` at construction,
which is why `logger.py main()` gained a required `--world-model-db` flag.

**How to apply:** three places the plan's prose left an implementation choice open, decided and
documented in `naked_eye_source.py`'s docstring -- read that docstring (or
`plans/pb1.5-naked-eye-detection/implementation.md`'s Notable Discoveries) before assuming a
different reading is "the bug":
1. `derived_world_position` is NOT quantised (stays exact ground-truth x/z, matching Hybrid) --
   only `bearing_deg`/`range_m`/`classification_raw` (the crew-facing fields) are quantised to
   ED's `OP_A*`/`OP_D*`/class vocabulary.
2. Bearing quantisation computes the clock bucket relative to ownship heading, then converts the
   quantised result back to a *true* bearing before storing -- `Observation.bearing_deg` stays
   true-bearing-convention across both channels, never a raw heading-relative angle.
3. Range quantisation is "snap up to the bucket's upper bound" (containment), not literal
   nearest-of-24-values rounding -- e.g. 549 m -> `OP_D600M`, not `OP_D500M`.

See also [[feedback_binocular_not_unaided_eye]] for the constant-naming trap this created.
