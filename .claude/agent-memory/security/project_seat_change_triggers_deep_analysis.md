---
name: project_seat_change_triggers_deep_analysis
description: seat-pilot/seat-copilot effector triggers (feature/seat-change-triggers) deep analysis -- approved clean; apw_seat validated by strict string-equality allow-list, not a numeric conversion, so the recurring NaN/Infinity/int-conversion LAN-boundary bug class does not apply here
metadata:
  type: project
---

Deep analysis (Mode 2) of `feature/seat-change-triggers` (`e2ee3f98` on `a55f7e97`), body-layer
only. Two new `EffectorTrigger`s (`SEAT_PILOT`/`SEAT_COPILOT`) fire from a new `apw_seat` field on
the existing `GET /ai_pilot_wheel/latest` LAN feed. Full writeup:
`plans/seat-change-triggers/security-review.md`.

**Worth remembering as a positive pattern, not just a clean verdict**: `belief.ai_pilot_wheel.
_as_seat` validates an incoming string field with `value == "pilot"` / `value == "operator"` else
`None` -- a closed allow-list, never a conversion. This is the right shape to point an Implementer
at when a new enum-like field arrives at a LAN boundary, specifically *because* it sidesteps
[[project_recurring_unguarded_nonfinite_float_before_conversion]] / 
[[project_nan_infinity_int_conversion_at_lan_boundary]]'s bug class entirely: that class only bites
when a wire value is parsed into a float/int before being used (`isinstance` passes NaN/Infinity,
then `int()` raises something other than the module's own `*ParseError`). A field that only needs
to answer "is it exactly one of these known strings" should be written as an equality allow-list,
never routed through a numeric conversion at all. Checked here: no numeric path for `apw_seat`
exists anywhere in `ai_pilot_wheel.py`.

**Trust-boundary reasoning reused directly from [[project_bl15_mission_start_plan_review]]**: the
LAN actor who can forge/MITM `GET /ai_pilot_wheel/latest` already has the same capability BL-15
accepted for the mission-start/belief-wipe channel (single-user/LAN-only scope, "same local-
attacker standard already applied to every other loopback/LAN channel, not a new trust boundary").
This feature's blast radius is narrower than that precedent (fires one of two fixed, committed
sequence files; no belief-state wipe, no arbitrary content) -- presented as an extension of the
standing acceptance rather than a new backlog item. Lapse condition restated: lapses if project
scope ever widens to multiplayer/shared-machine.

**Rate/DoS check**: `effector_engine`'s existing D1 rule (a trigger already running when re-fired
is marked pending, not queued twice; at most one write per trigger per poll) already bounds rapid
forged seat-flapping -- same bound every other `every_time` trigger has. No new DoS class.
