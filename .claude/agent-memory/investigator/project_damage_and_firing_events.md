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
- **RESOLVED, 2026-09-25 (HMMWV) and reconfirmed 2026-10-20 (M163 Vulcan, capability only)**: ground
  AAA/gun units DO raise `S_EVENT_SHOOTING_START` with a populated, correctly-named `target` —
  observed for M163 Vulcan via `debrief.log` parsing on 2026-10-20 (two separate Vulcan units in one
  mission, one genuinely targeting the player, one genuinely targeting a different aircraft, both
  with `target` present every time). "AAA carries no target" is not a real engine behavior for this
  DCS version, as a general capability claim. **But that 2026-10-20 `debrief.log` turned out to be
  from the previous run of the mission, not the sortie whose `Vulcan-2` reading prompted the
  question** (see [[reference_debrief_log_for_firing_event_ground_truth]]'s mission-attribution
  caveat) — so it is evidence the capability exists, not evidence about that specific unit's
  specific reading. **A live `since_sim` check also refuted this session's first guess that the
  specific reading was a stale watchdog latch** (see
  [[project_emitter_tracker_watchdog_staleness]], now a refutation record, not a standing
  explanation) — the entry was a fresh 0.2s-old `SHOOTING_START`. **CLOSED, confirmed from this
  sortie's own `debrief.log` once the mission ended**: the specific `Vulcan-2` reading genuinely
  targeted the player's wingman (`targetMissionID 447`, not the player's `344`) — `targets_ownship:
  false` was correct, no code defect. A *different* Vulcan really had been shooting at the player
  ~4-13s earlier, and had already expired from the active list by the time of the query — two real,
  separate engagements looked like one confusing reading from outside the collector's event-by-event
  view. Full account: `aircraft-layer/research/2026-10-20-aaa-firing-target-recon.md`.
- `world.addEventHandler` reachability from the `"scripting"` dostring_in state specifically was
  never itself live-probed (only `missionCommands`/`env`/`trigger`/`coalition` were, in the F10 and
  velocity work) — inferred reachable by analogy, not confirmed.
- Raw event feed (initiator/weapon/target, no LOS/range) is theatre-wide and omniscience-unsafe
  without a gate mirroring `body-layer/src/perception/visibility.py`'s naked-eye LOS gate — flagged
  for Architect, gate design itself out of scope for this note.
