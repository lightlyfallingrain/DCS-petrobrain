---
name: damage-and-firing-events
description: getLife/getLife0 damage-fraction and firing-event (S_EVENT_SHOT/SHOOTING_START/HIT/DEAD) findings over the mission-scripting bridge
metadata:
  type: project
---

Session 2026-09-24, desk research only (no DCS access). Full writeup:
`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`.

- `Unit.getLife()`/`getLife0()` are documented Mission Scripting API (Hoggit), reachable via the
  same `net.dostring_in("scripting", ...)` bridge and same per-unit loop shape already proven live
  by `petrobrain-mission-telemetry-hook.lua`'s `getVelocity()` poll — adding damage is a same-shape
  extension, not a new mechanism. No separate "is smoking" boolean exists; DCS's native
  health-correlated smoke (forum-claim level, not primary-source-read this session) means the same
  life-fraction ratio is very likely already the visual-correlate proxy.
- **Critical, confirmed-from-primary-text finding**: `S_EVENT_SHOT` explicitly excludes machine-gun/
  autocannon fire by name (Hoggit's own wording) — routed instead to `S_EVENT_SHOOTING_START`.
  Confirms the task's suspicion that AAA gunfire could be invisible to a shot-event-only design.
- **RESOLVED, 2026-09-25 (HMMWV) and reconfirmed 2026-10-20 (M163 Vulcan specifically)**: ground
  AAA/gun units DO raise `S_EVENT_SHOOTING_START` with a populated, correctly-named `target` —
  confirmed for M163 Vulcan via `debrief.log` parsing (two separate Vulcan units in one mission,
  one genuinely targeting the player, one genuinely targeting a different aircraft, both with
  `target` present every time). "AAA carries no target" is not a real engine behavior for this DCS
  version — see `aircraft-layer/research/2026-10-20-aaa-firing-target-recon.md` and
  [[reference_debrief_log_for_firing_event_ground_truth]]. A later `targets_ownship=false` reading
  for a unit visibly firing at the player is much more likely this project's own
  `EmitterTracker` watchdog staleness (see [[project_emitter_tracker_watchdog_staleness]]) than a
  DCS-internals gap.
- `world.addEventHandler` reachability from the `"scripting"` dostring_in state specifically was
  never itself live-probed (only `missionCommands`/`env`/`trigger`/`coalition` were, in the F10 and
  velocity work) — inferred reachable by analogy, not confirmed.
- Raw event feed (initiator/weapon/target, no LOS/range) is theatre-wide and omniscience-unsafe
  without a gate mirroring `body-layer/src/perception/visibility.py`'s naked-eye LOS gate — flagged
  for Architect, gate design itself out of scope for this note.
