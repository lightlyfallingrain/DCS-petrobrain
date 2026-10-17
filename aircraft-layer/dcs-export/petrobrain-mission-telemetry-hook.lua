--[[
Aircraft Layer -- mission-scripting unit-velocity Hook script
(`plans/movement-detection/plan.md` Stage 1).

Deploy: copy this file to `Saved Games\DCS\Scripts\Hooks\` on the Windows
box, alongside `petrobrain-f10-commands-hook.lua` and
`petrobrain-overlay-hook.lua`. This is the canonical, version-controlled
copy; the deployed copy is not tracked by this repo, same discipline as
every other Hook-state script.

**A third, independent Hook script, not an extension of
`petrobrain-f10-commands-hook.lua`** -- opposite data direction from that
script's registration/poll split (this one calls the bridge directly every
poll, no persistent mission-scripting-side queue), independent lifecycle
and rate, and per `plans/movement-detection/plan.md`'s Affected Modules
section, keeping `petrobrain-f10-commands-hook.lua`'s own audited "exactly
two fixed literal snippets, never built from runtime input" property intact
by not touching that file at all.

**REQUIRES the same `autoexec.cfg` opt-in as `petrobrain-f10-commands-hook.
lua`** -- `net.dostring_in` is gated off without it (see that script's own
header, and `aircraft-layer/WORKFLOW.md`). Without the opt-in,
`dostring_in` silently returns `("Invalid state name", false)` every poll
and this script is a no-op -- watch `dcs.log` for `PetrobrainMissionTelemetry`
lines to confirm.

Uses `"scripting"` as the bridge target state, for the same reasons
`petrobrain-f10-commands-hook.lua`'s header documents (`"mission"`'s
`a_do_script` never actually executed).

**`VELOCITY_CODE` below is a fixed string literal, baked in at authoring
time -- never built from network input, mission data, or any other runtime
value.** Same posture as `petrobrain-f10-commands-hook.lua`'s own two
snippets.

**Sim time is stamped INSIDE the scripting state, via `timer.getTime()` --
never in the Hook via `DCS.getRealTime()`.** This is the plan's sharpest
replay-determinism risk: `DCS.getRealTime()` is wall-clock-driven (the
constraint `petrobrain-f10-commands-hook.lua`'s own `F10CommandEvent` wire
format was forced to accept, having no cheap sim-clock access from Hook
state) and would make a replayed sortie diverge. `timer.getTime()` is real,
confirmed-available mission-scripting API, reachable because this snippet
runs *inside* that state via `dostring_in`, not in the Hook.

**Wire format (this script -> collector), UDP, one JSON object per
poll** (matches `aircraft-layer/src/schema/unit_velocity.py`):
    {"payload": "<unit_count>|<dcs_model_time_s>|<entries>", "bridge_call_ms": <float>}
`entries` is `"<unit_name>:<vx>:<vy>:<vz>:<life>:<life0>;..."`,
semicolon-separated -- `dostring_in` can only return one simple scalar
across the Hook/mission-scripting boundary (the same constraint
`petrobrain-f10-commands-hook.lua`'s `POLL_CODE` works around), so
`VELOCITY_CODE` packs the whole poll into one string and this Hook wraps it
in JSON rather than parsing it itself.

**`life`/`life0` (`AC-B7`, the transport half of `BL-B72`'s burning
emitter) are the two trailing fields, added to this same loop rather than a
new feed** (user decision 1, `plans/emitter-visibility/plan.md`): the
existing `getVelocity()` loop already runs in-state over every live unit and
static once a second, joined body-side by `unit_name` -- `getLife()`/
`getLife0()` are one more `pcall` per object on the same object reference,
not a second loop or a second bridge round-trip. Either field is the literal
string `"nil"` when the underlying call fails or returns a non-number (same
tri-state discipline `WorldObjectCandidate.heading_true_deg`/`velocity`
already use on the body-layer side) -- `schema.unit_velocity.
UnitVelocitySample.life`/`life0` are `None` in that case, never a guessed
`0.0`.

`bridge_call_ms` is this Hook's own `os.clock()`-measured wall-time cost of
the `dostring_in` call -- Stage 0 part 2's self-measurement design: the
in-state `O(N)` `getVelocity()` loop's per-call cost cannot be measured from
the Mac (no DCS, no mission-scripting sandbox), so the next sortie flown for
any reason answers the question for free, logged to `dcs.log` alongside
`unit_count` and forwarded to the collector so it lands in
`UnitVelocitySnapshot` too.

Reuses DCS's own shipped JSON encoder (`Scripts\JSON.lua`) and LuaSocket's
`package.path`/`cpath` extension, mirroring every other Hook script in this
project.
--]]

log.write("PetrobrainMissionTelemetry", log.INFO, "Loading - Petrobrain mission telemetry")

package.path = package.path
    .. ";.\\LuaSocket\\?.lua;"
    .. ".\\Scripts\\?.lua;"
    .. ".\\Scripts\\UI\\?.lua;"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll;"

local socket = require("socket")
local DCS = require("DCS")

local JSON = loadfile("Scripts\\JSON.lua")()

--: Loopback UDP port `collector.unit_velocity_receiver.DEFAULT_PORT`
--: listens on -- must match exactly. A fifth, distinct loopback port from
--: Export.lua's listener (7790), the overlay Hook's listener (7792),
--: Export.lua's inbound command listener (7793), and the F10 commands
--: Hook's sender (7794).
local UNIT_VELOCITY_PORT = 7795
local UNIT_VELOCITY_HOST = "127.0.0.1"

--: 1 Hz, matching `petrobrain-f10-commands-hook.lua`'s own poll rate and
--: the roadmap's stated design ("polling at 1 Hz").
local POLL_INTERVAL_S = 1.0

--: Enumerates every unit (via `coalition.getGroups`) and static object (via
--: `coalition.getStaticObjects`) across all three coalition sides, reading
--: `Unit:getVelocity()` for each live unit -- statics carry no velocity API
--: and are DCS-immobile by definition, so they're emitted at a fixed zero
--: vector rather than skipped (`plans/movement-detection/plan.md` Stage 1:
--: "zero velocity by definition, no getVelocity call needed" -- this also
--: means a static's `apparent_motion` reads `False`, not `None`, on the
--: body-layer side, rather than leaving every static permanently
--: "unknown"). `timer.getTime()` is read once and stamped into the
--: returned string -- see file header on why this must not be
--: `DCS.getRealTime()`. Joins on `Unit:getName()`, which returns the exact
--: same string `Export.lua`'s new `unit_name` field carries
--: (`LoGetWorldObjects`'s own `UnitName`) -- `plans/movement-detection/
--: plan.md` Decision 1.
--:
--: `lifeFields` (`AC-B7`) reads `getLife()`/`getLife0()` off the same
--: `unit`/`obj` reference the velocity read already has in hand -- one more
--: guarded `pcall` per object, not a second enumeration. Both live units and
--: static objects expose `getLife()`/`getLife0()` (both are DCS `Object`s),
--: confirmed per-unit over this same bridge by the closed probe
--: (`docs/acceptance/2026-09-24-damage-and-firing-probes.md`, flown
--: 2026-09-25). Returns the literal string `"nil"` for either field on any
--: failure (no such call, non-number result) -- never a guessed `0`, so the
--: body-layer parser's `None` means exactly "this poll could not read it".
--: **Defined inside `VELOCITY_CODE` itself, not as a Hook-local function**
--: -- `VELOCITY_CODE` is a string executed via `net.dostring_in("scripting",
--: ...)` in the separate mission-scripting Lua state, which cannot see any
--: function defined in this Hook's own state (the same reason
--: `petrobrain-f10-commands-hook.lua`'s snippets are self-contained strings).
local VELOCITY_CODE = [[
local function lifeFields(obj)
    local lifeOk, life = pcall(function() return obj:getLife() end)
    local life0Ok, life0 = pcall(function() return obj:getLife0() end)
    local lifeStr = (lifeOk and type(life) == "number") and tostring(life) or "nil"
    local life0Str = (life0Ok and type(life0) == "number") and tostring(life0) or "nil"
    return lifeStr .. ":" .. life0Str
end
local parts = {}
local count = 0
for _, coa in pairs({coalition.side.NEUTRAL, coalition.side.RED, coalition.side.BLUE}) do
    for _, grp in ipairs(coalition.getGroups(coa) or {}) do
        for _, unit in ipairs(grp:getUnits() or {}) do
            if unit and unit:isExist() then
                local ok, v = pcall(function() return unit:getVelocity() end)
                if ok and v ~= nil then
                    count = count + 1
                    parts[#parts + 1] = unit:getName() .. ":" .. tostring(v.x)
                        .. ":" .. tostring(v.y) .. ":" .. tostring(v.z)
                        .. ":" .. lifeFields(unit)
                end
            end
        end
    end
    for _, obj in ipairs(coalition.getStaticObjects(coa) or {}) do
        if obj and obj:isExist() then
            count = count + 1
            parts[#parts + 1] = obj:getName() .. ":0:0:0:" .. lifeFields(obj)
        end
    end
end
return tostring(count) .. "|" .. tostring(timer.getTime()) .. "|" .. table.concat(parts, ";")
]]

local petrobrainMissionTelemetry = {}

local simulationRunning = false
local nextPollAt = 0
local sendSocket = nil

local function logi(message)
    log.write("PetrobrainMissionTelemetry", log.INFO, message)
end

-- Mirrors petrobrain-f10-commands-hook.lua's own `dostring` wrapper exactly.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

local function sendPayload(payload, bridgeCallMs)
    if sendSocket == nil then
        sendSocket = socket.udp()
    end
    local envelope = JSON:encode({ payload = payload, bridge_call_ms = bridgeCallMs })
    local ok, err = sendSocket:sendto(envelope, UNIT_VELOCITY_HOST, UNIT_VELOCITY_PORT)
    if not ok then
        logi("send failed: " .. tostring(err))
    end
end

local function pollAndSend()
    local startClock = os.clock()
    local ok, result = dostring("scripting", VELOCITY_CODE)
    local bridgeCallMs = (os.clock() - startClock) * 1000.0
    if not ok or type(result) ~= "string" then
        logi("velocity poll failed: ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    -- Stage 0 part 2's self-measurement: log unit_count (the payload's own
    -- first field, per the module docstring) and bridge_call_ms to dcs.log
    -- on every poll, not only on failure, so any sortie flown answers the
    -- per-call cost question.
    local unitCountStr = result:match("^(%d+)|") or "?"
    logi(
        "velocity poll: unit_count=" .. unitCountStr
            .. " bridge_call_ms=" .. string.format("%.2f", bridgeCallMs)
    )
    sendPayload(result, bridgeCallMs)
end

function petrobrainMissionTelemetry.onSimulationStart()
    logi("onSimulationStart")
    simulationRunning = true
    nextPollAt = 0
end

function petrobrainMissionTelemetry.onSimulationFrame()
    if not simulationRunning then
        return
    end
    local now = DCS.getRealTime()
    if now < nextPollAt then
        return
    end
    nextPollAt = now + POLL_INTERVAL_S
    local ok, err = pcall(pollAndSend)
    if not ok then
        logi("poll failed: " .. tostring(err))
    end
end

function petrobrainMissionTelemetry.onSimulationStop()
    logi("onSimulationStop")
    simulationRunning = false
end

DCS.setUserCallbacks(petrobrainMissionTelemetry)

logi("loaded")
