--[[
SCAN-AT-BEARING PROBE -- not the production export script.

Self-contained. Appends to Logs\aircraft_layer_probe_scan.log.
Deploy to `Saved Games\DCS\Scripts\Export.lua`.

ESTABLISHED SO FAR (aircraft-layer/research/2026-09-11-*.md):
  * Sight pointing   : GetDevice(7):SetCommand(3061, deg/60)      [SetCommand]
  * Sight readback   : get_argument_value(874) * 136.36 = degrees
  * Wheel driving    : GetDevice(30):performClickableAction(cmd, 1/0)
                       -- note the OPPOSITE verb to the sight axes
  * A direction press EXECUTES that slot; no separate commit step.
  * Our sight command HELD 9/9 even while Petrovich was SEARCHING/TRACKING,
    and he resumes control as soon as we stop asserting.
  * Detections read from list_indication(6): middle_list_text = "T-90A".
  * Petrovich's state reads from list_indication(10) down slot:
    WAITING / SEARCHING / TRACKING.

THE TWO THINGS THIS PROBE SETTLES.

PART A -- how do you reach the FAR slots?
  Each direction has a near and a far slot but there are only four direction
  keys. No far slot ever fired last run, and every press was held 0.20s.
  HelperAI.lua:13 defines `long_press_time = 0.5`, so the model is almost
  certainly near = short press, far = press held > 0.5s. This matters because
  SRCH 9K113 LOS sits in the FAR DOWN slot. Part A presses each direction
  short then long, dumping the wheel after each, and reports the mapping.

PART B -- does pinning the sight SUPPRESS detection?
  The important open question, and the one last flight could not answer
  because no targets were ever in view. It alternates two conditions with
  targets present:
      PINNED : we hold the sight at SCAN_BEARING_DEG and Petrovich searches
      FREE   : we release the sight entirely and Petrovich searches
  and logs the contacts seen in each. If PINNED yields contacts, taking the
  sight does not blind him and scan_area works as designed. If PINNED is
  reliably empty while FREE finds things, then holding the sight suppresses
  detection and the design must instead ask HIM to look, not force the optics.

HOW TO FLY IT
  1. Level flight, sight powered, targets (a GROUP, ideally) ahead and within
     about +/-45 deg. 20s grace before anything starts.
  2. Hands off during PART A (~40s) -- it drives the wheel.
  3. During PART B just keep the targets in view and fly steady. The probe
     handles the sight and the search commands. Do not touch the wheel or the
     sight; that is what invalidates the comparison.
  4. If the targets are not straight ahead, set SCAN_BEARING_DEG below.
]]

-- Where to point the sight during PINNED phases, degrees from the nose.
-- Positive is right. Valid range -60..+60.
local SCAN_BEARING_DEG = 0.0

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_scan.log"

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
    if not ok then log(string.format("  %-22s ERROR: %s", label, tostring(a))) return nil end
    return a
end

local function safe_index(obj, key)
    local ok, v = pcall(function() return obj[key] end)
    if not ok then return nil end
    return v
end

-- ---------------------------------------------------------------- constants
local DEV_MAINPANEL, DEV_I9K113, DEV_HELPER_AI = 0, 7, 30
local HAI = { ShowMenu = 3001, Right = 3002, Left = 3003, Up = 3004, Down = 3005 }
local K113_AI_AZ = 3061
local ARG_AZ, ARG_NABL = 874, 886
local IND_HELPERAI, IND_WHEEL = 6, 10

local START_DELAY = 20.0
local SHORT_PRESS, LONG_PRESS = 0.20, 0.80   -- long_press_time is 0.5

local function read_arg(a)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, a)
end

local function dev_call(dev_id, method, cmd, value)
    local dev = try("GetDevice", GetDevice, dev_id)
    if dev == nil then return false end
    local fn = safe_index(dev, method)
    if type(fn) ~= "function" then return false end
    try(method, fn, dev, cmd, value)
    return true
end

local function wheel_press_begin(cmd) dev_call(DEV_HELPER_AI, "performClickableAction", cmd, 1) end
local function wheel_press_end(cmd)   dev_call(DEV_HELPER_AI, "performClickableAction", cmd, 0) end
local function point_sight(deg)       dev_call(DEV_I9K113, "SetCommand", K113_AI_AZ, deg / 60.0) end

