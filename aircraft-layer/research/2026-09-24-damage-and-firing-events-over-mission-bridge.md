# Damage state and firing events over the mission-scripting bridge

**Date:** 2026-09-24
**DCS version:** 2.9.29.27278 (per prior sessions' `autoupdate.cfg` read — this session had no
`$DCS_INSTALL_PATH`/`$DCS_SAVED_GAMES_PATH` access, Mac dev machine; desk research only, no live
probe run)
**Theatre:** n/a (scripting-API question)

### Question

`plans/brain-layer/explore-notes.md` records two findings that depend on unverified DCS-internals
claims:

1. **Can Petrovich perceive damage at all** — "is it dead yet?" → "no, but smoking" / "yes" — given
   `WorldObjectSample` today carries no life/fire/smoke field?
2. **Are firing events (being engaged) exportable**, and specifically: does AAA/cannon fire — the
   user's stated most-likely threat case — raise any detectable event, given `S_EVENT_SHOT` is
   known to be weapon-object-specific?

Both are scoped to what is reachable through the mission-scripting bridge already shipping in
production: `net.dostring_in("scripting", ...)`, polled at 1 Hz from a Hook script, exactly as
`petrobrain-f10-commands-hook.lua` (since 2026-09-13) and `petrobrain-mission-telemetry-hook.lua`
(unit velocity, since 2026-09-22) already do. See those two files and
`aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md` /
`2026-09-21-unit-velocity-via-mission-scripting.md` for the mechanism this note builds on rather
than re-derives.

### Findings

**Q1 — damage/life**

1. **`Unit.getLife()` / `Unit.getLife0()` are real Mission Scripting API, available since patch
   1.2.0, and apply to Unit, Static Object, and Scenery Object** — **evidence: documented** —
   **source:** Hoggit `DCS_func_getLife` / `DCS_func_getLife0`. `getLife()` returns the unit's
   **current absolute hit points** (a number, e.g. `9`); `getLife0()` returns the unit's **initial
   ("max") hit points**, fixed at spawn and never changing. Fraction remaining is
   `getLife() / getLife0()` — Hoggit gives this exact usage pattern. A unit is dead when `getLife()`
   drops below `1`. Ground/ship units that are actively burning-but-not-yet-detonated read `0`
   until detonation; aircraft have more complex per-subsystem damage that isn't further documented
   here.
2. **This is the same environment and the same per-unit-loop shape already proven live** —
   **evidence: reproduced-locally (existing production code)** — **source:**
   `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua`'s `VELOCITY_CODE`, which
   already iterates `coalition.getGroups(coa)` → `grp:getUnits()` → per-unit `pcall`, and packs a
   compact string return (`dostring_in` can only return one simple scalar). Adding `unit:getLife()`
   and `unit:getLife0()` to that existing loop is a same-shape, same-cost-class extension, not a new
   mechanism — no new bridge call, no new registration, no new `autoexec.cfg` requirement beyond
   what unit-velocity already needs.
3. **No queryable "is visibly smoking" boolean exists anywhere in the documented Mission Scripting
   API** — **evidence: documented (absence), inferred (mechanism)** — **source:** no Hoggit page,
   forum thread, or community script found this session exposes such a flag; `getDrawArgumentValue`
   exists (animation-argument reads, e.g. barrel rotation, canopy open) but nothing found ties a
   draw argument to a damage-smoke state, and DCS's damage-smoke rendering is not modeled as an
   `EDM` draw argument in any source surfaced.
