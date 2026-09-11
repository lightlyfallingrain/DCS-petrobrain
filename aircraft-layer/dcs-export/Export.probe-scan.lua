--[[
SCAN-AT-BEARING PROBE v2 -- not the production export script.
Log: Logs\aircraft_layer_probe_scan.log   Deploy to Saved Games\DCS\Scripts\Export.lua

WHAT CHANGED FROM v1, AND WHY
  v1 produced nothing usable because of my design fault, not DCS's: Part A's
  long-Left press opened the countermeasures submenu, the probe never navigated
  back, and Part B then pressed "Up to search" on the CM page -- which is
  CM INTERVAL. No search ever ran.

  The wheel is a STATEFUL, MULTI-PAGE menu. Pressing a direction by position is
  unsafe. But we can READ the slot labels, so v2 selects every press BY LABEL
  and verifies it afterwards. That is the whole advantage of this channel and
  v1 threw it away.

CONFIRMED MECHANICS (see aircraft-layer/research/2026-09-11-*.md)
  sight point    : GetDevice(7):SetCommand(3061, deg/60)          [SetCommand]
  sight readback : get_argument_value(874) * 136.36 = degrees
  wheel press    : GetDevice(30):performClickableAction(cmd, 1) .. (cmd, 0)
                   [performClickableAction -- the OPPOSITE verb to the sight]
  near slot      : short press (< 0.5s)
  far slot       : LONG press (> 0.5s)   -- HelperAI.lua long_press_time = 0.5
  a press EXECUTES that slot; there is no separate commit
  detections     : list_indication(6), rows upper_upper / upper (registered as
                   "LeftCenter") / middle / lower / lower_lower
  his state      : list_indication(10) down slot -- WAITING/SEARCHING/TRACKING

THE QUESTION THIS ANSWERS
  Does holding the sight ourselves SUPPRESS Petrovich's detection?
    PINNED : we hold the sight at SCAN_BEARING_DEG and ask him to search along
             the sight line (SRCH 9K113 LOS) -- this is literally the proposed
             scan_area design
    FREE   : we release the sight and let him run his own search (SRCH BRST)
  If PINNED finds contacts, scan_area works. If PINNED is reliably empty while
  FREE finds things, taking the sight blinds him and the design must ask him to
  look rather than force the optics.

HOW TO FLY IT
  1. Level, sight powered, a GROUP of targets ahead within about +/-45 deg.
  2. 20s grace, then hands off entirely -- do not touch the wheel or the sight.
  3. Set SCAN_BEARING_DEG if the targets are not off the nose.
  The probe restores HOLD FIRE at the end; v1 left Petrovich on FREE FIRE.
]]

local SCAN_BEARING_DEG = 0.0     -- where to pin the sight; + is right, -60..60

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_scan.log"
local log_file = nil
local function log(m)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then return end
        log_file = f
    end
    log_file:write(os.date("%H:%M:%S") .. " " .. tostring(m) .. "\n")
    log_file:flush()
end
local function try(l, fn, ...)
    local ok, a = pcall(fn, ...)
    if not ok then log("  ERROR " .. l .. ": " .. tostring(a)) return nil end
    return a
end
local function safe_index(o, k)
    local ok, v = pcall(function() return o[k] end)
    if not ok then return nil end
    return v
end

local DEV_MAIN, DEV_SIGHT, DEV_HAI = 0, 7, 30
local CMD = { ShowMenu = 3001, Right = 3002, Left = 3003, Up = 3004, Down = 3005 }
local SIGHT_AI_AZ, ARG_AZ = 3061, 874
local IND_HAI, IND_WHEEL = 6, 10
local SHORT_HOLD, LONG_HOLD = 0.20, 0.80
local START_DELAY = 20.0

local function read_arg(a)
    local mp = try("GetDevice0", GetDevice, DEV_MAIN)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_arg", fn, mp, a)
end
local function dev(id, method, c, v)
    local d = try("GetDevice", GetDevice, id)
    if d == nil then return end
    local fn = safe_index(d, method)
    if type(fn) == "function" then try(method, fn, d, c, v) end
end
local function point_sight(deg) dev(DEV_SIGHT, "SetCommand", SIGHT_AI_AZ, deg / 60.0) end
local function az_deg()
    local v = read_arg(ARG_AZ)
    if type(v) ~= "number" then return "?" end
    return string.format("%+.1f", v * 136.36)
end

