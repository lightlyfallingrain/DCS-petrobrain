# Reading the live theatre name from Hook state at `onSimulationStart`

**Date:** 2026-10-19
**DCS version:** not verified locally this session — last recorded in this tree is 2.9.29.27278
(build `20260826-084519`), read from `autoupdate.cfg` on 2026-09-20
(`2026-09-20-dcs-install-detection-deep-read.md`). No DCS box was reachable this session; re-read
`autoupdate.cfg` or the `dcs.log` header before trusting this number for a new probe run.
**Theatre:** n/a (this question is theatre-agnostic — it is about reading *which* theatre is loaded)

### Question

For BL-15 Stage 1 (`feature/bl15-mission-start`): at `onSimulationStart`, can body-layer's own
tooling learn the current mission's `theatre` string (e.g. `"Syria"`, `"Afghanistan"` — the same
string `mission-interpreter/src/miz/reader.py:119-123` reads from a `.miz`'s embedded mission table,
and the same string `body-layer/src/logger.py`'s theatre lookup matches against
`coordinates.projections.THEATRE_PROJECTIONS` keys) from a Hook-state script, either directly or via
the already-proven mission-scripting bridge? Secondary: does `onSimulationStart` ever fire for
anything other than a genuine mission (re)start?

### Findings

1. **The Hook-state global is `DCS`, not `Sim`, and this is already proven live, repeatedly** —
   **evidence: reproduced-locally** — **source:** every deployed Hook script in
   `aircraft-layer/dcs-export/*.lua` (`local DCS = require("DCS")`, then `DCS.getRealTime()`,
   `DCS.setUserCallbacks(...)`). The vendored `aircraft-layer/research/reference/Sim_ControlAPI.md`
   documents the same API surface under the name `Sim.*` throughout (`Sim.getMissionName()`,
   `Sim.setUserCallbacks`, `Sim.getCurrentMission()`), including in its own worked example
   (`test.onSimulationStart()` calling `Sim.getMissionName()`, lines 51-52). **`Sim` is the doc's
   name for the table; `DCS` is the real global this build's Hook state binds it to** — not two
   different objects, one renamed. This project has never seen a Hook script fail because it used
   `DCS` instead of `Sim`, across nine separate production/probe Hook scripts.

2. **`DCS.getCurrentMission()` / `DCS.getMissionName()` / `DCS.getMissionFilename()` have never been
   directly probed by this project** — **evidence: documented only** (`Sim_ControlAPI.md` lines
   144-153) — no existing research note or Hook script in this repo calls any of the three. The
   general naming convention (finding 1) is strong indirect evidence they exist as real `DCS.*`
   callables, matching `DCS.getRealTime()`/`DCS.setUserCallbacks()`, but **"the convention held for
   two functions" is not the same claim as "this third function exists and returns the shape the
   doc says."** This is the one piece of this investigation that is inference, not reproduction, and
   it should not be reported upward as settled.