4. **DCS's stock engine does render health-correlated smoke natively, without any mission script,
   as of a fairly recent version** — **evidence: forum-claim, moderately reliable** — **source:**
   Hoggit "DCS command smoke on off" / "DCS func smoke" page context plus ED changelog language
   surfaced in search ("smoke from vehicles and some static objects based on health... different
   levels of smoke giving a better idea visually of damage inflicted"; changelog entries reference
   tuning of "smoke after non-lethal damage" and "smoke after damage for ships with old damage
   model"). This is **not a primary-source read** — no changelog page or ED doc was fetched and
   read directly this session, only search-engine summary text. Label this **forum-claim**, not
   documented, until a changelog page is actually read.
5. **Consequence of 3+4, if 4 holds**: there is no separate boolean to query, but there does not
   need to be one. The visible "smoking" state a player observes is (per finding 4) already driven
   by the same health value `getLife()`/`getLife0()` expose. A "smoking, not dead" narration can be
   derived entirely from the life-fraction threshold (e.g. `life0 > life > 0` combined with a
   fraction cutoff), without any new DCS capability beyond finding 2. This is **inferred** — the
   claim is that DCS's own internal smoke-trigger fraction and a narration threshold chosen on the
   Petrobrain side will roughly agree, not that they are proven identical. A live-observed
   correlation (shoot a unit, watch when smoke starts, log `getLife()/getLife0()` at that moment)
   would upgrade this from inferred to reproduced-locally.
6. **A destroyed unit stops appearing in `LoGetWorldObjects()` — this is the existing, already
   fairly strong finding from `2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md`,
   re-cited, not re-derived** — **evidence: reproduced-locally (via Tacview's production source),
   not a first-party ED statement, not this project's own live probe** — **source:** that file's
   Finding 1 (Tacview's `TacviewExportDCS.lua` treats a `LoGetWorldObjects` key's disappearance as
   the object's destroy event, `!20`). **Latency**: bounded only by the export poll interval
   (currently 5 Hz / 0.2s for world-objects, per `Export.lua`'s shared throttle — see
   `aircraft-layer/ROADMAP.md`'s open "split the export throttle" item) once DCS's own internal
   state actually removes the unit. What is **not established** by any source found: how long DCS
   itself keeps a "dead wreck" as a distinct renderable object internally (a burning hulk visibly
   persists on screen for a while after a kill) — whether that wreck still appears in
   `LoGetWorldObjects()` under a different name/type (e.g. as a scenery/static "wreck" object) or
   vanishes immediately at the moment of death is **unresolved**, not covered by the Tacview read.
   This matters for the "is it dead yet" UX: if a burning-hulk wreck keeps appearing as some object
   with `getLife() < 1`, the fallback signal (disappearance) and the health signal (via finding 2)
   could briefly disagree.
7. **Cost per poll for ~50 units, if `getLife`/`getLife0` were added to the existing velocity
   loop**: **not established — same open question as unit-velocity's own unmeasured cost.**
   `aircraft-layer/ROADMAP.md`'s backlog already flags "no confirmed, quantified per-call cost
   exists at realistic unit counts (~50-200)" for the `getVelocity()` loop itself, unmeasured as of
   this session. Two additional field reads per unit (`getLife`, `getLife0`) on top of an
   already-unmeasured `O(N)` loop is a small constant-factor addition, not a new measurement
   category — it should ride on the same self-measurement instrumentation
   (`bridge_call_ms`/`unit_count` already logged every poll by
   `petrobrain-mission-telemetry-hook.lua`) rather than get its own separate probe.

**Q2 — firing events**

8. **`world.addEventHandler(handler)` is real, documented Mission Scripting API** — **evidence:
   documented** — **source:** Hoggit `DCS_func_addEventHandler`. Registration pattern: a table with
   an `onEvent(self, event)` method, passed to `world.addEventHandler`. The wiki does not state
   whether multiple handlers may coexist, though a paired `removeEventHandler` exists.
9. **The event-type enumerator (`world.event`) includes `S_EVENT_SHOT` (1), `S_EVENT_HIT` (2),
   `S_EVENT_DEAD` (8), `S_EVENT_SHOOTING_START`, `S_EVENT_SHOOTING_END`, and 55+ others** —
   **evidence: documented** — **source:** Hoggit `DCS_singleton_world`.
10. **`S_EVENT_SHOT` fires for "any unit that fires a weapon" — but explicitly, by name, excludes
    machine-gun/autocannon fire, which is routed to `S_EVENT_SHOOTING_START` instead** —
    **evidence: documented, primary Hoggit text quoted directly** — **source:**
    `DCS_event_shot`: *"whenever any unit in a mission fires a weapon... But not any machine gun or
    autocannon based weapon, those are handled by shooting_start."* Payload: `id`, `time`,
    `initiator` (Unit), `weapon` (Weapon object). **This confirms the concern stated in the task
    directly: `S_EVENT_SHOT` alone would miss AAA/cannon fire — the user's stated most likely
    threat case — entirely.**
11. **`S_EVENT_SHOOTING_START` is the documented event for exactly the excluded case** —
    **evidence: documented** — **source:** `DCS_event_shooting_start`: *"occurs when any unit
    begins firing a weapon that has a high rate of fire"*, with the wiki's own worked examples
    naming "aircraft cannons (GAU-8), autocannons, and machine guns." Payload per that page and
    MOOSE's `Core.Event` docs: `initiator` (the firing unit) and `target` (if the AI has one
    assigned). A paired `S_EVENT_SHOOTING_END` exists ("occurs when any unit stops firing its
    weapon").
12. **Whether ground AAA units (ZU-23, Shilka/2S6, etc.) specifically raise
    `S_EVENT_SHOOTING_START` — as opposed to only aircraft-mounted cannons — is not stated
    explicitly by any source read this session.** — **evidence: inferred, moderate confidence** —
    **source:** the Hoggit description's own wording is unit-generic — *"any unit begins firing a
    weapon that has a high rate of fire"* — not aircraft-scoped; only the worked examples happen to
    be aircraft guns (GAU-8). A ZU-23-2/Shilka autocannon is mechanically the same "high
    rate-of-fire weapon" class the event is defined against. No forum thread, MOOSE source excerpt,
    or ED doc found this session gives a ground-AAA worked example or states an exclusion. This is
    the single most important unresolved point in this report, flagged per the task's own framing —
    **it should not be treated as confirmed until a live probe or an explicit source names a ground
    AAA unit.**
13. **`S_EVENT_HIT` fires "whenever an object is hit by a weapon," with no stated weapon-type
    exclusion** — **evidence: documented** — **source:** `DCS_event_hit`. Payload: `initiator`
    (Unit that fired), `weapon` (Weapon object — noted as sometimes absent in multiplayer due to
    desync, not relevant to this project's single-player scope), `target` (Object hit). Read
    together with Finding 10, this suggests `S_EVENT_HIT` is **not** filtered the way `S_EVENT_SHOT`
    is — a gun round that actually connects should raise `S_EVENT_HIT` even though its firing never
    raised `S_EVENT_SHOT`. This was not independently confirmed for gun rounds specifically (no
    source explicitly states "gun hits raise `S_EVENT_HIT`"); it is an inference from the absence of
    an exclusion clause, not a positive statement. **Also note: `S_EVENT_HIT` requires an actual
    hit — a miss (the far more common case for a burst of tracer fire that alerts the crew visually
    without connecting) raises nothing on this channel.** For the user's stated scenario ("being
    engaged" perceived before any hit occurs), `S_EVENT_SHOOTING_START` is the relevant event, not
    `S_EVENT_HIT`.
14. **`S_EVENT_DEAD` fires "when an object is completely destroyed," payload `id`/`time`/
    `initiator` (the destroyed object)** — **evidence: documented** — **source:** `DCS_event_dead`.
    Wording is object-generic, not aircraft-scoped, consistent with Finding 6's `LoGetWorldObjects`-
    disappearance signal but a distinct, event-driven channel (push, not poll) that could in
    principle fire with lower latency than the 1 Hz/5 Hz poll cadence — **not measured, since no
    live probe was run this session.**
15. **Mechanically, registering `world.addEventHandler` once and draining a queue by poll is the
    same pattern already proven live for F10 commands, extrapolated, not newly invented** —
    **evidence: inferred by direct analogy to reproduced-locally code, not itself live-tested** —
    **source:** `petrobrain-f10-commands-hook.lua`'s `REGISTRATION_CODE`/`POLL_CODE` split: a fixed
    literal registers a global (`PB_F10_QUEUE` there), idempotently guarded (`removeItem` /
    equivalent guard before re-adding, so a second `onSimulationStart` doesn't double-register); a
    second fixed literal drains the queue and returns a compact string every poll. The same shape
    would work for events: register a `PB_EVENT_QUEUE = PB_EVENT_QUEUE or {}` global once, an
    `onEvent` handler that appends a compact serialized string
    (`event.id .. ":" .. tostring(initiator and initiator:getName()) .. ":" .. tostring(event.time)`,
    etc.) to it, guarded against double-registration the same way (e.g. a
    `PB_EVENT_HANDLER_REGISTERED` flag global, since `world.addEventHandler` has no documented
    idempotent-registration behavior the way `missionCommands.removeItem` gives F10 registration —
    calling it twice would very plausibly install two handlers and duplicate every event). **This
    exact mechanism — `world.addEventHandler` reachable and persistent across polls in the
    `"scripting"` state specifically — has never been live-probed by this project.** Findings 7-11
    of `2026-09-13-f10-radio-menu-command-input.md` confirmed `missionCommands`, `env`, `trigger`,
    and (later, via the velocity work) `coalition`/`Unit` methods are reachable and that globals
    persist across polls in that state; `world` itself was never explicitly named in a probe
    result. It is very likely present (it is core, always-available Mission Scripting API, and
    `coalition`, a sibling core singleton, already confirmed reachable) but this is **inferred, not
    confirmed**.
16. **Event rate in a busy mission is not established by any source read this session.** No
    Hoggit page, forum thread, or framework doc gives a quantified events/second figure for
    `S_EVENT_SHOOTING_START`/`S_EVENT_HIT` under sustained AAA fire (a Shilka can fire ~3600 rd/min
    per barrel across 4 barrels in bursts). Whether `S_EVENT_SHOOTING_START` fires once per burst
    or is retriggered mid-burst is **not documented** — MOOSE's own docs were checked and don't say
    either. This bounds confidence on the "cost" half of Q2 to "unknown," separate from the
    "does it exist" half (Findings 10-13), which is well-documented.

### The no-omniscience gate (per the task's framing, not a design decision made here)

`S_EVENT_SHOT`/`S_EVENT_SHOOTING_START`/`S_EVENT_HIT` are theatre-wide and carry no line-of-sight or
visual-range information whatsoever — the payload is `initiator`/`weapon`/`target` object
references and a sim timestamp, nothing spatial-relative-to-ownship, nothing about detectability.
An ungated consumer of this feed would make Petrovich aware of every gun firing anywhere on the
map, which is exactly the omniscience violation the project's guiding principle forbids. Any
consumer of this channel needs the same LOS + visual-range gate `body-layer/src/perception/
visibility.py` already applies to the naked-eye channel, evaluated against `initiator`'s (or, for
`S_EVENT_HIT`, `target`'s) position versus ownship — this report does not design that gate, per
the Investigator role's scope, but flags it as load-bearing: the raw feed by itself is unusable
without it.

### Reproducible Test

No live probe was run this session (Mac dev machine, no DCS access). Two probes, both direct
extensions of already-deployed, already-proven Hook scripts — copy-pasteable for the user to run
on the Windows box. Neither should be committed into `dcs-export/` by this role; they're scoped
here as throwaway variants, same posture as the project's existing `*.probe-*.lua` spike pattern.

**Probe A — damage/life fraction, extends the existing velocity loop.** Take a disposable copy of
`petrobrain-mission-telemetry-hook.lua` and change `VELOCITY_CODE` to also read life:

```lua
local VELOCITY_CODE = [[
local parts = {}
local count = 0
for _, coa in pairs({coalition.side.NEUTRAL, coalition.side.RED, coalition.side.BLUE}) do
    for _, grp in ipairs(coalition.getGroups(coa) or {}) do
        for _, unit in ipairs(grp:getUnits() or {}) do
            if unit and unit:isExist() then
                local ok, v = pcall(function() return unit:getVelocity() end)
                local lifeOk, life = pcall(function() return unit:getLife() end)
                local life0Ok, life0 = pcall(function() return unit:getLife0() end)
                if ok and v ~= nil then
                    count = count + 1
                    parts[#parts + 1] = unit:getName() .. ":" .. tostring(v.x)
                        .. ":" .. tostring(v.y) .. ":" .. tostring(v.z)
                        .. ":" .. tostring(lifeOk and life or "NA")
                        .. ":" .. tostring(life0Ok and life0 or "NA")
                end
            end
        end
    end
end
return tostring(count) .. "|" .. tostring(timer.getTime()) .. "|" .. table.concat(parts, ";")
]]
```

Run a mission, shoot one ground unit until it starts visibly smoking (do not kill it yet), and read
`dcs.log`'s logged line for that unit at that moment. **What settles Finding 5**: does
`life / life0` cross a consistent, repeatable threshold (e.g. ~0.5) at the moment smoke visibly
starts, across a few different unit types? Then kill it and confirm whether the id keeps appearing
in `/world_objects/latest` post-death (settles the wreck-persistence question in Finding 6) — watch
for either the object vanishing from the next poll, or continuing to appear with `getLife() < 1`
under the same or a different name/type.

**Probe B — event registration and AAA-specific firing.** New Hook script (or extend the F10
commands hook's registration pattern with a second, independent `PB_EVENT_QUEUE` global — keep it
a separate registration call so a failure in one doesn't affect the other):

```lua
local EVENT_REGISTER_CODE = [[
if not PB_EVENT_HANDLER_REGISTERED then
    PB_EVENT_QUEUE = PB_EVENT_QUEUE or {}
    local handler = {}
    function handler:onEvent(event)
        local initName = event.initiator and (pcall(function() return event.initiator:getName() end) and event.initiator:getName() or "?") or "?"
        table.insert(PB_EVENT_QUEUE, tostring(event.id) .. ":" .. tostring(event.time) .. ":" .. initName)
    end
    world.addEventHandler(handler)
    PB_EVENT_HANDLER_REGISTERED = true
end
return "registered"
]]

local EVENT_POLL_CODE = [[
local queue = PB_EVENT_QUEUE or {}
local out = {}
for i = 1, #queue do out[i] = queue[i] end
PB_EVENT_QUEUE = {}
return table.concat(out, ";")
]]
```

Register once at `onSimulationStart` (mirroring `registerF10Menu`), poll at 1 Hz (mirroring
`pollAndForward`), log every drained line to `dcs.log`. Fly a mission with an active AAA unit
(a ZU-23 or Shilka set to engage) firing at the player or a decoy. **What settles Findings 12 and
16**: do any `event.id`s matching `S_EVENT_SHOOTING_START` (check the numeric id against the
Hoggit enumerator) appear with the AAA unit's name as `initiator` while it is firing? If yes, at
roughly what rate (does the queue fill with one entry per burst, or many)? If the AAA unit fires
and the queue never shows a `SHOOTING_START`/`SHOT`/`HIT` entry naming it, that is the answer this
report's Question 2 most needs and could not obtain without DCS access — **write it up as its own
finding, since it would reverse Finding 12's current "likely yes" inference.**

### Possible Approaches

- **Damage (Q1)**: no new bridge, no new registration — extend the existing unit-velocity poll's
  per-unit loop with `getLife()`/`getLife0()` (Findings 2, 7). Narration threshold ("smoking, not
  dead" vs "destroyed") is a design choice for Architect, informed by Probe A's threshold-vs-visual
  correlation once run. `LoGetWorldObjects` disappearance remains the correct fallback for "gone
  entirely" regardless of whether the life-fraction correlation is ever tuned tightly.
- **Firing events (Q2)**: `S_EVENT_SHOOTING_START` (not `S_EVENT_SHOT`) is the correct event to
  register for the AAA/cannon case; `S_EVENT_SHOT` alone would silently miss the user's stated most
  likely scenario, per Finding 10. Registering both, plus `S_EVENT_HIT` and `S_EVENT_DEAD`, is cheap
  (all four just add `if event.id == ... then` branches or a shared serializer inside one
  `onEvent`) and gives Architect the full set to choose from rather than needing a second probe
  later. **A LOS/visual-range gate on `initiator`'s position vs ownship, symmetric to
  `perception/visibility.py`'s naked-eye gate, is a hard precondition for using this feed at all** —
  see "The no-omniscience gate" above.
- **If Probe B shows ground AAA does not raise `S_EVENT_SHOOTING_START`** (the one negative outcome
  this report cannot rule out): the fallback the user already named in the explore-notes conversation
  — naked-eye tracer visibility via the existing LOS-heuristic perception channel — is not a
  fallback at all in that scenario, it is the *only* channel, and the event-based "priority danger,
  we're being engaged" signal the explore-notes conversation wanted would not exist. That would be
  the most consequential possible finding here and is exactly what Probe B is for.

### Unresolved

- **Ground-AAA applicability of `S_EVENT_SHOOTING_START`** (Finding 12) — the single most important
  open question, not resolvable from documentation found this session. Needs Probe B.
- **Whether `world` (and `world.addEventHandler` specifically) is reachable from the `"scripting"`
  dostring_in state** (Finding 15) — inferred by analogy to `coalition`/`missionCommands`/`env`
  being reachable there, never itself probed. Needs Probe B.
- **Event rate under sustained fire** (Finding 16) — no source quantifies this; matters for whether
  a 1 Hz poll (matching the existing bridge cadence) risks queue overflow or coalesced/lost bursts
  within a single poll interval, though even a lossy queue is likely acceptable for a threat-alert
  use case (the alert only needs to fire once, not count rounds).
- **Whether DCS's native health-correlated smoke (Finding 4) is confirmed by a primary ED source**
  — currently search-summary-sourced only; a changelog page or forum thread was not directly read.
  Downgrade to "needs reading" if Architect wants firmer footing before designing the narration
  threshold; Probe A's live correlation would supersede needing this anyway.
- **Wreck-object persistence after death** (Finding 6) — whether a burning hulk continues to appear
  in `LoGetWorldObjects()` post-`S_EVENT_DEAD`, and under what name/type. Needs Probe A's second
  half (kill the unit, watch subsequent polls).
- **`forum.dcs.world` threads on this topic were not attempted this session** — per the standing
  project finding that automated fetches to that domain 403 (`aircraft-layer/research/` memory:
  `forum-dcs-world-fetch`), no attempt was made and none is recorded as an unread gap in the
  give-up sense. If the user wants faster resolution than a live probe on some of the above, a
  targeted forum search (e.g. "S_EVENT_SHOOTING_START AAA" or "getLife smoke threshold") pasted
  manually would help, particularly for Finding 12.

### Verdict per question

- **Q1 (damage perception)**: **answerable without a new bridge or registration.**
  `getLife()`/`getLife0()` are documented, reachable via the exact mechanism already shipping, and
  extend an existing loop at near-zero marginal engineering cost. The "smoking" visual correlate is
  not a separate queryable flag, but is very likely already implied by the same life fraction
  (forum-claim-level evidence, Finding 4) — Probe A would upgrade this to confirmed. Destroyed-unit
  handling already has a working fallback (`LoGetWorldObjects` disappearance, existing finding) with
  one open edge case (wreck persistence, Finding 6).
- **Q2 (firing events)**: **answerable in mechanism, unresolved on the one fact that matters most.**
  Event registration is documented (`world.addEventHandler`) and mechanically a direct extension of
  the already-proven F10 registration/poll pattern (needs the named live probe to confirm `world`
  is reachable in `"scripting"` state, Finding 15 — a real but likely gap). `S_EVENT_SHOT` alone
  would miss AAA fire exactly as the task suspected (Finding 10, confirmed from primary Hoggit
  text); `S_EVENT_SHOOTING_START` is the documented event for that case, but **whether ground AAA
  units actually raise it is not confirmed by any source found and is the single question Probe B
  must answer before Architect designs around this channel.** If Probe B comes back negative, the
  event channel for Q2 does not deliver the user's stated primary scenario and the naked-eye/LOS
  channel becomes the only route, not a backstop.

### Sources

- `aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua` — production code, registration/poll
  pattern this report extrapolates from.
- `aircraft-layer/dcs-export/petrobrain-mission-telemetry-hook.lua` — production code, per-unit loop
  extended in Probe A.
- `aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md` — Findings 7-11, state-name
  reachability (`missionCommands`, `env`, `trigger` confirmed live in `"scripting"` state).
- `aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md`,
  `2026-09-21-unit-velocity-via-mission-scripting.md` — bridge mechanism and `Object.getVelocity()`
  precedent.
- `aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md` —
  destroyed-unit-disappearance finding, re-cited (Finding 6).
- Hoggit DCS World Wiki: `DCS_func_getLife`, `DCS_func_getLife0`, `DCS_singleton_world`,
  `DCS_func_addEventHandler`, `DCS_event_shot`, `DCS_event_shooting_start`, `DCS_event_hit`,
  `DCS_event_dead`, `DCS_func_getDrawArgumentValue` — fetched and read this session (documented-tier
  findings).
- `flightcontrol-master.github.io/MOOSE_DOCS/Documentation/Core.Event.html` — cross-check for event
  payload/frequency notes, no additional information beyond Hoggit found.
- Search-engine summaries (not directly read) for DCS native damage-smoke behavior and ED changelog
  language — labeled forum-claim throughout, not promoted to documented.

---

## Addendum, same day — `debrief.log` is a cheaper route to Finding 12

**Added by the main loop after the user reported lived evidence**, which outranks anything in the
documentation search above: *"I've seen DCS post mission logs show the likes of SHOOTING_START /
_END for AAA."*

This reorders the probes, and makes the most important open question answerable with **no Lua, no
Hook script and no code at all**.

`Saved Games/DCS/Logs/debrief.log` carries a post-mission `events = { … }` table whose entries have
a human-readable `type` string. Confirmed directly against the one debrief log synced into this
repo (`win-mac-sync/from-windows/dcs-logs/debrief.log`, 13511 lines, the Mi-24P Caucasus Free
Flight quick-start):

```
events =
{
	[1] =
	{
		linked_event_id	=	0,
		t	=	0,
		event_id	=	215,
		type	=	"group change option",
	}, -- end of [1]
```

Its full set of `type` values is `group change option` (86), `""` (32), `under control`,
`mission start`, `mission end`, `Mi-24P`. **No shooting event appears — and that neither confirms
nor refutes anything**, because it is a free-flight mission in which nothing fired. The log is
useful here only as proof of the *shape*: a named-event table, which is where the user's
recollection of `SHOOTING_START`/`SHOOTING_END` would have come from.

### What this changes

**Probe the debrief log before running Probe B.** Fly (or let run) any mission with an AAA unit
actually firing, then read `debrief.log`'s `events` table for a shooting-typed entry naming that
unit. That settles Finding 12 — whether ground AAA raises the event *at the engine level* — at
essentially zero cost, against Probe B's new Hook script, event-handler registration and 1 Hz poll.

**The two facts are genuinely separate, and this route only establishes one of them:**

1. *Does the engine raise a shooting event for ground AAA?* — `debrief.log` answers this.
2. *Does a `world.addEventHandler` registered through the `net.dostring_in("scripting", …)` bridge
   receive it?* — `debrief.log` cannot answer this; only Probe B can (Finding 15's unprobed
   reachability question).

Do not let the first stand in for the second. But the ordering is now clear: if the debrief log
shows no shooting event for a firing AAA unit, **Probe B is pointless** and the naked-eye/LOS
tracer channel is the only route, exactly as this report's Q2 verdict warned. Probe B is worth
building only once fact 1 is confirmed.

**Confidence on Finding 12 is accordingly raised from "inferred, moderate" to "user-reported
recollection, pending a one-command check"** — still not confirmed, but no longer resting on the
absence of an exclusion clause in a wiki page.

### Second addendum — Tacview, and what it does not prove

The user also notes that Tacview captures AAA and renders the individual rounds (seen in others'
recordings; Tacview is not installed here). Tacview has precedent as evidence on this project —
`aircraft-layer/research/2026-09-10-worldobjects-object-id-stability-tacview-confirmation.md` used
it to confirm `object_id` stability.

**It lands in the same category as `debrief.log`, for the same reason.** Tacview's DCS exporter is
a compiled plugin, not Lua this project can read or imitate, so "Tacview shows the rounds" is
evidence that the *engine* tracks gun rounds as first-class objects — not evidence that any
documented Lua surface exposes them to us. It is a third independent signal pointing at fact 1
above, and silent on fact 2.

Checked locally and found nothing either way: no combat-sortie `LoGetWorldObjects` capture exists
in this repo (only elevation/terrain probe output), and `win-mac-sync/from-windows/collector.log`
contains no shell/bullet/tracer/projectile/weapon token. That is an absence in a log that may never
have recorded object types at all, so it is not a negative result — recorded only so the next
reader does not repeat the search.

**Open question this raises, worth one line in a future probe rather than its own pass:** whether
`LoGetWorldObjects()` returns in-flight weapon objects at all. If it does, the tracer channel needs
no event handler whatsoever — it becomes an ordinary object in the feed the naked-eye channel
already gates on LOS and visual range, which would be by far the cheapest possible answer. Fold
this into Probe A's run rather than building anything for it: the probe already walks the object
table, so it costs one extra look at what is in there while something is firing.

### Probes built, 2026-09-24 — what to deploy and in what order

Both probes are committed (the report above suggested keeping them out of
`dcs-export/`; project practice is the opposite — `petrobrain-f10-probe-hook.lua` and seven
`Export.probe-*.lua` files already live there, so these follow that convention). Both write only to
log files and open no socket, so neither needs the collector running. Both were syntax-checked with
`luac -p`, including each embedded `dostring_in` snippet extracted and compiled separately.

**Order matters, because each step can make the next one unnecessary.**

1. **`debrief.log`, no deployment at all.** Any already-flown mission where AAA fired. If a shooting
   event appears in its `events` table, fact 1 is settled for free.
2. **`aircraft-layer/dcs-export/Export.probe-weapons.lua`** → copy over `Saved Games\DCS\Scripts\
   Export.lua` (displacing production Export.lua for that sortie; restore it after). Logs total
   object count plus every first-seen object `Name`, once a second, to
   `Logs\aircraft_layer_probe_weapons.log`. **If gunfire shows as a count spike and new names, the
   whole event-handler question is moot** — tracers are ordinary objects in a feed the naked-eye
   channel already gates on FOV, angular size and terrain LOS, and no new channel is needed.
3. **`aircraft-layer/dcs-export/petrobrain-damage-events-probe-hook.lua`** → copy to
   `Saved Games\DCS\Scripts\Hooks\`. Answers both remaining questions in one sortie, logging to
   `dcs.log` under `PetrobrainDamageProbe`:
   - **Damage** — `getLife()`/`getLife0()` per unit, logging only units whose life fraction is
     below 1.0 (an undamaged sortie is silent, so the damaged rows are findable). Shoot a ground
     unit until it visibly smokes without killing it, and read whether the fraction crosses a
     consistent value at that moment.
   - **Firing events** — registers a `world.addEventHandler` inside the scripting state and drains
     its queue each second. **It resolves each event id back to its name at runtime by reversing
     the `world.event` enumerator**, rather than hardcoding ids this project has not verified, so
     the log prints `S_EVENT_SHOOTING_START` rather than a bare number whose meaning would have to
     be looked up and could be wrong.

The `register: ok=... result=...` line is the one to read first: it answers Finding 15 (whether
`world` is reachable from the `"scripting"` state) on its own, before any event has to arrive.
Registration succeeding *and* events then naming a firing AAA unit settles fact 1 and fact 2
together.

A negative result from step 3 is a real result and should be written up rather than retried — it
would reverse Finding 12 and leave the naked-eye/LOS tracer channel as the only route to perceiving
that we are being engaged.

---

## PROBE RESULTS, 2026-09-25 — flown by the user, and the two halves point opposite ways

Two artefacts came back in `win-mac-sync/from-windows/`:
`aircraft_layer_probe_weapons.log` (Probe A's object-feed half, run for 103 s) and `debrief.log`
from the same sortie. **The Hook probe (`petrobrain-damage-events-probe-hook.lua`) was not run** —
no `PetrobrainDamageProbe` lines anywhere — so `getLife()` and the live event handler remain
unmeasured. Everything below comes from the two files that did come back.

### Finding 12 is ANSWERED, affirmatively, with initiator and target

`debrief.log` carries **16 `"start shooting"` events and 16 `"end shooting"`**, every one of them
initiated by a **ground gun vehicle** and aimed at the player:

```
initiatorPilotName   = "M1043 HMMWV Armament"
initiator_unit_type  = "M1043 HMMWV Armament"
initiator_object_id  = 16780800
type                 = "start shooting"
target               = "Mi-8MT"
targetPilotName      = "sg"
target_object_id     = 16781056
t                    = 52.109
```

So the engine **does** raise a shooting event for a ground, gun-armed unit, and the event names
*who* is shooting, *what they are shooting at*, and **both object ids** — which is exactly the join
a perception gate would need against `LoGetWorldObjects`. The survey's Finding 12 (recorded as
"inferred, moderate confidence, the single most important unresolved point") is confirmed from the
user's own machine. Evidence class: **read from a real post-mission log**, not documentation.

Full field set available on a start-shooting event: `event_id`, `t`, `type`, `initiatorPilotName`,
`initiator_unit_type`, `initiator_object_id`, `initiator_coalition`, `initiator_ws_type1`,
`target`, `targetPilotName`, `target_unit_type`, `target_object_id`, `target_coalition`,
`target_ws_type1`, `weapon`, `linked_event_id`, `initiatorMissionID`, `targetMissionID`.

### But the cheap route does NOT work for guns — and this is the load-bearing negative

The second addendum hoped `LoGetWorldObjects()` might return in-flight weapon objects, which would
have made the whole event channel unnecessary: a tracer would be an ordinary object the naked-eye
path already gates on FOV, angular size and LOS. **Half true, and the useful half is false.**

**Rockets are objects.** The player's own S-8s appear immediately and unmistakably:

| debrief `shot` events (S-8KOM HEAT) | `aircraft_layer_probe_weapons.log` |
|---|---|
| 33.10, 33.16 | `[33.14] count=15 → 17  NEW: C_8` |
| 36.89 | `[37.16] count=20` |
| 48.70 – 49.40 (eight rockets) | `[49.20] 23`, `[50.21] 27`, `[51.21] 23`, `[52.22] 21` |

`C_8` is the S-8's own object name, first-seen at the exact poll the first pair was fired, and the
count tracks rockets in flight and settles back.

**Gun rounds are not.** Across all sixteen start-shooting events from that HMMWV — 58.1, 62.2,
64.8, 67.8, 69.2, 71.4, 72.1, 75.0, 78.7, 82.5, 82.7, 86.0, 86.6, 89.3 s — the object count sits
**flat at 14 on every single poll**. No new names, no spikes. A vehicle firing its gun at the player
for half a minute adds nothing to the object feed.

That is consistent with `S_EVENT_SHOT`'s own documented exclusion of machine-gun and autocannon
fire: gun rounds are not weapon *objects* in DCS, which is why they are neither in `SHOT` nor in
`LoGetWorldObjects`. **So the tracer channel cannot be built from the object feed. It has to be the
event.**

### Destroyed units do vanish from the feed — confirmed incidentally

The baseline object count steps down permanently, 15 → 14 at `[57.23]`, after the player's rockets
scored hits on an `M 818` and an `M978 HEMTT Tanker` at 37.0–37.2 s and an `M1043 HMMWV Armament`
at 50.97 s. `debrief.log` carries 27 `bda`/`dead` events. So Finding 6's coarse
destroyed-unit-disappearance fallback is real, at a lag of seconds rather than polls — though note
the step is smaller than the number of kills, so a wreck may persist for some types. Still not a
substitute for `getLife()`, which remains unmeasured.

### What this changes, and what is still open

| question | status after this sortie |
|---|---|
| Does the engine raise a shooting event for ground guns? | **Yes** — confirmed, with initiator, target and object ids |
| Can tracers be read from `LoGetWorldObjects`? | **No** for guns. Yes for rockets, which is not the case that mattered |
| Does a `world.addEventHandler` in the `"scripting"` state receive those events? | **Still unmeasured** — the Hook probe did not run |
| `Unit.getLife()` and the smoke correlation | **Still unmeasured** — same reason |

**The remaining probe is now the only one worth running**, and its scope has narrowed: the question
is no longer *whether* the event exists but whether the bridge can subscribe to it live.
`petrobrain-damage-events-probe-hook.lua` answers that and the damage half together, and its
`register: ok=...` line answers the reachability question before any event has to arrive.

**Design note for whoever builds the tracer channel.** The event is theatre-wide and knows no line
of sight, so it still needs the LOS + visual-range gate the naked-eye channel applies — that has not
changed. What *has* changed is that the gate now has something better than a position to work with:
the event names `target_object_id`, so "is this being shot *at us*" is a direct comparison rather
than an inference. And `weapon` is populated, which may let a gun burst be distinguished from a
missile launch without guessing from the initiator's type.

---

## HOOK PROBE RESULTS, 2026-09-25 — every remaining question answered

`win-mac-sync/from-windows/dcs.log`, 105 `PetrobrainDamageProbe` lines from a real sortie. Both
questions this report was written to answer are now closed, and the design is unblocked.

### Fact 2 — the bridge can subscribe. Finding 15 answered.

```
11:39:20.756  register: ok=true result=registered
```

`world.addEventHandler`, registered from inside the `"scripting"` state via
`net.dostring_in`, works. That was inferred by analogy to `coalition`/`missionCommands`/`env` and
never probed; it is now measured. Events then flowed for the whole sortie.

Event kinds actually delivered: `S_EVENT_SHOOTING_START` (45), `S_EVENT_SHOOTING_END` (45),
`S_EVENT_HIT` (37), plus `SIMULATION_UNFREEZE`, `GROUP_CHANGE_OPTION`, `BDA`, `HUMAN_FAILURE` (3),
`PILOT_DEAD`, `UNIT_LOST`, `CRASH`, `SIMULATION_FREEZE`.

### "We are being shot at" is directly readable — no inference

This is the finding the whole tracer idea rests on, and it is cleaner than hoped:

```
t= 60.319  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
t= 63.059  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
t= 70.059  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
t= 73.979  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
t= 78.179  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
t= 82.019  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
t= 85.859  S_EVENT_SHOOTING_START  init=Unit #013  target=Pilot #001
```

`Unit #013` is the `M1043 HMMWV Armament` — a ground, gun-armed vehicle. Every one of its
`SHOOTING_START` events **names the player as the target**. So the engagement channel does not have
to infer "is this aimed at us" from geometry: the event says so.

**`target` is populated on `SHOOTING_START` only.** All 7 of that unit's `SHOOTING_END` events carry
`target='-'`, as do all of the player's own outgoing shooting events. So pair a START with its END
by *initiator*, and read the target off the START. Of 90 shooting events, 83 had no target — all
either `SHOOTING_END` or the player's own fire.

**Duplicates are a weapon property, not a handler bug.** `Pilot #001`'s own events arrive in
identical pairs (twin-cannon), while `Unit #013`'s arrive singly — 7 STARTs, 7 ENDs, no repeats.
Registration happened exactly once (`PB_PROBE_HANDLER_REGISTERED` held). Still worth deduping on
`(kind, t, initiator)` rather than assuming one event per trigger pull.

### Fact 1 — `getLife()`/`getLife0()` work, with real numbers

65 `DAMAGED` lines, shape as designed:

```
DAMAGED t=51.47 units=15 name:type:life:life0:fraction ->
  Unit #012:MLRS:2.724:3.000:0.908;Unit #013:M1043 HMMWV Armament:2.106:2.500:0.842
```

So damage is readable per unit, absolute and as a fraction, over the bridge that already runs at
1 Hz for velocity. `life0` differs by type (MLRS 3.0, HMMWV 2.5, M 818 2.0, Hummer 2.5), which is
why the *fraction* rather than the raw number is the comparable quantity.

Lowest fraction reached per unit this sortie:

| unit | type | life0 | lowest fraction |
|---|---|---|---|
| `Unit #003` | M 818 | 2.0 | **0.680** |
| `Unit #009` | MLRS | 3.0 | **0.690** |
| `Unit #013` | M1043 HMMWV Armament | 2.5 | 0.842 |
| `Unit #012` | MLRS | 3.0 | 0.908 |
| `Unit #001` | Hummer | 2.5 | 0.946 |

### The one thing still unanswered, and only the user can answer it

**Whether any of those units visibly smoked, and at what fraction.** Nothing here went below
**0.68**, so if the smoke threshold is lower than that, this sortie never crossed it. The
probe records the number; it cannot record what the screen looked like. Finding 5's
smoke-correlation question therefore stands, narrowed to: *did anything smoke, and was it the M 818
or the MLRS at ~0.68?*

Worth noting the practical consequence either way: "is it dead yet" is answerable **now** from the
fraction plus disappearance, and *"no, but smoking"* is the only part still waiting on the
correlation.

### Status

| question | status |
|---|---|
| Engine raises shooting events for ground guns | **confirmed** (debrief.log, and now live) |
| Live handler in the `"scripting"` state receives them | **confirmed** — `register: ok=true` |
| Can we tell we are the target | **confirmed** — `target` on `SHOOTING_START` |
| `getLife()`/`getLife0()` over the bridge | **confirmed**, real numbers, per unit |
| Tracers as objects in `LoGetWorldObjects` | **no** for guns (rockets yes) — see previous section |
| Life fraction at which smoke appears | **still open** — needs the user's eye, not a probe |

**The design is unblocked.** The engagement channel is `SHOOTING_START` filtered to events whose
`target` is ownship, and it still wants the LOS/visual-range gate — a theatre-wide event feed would
otherwise make Petrovich aware of every gun firing anywhere. What has changed is that the gate now
works on a named target rather than a guess.

### The visual-damage correlation, 2026-09-25 — it is FIRE, and it brackets to (0.69, 0.84]

The user's observation, which closes Finding 5's last open question:

> *"I hit something and it started burning. long truck like thing. So, fire instead of just smoke."*

**First correction, and it matters for the callout vocabulary: the visible state is fire, not smoke.**
This report and the plan both said "smoking" throughout, inherited from the forum-claim about
health-correlated smoke. What a hit actually produces is a burning vehicle — which is *better* for a
crew callout, because "it's burning" is unambiguous where "smoking" is a judgement call.

**Second, the bracket.** Only two units in the sortie are plausibly a "long truck like thing", and
they are the two lowest-life units in it:

| unit | type | lowest fraction | burning? |
|---|---|---|---|
| `Unit #003` | **M 818** — long cargo truck | **0.680** | one of these is the burning one |
| `Unit #009` | **MLRS** — long, truck chassis | **0.690** | " |
| `Unit #013` | M1043 HMMWV Armament | 0.842 | not reported burning |
| `Unit #012` | MLRS | 0.908 | not reported burning |
| `Unit #001` | Hummer | 0.946 | not reported burning |

So **fire is present at a life fraction ≤ 0.69 and absent at ≥ 0.84**. The threshold lies in
**(0.69, 0.84]**. Which of the two lowest was the burning one cannot be resolved from the log — both
match the description and both sit at essentially the same fraction — but the bracket holds either
way, which is why it did not need resolving.

**Third, and this reshapes the design: life is flat once damaged, not decaying.** `Unit #003` held
`0.680` across **59 consecutive samples over 55 seconds** — every distinct fraction it ever reported
was `[0.68]`. `Unit #013` likewise `[0.842]`, `Unit #012` `[0.908]`, `Unit #001` `[0.946]`. Only
`Unit #009` moved at all, and only because it took a further hit (`0.939 → 0.690`).

Consequences:

- **"On fire" must be derived from the fraction, not from a rate of change.** There is no burn-down
  to observe; a burning vehicle sits at a constant life value indefinitely. A design watching for
  decreasing life would never fire.
- **A single sample is sufficient.** No need to track a trajectory per contact to answer "is it
  burning" — the current fraction answers it.
- **Nothing died in 109 s** despite four damaged units, so destruction is a separate, harder state
  than damage, and the disappearance fallback is the only signal for it so far.

**What this leaves genuinely open**, and it is narrower than before: the exact threshold inside
(0.69, 0.84], and whether it is a single global fraction or varies by type. `life0` already varies
by type (M 818 2.0, MLRS 3.0, HMMWV 2.5), so a per-type threshold is plausible rather than
paranoid. Resolving it needs a sortie that deliberately walks a single vehicle down through that
band and notes where it lights up — not a probe change.

**Good enough to build on now.** *"Is it dead yet"* is answerable from fraction plus disappearance,
and *"no, it's burning"* is answerable from a fraction at or below about 0.69 — conservative, since
the real threshold is somewhere above that and a conservative reading under-claims rather than
over-claims. Erring that way is the right default: a crew member who says "burning" when it is
merely damaged has lied, while one who says "hit, still up" about a burning vehicle has only been
cautious.