-- --------------------------------------------------------- wheel readback
-- slot name -> {direction command, hold time}. Near slots are a short press of
-- that direction, far slots a long press of the same key.
local SLOT_KEY = {
    wheel_text_up        = {CMD.Up,    SHORT_HOLD},
    wheel_text_down      = {CMD.Down,  SHORT_HOLD},
    wheel_text_left      = {CMD.Left,  SHORT_HOLD},
    wheel_text_right     = {CMD.Right, SHORT_HOLD},
    wheel_text_far_up    = {CMD.Up,    LONG_HOLD},
    wheel_text_far_down  = {CMD.Down,  LONG_HOLD},
    wheel_text_far_left  = {CMD.Left,  LONG_HOLD},
    wheel_text_far_right = {CMD.Right, LONG_HOLD},
}
local SLOT_ORDER = {"wheel_text_center","wheel_text_up","wheel_text_right",
    "wheel_text_down","wheel_text_left","wheel_text_far_up","wheel_text_far_right",
    "wheel_text_far_down","wheel_text_far_left"}
local SLOT_ABBR = {wheel_text_center="C",wheel_text_up="U",wheel_text_right="R",
    wheel_text_down="D",wheel_text_left="L",wheel_text_far_up="FU",
    wheel_text_far_right="FR",wheel_text_far_down="FD",wheel_text_far_left="FL"}

local function wheel_slots()
    local s = tostring(try("li", list_indication, IND_WHEEL))
    if #s < 70 then return nil end
    local vals, cur = {}, nil
    for line in s:gmatch("[^\n]*") do
        local n = line:match("^(wheel_text_[a-z_]+)%s*$")
        if n then cur = n ; vals[cur] = vals[cur] or ""
        elseif cur then
            if line:match("^%-%-%-") or line:match("^}") then cur = nil
            elseif line:match("%S") then
                vals[cur] = (vals[cur] == "" and line or (vals[cur] .. " " .. line))
            end
        end
    end
    return vals
