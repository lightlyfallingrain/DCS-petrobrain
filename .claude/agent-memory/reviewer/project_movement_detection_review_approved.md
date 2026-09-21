---
name: movement-detection-review-approved
description: Movement detection (feature/movement-detection) review outcome and how the omniscience-boundary/replay-determinism claims were independently verified
metadata:
  type: project
---

Reviewed and APPROVED clean (no required fixes) 2026-09-22, commit `2af3803`. First milestone to
introduce a behaviour-change event (`CONTACT_MOTION_CHANGED`) and the project's first general
mission-scripting **data** feed (a third Hook script, `petrobrain-mission-telemetry-hook.lua`,
polling `Object.getVelocity()` via `dostring_in` at 1 Hz).

**How the two sharpest claims were checked, not just read:**
- Omniscience boundary ("velocity never leaves `perception/`"): `grep -rn "velocity\|Vec3"
  body-layer/src/belief/` found only docstring prose, never a `Vec3`/velocity field; `grep -rn
  "^from belief" body-layer/src/perception/` was empty. Cheap, mechanical, and exactly the kind of
  check that would have caught a leak instantly if the implementer had gotten this wrong.
- Replay determinism (`t` in `s = v*t` must cancel, sim time must be stamped via `timer.getTime()`
  inside the scripting state, never `DCS.getRealTime()` in the Hook): read both gate functions in
  `perception/motion.py` line by line (no `dt` parameter anywhere) and read the Hook's Lua
  `VELOCITY_CODE` string itself — `DCS.getRealTime()` is used only for the poll-gate timing check
  in the Hook body, never inside the `dostring_in` payload that becomes the wire value.

**Reusable pattern**: for a plan with named "sharpest risk" items like these, grep for the
forbidden thing's absence (import boundary, a `dt` parameter, a wall-clock call inside the wrong
scope) rather than reading prose reassurances — a structural absence check is fast and catches a
regression a docstring claim can't.

See [[pb2-review-log-append-only]] — this was `plans/movement-detection/review.md`'s first
review, so a fresh file was correct; future stages on this feature (if any) should append, not
overwrite.
