-- petrobrain-f10-probe-hook.lua -- THROWAWAY recon probe, not pipeline code.
--
-- Question (aircraft-layer/research/2026-09-13-f10-radio-menu-command-input.md): can a
-- Hook-state script put its own item into the F10 radio menu, and learn when the player
-- selects it, without per-mission authoring?
--
-- Run 1 (no autoexec.cfg) showed: RadioCommandDialogsPanel and a_do_script unreachable from
-- Hooks; net.dostring_in("mission", ...) -> ("Invalid state name", false). See Finding 10.
--
-- Run 2 (this version) needs Saved Games\DCS\Config\autoexec.cfg:
--     net.allow_unsafe_api = { "userhooks", "gui" }
--     net.allow_dostring_in = { "mission", "scripting", "server", "export", "config", "gui" }
-- It asks, per candidate state name:
--   S1  does net.dostring_in accept the state at all?
--   S2  is missionCommands / a_do_script / env visible there?
--   S3  register an F10 "Other" item from each state that has missionCommands (directly) or
--       a_do_script (bridged into the mission scripting state); callback bumps a counter.
--   S4  poll that counter back out once a second, logging changes -- the inbound path.
--   S5  log onRadioCommand payloads (does selecting a mission item fire it?).
--
-- Deploy: copy to Saved Games\DCS\Scripts\Hooks\. Remove after the probe run.
-- Output: dcs.log lines tagged PB-F10-PROBE.

local DCS = require("DCS")

local TAG = "PB-F10-PROBE"
local STATES = { "mission", "scripting", "server", "export", "config", "gui" }
local POLL_INTERVAL_S = 1.0

local probe = {}
local registered = {} -- list of { state = name, how = "direct" | "a_do_script" }
local lastCounts = {}
local nextPollAt = 0

local function logi(msg)
    log.write(TAG, log.INFO, msg)
end

local function describe(value, depth)
    depth = depth or 0
    if type(value) ~= "table" or depth >= 2 then
        return type(value) .. ":" .. tostring(value)
    end
    local parts = {}
    local n = 0
    for k, v in pairs(value) do
        n = n + 1
        if n > 20 then
            table.insert(parts, "...")
            break
        end
        table.insert(parts, tostring(k) .. "=" .. describe(v, depth + 1))
    end
    return "{" .. table.concat(parts, ", ") .. "}"
end

-- Returns (ok, result): ok is dostring_in's own success flag, false on a raised error too.
local function dostring(state, code)
    local callOk, result, success = pcall(net.dostring_in, state, code)
    if not callOk then
        return false, "raised: " .. tostring(result)
    end
    return success ~= false, result
end

-- Code run in the mission scripting state: register one item whose callback bumps a global.
local function registerCode(label)
    return string.format(
        [==[
PB_F10_COUNTS = PB_F10_COUNTS or {}
PB_F10_COUNTS[%q] = 0
missionCommands.addCommand(%q, nil, function()
    PB_F10_COUNTS[%q] = PB_F10_COUNTS[%q] + 1
    if env then env.info("PB-F10-PROBE callback FIRED " .. %q) end
end)
return "registered"
]==],
        label, label, label, label, label
    )
end

local function probeStates()
    for _, state in ipairs(STATES) do
        local ok, result = dostring(state, "return 'pong'")
        logi("S1 " .. state .. " ping -> ok=" .. tostring(ok) .. " result=" .. describe(result))
        if ok then
            local _, visible = dostring(
                state,
                "return 'missionCommands=' .. type(missionCommands) .. ' a_do_script=' .. type(a_do_script)"
                    .. " .. ' env=' .. type(env) .. ' trigger=' .. type(trigger)"
            )
            logi("S2 " .. state .. " " .. tostring(visible))

            if type(visible) == "string" and visible:find("missionCommands=function")
                or type(visible) == "string" and visible:find("missionCommands=table")
            then
                local rOk, r = dostring(state, registerCode("PB probe: " .. state .. " direct"))
                logi("S3 " .. state .. " direct register -> ok=" .. tostring(rOk) .. " result=" .. describe(r))
                if rOk then
                    table.insert(registered, { state = state, how = "direct" })
                end
            end

            if type(visible) == "string" and visible:find("a_do_script=function") then
                local code = "return a_do_script(" .. string.format("%q", registerCode("PB probe: " .. state .. " via a_do_script")) .. ")"
                local rOk, r = dostring(state, code)
                logi("S3 " .. state .. " a_do_script register -> ok=" .. tostring(rOk) .. " result=" .. describe(r))
                if rOk then
                    table.insert(registered, { state = state, how = "a_do_script" })
                end
            end
        end
    end
end

local function pollCounts()
    for _, reg in ipairs(registered) do
        local state, how = reg.state, reg.how
        local code = "local out = {} for k, v in pairs(PB_F10_COUNTS or {}) do "
            .. "out[#out + 1] = k .. '=' .. v end return table.concat(out, '; ')"
        if how == "a_do_script" then
            code = "return a_do_script(" .. string.format("%q", code) .. ")"
        end
        local ok, count = dostring(state, code)
        local key = state .. "/" .. how
        if count ~= lastCounts[key] then
            logi("S4 " .. key .. " count -> ok=" .. tostring(ok) .. " value=" .. describe(count))
            lastCounts[key] = count
        end
    end
end

-- Callbacks ------------------------------------------------------------------------------
function probe.onSimulationStart()
    logi("onSimulationStart; net.dostring_in=" .. type(net.dostring_in))
    registered = {}
    lastCounts = {}
    nextPollAt = 0
    probeStates()
end

function probe.onSimulationFrame()
    local now = DCS.getRealTime()
    if now < nextPollAt then
        return
    end
    nextPollAt = now + POLL_INTERVAL_S
    pollCounts()
end

function probe.onRadioCommand(command_message)
    logi("S5 onRadioCommand msg=" .. describe(command_message))
end

function probe.onSimulationStop()
    logi("onSimulationStop")
end

DCS.setUserCallbacks(probe)
logi("loaded (run 2: state-name sweep)")
