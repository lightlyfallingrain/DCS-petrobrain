--[[
SIGHT-DRIVEN DETECTION PROBE -- not the production export script.
Log: Logs\aircraft_layer_probe_sightdetect.log
Deploy to Saved Games\DCS\Scripts\Export.lua

THE QUESTION (v2)
  Run 1 answered half of it and exposed a probe bug. The sight slewed exactly
  as commanded (-45.0, -25.0, +0.0) and NOTHING was ever detected -- but the
  probe never pressed ShowMenu, so the wheel was never open, the centre press
  had nothing to act on, and no search was ever running. The log shows it:
  "state=?" means petro_state() found no wheel slots at all.

  So run 1 is consistent with the pilot's reading -- the 9K113 can be slewed
  with the helper inactive, but with nobody looking through it, nothing is
  seen -- while not isolating it from "the probe never started a search".

  v2 asks the sharper question the pilot posed:
    WITH a search actively running, what happens when we slew by code?
  Does the swept bearing produce detections, or does Petrovich fight us for
  the sight / carry on with his own pattern?

  Sequence: open the wheel, VERIFY it is open, start SRCH FWD, VERIFY the state
  actually moved to WAITING/SEARCHING, wait out the gyro, take a baseline, then
  sweep -- logging contacts, state, and whether our commanded azimuth HOLDS.

  We know we can aim it: SetCommand(3061, deg/60) moves the real optics (the
  pilot confirms the HUD crosshair moves in missile mode), and the position
  holds. What we do NOT know is whether anything LOOKS through the sight on our
  behalf -- i.e. whether slewing onto an unlisted target adds it to the list.

  This matters because every other route to a DIRECTED scan has closed:
    SRCH PILOT LOS   triggerable, but aimed by the human's head (TrackIR)
    SRCH 9K113 LOS   would be exactly right, but appears broken -- pressing
                     down, short or long, just toggles OBSERV.
    SRCH FWD / BRST  triggerable, but not aimable
  If sight-driven detection works, scan_area(bearing) is one SetCommand plus a
  list read, with no wheel interaction at all.

METHOD
  1. Get Petrovich observing and searching (centre LONG = SRCH FWD).
  2. Record the baseline contact list.
  3. Sweep the sight across a series of bearings, holding each, and record the
     contact list at each one.
  4. Report which bearings produced contacts that were not in the baseline.

  It NEVER scrolls the list and NEVER selects a target -- the pilot established
  that Petrovich takes the sight back on either action, which would make the
  measurement his aim rather than ours.

  It also never toggles OBSERV. off: every OBSERV. ON costs the ~10s gyro
  alignment. Note Petrovich may turn observation off himself during hard
  manoeuvring to protect the gyros, so the log records OBSERV. state each step
  -- if it goes off mid-sweep, that step's result is void.

HOW TO FLY IT
  Level and STEADY (hard manoeuvring makes him stow the sight), sight powered,
  with targets spread across a decent arc ahead. 20s grace. Then hands off --
  in particular do not touch the wheel, the sight, or your TrackIR view more
  than necessary.
]]

local BEARINGS = {-45, -25, 0, 25, 45, 0}   -- degrees from the nose, + is right
local DWELL_S  = 12.0                       -- hold each bearing this long
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
local CMD_CENTRE, CMD_SHOWMENU, SIGHT_AI_AZ = 3015, 3001, 3061
local ARG_AZ, ARG_NABL = 874, 886
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
local P = {phase="grace", t=0, i=0, baseline={}, results={}}
local t0 = nil
local last_c = nil

local function add_set(tbl, csv)
    if csv == nil then return end
    for item in csv:gmatch("[^,]+") do
        item = item:gsub("^%s+", ""):gsub("%s+$", "")
        if item ~= "" then tbl[item] = true end
    end
end

