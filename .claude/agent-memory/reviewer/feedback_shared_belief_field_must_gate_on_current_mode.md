---
name: shared-belief-field-must-gate-on-current-mode
description: when a new sensor readback feeds a field that multiple perception/optic modes read, check every caller gates the readback on the mode actually in effect, not just "present or absent"
metadata:
  type: feedback
---

A new effector readback (e.g. the 9K113 sight's raw position, body-layer's
`GuidanceUnitState.sight_az_raw`/`sight_elev_raw`) that feeds a field shared across modes
(`OpticState.actual_aim_azimuth_deg`/`elevation_deg`, read generically by
`perception/naked_eye_source.py` for naked-eye *and* binocular gaze, not only sight gaze) must be
gated on **which mode is actually in effect this poll**, not merely on whether the readback exists.
BL-B80 wired `sight_az_raw`/`sight_elev_raw` into `_apply_active_gaze`/`advance_sight_aim`
unconditionally once a readback sample had ever arrived — so naked-eye/binocular perception's gaze
cone was anchored to the literal sight-head position for the rest of the mission after the sight's
first use, including during the gyro-alignment window where the optic is deliberately capped away
from the sight *for this exact reason* (perception must not come from the sight during alignment).
The cap worked for `optic_decision.optic` itself; the very next block undid its purpose by feeding
the sight's raw position into the shared aim field regardless.

**Why:** a readback field that is "sticky" (set once, never cleared back to `None`, per
`refresh_readback`'s own absence-leaves-prior-value convention — correct for its own purpose) looks
safe to pass unconditionally because it is `None` until first used. The bug only appears once the
feature it belongs to (the sight) has been used once this mission, after which it silently
contaminates every other mode for the rest of the mission. No test combining a non-sight optic with
a set readback field existed, so nothing caught it.

**How to apply:** whenever a new readback field is threaded into a shared struct/field that more
than one mode consumes, grep every consumer and confirm each caller passes the readback only while
its *own* mode is the one actually resolved this poll (the post-cap decision, not the pre-cap
request) — never "whenever the readback happens to be present." Write at least one test that holds
the readback set while a *different* mode is active and asserts the shared field still reflects
that other mode's own model, not the readback.
