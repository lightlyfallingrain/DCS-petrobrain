--[[
PETROVICH WHEEL-COMMAND + SIGHT-AUTHORITY PROBE -- not the production script.

Self-contained; does NOT need the collector. Appends to
Logs\aircraft_layer_probe_wheel.log. Deploy by copying to
`Saved Games\DCS\Scripts\Export.lua`.

WHERE WE ARE (see aircraft-layer/research/2026-09-11-*.md)
  * The 9K113 can be pointed from Export.lua:
        GetDevice(7):SetCommand(3061, azimuth_deg / 60.0)
    and read back from arg 874 (azimuth_deg = arg * 136.36).
  * Petrovich's detections are readable: list_indication(6) ->
    middle_list_text carries the classified type ("T-90A", "BTR-60"),
    gated on NABL (observation mode), NOT on weapon selection.
  * The AI wheel's live options are readable: list_indication(10) shows
    SRCH BRST / SRCH FWD / SRCH PILOT LOS / SRCH 9K113 LOS / HOLD FIRE /
    SELECT TGT / NEXT-PREV TGT / OBSERV. ON-OFF, and Petrovich's own state
    SEARCHING / TRACKING / WAITING.
  * The whole search -> slew -> detect -> report loop is confirmed working when
    the PILOT drives the wheel: Petrovich slews the sight himself (args
    874/876 track HIS gaze) and the contact appears in indicator 6.

THE TWO REMAINING QUESTIONS, which this probe answers.

PART A -- can WE drive the wheel?
  The wheel is device 30 with five momentary commands (ShowMenu 3001, Right
  3002, Left 3003, Up 3004, Down 3005), declared press/release
  (value_down = 1, value_up = 0) and having no clickable element -- so
  SetCommand is the likely verb, as it was for the sight axes.
  We do NOT know the selection model: whether a direction press selects that
  option outright, or moves a cursor that then needs a commit. So this part
  does not guess. It presses one key at a time and DUMPS THE WHEEL TEXT AFTER
  EACH, letting the interaction model be read off the log. Both verbs are
  tried, because getting this wrong cost two flights on the sight axes.

PART B -- does our sight command survive while Petrovich is searching?
  This is the risk the obvious design walks into. `av9K113::getHelperIsOn()`
  exists, so the module explicitly models "the helper is driving the sight".
  If Petrovich overrides SetCommand(3061,...) whenever he searches, then
  "point the sight, then trigger SRCH 9K113 LOS" does NOT compose, and the
  scan_area design has to be rethought. Part B commands the sight to a known
  position every few seconds and logs whether it HOLDS, continuously, so the
  pilot can trigger searches manually and the log shows the difference.

HOW TO FLY IT
  1. Get level, sight powered, NABL on. 20s grace before anything runs.
  2. Leave the controls alone during PART A (~60s) -- it drives the wheel.
  3. During PART B, deliberately trigger Petrovich searches from the wheel
     yourself (SRCH FWD, SRCH PILOT LOS) and let him run. The log records
     whether our commanded sight position holds or gets overridden while he
     is active. Targets in view help.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_wheel.log"

local log_file = nil
local function log(msg)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then return end
        log_file = f
    end
    log_file:write(os.date("%H:%M:%S") .. " " .. tostring(msg) .. "\n")
    log_file:flush()
end

local function try(label, fn, ...)
    local ok, a = pcall(fn, ...)
    if not ok then
        log(string.format("  %-26s ERROR: %s", label, tostring(a)))
        return nil
    end
    return a
end

local function safe_index(obj, key)
    local ok, v = pcall(function() return obj[key] end)
    if not ok then return nil end
    return v
end

-- ---------------------------------------------------------------- constants
local DEV_MAINPANEL = 0
local DEV_I9K113    = 7
local DEV_HELPER_AI = 30

local HAI = { ShowMenu = 3001, Right = 3002, Left = 3003, Up = 3004, Down = 3005 }
local K113_AI_AZ = 3061
local ARG_AZ, ARG_EL, ARG_NABL = 874, 876, 886

local IND_HELPERAI, IND_WHEEL = 6, 10

local START_DELAY = 20.0

local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function send(dev_id, method, cmd, value)
    local dev = try("GetDevice", GetDevice, dev_id)
    if dev == nil then return false end
    local fn = safe_index(dev, method)
    if type(fn) ~= "function" then return false end
    try(method, fn, dev, cmd, value)
    return true
end

-- Compact one-line view of the wheel: slot = text. Far easier to diff across
-- key presses than the raw indented tree.
local SLOTS = {
    "wheel_text_center", "wheel_text_up", "wheel_text_right", "wheel_text_down",
    "wheel_text_left", "wheel_text_far_up", "wheel_text_far_right",
    "wheel_text_far_down", "wheel_text_far_left",
}
local SHORT = {
    wheel_text_center = "C", wheel_text_up = "U", wheel_text_right = "R",
    wheel_text_down = "D", wheel_text_left = "L", wheel_text_far_up = "FU",
    wheel_text_far_right = "FR", wheel_text_far_down = "FD",
    wheel_text_far_left = "FL",
}

local function wheel_summary()
    local s = tostring(try("list_indication", list_indication, IND_WHEEL))
    if #s < 70 then return "<wheel closed/empty>" end
    local vals, cur = {}, nil
    for line in s:gmatch("[^\n]*") do
        local name = line:match("^(wheel_text_[a-z_]+)%s*$")
        if name then
            cur = name
            vals[cur] = vals[cur] or ""
        elseif cur then
            if line:match("^%-%-%-") or line:match("^}") then
                cur = nil
            elseif line:match("%S") then
                vals[cur] = (vals[cur] == "" and line or (vals[cur] .. "/" .. line))
            end
        end
    end
    local out = {}
    for _, k in ipairs(SLOTS) do
        local v = vals[k]
        if v and v ~= "" then out[#out + 1] = SHORT[k] .. "=" .. v end
    end
    if #out == 0 then return "<wheel present, all slots empty>" end
    return table.concat(out, "  ")
end

local function petrovich_contacts()
    local s = tostring(try("list_indication", list_indication, IND_HELPERAI))
    local names = {}
    local cur = nil
    for line in s:gmatch("[^\n]*") do
        local nm = line:match("^([a-z_]*list_text)%s*$")
        if nm then
            cur = nm
        elseif cur then
            if line:match("%S") and not line:match("^%-%-%-") and not line:match("^}")
               and not line:match("^children") then
                names[#names + 1] = cur .. "=" .. line
            end
            cur = nil
        end
    end
    if #names == 0 then return "<no contacts>" end
    return table.concat(names, ", ")
end

local function state_line()
    return string.format("az=%s el=%s NABL=%s | %s",
        tostring(read_arg(ARG_AZ)), tostring(read_arg(ARG_EL)),
        tostring(read_arg(ARG_NABL)), petrovich_contacts())
end

-- ============================================================= PART A
-- Press one wheel key, then read the wheel back. The sequence is deliberately
-- slow: press, hold, release, settle, read -- so each step's effect is
-- attributable to that step.
local A_SEQ = {
    {"ShowMenu", HAI.ShowMenu},
    {"Down",     HAI.Down},
    {"Down",     HAI.Down},
    {"Up",       HAI.Up},
    {"Left",     HAI.Left},
    {"Right",    HAI.Right},
    {"ShowMenu", HAI.ShowMenu},
}

local partA = {
    verb_idx = 1,
    verbs = {"SetCommand", "performClickableAction"},
    step = 0,
    phase = "begin",
    t_phase = 0,
    saw_change = false,
    last_wheel = nil,
}

local PRESS_HOLD = 0.20
local SETTLE     = 0.60

local function part_a(t)
    local verb = partA.verbs[partA.verb_idx]

    if partA.phase == "begin" then
        log("")
        log("=========================================================")
        log(string.format("PART A -- driving the wheel with %s", verb))
        log("=========================================================")
        log("  wheel before: " .. wheel_summary())
        partA.last_wheel = wheel_summary()
        partA.step = 0
        partA.saw_change = false
        partA.phase = "next"
        partA.t_phase = t

    elseif partA.phase == "next" then
        if (t - partA.t_phase) < 0.3 then return end
        partA.step = partA.step + 1
        local s = A_SEQ[partA.step]
        if s == nil then
            log(string.format("  --> %s: wheel %s change across the sequence",
                              verb, partA.saw_change and "DID" or "did NOT"))
            if partA.saw_change then
                partA.phase = "done"
            else
                partA.verb_idx = partA.verb_idx + 1
                if partA.verbs[partA.verb_idx] == nil then
                    log("  --> neither verb drove the wheel.")
                    partA.phase = "done"
                else
                    partA.phase = "begin"
                end
            end
            return
        end
        send(DEV_HELPER_AI, verb, s[2], 1)      -- press
        partA.phase = "holding"
        partA.t_phase = t

    elseif partA.phase == "holding" then
        if (t - partA.t_phase) > PRESS_HOLD then
            local s = A_SEQ[partA.step]
            send(DEV_HELPER_AI, verb, s[2], 0)  -- release
            partA.phase = "settling"
            partA.t_phase = t
        end

    elseif partA.phase == "settling" then
        if (t - partA.t_phase) > SETTLE then
            local s = A_SEQ[partA.step]
            local w = wheel_summary()
            local changed = (w ~= partA.last_wheel)
            if changed then partA.saw_change = true end
            log(string.format("  [%d] press %-9s (cmd %d) -> %s",
                              partA.step, s[1], s[2], changed and "CHANGED" or "no change"))
            log("        wheel: " .. w)
            log("        " .. state_line())
            partA.last_wheel = w
            partA.phase = "next"
            partA.t_phase = t
        end
    end
    return partA.phase == "done"
end

-- ============================================================= PART B
-- Command the sight to a known azimuth and see whether it HOLDS. Run
-- continuously so the pilot can trigger Petrovich searches underneath it.
local TARGET_VAL = 0.5            -- 0.5 * 60 deg = +30 deg, arg should be 0.22
local EXPECT_ARG = TARGET_VAL * 0.44

local partB = { phase = "idle", t_phase = 0, cycle = 0, samples = {} }

local function part_b(t)
    if partB.phase == "idle" then
        if (t - partB.t_phase) < 4.0 then return end
        partB.cycle = partB.cycle + 1
        partB.samples = {}
        log("")
        log(string.format("--- PART B cycle %d: commanding sight to %+0.2f (expect arg %+0.3f) ---",
                          partB.cycle, TARGET_VAL, EXPECT_ARG))
        log("    before: " .. state_line())
        log("    wheel : " .. wheel_summary())
        partB.phase = "holding"
        partB.t_phase = t

    elseif partB.phase == "holding" then
        send(DEV_I9K113, "SetCommand", K113_AI_AZ, TARGET_VAL)
        local v = read_arg(ARG_AZ)
        if type(v) == "number" then
            partB.samples[#partB.samples + 1] =
                string.format("%.1f:%+.3f", t - partB.t_phase, v)
        end
        if (t - partB.t_phase) > 6.0 then
            local v2 = read_arg(ARG_AZ)
            local held = (type(v2) == "number" and math.abs(v2 - EXPECT_ARG) < 0.02)
            log(string.format("    after 6s: arg=%s  ==> %s",
                tostring(v2),
                held and "HELD at the commanded position"
                      or "NOT holding -- something else is driving the sight"))
            local n, line = #partB.samples, {}
            local st = math.max(1, math.floor(n / 12))
            for i = 1, n, st do line[#line + 1] = partB.samples[i] end
            log("      traj: " .. table.concat(line, " "))
            log("    after : " .. state_line())
            partB.phase = "idle"
            partB.t_phase = t
        end
    end
end

-- ============================================================= driver
local started, t0 = false, nil
local part_a_done = false
local last_wheel_seen, last_petro_seen = nil, nil

function LuaExportStart()
    log("")
    log("#########################################################")
    log("WHEEL-COMMAND + SIGHT-AUTHORITY PROBE")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("wheel probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log("  waiting " .. START_DELAY .. "s for the pilot to settle")
        return
    end
    if (t - t0) < START_DELAY then return end

    -- always-on change watch, so nothing is missed during either part
    local w = wheel_summary()
    if w ~= last_wheel_seen then
        last_wheel_seen = w
        log(string.format("  ~ t=%.1f wheel: %s", t, w))
    end
    local p = petrovich_contacts()
    if p ~= last_petro_seen then
        last_petro_seen = p
        log(string.format("  ~ t=%.1f PETROVICH: %s   (az=%s)",
                          t, p, tostring(read_arg(ARG_AZ))))
    end

    if not part_a_done then
        if part_a(t) then
            part_a_done = true
            partB.t_phase = t
            log("")
            log("=========================================================")
            log("PART B -- sight authority while Petrovich is active.")
            log("  NOW: trigger searches from the wheel yourself (SRCH FWD,")
            log("  SRCH PILOT LOS) and let Petrovich run. Each cycle below")
            log("  commands the sight to +30 deg and reports whether it held.")
            log("=========================================================")
        end
    else
        part_b(t)
    end
end
