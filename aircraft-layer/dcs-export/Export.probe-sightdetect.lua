--[[
SIGHT-DRIVEN DETECTION PROBE v3 -- not the production export script.
Log: Logs\aircraft_layer_probe_sightdetect.log
Deploy to Saved Games\DCS\Scripts\Export.lua

WHERE THIS GOT TO
  v1: the probe never pressed ShowMenu, so no wheel, no search. The sight
      slewed exactly as commanded and nothing was detected -- consistent with
      "nobody is looking through it", but not isolated from "no search ran".
  v2: fixed that. SRCH FWD genuinely running (state=SEARCHING throughout), the
      sight pinned at five bearings for 12s each. Our azimuth HELD every time --
      he never fought us for it -- and there were ZERO detections at any
      bearing. The pilot then commanded a boresight search with the target
      group ON the boresight, and still got nothing.

  Two explanations are confounded in v2, and one of them is my omission:
    (a) v2 never commanded ELEVATION (3060), only azimuth, so the sight sat
        wherever it happened to be. The pilot saw it pointing too high -- so
        the sweep may simply have been scanning sky.
    (b) Pinning the sight SUPPRESSES the search. "Searching" means slewing the
        sight in a pattern; we were overriding that every frame, so he could be
        nominally SEARCHING while unable to actually look anywhere.

WHAT v3 DOES
  Tests (b) directly, which also sidesteps (a):

    FREE   -- search running, we do NOT touch the sight. He aims it himself,
              at whatever elevation is right, and we log both what he finds and
              WHERE HE POINTS IT.
    PINNED -- search running, we hold azimuth AND elevation.

  Alternating rounds. If FREE detects and PINNED does not, pinning suppresses
  detection and the question is settled. The FREE rounds also reveal the
  elevation he uses for ground targets -- the number v2 was missing.

HOW TO FLY IT
  Level and STEADY (hard manoeuvring makes him stow the sight), sight powered,
  targets ahead. 20s grace, then hands off -- wheel, sight and TrackIR.
]]

