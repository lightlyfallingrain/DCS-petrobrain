---
name: project-emitter-tracker-watchdog-staleness
description: a stale, frozen-at-SHOOTING_START targets_ownship can outlive the real engagement by up to FIRING_WATCHDOG_S (180s) if the live Hook misses the matching SHOOTING_END -- the likely explanation for a live "false" reading on a unit visibly firing at the player
metadata:
  type: project
---

Session 2026-10-20 (`aircraft-layer/research/2026-10-20-aaa-firing-target-recon.md`), investigating
why a visibly-player-targeting M163 Vulcan read `targets_ownship: false` in `/firing/latest`
(`docs/acceptance/2026-10-20-sortie-feedback.md` F6).

**The mechanism, read from code, not inferred**: `collector/firing_receiver.py`'s `ActiveEmitter.
targets_ownship` is set only in `EmitterTracker._apply`'s `S_EVENT_SHOOTING_START` branch
(mirroring `petrobrain-firing-events-hook.lua`'s own Hook-side `targetsOwnship()`, which likewise
computes the bit only at `SHOOTING_START` and never revisits it). A `SHOOTING_END` only tightens
`expires_at_sim`; it never updates `targets_ownship`. So once an entry exists, its `targets_ownship`
value is frozen at whatever the *original* engagement was — correct for that engagement, but stale
forever after if the entry itself outlives it.

**When an entry outlives its real engagement**: if the Hook's live `world.addEventHandler` channel
receives the matching `SHOOTING_END`, the entry expires quickly (`FIRING_MIN_VISIBLE_S = 1.5`s past
`since_sim`). If it does **not** receive that `SHOOTING_END` (the unit is still alive, so the
`S_EVENT_DEAD`/`_CRASH` removal path doesn't apply either), the entry instead survives until
`FIRING_WATCHDOG_S = 180.0`s past `since_sim` — two and a half minutes of a stale, correctly-computed
-at-the-time-but-now-meaningless `targets_ownship` value.

**Why a live reading can disagree with DCS's own `debrief.log` for the same unit**: these are two
independently-implemented DCS subsystems (debrief.log's recorder vs. the live
`world.addEventHandler` registration this project's Hook subscribes to) — already established in
`aircraft-layer/research/2026-09-24-damage-and-firing-events-over-mission-bridge.md`'s Addendum,
re-confirmed as load-bearing here. `debrief.log` captured the `SHOOTING_END` for the Vulcan in
question; the live channel plausibly did not, which is the simplest explanation consistent with
every artifact gathered (see the research note's Finding 3 for the full timing argument).

**What would upgrade this from "well-supported hypothesis" to "confirmed"**: live-querying
`GET /firing/latest` at the moment of a stale reading and checking the active entry's `since_sim`
against the nearest `debrief.log` `start shooting` timestamp for the same unit. Not done this
session — see [[feedback_bash_network_to_localhost_blocked_this_session]].

**Relevant to Architect, not decided here**: surfacing `since_sim`/engagement age on the wire, or
re-examining `FIRING_WATCHDOG_S`'s value, are both named as options in the research note's
"Possible Approaches" — this memory does not pick one.
