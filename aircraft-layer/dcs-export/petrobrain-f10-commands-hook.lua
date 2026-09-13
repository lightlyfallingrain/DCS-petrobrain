--[[
Aircraft Layer -- F10 radio-menu crew-command input Hook script
(`plans/f10-crew-commands/plan.md`).

Deploy: copy this file to `Saved Games\DCS\Scripts\Hooks\` on the Windows
box (see aircraft-layer/WORKFLOW.md's "Deploy the F10 commands Hook
script" section). This is the canonical, version-controlled copy; the
deployed copy is not tracked by this repo, same discipline as Export.lua
and petrobrain-overlay-hook.lua.

**This is Approach B** from `aircraft-layer/research/
2026-09-13-f10-radio-menu-command-input.md` (Findings 7-11): this Hook
script registers three fixed F10 -> Other -> Petrovich radio-menu items in
the mission-scripting state via `net.dostring_in("scripting", ...)` at
`onSimulationStart`, drains player selections back out by polling the same
bridge once a second, and forwards each drained token to the collector's
`F10CommandReceiver` (`aircraft-layer/src/collector/
f10_command_receiver.py`) over loopback UDP, port 7794. This is the
opposite data direction from `petrobrain-overlay-hook.lua` (which
*receives* UDP from the collector) -- kept as its own file rather than an
extension of that one, since the two scripts have opposite directions and
different lifecycle triggers (see the plan's Decision 2).

**REQUIRES an `autoexec.cfg` opt-in** the same as the research doc's probe
run 2 needed -- `net.dostring_in` is otherwise gated off. See
aircraft-layer/WORKFLOW.md for the exact `Config/autoexec.cfg` entries.
Without that opt-in, registration silently fails (`dostring_in` returns
`("Invalid state name", false)` for every state) and this script is
effectively a no-op -- watch `dcs.log` for `PetrobrainF10Commands` lines to
confirm.

Uses `"scripting"` as the bridge target state, never `"mission"`/
`a_do_script` -- the research doc's run 2 found `"mission"`'s
`a_do_script` never actually executed the registration code (its label
never appeared in the scripting-state counter table) and additionally went
invalid between missions, while `"scripting"` stayed valid and is where
`missionCommands`/`addCommand` were confirmed live and reachable.

**The `dostring_in` snippets below (`REGISTRATION_CODE`/`POLL_CODE`) are
fixed string literals, baked in at authoring time -- never built from
network input, mission data, or any other runtime value.** This keeps this
script from being a general-purpose remote-exec bridge even though the
underlying `net.dostring_in` mechanism can run arbitrary mission-scripting
code; only these two hard-coded strings are ever run.

**Idempotent registration.** `REGISTRATION_CODE` calls
`missionCommands.removeItem({"Petrovich"})` (in its own `pcall`, since the
menu item does not exist on the very first registration) before
`addSubMenu`/`addCommand`, so a second `onSimulationStart` firing within
one mission-scripting-state lifetime cannot duplicate the "Petrovich"
submenu -- per the plan's explicit "no duplicate menu entries" requirement.
`missionCommands.removeItem` (the non-`ForGroup` form) is standard DCS
Mission Scripting API per general convention (mirroring
`missionCommands.addCommand`/`addSubMenu`, both live-confirmed by the
research doc's run 2) but was **not itself independently live-probed this
session** -- wrapped in `pcall` as a defensive guard, and Stage 4's live
acceptance "mission-restart check" is exactly what confirms it actually
prevents duplication rather than merely not erroring.

**Poll gating.** The 1 Hz poll (`onSimulationFrame`, `DCS.getRealTime()`-
driven, mirroring `petrobrain-f10-probe-hook.lua`'s own timer pattern)
only runs between `onSimulationStart` and `onSimulationStop` -- the
research doc's run 2 found `onSimulationFrame` keeps firing between
missions (at mission load, before `onSimulationStart`), when
`dostring_in("scripting", ...)` is not yet valid. The poll timer is also
reset (`nextPollAt = 0`) at every `onSimulationStart`, so a new mission's
first poll fires promptly rather than waiting out whatever fraction of the
interval elapsed before the previous mission ended.

**Wire format (this script -> collector), UDP, one JSON object per
datagram** (matches `aircraft-layer/src/schema/f10_command.py`):
    {"command": "<token>"}
No timestamp field -- see that schema module's own docstring for why (no
cheap DCS sim-clock access from Hook state); the collector stamps
`received_wall_clock_s` itself on receipt.

Reuses DCS's own shipped JSON encoder (`Scripts\JSON.lua`) and LuaSocket's
`package.path`/`cpath` extension, both mirroring
`petrobrain-overlay-hook.lua`'s own exact approach (see that file's header
for the reasoning) -- one already-proven mechanism for both directions of
this project's Hook-state UDP traffic.
--]]

log.write("PetrobrainF10Commands", log.INFO, "Loading - Petrobrain F10 commands")

-- Mirrors petrobrain-overlay-hook.lua's own package.path/cpath extension
-- verbatim -- see that file's header for why this is the safe,
-- risk-reducing choice (harmless if redundant, load-bearing if not).
package.path = package.path
    .. ";.\\LuaSocket\\?.lua;"
    .. ".\\Scripts\\?.lua;"
    .. ".\\Scripts\\UI\\?.lua;"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll;"

local socket = require("socket")
local DCS = require("DCS")

-- Same JSON library petrobrain-overlay-hook.lua already uses -- see that
-- file's "Deviation 1" for why this is preferred over hand-rolling a
-- codec (DCS ships a real, general-purpose one at Scripts\JSON.lua).
local JSON = loadfile("Scripts\\JSON.lua")()

--: Loopback UDP port `collector.f10_command_receiver.DEFAULT_PORT` listens
--: on -- must match exactly. A fourth, distinct loopback port from
--: Export.lua's listener (7790), the overlay Hook's listener (7792), and
--: Export.lua's inbound command listener (7793).
local F10_COMMAND_PORT = 7794
local F10_COMMAND_HOST = "127.0.0.1"

--: How often the drained-selection queue is polled once a mission is
--: running. Matches petrobrain-f10-probe-hook.lua's own probe interval --
--: fast enough that a player does not notice the delay between selecting
--: an F10 item and CrewConsole acting on it, slow enough not to spam the
--: dostring_in bridge every frame.
local POLL_INTERVAL_S = 1.0

--: Registers (or re-registers, idempotently) the F10 -> Other ->
--: Petrovich submenu in the mission-scripting state. Each callback
--: appends its own fixed literal token to `PB_F10_QUEUE`, a global table
--: in that state -- never anything derived from network input. See the
--: file header for the removeItem-before-addSubMenu idempotency
--: reasoning.
local REGISTRATION_CODE = [[
PB_F10_QUEUE = PB_F10_QUEUE or {}
local function pbF10Enqueue(token)
    return function()
        table.insert(PB_F10_QUEUE, token)
    end
end
pcall(function() missionCommands.removeItem({"Petrovich"}) end)
local sub = missionCommands.addSubMenu("Petrovich", nil)
missionCommands.addCommand("Watch Nearest", sub, pbF10Enqueue("watch_nearest"))
missionCommands.addCommand("Scan Forward", sub, pbF10Enqueue("scan_forward"))
missionCommands.addCommand("Cancel Task", sub, pbF10Enqueue("cancel_task"))
return "registered"
]]

--: Drains `PB_F10_QUEUE` and returns its tokens as one comma-joined
--: string (`dostring_in` can only return simple values across the
--: Hook/mission-scripting boundary, per the research doc's own probe
--: pattern) -- empty string if nothing is pending.
local POLL_CODE = [[
local queue = PB_F10_QUEUE or {}
local out = {}
for i = 1, #queue do
    out[i] = queue[i]
end
PB_F10_QUEUE = {}
return table.concat(out, ",")
]]

local petrobrainF10 = {}

local simulationRunning = false
local nextPollAt = 0
local sendSocket = nil

local function logi(message)
    log.write("PetrobrainF10Commands", log.INFO, message)
end

-- Mirrors petrobrain-f10-probe-hook.lua's own `dostring` wrapper: `ok` is
-- true only if the bridge call itself did not raise AND dostring_in's own
-- success flag was not explicitly `false`.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

local function registerF10Menu()
    local ok, result = dostring("scripting", REGISTRATION_CODE)
    logi("registration -> ok=" .. tostring(ok) .. " result=" .. tostring(result))
end

local function sendToken(token)
    if sendSocket == nil then
        sendSocket = socket.udp()
    end
    local payload = JSON:encode({ command = token })
    local ok, err = sendSocket:sendto(payload, F10_COMMAND_HOST, F10_COMMAND_PORT)
    if not ok then
        logi("send failed for token=" .. tostring(token) .. ": " .. tostring(err))
    end
end

local function pollAndForward()
    local ok, result = dostring("scripting", POLL_CODE)
    if not ok or type(result) ~= "string" or result == "" then
        return
    end
    for token in string.gmatch(result, "[^,]+") do
        sendToken(token)
    end
end

function petrobrainF10.onSimulationStart()
    logi("onSimulationStart")
    simulationRunning = true
    nextPollAt = 0
    local ok, err = pcall(registerF10Menu)
    if not ok then
        logi("registration failed: " .. tostring(err))
    end
end

function petrobrainF10.onSimulationFrame()
    if not simulationRunning then
        return
    end
    local now = DCS.getRealTime()
    if now < nextPollAt then
        return
    end
    nextPollAt = now + POLL_INTERVAL_S
    local ok, err = pcall(pollAndForward)
    if not ok then
        logi("poll failed: " .. tostring(err))
    end
end

function petrobrainF10.onSimulationStop()
    logi("onSimulationStop")
    simulationRunning = false
end

DCS.setUserCallbacks(petrobrainF10)

logi("loaded")
