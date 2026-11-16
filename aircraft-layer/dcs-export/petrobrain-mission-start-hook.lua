--[[
Aircraft Layer -- mission-start signal Hook script (`plans/bl15-mission-start/
plan.md`, BL-15 Stage 1).

Deploy: copy this file to `Saved Games\DCS\Scripts\Hooks\` on the Windows
box (see aircraft-layer/WORKFLOW.md). This is the canonical, version-
controlled copy; the deployed copy is not tracked by this repo, same
discipline as Export.lua and the other Hook scripts.

Registers `onSimulationStart`, increments a local sequence counter, attempts
to read the live mission's `theatre` string over the already-proven
`net.dostring_in("scripting", ...)` bridge (the same bridge
`petrobrain-f10-commands-hook.lua` already uses at this exact callback),
and sends one UDP datagram to `collector.mission_start_receiver.
MissionStartReceiver`, port 7799.

**One-shot per mission start, not a per-frame poll.** Unlike the F10
commands Hook (which drains a selection queue once a second), there is
nothing to drain here -- `onSimulationStart` itself is the signal, so this
script needs no `onSimulationFrame` handler at all.

**`theatre` resolution is read-only and best-effort.** `net.dostring_in
("scripting", "return env.mission.theatre")` is the hard-coded expression
run -- never built from network input, mission data, or any other runtime
value, same posture as every other `dostring_in` call in this codebase. If
the call fails, raises, or returns something other than a string, `theatre`
is sent as `null` rather than blocking the rest of the signal -- body-layer
treats a `null` theatre as "no new theatre information this (re)start", per
`aircraft-layer/src/schema/mission_start.py`'s own docstring, not a parse
failure.

**Wire format (this script -> collector), UDP, one JSON object per
datagram** (matches `aircraft-layer/src/schema/mission_start.py`):
    {"sequence": <int>, "theatre": "<string>"|null,
     "qnh": <number>|null, "atmosphere_type": <int>|null}

Reuses DCS's own shipped JSON encoder (`Scripts\JSON.lua`) and LuaSocket's
`package.path`/`cpath` extension, same approach as every other Hook script
in this directory.

**`qnh`/`atmosphere_type` added by `BL-B118`** (`plans/
bl16-qnh-mission-start/plan.md`) -- read the same best-effort,
`net.dostring_in` way as `theatre`, mirroring `resolveTheatre()` exactly.
`qnh` (`env.mission.weather.qnh`, mmHg) is what body-layer's operator-
altimeter sync loop drives the cockpit toward; `atmosphere_type`
(`env.mission.weather.atmosphere_type`) rides beside it purely for the
record, in case a dynamic-weather mission's `qnh` turns out not to be
meaningful -- neither field is special-cased here.
--]]

log.write("PetrobrainMissionStart", log.INFO, "Loading - Petrobrain mission start")

package.path = package.path
    .. ";.\\LuaSocket\\?.lua;"
    .. ".\\Scripts\\?.lua;"
    .. ".\\Scripts\\UI\\?.lua;"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll;"

local socket = require("socket")
local DCS = require("DCS")

local JSON = loadfile("Scripts\\JSON.lua")()

--: Loopback UDP port `collector.mission_start_receiver.DEFAULT_PORT`
--: listens on -- must match exactly.
local MISSION_START_PORT = 7799
local MISSION_START_HOST = "127.0.0.1"

local petrobrainMissionStart = {}

local sequence = 0
local sendSocket = nil

local function logi(message)
    log.write("PetrobrainMissionStart", log.INFO, message)
end

--: Mirrors `petrobrain-f10-commands-hook.lua`'s own `dostring` wrapper:
--: `ok` is true only if the bridge call itself did not raise AND
--: `dostring_in`'s own success flag was not explicitly `false`.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

--: Best-effort read of the live mission's theatre string. Returns `nil`
--: (never raises) on any failure -- the mission-start signal must still be
--: sent even if theatre resolution does not work this firing.
local function resolveTheatre()
    local ok, result = dostring("scripting", "return env.mission.theatre")
    if ok and type(result) == "string" and result ~= "" then
        return result
    end
    return nil
end

--: `BL-B118` -- best-effort read of the live mission's QNH (mmHg),
--: mirroring `resolveTheatre()` exactly. Returns `nil` (never raises) on
--: any failure or non-number result.
local function resolveQnh()
    local ok, result = dostring("scripting", "return env.mission.weather.qnh")
    if ok and type(result) == "number" then
        return result
    end
    return nil
end

--: `BL-B118` -- same shape as `resolveQnh()`, for `env.mission.
--: weather.atmosphere_type`, carried for the record only.
local function resolveAtmosphereType()
    local ok, result = dostring("scripting", "return env.mission.weather.atmosphere_type")
    if ok and type(result) == "number" then
        return result
    end
    return nil
end

local function sendMissionStart(seq, theatre, qnh, atmosphereType)
    if sendSocket == nil then
        sendSocket = socket.udp()
    end
    local payload = JSON:encode({
        sequence = seq,
        theatre = theatre,
        qnh = qnh,
        atmosphere_type = atmosphereType,
    })
    local ok, err = sendSocket:sendto(payload, MISSION_START_HOST, MISSION_START_PORT)
    if not ok then
        logi("send failed for sequence=" .. tostring(seq) .. ": " .. tostring(err))
    end
end

function petrobrainMissionStart.onSimulationStart()
    sequence = sequence + 1
    local theatreOk, theatre = pcall(resolveTheatre)
    local resolvedTheatre = theatreOk and theatre or nil
    local qnhOk, qnh = pcall(resolveQnh)
    local resolvedQnh = qnhOk and qnh or nil
    local atmosphereOk, atmosphereType = pcall(resolveAtmosphereType)
    local resolvedAtmosphereType = atmosphereOk and atmosphereType or nil
    logi(
        "onSimulationStart sequence=" .. tostring(sequence)
            .. " theatre=" .. tostring(resolvedTheatre)
            .. " qnh=" .. tostring(resolvedQnh)
            .. " atmosphere_type=" .. tostring(resolvedAtmosphereType)
    )
    local ok, err = pcall(
        sendMissionStart, sequence, resolvedTheatre, resolvedQnh, resolvedAtmosphereType
    )
    if not ok then
        logi("sendMissionStart failed: " .. tostring(err))
    end
end

DCS.setUserCallbacks(petrobrainMissionStart)

logi("loaded")
