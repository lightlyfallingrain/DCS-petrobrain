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
- **Single most important open question**: whether ground AAA units (ZU-23/Shilka) specifically
  raise `S_EVENT_SHOOTING_START` (the wiki's own definition is unit-generic — "any unit... high
  rate of fire" — but every worked example given is an aircraft cannon, e.g. GAU-8). Not resolved
  by any source found. A named live probe (Probe B in the research file) is the way to close it —
  do not assume yes.
- `world.addEventHandler` reachability from the `"scripting"` dostring_in state specifically was
  never itself live-probed (only `missionCommands`/`env`/`trigger`/`coalition` were, in the F10 and
  velocity work) — inferred reachable by analogy, not confirmed.
- Raw event feed (initiator/weapon/target, no LOS/range) is theatre-wide and omniscience-unsafe
  without a gate mirroring `body-layer/src/perception/visibility.py`'s naked-eye LOS gate — flagged
  for Architect, gate design itself out of scope for this note.
