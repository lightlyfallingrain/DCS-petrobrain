--[[
Aircraft Layer -- production firing-events Hook script
(`plans/emitter-visibility/plan.md` Stage B, `AC-B8`).

Deploy: copy this file to `Saved Games\DCS\Scripts\Hooks\` on the Windows
box, alongside every other Petrobrain Hook script. This is the canonical,
version-controlled copy; the deployed copy is not tracked by this repo,
same discipline as every other Hook-state script.

**Productionises `petrobrain-damage-events-probe-hook.lua`, does not
promote it** -- `AC-B5` records that a probe Hook left deployed taxes
every sortie, so this is a separate, purpose-built file: only the event
kinds this feature actually needs (`S_EVENT_SHOOTING_START`/`_END`,
`S_EVENT_SHOT`, `S_EVENT_DEAD`, `S_EVENT_CRASH`), a real UDP sender (the
probe only ever wrote to `dcs.log`), and `targets_ownship`/position
resolution the probe never needed.

**REQUIRES the same `autoexec.cfg` opt-in as every other `dostring_in`-
using Hook script** -- see `petrobrain-mission-telemetry-hook.lua`'s own
header and `aircraft-layer/WORKFLOW.md`. Without it, `dostring_in` silently
returns `("Invalid state name", false)` every poll and this script is a
no-op -- watch `dcs.log` for `PetrobrainFiringEvents` lines to confirm.

**Feasibility is closed, not open.** The 2026-09-25 probe
(`docs/acceptance/2026-09-24-damage-and-firing-probes.md`, *"do not
re-fly it"*) logged `register: ok=true` and a ground gun unit's
`SHOOTING_START` naming the player as its `target`. This file's event
handler and registration/poll split are a direct extension of that
probe's own `EVENT_REGISTER_CODE`/`EVENT_POLL_CODE`.

**The latch and the watchdog are NOT this file's job.** This Hook
accumulates raw events and drains them once a second, exactly like every
other `dostring_in`-based feed in this codebase -- "who is currently
firing, for how much longer" is a stateful question the *collector* owns
(`collector.firing_receiver.EmitterTracker`, `plans/emitter-visibility/
plan.md`'s "Answers to the five design questions" #1: body-layer's
perception is deliberately recomputed-per-poll and stateless, so a
latch/watchdog machine does not belong there either, and definitely not
in this Lua state, which has no persistent-state discipline worth trusting
a timer to).

**`PB_ACTIVE_FIRING_UNITS` is the one piece of state this file DOES own,
and it exists for a different reason: the 128-sightline-cap mitigation.**
`petrobrain-line-of-sight-hook.lua`'s own cap
(`MAX_SIGHTLINES_PER_CALL = 128`, nearest-first) truncates the *far*
candidates first -- exactly the distant emitters this whole feature exists
to admit (plan Risks section). Both this file and that one run their own
`dostring_in` calls into the *same* `"scripting"` mission state, which
shares one set of globals across calls -- the same mechanism
`petrobrain-f10-commands-hook.lua`'s `PB_F10_QUEUE` already proves
persists across polls. So this file maintains a small, real-time-updated
name set (`PB_ACTIVE_FIRING_UNITS[name] = true` on `SHOOTING_START`,
cleared on `SHOOTING_END`/`DEAD`/`CRASH`) directly inside its own event
handler -- no 1 Hz poll latency, no collector round trip -- and the LOS
Hook's own `LOS_CODE` reads it (`PB_ACTIVE_FIRING_UNITS or {}`, a true
no-op when this file is not loaded) to splice currently-firing units ahead
of the nearest-first sort, so they are never truncated by the cap. This is
a second, independent purpose from the collector-side latch/watchdog
above: that one decides how long a *body-layer-facing* sighting persists;
this one decides whether the *engine-facing* sightline query ever drops
the candidate in the first place. Keeping it in Lua is deliberate -- a
collector round trip would add exactly the latency the splice exists to
avoid, and the real-time engine event already has the answer for free.

**Idempotent registration**, mirroring `petrobrain-damage-events-probe-
hook.lua`'s own `PB_PROBE_HANDLER_REGISTERED` guard exactly -- a second
`onSimulationStart` within one mission-scripting-state lifetime cannot
install a second handler and double every event.

**Event-name resolution by reversing `world.event`, never a hardcoded
id** -- same discipline the probe established, so a wire `kind` string is
always one DCS actually names, not a number this project guessed at.

**`targets_ownship` is resolved once, Hook-side, per `SHOOTING_START`
event** -- `world.getPlayer()`'s own id/name, compared against
`event.target`'s. The wire carries only the resulting `0`/`1`, never the
raw target identity (see `schema.firing`'s own module docstring on why
crossing more than that one bit would be more than this feature needs).

**`S_EVENT_SHOT`'s initiator position is resolved once, at event time,
and never re-read** -- `BL-B74`'s seam (the SAM launch position must
be frozen at the moment of launch, never the launcher's current position),
built here because position is a `Unit:getPosition()` call this Hook's own
event handler already has the initiator object in hand for; re-deriving it
collector-side later would need a second, separate position query this
project has no channel for.

Wire format (this script -> collector), UDP, one JSON object per poll
(matches `schema.firing.FiringEventBatch.from_wire`):
    {"payload": "<count>|<dcs_model_time_s>|<entries>", "bridge_call_ms": <float>}
`entries` is `"<kind>:<t>:<initiator>:<targets_ownship01>:<x>:<z>;..."`.

Reuses DCS's own shipped JSON encoder (`Scripts\JSON.lua`) and LuaSocket's
`package.path`/`cpath` extension, mirroring every other Hook script here.
--]]

log.write("PetrobrainFiringEvents", log.INFO, "Loading - Petrobrain firing events")

package.path = package.path
    .. ";.\\LuaSocket\\?.lua;"
    .. ".\\Scripts\\?.lua;"
    .. ".\\Scripts\\UI\\?.lua;"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll;"

local socket = require("socket")
local DCS = require("DCS")

local JSON = loadfile("Scripts\\JSON.lua")()

--: Loopback UDP port `collector.firing_receiver.DEFAULT_PORT` listens on --
--: must match exactly. An eighth, distinct loopback port from every other
--: channel in this codebase (see that module's own docstring for the full
--: list).
local FIRING_SEND_HOST = "127.0.0.1"
local FIRING_SEND_PORT = 7798

--: 1 Hz -- same cadence every other `dostring_in`-based feed in this
--: codebase polls at.
local POLL_INTERVAL_S = 1.0

--: Registers a `world.addEventHandler` inside the `"scripting"` state,
--: idempotently (mirrors `petrobrain-damage-events-probe-hook.lua`'s own
--: `PB_PROBE_HANDLER_REGISTERED` guard). The handler itself:
--:
--:   * resolves each event's numeric id back to its name via the reversed
--:     `world.event` enumerator, built once at registration time -- the
--:     same "never hardcode the id" discipline the probe established;
--:   * filters to the five kinds this feature needs
--:     (`S_EVENT_SHOOTING_START`/`_END`, `S_EVENT_SHOT`, `S_EVENT_DEAD`,
--:     `S_EVENT_CRASH`) -- every other kind (and there were a dozen more
--:     in the probe's own sortie: `BDA`, `HUMAN_FAILURE`,
--:     `SIMULATION_FREEZE`, ...) is dropped at the handler, not forwarded
--:     and filtered collector-side, so the queue and the wire never carry
--:     traffic nothing here will ever read;
--:   * resolves `targets_ownship` once, Hook-side, for `SHOOTING_START`
--:     only -- `world.getPlayer()`'s id/name against `event.target`'s,
--:     `pcall`-guarded throughout (a unit that died in the same frame as
--:     the event can raise on `getName()`/`getID()`);
--:   * resolves `x`/`z` once, Hook-side, for `S_EVENT_SHOT` only -- the
--:     initiator's position *at event time* (`BL-B74`'s seam, not
--:     acted on by this stage's collector logic);
--:   * maintains `PB_ACTIVE_FIRING_UNITS`, the real-time name set the LOS
--:     Hook's own sort-key splice reads (file header) -- added on
--:     `SHOOTING_START`, removed on `SHOOTING_END`/`DEAD`/`CRASH`, kept in
--:     lock-step with the queue entries below rather than derived from
--:     them later, since a unit's own `initiator:getName()` is already in
--:     hand at the exact point each queue entry is built.
--:
--: Every field read off `event`/`event.initiator`/`event.target` is
--: `pcall`-guarded -- same defensive posture the probe already
--: established, for the same reason: a handler that raises on a bad field
--: would silently stop reporting for the rest of the sortie, which is the
--: one failure mode worse than a missing field.
local EVENT_REGISTER_CODE = [[
if not PB_FIRING_HANDLER_REGISTERED then
    PB_FIRING_EVENT_QUEUE = {}
    PB_ACTIVE_FIRING_UNITS = PB_ACTIVE_FIRING_UNITS or {}
    local eventNames = {}
    for name, id in pairs(world.event) do
        eventNames[id] = name
    end
    local ALLOWED_KINDS = {
        S_EVENT_SHOOTING_START = true,
        S_EVENT_SHOOTING_END = true,
        S_EVENT_SHOT = true,
        S_EVENT_DEAD = true,
        S_EVENT_CRASH = true,
    }
    local function safeName(obj)
        if obj == nil then return nil end
        local ok, n = pcall(function() return obj:getName() end)
        if ok and n ~= nil then return tostring(n) end
        return nil
    end
    local function targetsOwnship(target)
        if target == nil then return false end
        local okP, player = pcall(world.getPlayer)
        if not okP or player == nil then return false end
        local playerName = safeName(player)
        local targetName = safeName(target)
        if playerName == nil or targetName == nil then return false end
        return playerName == targetName
    end
    local function initiatorPosition(initiator)
        if initiator == nil then return nil, nil end
        local okPos, pos = pcall(function() return initiator:getPosition() end)
        if not okPos or pos == nil or pos.p == nil then return nil, nil end
        return pos.p.x, pos.p.z
    end
    local handler = {}
    function handler:onEvent(event)
        if event == nil or event.id == nil then return end
        local kind = eventNames[event.id]
        if kind == nil or not ALLOWED_KINDS[kind] then return end
        local initName = safeName(event.initiator)
        if initName == nil then return end

        if kind == "S_EVENT_SHOOTING_START" then
            PB_ACTIVE_FIRING_UNITS[initName] = true
        elseif kind == "S_EVENT_SHOOTING_END"
            or kind == "S_EVENT_DEAD"
            or kind == "S_EVENT_CRASH" then
            PB_ACTIVE_FIRING_UNITS[initName] = nil
        end

        local ownship01 = "0"
        if kind == "S_EVENT_SHOOTING_START" and targetsOwnship(event.target) then
            ownship01 = "1"
        end
        local xStr, zStr = "nil", "nil"
        if kind == "S_EVENT_SHOT" then
            local x, z = initiatorPosition(event.initiator)
            if x ~= nil and z ~= nil then
                xStr, zStr = tostring(x), tostring(z)
            end
        end

        PB_FIRING_EVENT_QUEUE[#PB_FIRING_EVENT_QUEUE + 1] = kind
            .. ":" .. tostring(event.time)
            .. ":" .. initName
            .. ":" .. ownship01
            .. ":" .. xStr
            .. ":" .. zStr
    end
    world.addEventHandler(handler)
    PB_FIRING_HANDLER_REGISTERED = true
    return "registered"
end
return "already-registered"
]]

--: Drains `PB_FIRING_EVENT_QUEUE`, mirroring every other registration/poll
--: Hook script's own drain-and-clear snippet.
local EVENT_POLL_CODE = [[
local queue = PB_FIRING_EVENT_QUEUE or {}
local out = {}
for i = 1, #queue do out[i] = queue[i] end
PB_FIRING_EVENT_QUEUE = {}
return tostring(#out) .. "|" .. tostring(timer.getTime()) .. "|" .. table.concat(out, ";")
]]

local petrobrainFiringEvents = {}

local simulationRunning = false
local nextPollAt = 0
local registered = false
local sendSocket = nil

local function logi(message)
    log.write("PetrobrainFiringEvents", log.INFO, message)
end

-- Mirrors every other Hook script's own `dostring_in` wrapper exactly.
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
    if ok and type(result) == "string" then
        registered = true
    end
end

local function sendPayload(payload, bridgeCallMs)
    if sendSocket == nil then
        sendSocket = socket.udp()
    end
    local envelope = JSON:encode({ payload = payload, bridge_call_ms = bridgeCallMs })
    local ok, err = sendSocket:sendto(envelope, FIRING_SEND_HOST, FIRING_SEND_PORT)
    if not ok then
        logi("send failed: " .. tostring(err))
    end
end

local function pollAndSend()
    local startClock = os.clock()
    local ok, result = dostring("scripting", EVENT_POLL_CODE)
    local bridgeCallMs = (os.clock() - startClock) * 1000.0
    if not ok or type(result) ~= "string" then
        logi("event poll failed: ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    local count = result:match("^(%d+)|") or "?"
    if count ~= "0" and count ~= "?" then
        logi("firing events poll: n=" .. count .. " bridge_call_ms=" .. string.format("%.2f", bridgeCallMs))
    end
    sendPayload(result, bridgeCallMs)
end

function petrobrainFiringEvents.onSimulationStart()
    logi("onSimulationStart")
    simulationRunning = true
    registered = false
    nextPollAt = 0
end

function petrobrainFiringEvents.onSimulationFrame()
    if not simulationRunning then
        return
    end
    local now = DCS.getRealTime()
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
    local ok, err = pcall(pollAndSend)
    if not ok then
        logi("poll failed: " .. tostring(err))
    end
end

function petrobrainFiringEvents.onSimulationStop()
    logi("onSimulationStop")
    simulationRunning = false
    registered = false
end

DCS.setUserCallbacks(petrobrainFiringEvents)

logi("loaded")