-- ------------------------------------------------------------- readback
local SLOTS = {"wheel_text_center","wheel_text_up","wheel_text_right","wheel_text_down",
               "wheel_text_left","wheel_text_far_up","wheel_text_far_right",
               "wheel_text_far_down","wheel_text_far_left"}
local SHORT = {wheel_text_center="C",wheel_text_up="U",wheel_text_right="R",
               wheel_text_down="D",wheel_text_left="L",wheel_text_far_up="FU",
               wheel_text_far_right="FR",wheel_text_far_down="FD",wheel_text_far_left="FL"}

local function parse_slots(s)
    local vals, cur = {}, nil
    for line in s:gmatch("[^\n]*") do
        local name = line:match("^(wheel_text_[a-z_]+)%s*$")
        if name then
            cur = name ; vals[cur] = vals[cur] or ""
        elseif cur then
            if line:match("^%-%-%-") or line:match("^}") then cur = nil
            elseif line:match("%S") then
                vals[cur] = (vals[cur] == "" and line or (vals[cur] .. "/" .. line))
            end
        end
    end
    return vals
end

local function wheel_summary()
    local s = tostring(try("list_indication", list_indication, IND_WHEEL))
    if #s < 70 then return "<closed>", {} end
    local vals = parse_slots(s)
    local out = {}
    for _, k in ipairs(SLOTS) do
        if vals[k] and vals[k] ~= "" then out[#out+1] = SHORT[k] .. "=" .. vals[k] end
    end
    return (#out > 0 and table.concat(out, "  ") or "<open, empty>"), vals
end

-- Petrovich state lives in the down slot (WAITING/SEARCHING/TRACKING).
local function petrovich_state()
    local _, vals = wheel_summary()
    return vals["wheel_text_down"] or "?"
end

local function contacts()
    local s = tostring(try("list_indication", list_indication, IND_HELPERAI))
    local names, cur = {}, nil
    for line in s:gmatch("[^\n]*") do
        local nm = line:match("^([a-z_]*list_text)%s*$")
        if nm then cur = nm
        elseif cur then
            if line:match("%S") and not line:match("^%-%-%-") and not line:match("^}")
               and not line:match("^children") then
                names[#names+1] = cur .. "=" .. line
            end
            cur = nil
        end
    end
    if #names == 0 then return nil end
    return table.concat(names, ", ")
end

local function az_deg()
    local v = read_arg(ARG_AZ)
    if type(v) ~= "number" then return "?" end
    return string.format("%+.1f", v * 136.36)
end

-- ============================================================= PART A
-- Short press then long press on each direction, reading the wheel after
-- each, to establish the near/far mapping.
local A_DIRS = {{"Down", HAI.Down}, {"Up", HAI.Up}, {"Left", HAI.Left}, {"Right", HAI.Right}}
local A = {phase="open", t=0, i=0, long=false, before=nil}

local function part_a(t)
    if A.phase == "open" then
        log("")
        log("========== PART A: near vs far slot mapping ==========")
        wheel_press_begin(HAI.ShowMenu)
        A.phase = "open_rel" ; A.t = t
    elseif A.phase == "open_rel" then
        if t - A.t > SHORT_PRESS then
            wheel_press_end(HAI.ShowMenu) ; A.phase = "open_settle" ; A.t = t
        end
    elseif A.phase == "open_settle" then
        if t - A.t > 0.8 then
            log("  wheel open: " .. (wheel_summary()))
            A.phase = "next" ; A.t = t
        end
    elseif A.phase == "next" then
        if t - A.t < 1.0 then return end
        if not A.long then A.i = A.i + 1 end
        local d = A_DIRS[A.i]
        if d == nil then
            log("  --- PART A complete ---")
            return true
        end
        A.before = wheel_summary()
        wheel_press_begin(d[2])
        A.phase = "press" ; A.t = t
    elseif A.phase == "press" then
        local hold = A.long and LONG_PRESS or SHORT_PRESS
        if t - A.t > hold then
            wheel_press_end(A_DIRS[A.i][2])
            A.phase = "settle" ; A.t = t
        end
    elseif A.phase == "settle" then
        if t - A.t > 1.0 then
            local w = wheel_summary()
            log(string.format("  %-5s %s press -> %s",
                A_DIRS[A.i][1], A.long and "LONG " or "short",
                (w ~= A.before) and "CHANGED" or "no change"))
            log("      wheel: " .. w)
            log(string.format("      state=%s  az=%s  contacts=%s",
                petrovich_state(), az_deg(), tostring(contacts())))
            A.long = not A.long          -- short, then long, then next direction
            A.phase = "next" ; A.t = t
        end
    end
    return false
end

-- ============================================================= PART B
-- Alternate PINNED / FREE with targets in view and compare detections.
local PHASE_S = 20.0
local B = {phase="start", t=0, round=0, pinned=true, seen={}, n=0}

local function b_observe(t, label)
    local c = contacts()
    if c ~= nil and B.seen[c] == nil then
        B.seen[c] = true
        B.n = B.n + 1
        log(string.format("    [%s] t=%.0f  CONTACT: %s   (state=%s az=%s)",
                          label, t - B.t, c, petrovich_state(), az_deg()))
    end
end

local function b_start_search(label)
    -- ask Petrovich to search: the near-UP slot is SRCH PILOT LOS, which is
    -- reachable with a short press and is confirmed to start a search.
    log(string.format("    [%s] issuing search (Up / SRCH PILOT LOS)", label))
    wheel_press_begin(HAI.Up)
    return true
end

local function part_b(t)
    if B.phase == "start" then
        B.round = B.round + 1
        B.pinned = not B.pinned
        B.seen = {} ; B.n = 0
        local label = B.pinned and "PINNED" or "FREE"
        log("")
        log(string.format("========== PART B round %d: %s ==========", B.round, label))
        log(string.format("    wheel: %s", (wheel_summary())))
        log(string.format("    state=%s az=%s NABL=%s",
                          petrovich_state(), az_deg(), tostring(read_arg(ARG_NABL))))
        b_start_search(label)
        B.phase = "search_rel" ; B.t = t
    elseif B.phase == "search_rel" then
        if t - B.t > SHORT_PRESS then
            wheel_press_end(HAI.Up)
            B.phase = "running" ; B.t = t
        end
    elseif B.phase == "running" then
        local label = B.pinned and "PINNED" or "FREE"
        if B.pinned then point_sight(SCAN_BEARING_DEG) end
        b_observe(t, label)
        if t - B.t > PHASE_S then
            log(string.format("    ==> %s round %d: %d distinct contact readings, final state=%s, az=%s",
                              label, B.round, B.n, petrovich_state(), az_deg()))
            B.phase = "gap" ; B.t = t
        end
    elseif B.phase == "gap" then
        if t - B.t > 5.0 then B.phase = "start" ; B.t = t end
    end
end

-- ============================================================= driver
local started, t0, a_done = false, nil, false
local last_w, last_c = nil, nil

function LuaExportStart()
    log("")
    log("#########################################################")
    log(string.format("SCAN-AT-BEARING PROBE   (scan bearing %+0.1f deg)", SCAN_BEARING_DEG))
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("scan probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then t0 = t ; log("  " .. START_DELAY .. "s grace, get level with targets ahead") return end
    if t - t0 < START_DELAY then return end

    local w = wheel_summary()
    if w ~= last_w then last_w = w ; log(string.format("  ~ t=%.0f wheel: %s", t, w)) end
    local c = contacts()
    if c ~= last_c then
        last_c = c
        log(string.format("  ~ t=%.0f contacts: %s   (state=%s az=%s)",
                          t, tostring(c), petrovich_state(), az_deg()))
    end

    if not a_done then
        if part_a(t) then
            a_done = true ; B.t = t
            log("")
            log("=========================================================")
            log("PART B -- keep the targets in view and fly steady.")
            log("  Alternating PINNED (we hold the sight at the scan bearing)")
            log("  and FREE (Petrovich has the sight). Do NOT touch the wheel")
            log("  or the sight from here on -- that is what invalidates it.")
            log("=========================================================")
        end
    else
        part_b(t)
    end
end
