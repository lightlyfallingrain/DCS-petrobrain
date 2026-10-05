--[[
Aircraft Layer -- DCS-driven, cone-scoped line-of-sight Hook script
(`plans/dcs-driven-los/plan.md`, X-B29).

Deploy: copy this file to `Saved Games\DCS\Scripts\Hooks\` on the Windows
box, alongside every other Petrobrain Hook script. This is the canonical,
version-controlled copy; the deployed copy is not tracked by this repo,
same discipline as every other Hook-state script.

**REQUIRES the same `autoexec.cfg` opt-in as every other `dostring_in`-
using Hook script** -- see `petrobrain-mission-telemetry-hook.lua`'s own
header and `aircraft-layer/WORKFLOW.md`. Without it, `dostring_in` silently
returns `("Invalid state name", false)` every poll and this script is a
no-op -- watch `dcs.log` for `PetrobrainLineOfSight` lines to confirm.

**Two independent engine calls, computed once per sightline and published
as two separate fields, never pre-ANDed** (plan "REVISION 2026-09-29"):
`world.searchObjects`/`world.VolumeType.SEGMENT` for buildings
(`building_clear`), `land.isVisible` for terrain (`terrain_clear`).
Confirmed terrain-only, not building-aware (`aircraft-layer/research/
2026-09-29-bridge-terrain-probe-results.md` Finding 12/16/19, re-confirmed
by the plan's SS4). Keeping the two fields separable means a live
misbehaviour is attributable to one half, not "LOS was wrong" in general.

**The query set is the look-direction wedge, not the player bubble** (plan
Second Revision, SS8-SS10): the bubble (10 km) bounds *candidates*;
`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG` (mission-scripting globals, set by the
inbound look-direction command below) bound *which of those candidates
this poll actually computes a sightline for*. A unit outside the wedge is
simply absent from the payload -- the tri-state join on the body-layer
side (`naked_eye_source._resolve_los_by_unit_name`) reads that as `None`
("not looked at"), which is both correct and cheap: ~10 units/poll reach
this gate in the measured sortie (plan SS8), not the ~172-195 the whole
bubble would cost.

**`MAX_SIGHTLINES_PER_CALL` is a blow-up guard, not a policy** (plan SS10):
at the measured per-sightline cost (~25 microseconds peak, buildings +
terrain) even the full bubble is a few milliseconds, so this cap should
essentially never bite under a correctly-sized wedge. If
`sightlines_computed < units_in_wedge` ever shows up in the log, the wedge
is wrong, not the budget -- see `sightlines_computed`/`units_in_wedge` on
the wire schema (`aircraft-layer/src/schema/line_of_sight.py`).

**The look-direction command channel -- a validated `string.format`
splice, not digit dispatch (plan SS17, user's informed call after the
architect's digit-dispatch recommendation; Security plan review APPROVED
w/ 2 required fixes, both implemented below).** `SET_LOOK_TEMPLATE` below
is a module-level constant with **exactly two `%d` substitutions and
nothing else** -- one more than the Security review's "exactly one %d"
phrasing anticipated, because this channel sets *two* already-validated
integers (`hour`, `fov_half_deg`) in one coalesced `dostring_in` call
rather than two separate calls (the review's own Finding 5/required fix
2: coalesce to at most one setter call per frame). The safety argument is
identical for each substitution point and does not depend on there being
only one: Lua 5.1's `string.format("%d", x)` is a thin wrapper over C
`sprintf` and can only ever emit an optional leading `-` followed by
decimal digits, for *any* finite integer `x` -- there is no way for a
`%d` conversion to emit a quote, `]==]`, `end`, `;`, or anything else that
could close the template early or open a new statement. Adding a *third*
substitution point, or changing either of these two from `%d` to `%s` or
any other specifier, is what would make this genuinely unsafe -- don't.
`aircraft-layer/tests/test_line_of_sight_hook_lua.py` asserts this file's
`SET_LOOK_TEMPLATE` literal contains exactly two `%d` conversions and no
other `%` specifier, as a mechanical guard against exactly that edit.

**The clamp feeding that splice is the actual safety property, and it
must be total** (Security review Finding 1, required fix 1):
`_safeClampInt` below explicitly tests for non-number input, NaN
(`x ~= x`, the standard Lua self-inequality test -- every IEEE-754
comparison against NaN is false, so the idiomatic `math.max(lo,
math.min(hi, x))` clamp silently passes a NaN straight through) and
`math.huge`/`-math.huge` *before* any ordinary min/max comparison, then
rounds to the nearest integer. The whole decode-clamp-format-dostring_in
sequence for an inbound look-direction datagram is wrapped in `pcall`
(`_applyLookDirection`), so an unanticipated error leaves the previous
`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG` globals in place rather than silently
corrupting them -- never a half-applied update.

**`tonumber("nan")`/`tonumber("inf")` behaviour on DCS's own bundled Lua/
CRT was not verified this session** (no live DCS available to this
agent) -- per the Security review, this is platform-dependent (C99
`strtod`-conformant runtimes parse those strings case-insensitively;
older MSVC CRT does not). `_safeClampInt` is written to be correct under
*either* behaviour: if `tonumber` ever does produce a Lua NaN/Inf here,
the explicit guards above catch it before the clamp; if it instead
returns `nil` (the string failed to parse as a number at all), the
`type(x) ~= "number"` check at the top of `_safeClampInt` catches that
case just as well. **Confirm directly against the real DCS install before
relying on either path being exercised in practice** -- a debug print of
`tonumber("nan")`/`tonumber("inf")` from this Hook's own log line is
enough; not done here.

**Where the look-direction state lives -- forced, not chosen** (plan
SS9a): a global in the *mission-scripting* state (`PB_LOOK_HOUR`/
`PB_LOOK_FOV_DEG`), not the Hook's own Lua state and not `Export.lua`'s
(a separate Lua state entirely, with no shared globals and no access to
`land.*`/`world.*`). Persistence of a mission-scripting-state global
across repeated `dostring_in` calls is the same mechanism
`petrobrain-f10-commands-hook.lua`'s `PB_F10_QUEUE` already proves.

**The inbound look-direction listener is this Hook's own UDP socket**
(bound `127.0.0.1` only -- Security review Finding 7/this plan's Risk:
same box as the collector, no new network exposure), structurally mirroring
`petrobrain-overlay-hook.lua`'s own inbound listener (the only existing
precedent for a Hook-state script *receiving* UDP, as opposed to
`Export.lua`'s `try_open_command_socket`, which lives in a different Lua
state and could not reach the mission-scripting globals this channel
needs to set).

**Sim time is stamped INSIDE the scripting state via `timer.getTime()`,
never in the Hook via `DCS.getRealTime()`** -- same replay-determinism
reasoning as every other `dostring_in`-based feed in this codebase
(`petrobrain-mission-telemetry-hook.lua`'s own header).

**Heading/bearing geometry below (`Unit:getPosition()`'s `x` forward
vector, `atan2`-derived true heading) follows the standard DCS Mission
Scripting Engine convention documented across the DCS modding community
-- it has NOT been live-verified against a running DCS session by this
agent** (no DCS available in this environment). Flagged explicitly in
`plans/dcs-driven-los/implementation.md`'s own "could not be verified
without DCS" section; Stage 4's acceptance sortie is what confirms it.

Wire format (this script -> collector), UDP, one JSON object per poll
(matches `aircraft-layer/src/schema/line_of_sight.py`):
    {"payload": "<units_in_bubble>|<units_in_wedge>|<sightlines_computed>|"
                "<hour_used>|<fov_half_deg_used>|<dcs_model_time_s>|<entries>",
     "bridge_call_ms": <float>}
`entries` is `"<unit_name>:<building_clear01>:<terrain_clear01>;..."`.

Reuses DCS's own shipped JSON encoder (`Scripts\JSON.lua`) and LuaSocket's
`package.path`/`cpath` extension, mirroring every other Hook script here.
--]]

log.write("PetrobrainLineOfSight", log.INFO, "Loading - Petrobrain line of sight")

package.path = package.path
    .. ";.\\LuaSocket\\?.lua;"
    .. ".\\Scripts\\?.lua;"
    .. ".\\Scripts\\UI\\?.lua;"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll;"

local socket = require("socket")
local DCS = require("DCS")

local JSON = loadfile("Scripts\\JSON.lua")()

--: Loopback UDP port `collector.line_of_sight_receiver.DEFAULT_PORT`
--: listens on (outbound, this script -> collector) -- must match exactly.
--: A sixth, distinct loopback port from Export.lua's listener (7790), the
--: overlay Hook's listener (7792), Export.lua's inbound command listener
--: (7793), the F10 Hook's sender (7794), and the mission-telemetry Hook's
--: sender (7795).
local LOS_SEND_HOST = "127.0.0.1"
local LOS_SEND_PORT = 7796

--: This Hook's own inbound listener (collector -> this script, carrying
--: look-direction commands) -- `collector.command_sender.
--: LOOK_DIRECTION_DEFAULT_PORT`. A seventh, distinct loopback port.
--: Bound `"127.0.0.1"` only, never `"*"` -- Security review Finding 7.
local LOOK_DIRECTION_LISTEN_HOST = "127.0.0.1"
local LOOK_DIRECTION_LISTEN_PORT = 7797

--: 1 Hz -- same cadence every other `dostring_in`-based feed in this
--: codebase polls at (plan "Cadence re-derived... conclusion unchanged").
local POLL_INTERVAL_S = 1.0

--: `perception.association.PLAYER_BUBBLE_RADIUS_M` -- the candidate bound
--: (not the query bound; the wedge filter inside LOS_CODE is what actually
--: scopes the engine work, plan SS8-SS10).
local PLAYER_BUBBLE_RADIUS_M = 10000.0

--: A blow-up guard, not a policy -- see file header. Sized at the
--: 260-degree (`fov_half_deg=130`, attention-capture) estimate from the
--: plan's SS10 table (~124 units, ~3.1 ms), not the 90-degree ship value,
--: so widening the query cone later (a pure data change, per SS14) does
--: not also require raising this guard.
local MAX_SIGHTLINES_PER_CALL = 128

--: Look-direction vocabulary bounds (plan SS9b). `fov_half_deg=180` is a
--: full-circle query and is legal only as the honest ceiling -- never the
--: fallback/default.
local HOUR_MIN = 0
local HOUR_MAX = 11
local FOV_MIN_DEG = 5
local FOV_MAX_DEG = 180

--: The default wedge when no look-direction command has arrived yet this
--: mission-scripting-state lifetime (mirrors `PB_F10_QUEUE`'s own
--: `PB_LOOK_HOUR or <default>` read pattern inside LOS_CODE below) --
--: 12 o'clock, 90 degrees full width. Arbitrary hour choice (nothing
--: downstream treats "no directive yet" as meaningful beyond "some
--: wedge"); `FOV_DEFAULT_DEG` itself is plan SS17's own settled value.
local HOUR_DEFAULT = 0
local FOV_DEFAULT_DEG = 45

--: Bounded drain per frame for the inbound look-direction socket, mirroring
--: `petrobrain-overlay-hook.lua`'s own `MAX_DATAGRAMS_PER_FRAME` -- a
--: pathological flood cannot stall a frame. Only the **last** datagram
--: drained this frame is ever applied (Security review Finding 5/required
--: fix 2: coalesce to at most one `dostring_in` setter call per frame,
--: never one per queued datagram).
local MAX_LOOK_DIRECTION_DATAGRAMS_PER_FRAME = 20

--: The only runtime-value splice in this codebase (plan SS17) -- see file
--: header for the full safety argument. Exactly two `%d` conversions, no
--: other `%` specifier, ever.
local SET_LOOK_TEMPLATE = "PB_LOOK_HOUR=%d\nPB_LOOK_FOV_DEG=%d\nreturn \"ok\""

--: Enumerates every live unit across all three coalition sides within
--: `PLAYER_BUBBLE_RADIUS_M` of ownship's own true position, filters those
--: down to the ones inside the currently-commanded look-direction wedge
--: (`PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG`, defaulting per `HOUR_DEFAULT`/
--: `FOV_DEFAULT_DEG` when unset), sorts the wedge survivors nearest-first,
--: caps at `MAX_SIGHTLINES_PER_CALL`, and for each capped unit runs both
--: the building (`SEGMENT`) and terrain (`isVisible`) sightline tests
--: true-position-to-true-position (never a believed position -- the
--: plan's own "Why it must be true-to-true" section). `timer.getTime()`
--: is read once and stamped into the returned string, for the same
--: replay-determinism reason every other feed here uses it instead of
--: `DCS.getRealTime()`.
--:
--: Ownship identity/heading: `world.getPlayer()`, the same call this
--: project's earlier LOS probes already used live
--: (`petrobrain-segment-los-probe-hook.lua`,
--: `petrobrain-elevation-cost-probe-hook.lua`). Heading is derived from
--: `Unit:getPosition()`'s forward (`x`) vector via `atan2` -- the standard
--: DCS Mission Scripting Engine convention; **not independently
--: live-verified this session** (file header).
local LOS_CODE = [[
local hour = PB_LOOK_HOUR or 0
local fovHalfDeg = PB_LOOK_FOV_DEG or 45

local okP, player = pcall(world.getPlayer)
if not okP or player == nil then
    return "ERR|world.getPlayer unavailable"
end
local okPos, pos = pcall(function() return player:getPosition() end)
if not okPos or pos == nil then
    return "ERR|getPosition failed"
end
local ox, oy, oz = pos.p.x, pos.p.y, pos.p.z
local headingRad = math.atan2(pos.x.z, pos.x.x)
local headingDeg = headingRad * 180.0 / math.pi
if headingDeg < 0 then headingDeg = headingDeg + 360.0 end

-- The commanded wedge's own centre, body-relative, matching
-- `perception.gaze._gaze_for_clock_hour`'s exact convention (12 = 0,
-- positive clockwise): `((hour % 12) * 30 + 180) % 360 - 180`.
local centerAzimuthDeg = ((hour % 12) * 30 + 180) % 360 - 180

local function wrapSigned180(deg)
    local wrapped = deg % 360
    if wrapped > 180 then wrapped = wrapped - 360 end
    return wrapped
end

local candidates = {}
local unitsInBubble = 0
local unitsInWedge = 0

for _, coa in pairs({coalition.side.NEUTRAL, coalition.side.RED, coalition.side.BLUE}) do
    for _, grp in ipairs(coalition.getGroups(coa) or {}) do
        for _, unit in ipairs(grp:getUnits() or {}) do
            if unit and unit:isExist() and unit:getID() ~= player:getID() then
                local okUP, up = pcall(function() return unit:getPoint() end)
                if okUP and up ~= nil then
                    local dx, dz = up.x - ox, up.z - oz
                    local rangeM = math.sqrt(dx * dx + dz * dz)
                    if rangeM <= 10000.0 then
                        unitsInBubble = unitsInBubble + 1
                        local trueBearingDeg = math.atan2(dz, dx) * 180.0 / math.pi
                        if trueBearingDeg < 0 then trueBearingDeg = trueBearingDeg + 360.0 end
                        local bodyBearingDeg = wrapSigned180(trueBearingDeg - headingDeg)
                        local delta = wrapSigned180(bodyBearingDeg - centerAzimuthDeg)
                        if delta < 0 then delta = -delta end
                        if delta <= fovHalfDeg then
                            unitsInWedge = unitsInWedge + 1
                            local okName, name = pcall(function() return unit:getName() end)
                            if okName then
                                candidates[#candidates + 1] = {
                                    name = name,
                                    x = up.x, y = up.y, z = up.z,
                                    rangeM = rangeM,
                                }
                            end
                        end
                    end
                end
            end
        end
    end
end

table.sort(candidates, function(a, b) return a.rangeM < b.rangeM end)

local function buildingClear(fromPoint, toPoint)
    local hit = false
    local ok = pcall(function()
        world.searchObjects(Object.Category.SCENERY,
            { id = world.VolumeType.SEGMENT,
              params = { from = fromPoint, to = toPoint } },
            function(_obj)
                hit = true
                return false
            end)
    end)
    if not ok then return true end
    return not hit
end

local function terrainClear(fromPoint, toPoint)
    local ok, visible = pcall(land.isVisible, fromPoint, toPoint)
    if not ok then return true end
    return visible == true
end

local parts = {}
local sightlinesComputed = 0
local observerPoint = { x = ox, y = oy + 2.0, z = oz }

for i = 1, #candidates do
    if sightlinesComputed >= 128 then break end
    local c = candidates[i]
    local targetPoint = { x = c.x, y = c.y + 2.0, z = c.z }
    local bClear = buildingClear(observerPoint, targetPoint)
    local tClear = terrainClear(observerPoint, targetPoint)
    sightlinesComputed = sightlinesComputed + 1
    parts[#parts + 1] = c.name .. ":" .. (bClear and "1" or "0") .. ":" .. (tClear and "1" or "0")
end

return tostring(unitsInBubble) .. "|" .. tostring(unitsInWedge) .. "|"
    .. tostring(sightlinesComputed) .. "|" .. tostring(hour) .. "|"
    .. tostring(fovHalfDeg) .. "|" .. tostring(timer.getTime()) .. "|"
    .. table.concat(parts, ";")
]]

local petrobrainLineOfSight = {}

local simulationRunning = false
local nextPollAt = 0
local sendSocket = nil
local listenSocket = nil
local lastSentHour = nil
local lastSentFovHalfDeg = nil

local function logi(message)
    log.write("PetrobrainLineOfSight", log.INFO, message)
end

-- Mirrors every other Hook script's own `dostring_in` wrapper exactly.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

--: Total, NaN/Inf-guarded integer clamp (Security review Finding 1,
--: required fix 1) -- see file header for the full reasoning. Never
--: relies on `math.min`/`math.max` alone, since those silently pass a
--: NaN straight through (every IEEE-754 comparison against NaN is
--: false). Always returns an integer in `[minValue, maxValue]`: a
--: non-number, NaN, or either infinity resolves to `defaultValue`
--: (mid-range default, itself required to be in range by every call
--: site below) or the matching boundary for +-infinity respectively,
--: never a pass-through of the bad value.
local function _safeClampInt(value, minValue, maxValue, defaultValue)
    if type(value) ~= "number" then
        return defaultValue
    end
    if value ~= value then -- NaN: the standard Lua self-inequality test
        return defaultValue
    end
    if value == math.huge then
        return maxValue
    end
    if value == -math.huge then
        return minValue
    end
    local clamped = value
    if clamped < minValue then
        clamped = minValue
    elseif clamped > maxValue then
        clamped = maxValue
    end
    return math.floor(clamped + 0.5)
end

--: Decodes one look-direction datagram body, clamps both fields, and
--: issues exactly one coalesced `dostring_in` setter call -- wrapped in
--: `pcall` end-to-end (Security review required fix 1's "no error path
--: leaves a stale value silently in place": on any failure here, the
--: previous `PB_LOOK_HOUR`/`PB_LOOK_FOV_DEG` globals are simply left
--: untouched, which is the correct degradation per the plan's own
--: SS9c -- a wrong/stale wedge costs coverage, never correctness).
--: Only pushes when the resolved pair differs from the last one actually
--: sent (plan SS9b "pushed on change"), plus unconditionally on
--: `onSimulationStart` (`lastSentHour`/`lastSentFovHalfDeg` reset there).
local function _applyLookDirection(decoded)
    local hourRaw = decoded.hour
    local fovRaw = decoded.fov_half_deg
    local hour = _safeClampInt(hourRaw, HOUR_MIN, HOUR_MAX, HOUR_DEFAULT)
    local fovHalfDeg = _safeClampInt(fovRaw, FOV_MIN_DEG, FOV_MAX_DEG, FOV_DEFAULT_DEG)

    if hour == lastSentHour and fovHalfDeg == lastSentFovHalfDeg then
        return
    end

    local snippet = string.format(SET_LOOK_TEMPLATE, hour, fovHalfDeg)
    local ok, result = dostring("scripting", snippet)
    if ok then
        lastSentHour = hour
        lastSentFovHalfDeg = fovHalfDeg
        logi("look direction set: hour=" .. tostring(hour) .. " fov_half_deg=" .. tostring(fovHalfDeg))
    else
        logi("look direction set failed: " .. tostring(result))
    end
end

--: Drains up to `MAX_LOOK_DIRECTION_DATAGRAMS_PER_FRAME` pending
--: datagrams, applying only the last successfully-decoded one this frame
--: -- Security review Finding 5/required fix 2: coalesce to at most one
--: `dostring_in` setter call per frame, never one per queued datagram.
local function pollLookDirection()
    if listenSocket == nil then
        return
    end
    local latest = nil
    for _ = 1, MAX_LOOK_DIRECTION_DATAGRAMS_PER_FRAME do
        local data, _err = listenSocket:receivefrom()
        if data == nil then
            break
        end
        local decodeOk, decoded = pcall(function() return JSON:decode(data) end)
        if decodeOk and type(decoded) == "table" and decoded.op == "look_direction" then
            latest = decoded
        end
    end
    if latest ~= nil then
        _applyLookDirection(latest)
    end
end

local function sendPayload(payload, bridgeCallMs)
    if sendSocket == nil then
        sendSocket = socket.udp()
    end
    local envelope = JSON:encode({ payload = payload, bridge_call_ms = bridgeCallMs })
    local ok, err = sendSocket:sendto(envelope, LOS_SEND_HOST, LOS_SEND_PORT)
    if not ok then
        logi("send failed: " .. tostring(err))
    end
end

local function pollAndSend()
    local startClock = os.clock()
    local ok, result = dostring("scripting", LOS_CODE)
    local bridgeCallMs = (os.clock() - startClock) * 1000.0
    if not ok or type(result) ~= "string" then
        logi("LOS poll failed: ok=" .. tostring(ok) .. " result=" .. tostring(result))
        return
    end
    if result:sub(1, 4) == "ERR|" then
        logi("LOS poll error: " .. result)
        return
    end
    logi(
        "LOS poll: bridge_call_ms=" .. string.format("%.2f", bridgeCallMs)
            .. " result_head=" .. result:sub(1, 40)
    )
    sendPayload(result, bridgeCallMs)
end

function petrobrainLineOfSight.onSimulationStart()
    logi("onSimulationStart")
    simulationRunning = true
    nextPollAt = 0
    -- Mission-scripting-state globals are cleared on a mission
    -- restart (the same reason `petrobrain-mission-telemetry-hook.lua`'s
    -- sibling feeds reset their own per-mission state here) -- forcing an
    -- unconditional re-push on the *next* look-direction command, per
    -- plan SS9b ("pushed on change, plus unconditionally on
    -- onSimulationStart"). There is nothing to re-push yet at this exact
    -- point (no command has necessarily arrived this mission), so this
    -- only resets the "last sent" bookkeeping; LOS_CODE's own `or`
    -- defaults (`HOUR_DEFAULT`/`FOV_DEFAULT_DEG`-equivalent literals)
    -- cover the gap until the first command lands.
    lastSentHour = nil
    lastSentFovHalfDeg = nil
    if listenSocket == nil then
        local sock = socket.udp()
        local ok, err = sock:setsockname(LOOK_DIRECTION_LISTEN_HOST, LOOK_DIRECTION_LISTEN_PORT)
        if ok then
            sock:settimeout(0)
            listenSocket = sock
            logi("look-direction listener bound on " .. LOOK_DIRECTION_LISTEN_HOST .. ":" .. tostring(LOOK_DIRECTION_LISTEN_PORT))
        else
            logi("failed to bind look-direction listener: " .. tostring(err))
        end
    end
end

function petrobrainLineOfSight.onSimulationFrame()
    if not simulationRunning then
        return
    end
    local pollOk, pollErr = pcall(pollLookDirection)
    if not pollOk then
        logi("look-direction poll failed: " .. tostring(pollErr))
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

function petrobrainLineOfSight.onSimulationStop()
    logi("onSimulationStop")
    simulationRunning = false
    if listenSocket ~= nil then
        listenSocket:close()
        listenSocket = nil
    end
end

DCS.setUserCallbacks(petrobrainLineOfSight)

logi("loaded")
