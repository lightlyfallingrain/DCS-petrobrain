---
name: reference_firing_events_channel
description: Where to look first for anything about DCS firing/damage events (S_EVENT_*) on the mission-scripting bridge -- the production Hook script and schema are the ground truth, not the 2026-09-24 research note alone.
metadata:
  type: reference
---

For any question about what firing/damage events DCS exposes and what's already wired into
Petrobrain, read in this order:

1. `aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua` — the production Hook script.
   Its `ALLOWED_KINDS` table (currently `S_EVENT_SHOOTING_START`/`_END`, `S_EVENT_SHOT`,
   `S_EVENT_DEAD`, `S_EVENT_CRASH` — **not** `S_EVENT_HIT`) is the authoritative list of what
   actually reaches the wire today. Position (`x`/`z`) is resolved Hook-side **only** for
   `S_EVENT_SHOT` (the initiator's position at launch time, frozen — the `[[BL-B74]]` seam);
   every other kind sends the literal string `"nil"` for both coordinates.
2. `aircraft-layer/src/schema/firing.py` — wire format / `FiringRawEvent` fields (`kind`, `t_sim`,
   `initiator: str`, `targets_ownship: bool`, `x: float | None`, `z: float | None`).
3. `aircraft-layer/src/collector/firing_receiver.py` — `EmitterTracker`, the latch/watchdog state
   machine (`FIRING_MIN_VISIBLE_S = 1.5`, `FIRING_WATCHDOG_S = 180.0`). It already has the "visible
   for a few seconds past the event" mechanism any new light-source/visibility feature would want
   to reuse — but it currently only acts on `S_EVENT_SHOOTING_START`/`_END`/death kinds;
   `S_EVENT_SHOT` is explicitly a documented no-op in `_apply()` (a seam reserved for `[[BL-B74]]`,
   not yet built).

The `2026-09-24-damage-and-firing-events-over-mission-bridge.md` research note is the *design*
history (why these event kinds were chosen, what was probed) but is dated before the Hook shipped
— always cross-check its claims against the Hook/schema/receiver files above, which are the
current ground truth. E.g. that note discusses `S_EVENT_HIT` as documented/available, but the
shipped Hook never forwards it — "documented as existing" and "already wired into this project"
are different claims and this note conflates them if read alone.

See also `mission-interpreter/research/2026-11-25-mission-date-and-start-time-for-light-level.md`
and `aircraft-layer/research/2026-11-25-mission-start-time-and-light-level-export-api.md`
(BL-B124 investigation) for a worked example of reading this chain end to end.
