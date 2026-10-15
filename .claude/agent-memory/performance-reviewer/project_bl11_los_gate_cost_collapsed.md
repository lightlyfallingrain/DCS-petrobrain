---
name: bl11-los-gate-cost-collapsed
description: check_visibility's terrain-LOS gate (gate 4) now costs ~4.3us/candidate, not the pre-BL-11 540us/candidate sqlite-sample figure -- BL-11 Stage 4's fail-closed rewrite made it a boolean read, not a raycast
metadata:
  type: project
---

`plans/player-bubble/performance.md`'s **540 us/candidate** terrain-LOS cost (measured against
`store.reader.sample_grid`, a ~20-point sqlite grid sample) is **stale** as of `BL-11` Stage 4
(`plans/bl11-stage4-fail-closed/plan.md`). `visibility.check_visibility`'s gate 4 no longer calls
world-model's offline `line_of_sight_clear` primitive at all -- it reads `candidate.live_los_clear`
(a plain boolean, already joined onto every raw candidate upstream by
`naked_eye_source._resolve_los_by_unit_name`, the same cheap per-object dict-join shape as the
velocity join) and treats `None` as a fail-closed reject. The actual terrain/building raycast moved
to the DCS-side Lua Hook (`plans/dcs-driven-los/plan.md`, X-B29), bounded at
`MAX_SIGHTLINES_PER_CALL = 128` -- a different subsystem with its own already-measured bound
([[dcs-driven-los-cone-scoping]]), not reachable from `check_visibility` any more.

**Measured** (`body-layer/.venv`, pinned ruff==0.16.6/mypy==2.3.1/pytest==9.1.1/numpy==2.4.6/
pyproj==3.8.0, 200 000 calls per path, `UNAIDED_OPTIC`, `conn`/`theatre` passed as dead params per
the function's own docstring):

- Full gate chain through `ADMITTED` (`live_los_clear=True`): **4.345 us/call**.
- Rejected at gate 4 (`live_los_clear=False`): 3.419 us/call.
- Rejected at gate 4, fail-closed (`live_los_clear=None`): 3.424 us/call.

That's a **~125x** reduction from the figure still being cited in `plans/9k113-sight/plan.md` §12b
as the basis for a "+20-40% on a 12.6ms tick" cost estimate for the 9K113 player-bubble cone. The
plan cites both the stale 540us figure and "12.6ms after BL-11" in the same paragraph without
noticing they're inconsistent -- the 12.6ms figure already reflects the cheap post-BL-11 gate.

**Lesson for future reviews**: a per-candidate cost figure attached to a specific gate is only as
current as the code behind that gate. `BL-11`/X-B29 replaced an expensive in-process DB primitive
with a cheap join to an externally-computed (DCS-side) verdict -- the kind of architecture change
that silently invalidates every downstream cost estimate built on the old primitive's number, with
no test failure to flag it (the old number was never wrong when measured, only stale once the gate
it described was rewritten). Grep for the primitive (`sample_grid`, `line_of_sight_clear`) in the
current gate's own code before trusting an inherited per-candidate figure, not just in the plan that
cites it. Full numbers and the corrected cone-cost projection:
`plans/9k113-sight/performance-cone-gate.md`.

See also [[project_player_bubble_capped_by_existing_gates]] (the same filter, the same kind of
"exclusion rate is not the saving" lesson, now compounded by this cost collapse) and
[[dcs-driven-los-cone-scoping]] (where the real raycast cost now lives, and its own bound).
