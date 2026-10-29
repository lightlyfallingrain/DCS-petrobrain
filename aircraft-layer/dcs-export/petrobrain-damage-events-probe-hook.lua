--[[
Aircraft Layer -- damage-state and firing-event PROBE Hook script.

**This is a throwaway probe, not production.** It answers two open questions
from `aircraft-layer/research/2026-09-24-damage-and-firing-events-over-
mission-bridge.md` and is meant to be deleted once they are answered. It
writes nothing to the collector and opens no socket -- every result goes to
`dcs.log`, so it runs with nothing else of this project running. Same
posture as `petrobrain-f10-probe-hook.lua`.

Deploy: copy to `Saved Games\DCS\Scripts\Hooks\` on the Windows box. Remove
it again afterwards. It is safe to leave the production Hooks in place
alongside it -- this script registers its own callbacks under its own name
and shares no state with them.

**REQUIRES the same `autoexec.cfg` opt-in as every other bridge user**:
`net.allow_dostring_in = { "scripting" }`. Without it `dostring_in` returns
`("Invalid state name", false)` every poll and this probe logs that failure
rather than silently doing nothing -- watch for `PetrobrainDamageProbe`
lines in `dcs.log`.

Both snippets below are fixed string literals baked in at authoring time,
never built from runtime input -- the same audited property
`petrobrain-f10-commands-hook.lua` holds.

WHAT IT ANSWERS

Question 1 -- damage. `LIFE_CODE` reads `Unit:getLife()` and
`Unit:getLife0()` per unit, the same loop shape
`petrobrain-mission-telemetry-hook.lua` already runs for `getVelocity()`.
Logs one line per poll naming only units whose life fraction is below 1.0,
because an undamaged sortie would otherwise bury the interesting rows. The
question is whether the fraction crosses a consistent, repeatable value at
the moment a unit visibly starts smoking.

Question 2 -- firing events, and this is the load-bearing one.
`EVENT_REGISTER_CODE` installs a `world.addEventHandler` inside the
scripting state and accumulates events into a global queue;
`EVENT_POLL_CODE` drains it each second. **It resolves each event's numeric
id back to its name at runtime**, by reversing the `world.event` enumerator
table, rather than hardcoding ids this project has not verified -- so the
log says `S_EVENT_SHOOTING_START` rather than `23`, and cannot be wrong
about which constant a number meant.

Two separate facts are in play here and the probe distinguishes them:

  1. Does the engine raise a firing event for *ground* AAA (a ZU-23 or a
     Shilka, not an aircraft cannon)? `S_EVENT_SHOT` explicitly excludes
     gun/autocannon fire -- confirmed from primary Hoggit text -- so
     `S_EVENT_SHOOTING_START` is the event that would have to carry it, and
     no source found says whether ground guns raise it.
  2. Does a handler registered through `net.dostring_in("scripting", ...)`
     actually receive those events? `world`'s reachability from that state
     was never itself probed -- only `missionCommands`, `env`, `trigger`
     and `coalition` were. **If the registration line logs
     `register: registered` and events then arrive, both facts are settled
     at once.** If registration fails, only fact 2 has been answered, and
     the debrief-log route in that research file's addendum answers fact 1
     separately.

A negative result is a real result here. If an AAA unit fires visibly and
no event naming it ever appears, that reverses the research file's
Finding 12 and means the naked-eye/LOS tracer channel is the only route to
perceiving being engaged -- write it up rather than retrying.

STAGE 0 EXTENSION (`plans/bl-b67-atgm-run/plan.md`, BL-B67) -- 2026-10-29,
now mandatory rather than optional (the plan's own Q6). Answers: does
`S_EVENT_SHOT` arrive for our own ATGM launch with `event.weapon`
populated; what do `getTypeName()`/`getDesc().category`/`.guidance`/
`.displayName` read for it; does `isExist()` hold for the flight and turn
false at impact, and when; does `S_EVENT_HIT` fire on that same weapon
object.

  * `handler:onEvent` now special-cases `S_EVENT_SHOT` where the
    initiator is the player: it reads the weapon's `getTypeName()`/
    `getDesc()`/`isExist()` at event time and appends them to that
    event's own queued line, then keeps a reference to the weapon object
    in `PB_PROBE_KEPT_WEAPON` (a global in the `"scripting"` state, same
    persistence mechanism `petrobrain-firing-events-hook.lua`'s own
    `PB_ACTIVE_FIRING_UNITS` already relies on) if it exists at launch.
  * It also special-cases `S_EVENT_HIT` where `event.weapon` is that same
    kept object, appending a marker to that event's line.
  * `WEAPON_EXIST_POLL_CODE`/`pollWeaponExist` poll the kept weapon's
    `isExist()` at 5 Hz (`WEAPON_EXIST_POLL_INTERVAL_S`), independently of
    the 1 Hz life/event poll above, and log the sim time
    (`timer.getTime()`, read inside the `"scripting"` state, not the Hook
    state's own `DCS.getRealTime()`) it first reads false -- the model
    time Q6 asks for.
--]]

log.write("PetrobrainDamageProbe", log.INFO, "Loading - Petrobrain damage/events probe")

local DCS = require("DCS")

--: 1 Hz, matching every other bridge user's poll rate.
local POLL_INTERVAL_S = 1.0

--: Same enumeration shape as `petrobrain-mission-telemetry-hook.lua`'s
--: `VELOCITY_CODE`, reading life instead of velocity. Statics are skipped
--: entirely (they carry no life API and are not what is being shot at in
--: this probe). Only damaged units are returned -- an undamaged unit is
--: `life == life0` and says nothing, while a sortie's worth of them would
--: make the log unreadable.
local LIFE_CODE = [[
local parts = {}
local total = 0
for _, coa in pairs({coalition.side.NEUTRAL, coalition.side.RED, coalition.side.BLUE}) do
    for _, grp in ipairs(coalition.getGroups(coa) or {}) do
        for _, unit in ipairs(grp:getUnits() or {}) do
            if unit and unit:isExist() then
                total = total + 1
                local lifeOk, life = pcall(function() return unit:getLife() end)
                local life0Ok, life0 = pcall(function() return unit:getLife0() end)
                if lifeOk and life0Ok and type(life) == "number" and type(life0) == "number"
                    and life0 > 0 and life < life0 then
                    parts[#parts + 1] = unit:getName()
                        .. ":" .. tostring(unit:getTypeName())
                        .. ":" .. string.format("%.3f", life)
                        .. ":" .. string.format("%.3f", life0)
                        .. ":" .. string.format("%.3f", life / life0)
                end
            end
        end
    end
end
return tostring(total) .. "|" .. tostring(timer.getTime()) .. "|" .. table.concat(parts, ";")
]]

--: Registers once and is idempotent -- a second call while
--: `PB_PROBE_HANDLER_REGISTERED` is set does nothing, so a mission restart
--: cannot stack duplicate handlers.
--:
--: `PB_PROBE_EVENT_NAMES` is the reversed `world.event` enumerator, built
--: at registration time. This is why the log can name an event rather than
--: print a number whose meaning this project has not verified.
--:
--: Every field read off `event` is pcall-guarded: a weapon object may be
--: absent, and `getName()` on a unit that died in the same frame can
--: raise. A probe that crashes inside its own handler would silently stop
--: reporting, which is the one failure mode that would waste the sortie.
local EVENT_REGISTER_CODE = [[
if not PB_PROBE_HANDLER_REGISTERED then
    PB_PROBE_EVENT_QUEUE = {}
    PB_PROBE_EVENT_NAMES = {}
    for name, id in pairs(world.event) do
        PB_PROBE_EVENT_NAMES[id] = name
    end
    local function safeName(obj)
        if obj == nil then return "-" end
        local ok, n = pcall(function() return obj:getName() end)
        if ok and n ~= nil then return tostring(n) end
        return "?"
    end
    --: `PB_PROBE_KEPT_WEAPON` is the one own-launched weapon object this
    --: probe tracks at a time (the most recent S_EVENT_SHOT where the
    --: initiator was the player and the weapon existed at launch) -- a
    --: second launch while the first is still tracked simply overwrites
    --: it, which is fine for a Stage 0 probe sortie that fires one
    --: missile, waits for impact, and fires the next.
    local handler = {}
    function handler:onEvent(event)
        if event == nil or event.id == nil then return end
        local eventName = PB_PROBE_EVENT_NAMES[event.id] or ("UNKNOWN_" .. tostring(event.id))
        local line = eventName
            .. "|t=" .. tostring(event.time)
            .. "|init=" .. safeName(event.initiator)
            .. "|weapon=" .. safeName(event.weapon)
            .. "|target=" .. safeName(event.target)

        if event.id == world.event.S_EVENT_SHOT then
            local isPlayer = false
            local okp, player = pcall(world.getPlayer)
            if okp and player ~= nil and event.initiator ~= nil then
                local okn1, playerName = pcall(function() return player:getName() end)
                local okn2, initName = pcall(function() return event.initiator:getName() end)
                if okn1 and okn2 and playerName == initName then
                    isPlayer = true
                end
            end
            if isPlayer and event.weapon ~= nil then
                local okTn, typeName = pcall(function() return event.weapon:getTypeName() end)
                local okDesc, desc = pcall(function() return event.weapon:getDesc() end)
                local okEx, exists = pcall(function() return event.weapon:isExist() end)
                local category, guidance, displayName = "?", "?", "?"
                if okDesc and type(desc) == "table" then
                    category = tostring(desc.category)
                    guidance = tostring(desc.guidance)
                    displayName = tostring(desc.displayName)
                end
                line = line
                    .. "|OWN_SHOT typeName=" .. tostring(okTn and typeName or "?")
                    .. " category=" .. category
                    .. " guidance=" .. guidance
                    .. " displayName=" .. displayName
                    .. " isExist=" .. tostring(okEx and exists or "?")
                if okEx and exists then
                    PB_PROBE_KEPT_WEAPON = event.weapon
                end
            end
        elseif event.id == world.event.S_EVENT_HIT then
            if PB_PROBE_KEPT_WEAPON ~= nil and event.weapon == PB_PROBE_KEPT_WEAPON then
                line = line .. "|HIT_ON_KEPT_WEAPON"
            end
        end

        PB_PROBE_EVENT_QUEUE[#PB_PROBE_EVENT_QUEUE + 1] = line
    end
    world.addEventHandler(handler)
    PB_PROBE_HANDLER_REGISTERED = true
    return "registered"
end
return "already-registered"
]]

--: Drain-and-clear, mirroring `petrobrain-f10-commands-hook.lua`'s own
--: `POLL_CODE`. One simple scalar is all `dostring_in` can return across
--: the boundary, so entries are packed into one semicolon-separated string.
local EVENT_POLL_CODE = [[
local queue = PB_PROBE_EVENT_QUEUE or {}
local out = {}
for i = 1, #queue do out[i] = queue[i] end
PB_PROBE_EVENT_QUEUE = {}
return tostring(#out) .. "|" .. table.concat(out, ";")
]]

--: Reads `PB_PROBE_KEPT_WEAPON:isExist()` (set by `EVENT_REGISTER_CODE`'s
--: own S_EVENT_SHOT handling above) and clears the reference once it
--: reads false or raises, so a stale dead object cannot be reported as
--: "gone" twice. `timer.getTime()` is this state's own sim clock -- the
--: model time Q6 asks for, not the Hook state's wall-clock `getRealTime`.
local WEAPON_EXIST_POLL_CODE = [[
local t = timer.getTime()
if PB_PROBE_KEPT_WEAPON == nil then
    return "none|" .. tostring(t)
end
local ok, exists = pcall(function() return PB_PROBE_KEPT_WEAPON:isExist() end)
if not ok then
    PB_PROBE_KEPT_WEAPON = nil
    return "error|" .. tostring(t)
end
if not exists then
    PB_PROBE_KEPT_WEAPON = nil
    return "false|" .. tostring(t)
end
return "true|" .. tostring(t)
]]

local petrobrainDamageProbe = {}

local simulationRunning = false
local nextPollAt = 0
local registered = false

--: 5 Hz per Stage 0's own requirement (Q6) -- independent of
--: `POLL_INTERVAL_S` above, which is too coarse to time an impact
--: against the visible explosion.
local WEAPON_EXIST_POLL_INTERVAL_S = 0.2
local nextWeaponPollAt = 0
--: Tracks the true->false edge so "gone" is logged exactly once, not on
--: every poll after the weapon stops existing (and not at all while
--: nothing is being tracked).
local weaponWasAlive = false

local function logi(message)
    log.write("PetrobrainDamageProbe", log.INFO, message)
end

-- Mirrors petrobrain-mission-telemetry-hook.lua's own wrapper exactly.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

local function tryRegister()
    local ok, result = dostring("scripting", EVENT_REGISTER_CODE)
    logi("register: ok=" .. tostring(ok) .. " result=" .. tostring(result))
    -- Only treat it as registered on a real success, so a failed opt-in
    -- retries on the next poll rather than going quiet for the sortie.
    if ok and type(result) == "string" then
        registered = true
    end
end

local function pollLife()
    local ok, result = dostring("scripting", LIFE_CODE)
    if not ok or type(result) ~= "string" then
        logi("life poll failed: ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    local total, t, entries = result:match("^(%d+)|([^|]*)|(.*)$")
    if entries == nil or entries == "" then
        -- Deliberately quiet: logging "no damaged units" every second for a
        -- whole sortie would bury the rows that matter.
        return
    end
    logi("DAMAGED t=" .. tostring(t) .. " units=" .. tostring(total)
        .. " name:type:life:life0:fraction -> " .. entries)
end

local function pollEvents()
    local ok, result = dostring("scripting", EVENT_POLL_CODE)
    if not ok or type(result) ~= "string" then
        logi("event poll failed: ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    local count, entries = result:match("^(%d+)|(.*)$")
    if count == nil or count == "0" then
        return
    end
    logi("EVENTS n=" .. tostring(count) .. " -> " .. tostring(entries))
end

--: Runs at 5 Hz, separately from `pollEvents`'s 1 Hz cadence -- see this
--: file's "STAGE 0 EXTENSION" header note.
local function pollWeaponExist()
    local ok, result = dostring("scripting", WEAPON_EXIST_POLL_CODE)
    if not ok or type(result) ~= "string" then
        logi("weapon-exist poll failed: ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    local state, t = result:match("^(%a+)|(.*)$")
    if state == "true" then
        weaponWasAlive = true
        return
    end
    if state == "false" then
        if weaponWasAlive then
            logi("WEAPON_GONE t=" .. tostring(t))
        end
        weaponWasAlive = false
        return
    end
    -- "none" or "error": nothing kept right now.
    weaponWasAlive = false
end

function petrobrainDamageProbe.onSimulationStart()
    logi("onSimulationStart")
    simulationRunning = true
    registered = false
    nextPollAt = 0
    nextWeaponPollAt = 0
    weaponWasAlive = false
end

function petrobrainDamageProbe.onSimulationFrame()
    if not simulationRunning then
        return
    end
    local now = DCS.getRealTime()

    -- The 5 Hz weapon-exist poll runs on its own cadence, independent of
    -- the 1 Hz life/event poll below -- see "STAGE 0 EXTENSION" above.
    if now >= nextWeaponPollAt then
        nextWeaponPollAt = now + WEAPON_EXIST_POLL_INTERVAL_S
        local wok, werr = pcall(pollWeaponExist)
        if not wok then
            logi("weapon poll raised: " .. tostring(werr))
        end
    end

    if now < nextPollAt then
        return
    end
    nextPollAt = now + POLL_INTERVAL_S
    if not registered then
        local ok, err = pcall(tryRegister)
        if not ok then
            logi("register raised: " .. tostring(err))
        end
    end
    local ok, err = pcall(function()
        pollLife()
        pollEvents()
    end)
    if not ok then
        logi("poll failed: " .. tostring(err))
    end
end

function petrobrainDamageProbe.onSimulationStop()
    logi("onSimulationStop")
    simulationRunning = false
    registered = false
    weaponWasAlive = false
end

DCS.setUserCallbacks(petrobrainDamageProbe)

logi("loaded")