3. **The `net.dostring_in("scripting", ...)` bridge from Hook state, at `onSimulationStart`, is
   already shipping in production** — **evidence: reproduced-locally (by prior investigation,
   re-confirmed by reading the shipped script)** — **source:**
   `aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md`;
   `aircraft-layer/dcs-export/petrobrain-f10-commands-hook.lua` (registers its F10 menu via this
   exact bridge inside `onSimulationStart`, flown and accepted by the user). This settles the
   mechanics of question 2 completely: the bridge call shape, the state name (`"scripting"`, not
   `"mission"`), the `autoexec.cfg` opt-in (`net.allow_dostring_in = { "scripting" }`, already
   present on the user's machine), and the fact that it works *at* `onSimulationStart` specifically
   — not just at some later point in the mission — are all proven, not assumed.

4. **`env.mission` is the live analogue of the `.miz`'s mission Lua table, and `theatre` is a
   top-level key on it** — **evidence: documented (Hoggit convention) + inferred (by analogy to the
   `.miz` reader's own confirmed finding), not yet probed live from this build** — **source:**
   `mission-interpreter/src/miz/reader.py:119-123` (`mission["theatre"]`, confirmed against real
   `.miz` bytes); Hoggit's `env` table is widely documented as exposing the currently-running
   mission's own table (the same structure the `.miz`'s embedded Lua produces) under
   `env.mission` in the Mission Scripting environment, which is the state `"scripting"` names in
   `net.dostring_in`. No research note in this repo has run `net.dostring_in("scripting", "return
   env.mission.theatre")` or similar against a live DCS session. This project's own
   `2026-09-20-dcs-install-detection-deep-read.md` flagged `env.mission.date` as an open,
   `net.dostring_in("mission", ...)`-gated unknown (finding 9) — written *before*
   `2026-09-22-mission-bridge-already-shipping.md` corrected the state name from `"mission"` to
   `"scripting"`. That correction applies equally here: the right call to test is
   `net.dostring_in("scripting", "return env.mission.theatre")`, not `"mission"`.

5. **`onSimulationPause`/`onSimulationResume` are separate, named callbacks from
   `onSimulationStart`/`onSimulationStop`** — **evidence: documented** — **source:**
   `Sim_ControlAPI.md` lines 585-597 — a flat callback list with no shared dispatch path described
   between the pause/resume pair and the start/stop pair. This is consistent with (does not prove)
   the desired behaviour: pausing and resuming a running mission should not re-fire
   `onSimulationStart` and should not look, from a Hook script's point of view, like a fresh mission
   load. No text anywhere in the vendored doc or this project's prior research says what single-player
   "restart mission" does to the callback sequence — whether it calls `onSimulationStop` then
   `onSimulationStart` again (desired — a clean belief reset) or does something else (e.g. reloading
   without a stop, or restarting without one at all).

### Reproducible Test

No DCS access this session; this is the probe to run on the Windows box. It follows the same
pattern as `aircraft-layer/dcs-export/petrobrain-api-surface-probe-hook.lua` (throwaway Hook script,
deploy by hand, read `dcs.log`, delete) and reuses the proven bridge call shape from
`petrobrain-f10-commands-hook.lua`.

```lua
--[[
Throwaway probe: does DCS.getCurrentMission()/getMissionName()/getMissionFilename() work in Hook
state, and does env.mission.theatre resolve over the scripting bridge, at onSimulationStart?
Deploy to Saved Games\DCS\Scripts\Hooks\, start/restart a mission, read dcs.log, delete the file.
Requires net.allow_dostring_in = { "scripting" } in autoexec.cfg (already present per
aircraft-layer/WORKFLOW.md).
--]]
local DCS = require("DCS")
local probe = {}

function probe.onSimulationStart()
    log.write("PetrobrainTheatreProbe", log.INFO, "onSimulationStart fired")

    -- 1. Direct Hook-state calls -- do these exist at all in this build?
    local ok1, name = pcall(function() return DCS.getMissionName() end)
    log.write("PetrobrainTheatreProbe", log.INFO, "getMissionName ok=" .. tostring(ok1) .. " -> " .. tostring(name))

    local ok2, fname = pcall(function() return DCS.getMissionFilename() end)
    log.write("PetrobrainTheatreProbe", log.INFO, "getMissionFilename ok=" .. tostring(ok2) .. " -> " .. tostring(fname))

    local ok3, mission = pcall(function() return DCS.getCurrentMission() end)
    if ok3 and type(mission) == "table" then
        local keys = {}
        for k, _ in pairs(mission) do keys[#keys+1] = tostring(k) end
        table.sort(keys)
        log.write("PetrobrainTheatreProbe", log.INFO, "getCurrentMission keys: " .. table.concat(keys, ","))
        log.write("PetrobrainTheatreProbe", log.INFO, "getCurrentMission.theatre = " .. tostring(mission.theatre))
    else
        log.write("PetrobrainTheatreProbe", log.INFO, "getCurrentMission ok=" .. tostring(ok3) .. " -> " .. tostring(mission))
    end

    -- 2. The proven bridge, same state name and call shape as petrobrain-f10-commands-hook.lua.
    local callOk, result, success = pcall(net.dostring_in, "scripting", "return env.mission.theatre")
    log.write("PetrobrainTheatreProbe", log.INFO,
        "bridge callOk=" .. tostring(callOk) .. " success=" .. tostring(success) .. " result=" .. tostring(result))
end

DCS.setUserCallbacks(probe)
log.write("PetrobrainTheatreProbe", log.INFO, "hook loaded")
```

Then, separately, to settle finding 5: start a mission, pause it, resume it, and use in-game
"restart mission" — each time checking whether a *fresh* `"onSimulationStart fired"` line appears in
`dcs.log` (grep: `grep PetrobrainTheatreProbe "Saved Games\DCS\Logs\dcs.log"`), versus
`onSimulationPause`/`onSimulationResume` lines appearing instead (not logged by the probe above as
written — add `probe.onSimulationPause`/`probe.onSimulationResume` stubs that log their own names if
this check is run).

### Possible Approaches

- **If the direct `DCS.getCurrentMission()` call works and carries `theatre`** (most likely outcome,
  given the global-naming precedent in finding 1): this is the cheapest path — no bridge, no
  `autoexec.cfg` dependency, one Hook-state call at `onSimulationStart`. Prefer it over the bridge if
  confirmed.
- **If it is absent or its table lacks `theatre`, fall back to the bridge** (`net.dostring_in
  ("scripting", "return env.mission.theatre")`). This is already proven machinery at exactly this
  callback (finding 3), so the fallback carries no new risk — it is the same call shape as code
  already flown and accepted by the user, pointed at a different Lua expression. Either `DCS.
  getMissionFilename()` (if it works) or re-reading the `.miz` referenced by the mission-scripting
  bridge's own `a_do_script` filename could additionally cross-check which mission file is loaded,
  if theatre alone is ever ambiguous (e.g. a custom mission with an unexpected theatre string) —
  not needed unless the direct value proves unreliable.
- **Either way, the received string needs the same matching discipline `body-layer/src/logger.py`
  already uses against `coordinates.projections.THEATRE_PROJECTIONS`** — an unrecognised theatre
  string should be a clear, logged "no world-model store for theatre X" condition, not a silent
  fallback to whatever `--theatre` last pointed at. That is an Architect/Implementer decision, not
  this note's to make.
- **Pin down the restart/pause question with the second half of the reproducible test above before
  relying on `onSimulationStart` as the sole reset trigger.** If single-player restart is ever found
  not to re-fire it, the fallback is to additionally watch `onMissionLoadEnd` (documented,
  `Sim_ControlAPI.md` line 582, never probed here either) as a second, earlier signal — a decision
  for Architect once the probe result is in hand, not assumed now.

### Unresolved

- **Whether `DCS.getCurrentMission()`/`getMissionName()`/`getMissionFilename()` are real, callable
  Hook-state functions in this DCS version, and what keys the returned table actually has.** This is
  the single question this note could not settle without the box. Resolve with the probe script
  above; bring back the `dcs.log` lines (`grep PetrobrainTheatreProbe`).
- **Whether `env.mission.theatre` resolves over the `"scripting"` bridge** at `onSimulationStart`
  specifically (not just "at some point in the mission," which is all finding 3 proves for
  `missionCommands`). Same probe settles it.
- **What single-player "restart mission" does to the callback sequence**, and whether
  `onSimulationPause`/`onSimulationResume` can ever fire without a preceding `onSimulationStop` in a
  way that could be mistaken for a restart. No documentary or local evidence either confirms or
  contradicts the desired behaviour — this needs the live pause/resume/restart check described above,
  not a static-doc read, since `Sim_ControlAPI.md` only lists the callbacks' names and signatures,
  never their triggering conditions relative to each other.
- **DCS version for any new probe run** — this note's version line is stale (last read
  2026-09-20); re-read `autoupdate.cfg` or `dcs.log`'s header when the probe above is actually run,
  and record it in whatever follow-up note captures the result.