end
local function wheel_str()
    local v = wheel_slots()
    if v == nil then return "<closed>" end
    local out = {}
    for _, k in ipairs(SLOT_ORDER) do
        if v[k] and v[k] ~= "" then out[#out+1] = SLOT_ABBR[k] .. "=" .. v[k] end
    end
    return #out > 0 and table.concat(out, "  ") or "<open, empty>"
end
local function petro_state()
    local v = wheel_slots()
    return (v and v["wheel_text_down"]) or "?"
end

-- Find a slot whose label contains `needle`. Returns slot, key command, hold.
local function find_option(needle)
    local v = wheel_slots()
    if v == nil then return nil end
    for slot, txt in pairs(v) do
        if txt ~= "" and txt:upper():find(needle, 1, true) and SLOT_KEY[slot] then
            return slot, SLOT_KEY[slot][1], SLOT_KEY[slot][2]
        end
    end
    return nil
end

local function contacts()
    local s = tostring(try("li6", list_indication, IND_HAI))
    local names, cur = {}, nil
    for line in s:gmatch("[^\n]*") do
        local n = line:match("^([a-z_]*list_text)%s*$")
        -- row -1 is registered under the name "LeftCenter" (ED naming slip)
        if n == nil and line:match("^LeftCenter%s*$") then n = "upper_list_text" end
        if n then cur = n
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

-- ------------------------------------------------------ label-driven press
-- Press an option by its LABEL, not its position, and report what happened.
local press = {active=false, phase=nil, t=0, cmd=nil, hold=0, label="", slot="", before=""}
local function press_start(needle, why)
    local slot, cmd, hold = find_option(needle)
    if slot == nil then
        log(string.format("    !! option %q not on this page: %s", needle, wheel_str()))
        return false
    end
    log(string.format("    press %q  [%s, %s press]  %s",
        needle, SLOT_ABBR[slot], (hold >= LONG_HOLD) and "LONG" or "short", why or ""))
    press.active, press.phase, press.t = true, "down", 0
    press.cmd, press.hold, press.label, press.slot = cmd, hold, needle, slot
    press.before = wheel_str()
    return true
end
local function press_update(t)
    if not press.active then return true end
    if press.phase == "down" then
        dev(DEV_HAI, "performClickableAction", press.cmd, 1)
        press.phase, press.t = "hold", t
    elseif press.phase == "hold" then
        if t - press.t > press.hold then
            dev(DEV_HAI, "performClickableAction", press.cmd, 0)
            press.phase, press.t = "settle", t
        end
    elseif press.phase == "settle" then
        if t - press.t > 1.0 then
            log("      -> " .. wheel_str())
            press.active = false
            return true
        end
    end
    return false
end

-- Make sure we are on the root/search page: if a SRCH option is visible we are.
local function on_search_page() return find_option("SRCH") ~= nil end

-- ============================================================== PART B
local PHASE_S = 25.0
local B = {phase="init", t=0, round=0, pinned=false, seen={}, n=0}

local function observe(t, tag)
    local c = contacts()
    if c ~= nil and B.seen[c] == nil then
        B.seen[c] = true ; B.n = B.n + 1
        log(string.format("      [%s] +%.0fs CONTACT: %s   (state=%s az=%s)",
            tag, t - B.t, c, petro_state(), az_deg()))
    end
end

local function part_b(t)
    local tag = B.pinned and "PINNED" or "FREE"

    if B.phase == "init" then
        if not wheel_slots() then
            if press.active then press_update(t) return end
            log("  wheel closed; opening")
            press.active, press.phase, press.cmd, press.hold = true, "down", CMD.ShowMenu, SHORT_HOLD
            press.before = ""
            return
        end
        if not on_search_page() then
            if press.active then press_update(t) return end
            -- CLOSE gets us out of a submenu; try it, else toggle the wheel
            if not press_start("CLOSE", "leaving submenu") then
                press.active, press.phase, press.cmd, press.hold = true, "down", CMD.ShowMenu, SHORT_HOLD
            end
            return
        end
        log("")
        log("  on the search page: " .. wheel_str())
        B.phase = "round" ; B.t = t

    elseif B.phase == "round" then
        if press.active then if press_update(t) then B.phase = "running" ; B.t = t end return end
        B.round = B.round + 1
        if B.round > 6 then B.phase = "restore" ; B.t = t return end
        B.pinned = not B.pinned
        B.seen, B.n = {}, 0
        tag = B.pinned and "PINNED" or "FREE"
        log("")
        log(string.format("========== round %d: %s ==========", B.round, tag))
        log("    wheel: " .. wheel_str())
        log(string.format("    state=%s az=%s", petro_state(), az_deg()))
        if not on_search_page() then
            log("    !! not on search page, re-syncing")
            B.phase = "init" ; return
        end
        if B.pinned then
            point_sight(SCAN_BEARING_DEG)
            if not press_start("SRCH 9K113", "search along OUR pinned sight line") then
                press_start("SRCH", "fallback: any search")
            end
        else
            if not press_start("SRCH BRST", "his own search, sight free") then
                press_start("SRCH", "fallback: any search")
            end
        end

    elseif B.phase == "running" then
        if B.pinned then point_sight(SCAN_BEARING_DEG) end
        observe(t, tag)
        if t - B.t > PHASE_S then
            log(string.format("    ==> %s round %d: %d distinct readings, state=%s, az=%s",
                tag, B.round, B.n, petro_state(), az_deg()))
            B.phase = "gap" ; B.t = t
        end

    elseif B.phase == "gap" then
        if t - B.t > 6.0 then B.phase = "round" ; B.t = t end

    elseif B.phase == "restore" then
        if press.active then if press_update(t) then B.phase = "done" end return end
        log("")
        log("  restoring HOLD FIRE if it is showing as FREE FIRE")
        if not press_start("FREE FIRE", "restore weapons-hold") then B.phase = "done" end

    elseif B.phase == "done" then
    end
end

-- ============================================================== driver
local started, t0 = false, nil
local last_w, last_c = nil, nil

function LuaExportStart()
    log("")
    log("#########################################################")
    log(string.format("SCAN PROBE v2 -- label-driven presses (bearing %+0.1f)", SCAN_BEARING_DEG))
    log("#########################################################")
    started = true
end
function LuaExportStop()
    log("scan probe v2: stopped.")
    if log_file then log_file:close() log_file = nil end
end
function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("t", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then t0 = t ; log("  " .. START_DELAY .. "s grace -- get level, targets ahead") return end
    if t - t0 < START_DELAY then return end

    local w = wheel_str()
    if w ~= last_w then last_w = w ; log(string.format("  ~ t=%.0f wheel: %s", t, w)) end
    local c = contacts()
    if c ~= last_c then
        last_c = c
        log(string.format("  ~ t=%.0f contacts: %s  (state=%s az=%s)",
            t, tostring(c), petro_state(), az_deg()))
    end

    if press.active and B.phase ~= "round" and B.phase ~= "restore" and B.phase ~= "init" then
        press_update(t)
        return
    end
    part_b(t)
end