function LuaExportStart()
    log("")
    log("#########################################################")
    log("SIGHT-DRIVEN DETECTION PROBE")
    log("  does aiming the 9K113 ourselves make Petrovich detect?")
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
        log(string.format("  ~ t=%.0f contacts: %s   (state=%s az=%s NABL=%s)",
            t, tostring(c), petro_state(), az_deg(), tostring(read_arg(ARG_NABL))))
    end

    if P.phase == "grace" then
        -- run 1's bug: it pressed the centre without ever opening the wheel.
        if wheel_slots() ~= nil then
            log("  wheel already open: " .. tostring(petro_state()))
            P.phase = "search" ; P.t = t
            return
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
            log("  !! wheel did not open -- cannot run a search; aborting")
            log("     (without the helper UI there is nobody looking through the sight)")
            P.phase = "done" ; return
        end
        log("  wheel open, state=" .. tostring(petro_state()))
        P.phase = "search" ; P.t = t

    elseif P.phase == "search" then
        log("  starting a forward search (centre LONG = SRCH FWD)")
        press_centre(LONG_HOLD, t)
        P.phase = "rel" ; P.t = t

    elseif P.phase == "rel" then
        if t - P.t > LONG_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 0)
            P.phase = "search_check" ; P.t = t
        end

    elseif P.phase == "search_check" then
        if t - P.t < 2.0 then return end
        local st = tostring(petro_state())
        if st:find("WAITING", 1, true) or st:find("SEARCHING", 1, true)
           or st:find("TRACKING", 1, true) then
            log("  search running, state=" .. st)
        else
            log("  !! state is " .. st .. " -- the search may not have started.")
            log("     Continuing anyway; the sweep results will say.")
        end
        log(string.format("  waiting %.0fs for gyro alignment", GYRO_WAIT))
        P.phase = "gyro" ; P.t = t

    elseif P.phase == "gyro" then
        if t - P.t > GYRO_WAIT then
            add_set(P.baseline, contacts())
            log("")
            log("  BASELINE contacts: " .. tostring(contacts()))
            log(string.format("  state=%s  now sweeping the sight across %d bearings",
                petro_state(), #BEARINGS))
            log("  (never scrolling, never selecting -- either hands the sight back)")
            P.phase = "next" ; P.t = t
        end

    elseif P.phase == "next" then
        P.i = P.i + 1
        if BEARINGS[P.i] == nil then P.phase = "report" ; return end
        log("")
        log(string.format("--- bearing %+d deg ---", BEARINGS[P.i]))
        P.seen = {}
        P.phase = "dwell" ; P.t = t

    elseif P.phase == "dwell" then
        point_sight(BEARINGS[P.i])          -- re-assert every frame
        local cur = contacts()
        if cur ~= nil and P.seen[cur] == nil then
            P.seen[cur] = true
            local novel = {}
            for item in cur:gmatch("[^,]+") do
                item = item:gsub("^%s+", ""):gsub("%s+$", "")
                if item ~= "" and not P.baseline[item] then novel[#novel+1] = item end
            end
            log(string.format("    +%.0fs az=%s NABL=%s state=%s", t - P.t, az_deg(),
                tostring(read_arg(ARG_NABL)), petro_state()))
            log("      list : " .. cur)
            if #novel > 0 then
                log("      NEW  : " .. table.concat(novel, ", ") .. "   <== NOT IN BASELINE")
                P.results[#P.results+1] = string.format("%+d deg -> %s",
                    BEARINGS[P.i], table.concat(novel, ", "))
            end
        end
        if t - P.t > DWELL_S then
            local actual = tonumber(az_deg()) or 0
            local held = math.abs(actual - BEARINGS[P.i]) < 2.0
            log(string.format("    settled az=%s (commanded %+d) %s  state=%s  list=%s",
                az_deg(), BEARINGS[P.i],
                held and "HELD" or "<== PETROVICH TOOK THE SIGHT BACK",
                petro_state(), tostring(contacts())))
            P.phase = "next" ; P.t = t
        end

    elseif P.phase == "report" then
        log("")
        log("=========================================================")
        if #P.results == 0 then
            log("NO bearing produced a contact outside the baseline.")
            log("  Aiming the sight does NOT appear to drive detection on its own.")
            log("  If so, directed scanning rests on DesignateAttackPoint (3020),")
            log("  which remains untested under good conditions.")
        else
            log("BEARINGS THAT PRODUCED NEW CONTACTS:")
            for _, r in ipairs(P.results) do log("   " .. r) end
            log("  Aiming the sight DOES drive detection -- scan_area(bearing)")
            log("  is one SetCommand plus a list read, no wheel interaction.")
        end
        log("=========================================================")
        P.phase = "done"
    end
end
