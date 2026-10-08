# The ED forum thread on detecting destroyed objects from `Export.lua` — closed, no finding

**Date:** 2026-10-08
**Source:** `forum.dcs.world/topic/194777-exportlua-destroyed-object/`, pasted by the user after the
URL 403'd across three separate sessions (the standing "forum 403 → ask the user to paste" rule).
**Status:** **Closed. The thread does not answer the question it was wanted for.**

---

## Why it was wanted

`todo/questions.md` `Q9.1` had this thread open because its title points straight at the
destroy/respawn **object-id lifecycle** — the open risk on the `Unit:getID()` branch of the
2026-10-06 unit-id join probe. The hope was that a paste would settle it without a second probe.

## What the thread actually contains

Three posts over sixteen months, and **no answer**. The asker tries two approaches from
`Export.lua`:

1. Walking `coalition.getGroups(...)` → `group:getUnits()` → `unit:getLife()` to detect death by
   life value. Reports: *"coalition seems to be null in Export.lua"*.
2. Registering a `world.addEventHandler` for `S_EVENT_CRASH` / `S_EVENT_DEAD`. Reports it
   *"doesn't work in export.lua"*.

Closing with: *"I really don't understand why objects like coalition or world are not available in
Export.lua ??"* — and, over a year later, a second user asking *"Have you found a solution for
this?"* Nobody replied.

**So the destroy/respawn id-lifecycle question is untouched by this thread.** It is not a source of
an answer, and no further attempt on this URL is warranted. Recorded here so a fourth session does
not rediscover that.

## Two incidental confirmations worth keeping

Neither is new to this project, but both are now attested by an independent source rather than only
by our own probing:

- **`Export.lua` state has no `coalition` and no `world`.** This is exactly the state separation this
  project already works around: the LOS Hook and the F10 Hook reach the mission-scripting state via
  `net.dostring_in("scripting", ...)` from Hook state rather than trying to touch those tables from
  `Export.lua`. The thread is a 2018/2020 datapoint that this is longstanding engine behaviour and
  not a version quirk — and that a user hitting it head-on simply gets stuck, which is what the
  bridge exists to avoid.
- **`unit:getLife()` and the `S_EVENT_DEAD`/`S_EVENT_CRASH` event handlers do exist** — in the
  *scripting* state, which is reachable from our Hook scripts by the same bridge. If a damage/death
  feed is ever wanted (there is already a `petrobrain-damage-events-probe-hook.lua` in
  `dcs-export/`), those are the two mechanisms, and the thread is a reminder that they must be
  called from the scripting state, never from `Export.lua`.
- The thread also mentions **MIST** maintaining a list of destroyed objects and scenery. Not adopted
  and not recommended here — a mission-editor script library is a dependency on the mission author's
  setup, and this project flies missions created by others (user direction: *"I do not create
  missions myself"*). Noted only so the option is on record as considered and declined.

## Consequence for the open risk

The `Unit:getID()` destroy/respawn lifecycle question stays open — **and it no longer matters much**,
for a reason that arrived from a different direction entirely. The 2026-10-06 probe established that
`Unit:getObjectID()` does not exist on `StaticObject` (`<NONE>`, 94/94), so no integer key spans both
populations and the join key stays `getName()`. The id-lifecycle risk was a risk *on a branch this
project did not take*.

If it ever becomes live again, the answer will have to come from a probe — spawn, destroy, respawn,
compare ids — not from the forums.