local DWELL_S   = 25.0     -- how long each condition runs
local ROUNDS    = 6        -- alternating FREE / PINNED
-- v4: DO NOT command elevation at all (pilot's call, and the v3 data agrees).
-- During his own search his elevation sits in arg 876 ~= -0.07 .. +0.18, i.e.
-- essentially level. v3 commanded el_cmd=-0.40, which settled at arg -0.30 --
-- roughly 4x more depressed than he ever uses, i.e. pointed at ground close in
-- with nothing on it. Targets are all at much the same vertical level, so
-- elevation is his to manage; we only take azimuth.
--
-- v5: PINNED is a SWEEP, not a hold, across the arc where the targets are.
-- v4 pinned a single bearing derived from a detection -- but no new detection
-- ever occurred, so it stayed at the +0 default, which was within half a degree
-- of where the sight already sat. Nothing moved, so nothing was tested.
-- The pilot's call: sweep 12 -> 10 o'clock, i.e. 0 to -60 degrees.
local SWEEP_FROM, SWEEP_TO = 0.0, -60.0

-- v5 also RE-ISSUES THE SEARCH each round. v4's rounds all ran with
-- state=NEXT TGT: after the pilot's SRCH PILOT LOS populated the list, the
-- wheel sat on the TARGET page and he was not searching at all. Both
-- conditions were measuring a parked crew.
local SEARCHING_STATES = {["WAITING"]=true, ["SEARCHING"]=true}
local function is_searching(st)
    for k in pairs(SEARCHING_STATES) do
        if st:find(k, 1, true) then return true end
    end
    return false
end
local START_DELAY, GYRO_WAIT = 20.0, 20.0

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_sightdetect.log"
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
local CMD_CENTRE, CMD_SHOWMENU, CMD_LEFT = 3015, 3001, 3003
local SIGHT_AI_AZ, SIGHT_AI_EL = 3061, 3060   -- Intern_SIGHT_*_AI_AXIS
local ARG_AZ, ARG_EL, ARG_NABL = 874, 876, 886
local IND_HAI, IND_WHEEL = 6, 10
local SHORT_HOLD, LONG_HOLD = 0.20, 0.80

local function read_arg(a)
    local mp = try("gd0", GetDevice, DEV_MAIN)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("arg", fn, mp, a)
end
local function dev(id, method, c, v)
    local d = try("gd", GetDevice, id)
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

-- wheel slots, using "[^\n]+" -- Lua's gmatch with * yields empty matches
-- between lines, which silently broke every earlier contact parser
local function wheel_slots()
    local s = tostring(try("li10", list_indication, IND_WHEEL))
    if #s < 70 then return nil end
    local vals, cur = {}, nil
    for line in s:gmatch("[^\n]+") do
        local n = line:match("^(wheel_text_[a-z_]+)%s*$")
        if n then cur = n ; vals[cur] = vals[cur] or ""
        elseif cur then
            local dashes = line:match("^(%-+)%s*$")
            if dashes and #dashes >= 20 then cur = nil
            elseif not dashes and not line:match("^}") then
                vals[cur] = (vals[cur] == "" and line or (vals[cur] .. " | " .. line))
            end
        end
    end
    return vals
end
local function petro_state()
    local v = wheel_slots()
    return (v and v["wheel_text_down"]) or "?"
end

local function contacts()
    local s = tostring(try("li6", list_indication, IND_HAI))
    local names, cur = {}, nil
    for line in s:gmatch("[^\n]+") do
        local n = line:match("^([a-z_]*list_text)%s*$")
        if n == nil and line:match("^LeftCenter%s*$") then n = "upper_list_text" end
        if n then cur = n
        elseif cur then
            if line:match("^%-%-%-") or line:match("^}") or line:match("^children") then
                cur = nil
            else
                names[#names+1] = line ; cur = nil
            end
        end
    end
    if #names == 0 then return nil end
    return table.concat(names, ", ")
end

local function press_centre(hold, t) -- caller drives the release via the phase machine
    dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 1)
end

-- ============================================================== driver
local P = {phase="grace", t=0, i=0, pinned=true, seen={}, results={},
           base = {}, void = false}

-- Contacts persist across rounds, so a PINNED round inherits whatever the
-- previous FREE round found and would look like a detection. Count only items
-- absent from THIS round's starting list.
local function to_set(csv)
    local set = {}
    if csv == nil then return set end
    for item in csv:gmatch("[^,]+") do
        item = item:gsub("^%s+", ""):gsub("%s+$", "")
        if item ~= "" then set[item] = true end
    end
    return set
end
local function novel_against(csv, base)
    if csv == nil then return nil end
    local out = {}
    for item in csv:gmatch("[^,]+") do
        item = item:gsub("^%s+", ""):gsub("%s+$", "")
        if item ~= "" and not base[item] then out[#out+1] = item end
    end
    if #out == 0 then return nil end
    return table.concat(out, ", ")
end
local t0, last_c = nil, nil

local function el_arg() return tostring(read_arg(ARG_EL)) end

-- Args 874/876 are the sight position relative to the AIRFRAME, so the
-- helicopter's own attitude changes where that actually points in the world
-- (pilot, 2026-09-11). A sight elevation that looks "level" in arg 876 is
-- nose-high or nose-low in the world by exactly the aircraft pitch -- which is
-- very likely why v3's sweep was seen "scanning too high and too low" while the
-- argument barely moved. Log attitude alongside so the numbers are readable
-- against the horizon rather than against the airframe.
local function attitude()
    local p, b, y = try("adi", LoGetADIPitchBankYaw)
    if type(p) ~= "number" then return "pitch=? bank=?", nil end
    local deg = 180.0 / math.pi
    return string.format("pitch=%+.1f bank=%+.1f", p * deg, (b or 0) * deg), p * deg
end

-- Sight elevation relative to the HORIZON, as far as we can state it: the
-- gauge value plus aircraft pitch. Elevation is not calibrated to degrees (its
-- limits are still unmeasured), so this reports the two parts rather than
-- pretending to a single angle.
local function sight_world_el()
    local a = read_arg(ARG_EL)
    local att, pitch = attitude()
    if type(a) ~= "number" or pitch == nil then return "el=? " .. att end
    return string.format("el_arg=%+.3f %s (horizon-relative = arg + pitch)", a, att)
end

function LuaExportStart()
    log("")
    log("#########################################################")
    log("SIGHT-DETECTION PROBE v3 -- FREE vs PINNED")
    log("  does holding the sight stop Petrovich finding anything?")
    log("#########################################################")
end
function LuaExportStop()
    log("sightdetect probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end
function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    local t = try("t", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then t0 = t ; log("  " .. START_DELAY .. "s grace -- get level and steady") return end
    if t - t0 < START_DELAY then return end

    local c = contacts()
    if c ~= last_c then
        last_c = c
        log(string.format("  ~ t=%.0f contacts: %s  (state=%s az=%s %s)",
            t, tostring(c), petro_state(), az_deg(), sight_world_el()))
    end

    if P.phase == "grace" then
        if wheel_slots() ~= nil then
            log("  wheel already open, state=" .. petro_state())
            P.phase = "search" ; P.t = t ; return
        end
        log("  opening the AI wheel (ShowMenu)")
        dev(DEV_HAI, "performClickableAction", CMD_SHOWMENU, 1)
        P.phase = "open_rel" ; P.t = t

    elseif P.phase == "open_rel" then
        if t - P.t > SHORT_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_SHOWMENU, 0)
            P.phase = "open_check" ; P.t = t
        end

    elseif P.phase == "open_check" then
        if t - P.t < 1.5 then return end
        if wheel_slots() == nil then
            log("  !! wheel did not open -- no search possible; aborting")
            P.phase = "done" ; return
        end
        log("  wheel open, state=" .. petro_state())
        P.phase = "search" ; P.t = t

    elseif P.phase == "search" then
        log("  starting a forward search (centre LONG = SRCH FWD)")
        dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 1)
        P.phase = "search_rel" ; P.t = t

    elseif P.phase == "search_rel" then
        if t - P.t > LONG_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 0)
            P.phase = "search_check" ; P.t = t
        end

    elseif P.phase == "search_check" then
        if t - P.t < 2.0 then return end
        local st = petro_state()
        if st:find("WAITING", 1, true) or st:find("SEARCHING", 1, true)
           or st:find("TRACKING", 1, true) then
            log("  search running, state=" .. st)
        else
            log("  !! state is " .. st .. " -- search may not have started; continuing")
        end
        log(string.format("  waiting %.0fs for gyro alignment", GYRO_WAIT))
        P.phase = "gyro" ; P.t = t

    elseif P.phase == "gyro" then
        if t - P.t > GYRO_WAIT then
            log("")
            log("  baseline: state=" .. petro_state() .. " az=" .. az_deg()
                .. " " .. sight_world_el() .. " list=" .. tostring(contacts()))
            P.phase = "next" ; P.t = t
        end

    elseif P.phase == "next" then
        P.i = P.i + 1
        if P.i > ROUNDS then P.phase = "report" ; return end
        -- get him searching again: the previous round may have ended with the
        -- target page up, in which case he is parked, not scanning.
        P.phase = "rearm" ; P.t = t
        return

    elseif P.phase == "rearm" then
        if t - P.t < 1.0 then return end
        local st = petro_state()
        if is_searching(st) then
            log(string.format("  (already searching: %s)", st))
            P.phase = "round_start" ; P.t = t ; return
        end
        log(string.format("  re-arming search (state was %s)", st))
        -- close the list first if the target page is up, else the centre press
        -- lands on MARK TGT instead of a search option
        local v = wheel_slots()
        local on_target = v and ((v["wheel_text_center"] or ""):upper():find("MARK", 1, true)
                                 or (v["wheel_text_down"] or ""):upper():find("NEXT TGT", 1, true))
        if on_target then
            dev(DEV_HAI, "performClickableAction", CMD_LEFT, 1)
            P.phase = "rearm_close" ; P.t = t
        else
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 1)
            P.phase = "rearm_search" ; P.t = t
        end

    elseif P.phase == "rearm_close" then
        if t - P.t > SHORT_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_LEFT, 0)
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 1)
            P.phase = "rearm_search" ; P.t = t
        end

    elseif P.phase == "rearm_search" then
        if t - P.t > LONG_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 0)
            P.phase = "rearm_check" ; P.t = t
        end

    elseif P.phase == "rearm_check" then
        if t - P.t < 2.5 then return end
        local st = petro_state()
        if not is_searching(st) then
            log(string.format("  !! still not searching (state=%s) -- round will be marked void", st))
            P.void = true
        else
            P.void = false
        end
        P.phase = "round_start" ; P.t = t

    elseif P.phase == "round_start" then
        P.pinned = not P.pinned
        P.seen = {}
        P.base = to_set(contacts())          -- this round's starting list
        log("")
        log(string.format("========== round %d: %s ==========",
            P.i, P.pinned and "PINNED" or "FREE"))
        log(string.format("    start: state=%s az=%s %s list=%s",
            petro_state(), az_deg(), sight_world_el(), tostring(contacts())))
        if P.pinned then
            log(string.format("    sweeping az %+.0f -> %+.0f deg over %.0fs (elevation left to him)",
                SWEEP_FROM, SWEEP_TO, DWELL_S))
        else
            log("    not touching the sight -- he aims it himself")
        end
        P.phase = "dwell" ; P.t = t

    elseif P.phase == "dwell" then
        if P.pinned then
            -- azimuth only; elevation stays his. Sweep rather than hold, so we
            -- actually cover the arc the targets are in.
            local frac = math.min(1.0, (t - P.t) / DWELL_S)
            local az = SWEEP_FROM + (SWEEP_TO - SWEEP_FROM) * frac
            dev(DEV_SIGHT, "SetCommand", SIGHT_AI_AZ, az / 60.0)
        end
        local cur = contacts()
        local novel = novel_against(cur, P.base)
        if novel ~= nil and P.seen[novel] == nil then
            P.seen[novel] = true
            log(string.format("    +%.0fs NEW: %s   (az=%s %s state=%s)",
                t - P.t, novel, az_deg(), sight_world_el(), petro_state()))
            P.results[#P.results+1] = string.format("%s round %d: %s%s",
                P.pinned and "PINNED" or "FREE", P.i, novel,
                P.void and " [VOID]" or "")

        end
        if t - P.t > DWELL_S then
            log(string.format("    end  : state=%s az=%s %s  %s%s",
                petro_state(), az_deg(), sight_world_el(),
                (next(P.seen) == nil) and "NO NEW DETECTIONS" or "(new detections above)",
                P.void and "   [VOID -- he was not searching]" or ""))
            P.phase = "next" ; P.t = t
        end

    elseif P.phase == "report" then
        log("")
        log("=========================================================")
        local free_hits, pin_hits = 0, 0
        for _, r in ipairs(P.results) do
            if r:sub(1, 4) == "FREE" then free_hits = free_hits + 1
            else pin_hits = pin_hits + 1 end
            log("   " .. r)
        end
        log(string.format("  FREE detections: %d    PINNED detections: %d",
            free_hits, pin_hits))
        if free_hits > 0 and pin_hits == 0 then
            log("  ==> PINNING SUPPRESSES DETECTION. He has to be free to slew")
            log("      the sight in order to find anything, so holding it blinds")
            log("      him. scan_area cannot work by pinning -- the directed")
            log("      scan rests on DesignateAttackPoint (3020).")
        elseif free_hits > 0 and pin_hits > 0 then
            log("  ==> detection happens in BOTH. Pinning does not blind him.")
        elseif free_hits == 0 and pin_hits == 0 then
            log("  ==> NO detections in either condition -- INCONCLUSIVE. Either")
            log("      no targets were in view, or something else gates detection.")
            log("      Check the FREE rounds' az/el above to see where he looked.")
        end
        log("=========================================================")
        P.phase = "done"

    elseif P.phase == "done" then
    end
end
