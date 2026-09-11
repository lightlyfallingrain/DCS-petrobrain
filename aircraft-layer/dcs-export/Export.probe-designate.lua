--[[
DESIGNATE-ATTACK-POINT PROBE -- not the production export script.
Log: Logs\aircraft_layer_probe_designate.log
Deploy to Saved Games\DCS\Scripts\Export.lua

THE QUESTION
  helperai_commands.DesignateAttackPoint (3020) is labelled, in DCS's own key
  binding list, "Designate custom AI attack point". HelperAI.lua defines
  scan_rad_around_point = 2500 and custom_attack_point_speed = 0.125 alongside
  it. So a point gets designated and something scans a 2.5 km radius around it.

  WHERE DOES THE POINT COME FROM? The pilot's hypothesis is that this is the
  actual mechanism behind SRCH PILOT LOS -- DCS computing where the
  centre-screen crosshair meets the terrain. That splits into two cases, and
  the difference decides BL-6:

    (a) the point comes from the PILOT'S VIEW
        -> as uncontrollable from code as SRCH PILOT LOS is, because the view
           follows the human's head (TrackIR)
    (b) the point comes from the 9K113's own ground intersection
        -> exactly what we need. We can already aim that sight precisely, so
           "point, then designate" becomes scan_area(bearing).
           av9K113::get_LandPoint() exists in the DLL ("the ground point the
           sight is aimed at"), which makes (b) mechanically plausible.

THE SEPARATING TEST
  For each of several bearings:
    1. aim the 9K113 there and hold until it settles
    2. fire DesignateAttackPoint (3020)
    3. RELEASE the sight completely
    4. watch for DWELL_S: where does he go, and does he find anything?

  If he stays at or returns to OUR bearing and works that area, the point came
  from the sight -- case (b), and BL-6 is solved. If he departs to somewhere
  unrelated -- particularly somewhere matching where the pilot is looking --
  it came from the view, case (a).

  The pilot should keep their head/TrackIR view pointed SOMEWHERE OTHER than
  the test bearings, which is what makes the two cases distinguishable: under
  (a) he will go where the pilot is looking, under (b) where we aimed.

HOW TO FLY IT
  Level and steady, sight powered, targets ahead spread across some arc.
  20s grace. Then hands off the wheel and sight -- but deliberately keep
  looking somewhere AWAY from where the sight is being pointed.
]]

local BEARINGS = {-30.0, 0.0, 30.0}   -- where we aim before designating
local SETTLE_S = 4.0                  -- let the sight arrive before designating
local DWELL_S  = 20.0                 -- watch this long after releasing
local START_DELAY, GYRO_WAIT = 20.0, 20.0

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_designate.log"
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
local CMD_DESIGNATE = 3020            -- "Designate custom AI attack point"

local P = {phase="grace", t=0, i=0, seen={}, results={}, aimed=nil}
local t0, last_c = nil, nil

local function el_arg() return tostring(read_arg(ARG_EL)) end

local function attitude()
    local p, b = try("adi", LoGetADIPitchBankYaw)
    if type(p) ~= "number" then return "pitch=? bank=?" end
    local deg = 180.0 / math.pi
    return string.format("pitch=%+.1f bank=%+.1f", p * deg, (b or 0) * deg)
end
local function where()
    return string.format("az=%s el_arg=%s %s", az_deg(), el_arg(), attitude())
end

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

function LuaExportStart()
    log("")
    log("#########################################################")
    log("DESIGNATE-ATTACK-POINT PROBE")
    log("  does the designated point come from the SIGHT or the VIEW?")
    log("#########################################################")
end
function LuaExportStop()
    log("designate probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end
function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    local t = try("t", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log("  " .. START_DELAY .. "s grace -- get level, and look AWAY from")
        log("  where the sight will be pointed, so the two cases separate")
        return
    end
    if t - t0 < START_DELAY then return end

    local c = contacts()
    if c ~= last_c then
        last_c = c
        log(string.format("  ~ t=%.0f contacts: %s  (state=%s %s)",
            t, tostring(c), petro_state(), where()))
    end

    if P.phase == "grace" then
        if wheel_slots() ~= nil then P.phase = "observ" ; P.t = t ; return end
        log("  opening the AI wheel")
        dev(DEV_HAI, "performClickableAction", CMD_SHOWMENU, 1)
        P.phase = "open_rel" ; P.t = t

    elseif P.phase == "open_rel" then
        if t - P.t > SHORT_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_SHOWMENU, 0)
            P.phase = "observ" ; P.t = t
        end

    elseif P.phase == "observ" then
        if t - P.t < 1.5 then return end
        if wheel_slots() == nil then
            log("  !! wheel did not open; aborting")
            P.phase = "done" ; return
        end
        -- observation must be on, else there is nobody looking. Starting a
        -- forward search is the cheapest way to get there (centre LONG).
        local st = petro_state()
        log("  wheel open, state=" .. st)
        if st:find("OBSERV. OFF", 1, true) then
            log("  starting a forward search to enable observation")
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 1)
            P.phase = "search_rel" ; P.t = t
        else
            P.phase = "gyro" ; P.t = t
        end

    elseif P.phase == "search_rel" then
        if t - P.t > LONG_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_CENTRE, 0)
            P.phase = "gyro" ; P.t = t
        end

    elseif P.phase == "gyro" then
        if t - P.t > GYRO_WAIT then
            log(string.format("  ready: state=%s %s", petro_state(), where()))
            P.phase = "next" ; P.t = t
        end

    elseif P.phase == "next" then
        P.i = P.i + 1
        if BEARINGS[P.i] == nil then P.phase = "report" ; return end
        P.seen = {}
        P.base = to_set(contacts())
        log("")
        log(string.format("========== aiming %+0.0f deg, then designating ==========",
            BEARINGS[P.i]))
        log("    before: " .. where() .. " state=" .. petro_state())
        P.phase = "aim" ; P.t = t

    elseif P.phase == "aim" then
        dev(DEV_SIGHT, "SetCommand", SIGHT_AI_AZ, BEARINGS[P.i] / 60.0)
        if t - P.t > SETTLE_S then
            P.aimed = az_deg()
            log("    sight settled at " .. P.aimed .. " -- firing DesignateAttackPoint (3020)")
            dev(DEV_HAI, "performClickableAction", CMD_DESIGNATE, 1)
            P.phase = "designate_rel" ; P.t = t
        end

    elseif P.phase == "designate_rel" then
        -- keep holding the sight until the command is released, so the
        -- designation cannot be attributed to the sight drifting first
        dev(DEV_SIGHT, "SetCommand", SIGHT_AI_AZ, BEARINGS[P.i] / 60.0)
        if t - P.t > SHORT_HOLD then
            dev(DEV_HAI, "performClickableAction", CMD_DESIGNATE, 0)
            log("    released the sight; watching where he goes")
            P.phase = "watch" ; P.t = t
        end

    elseif P.phase == "watch" then
        -- deliberately NOT commanding the sight now
        local cur = contacts()
        local novel = novel_against(cur, P.base)
        if novel ~= nil and P.seen[novel] == nil then
            P.seen[novel] = true
            log(string.format("    +%.0fs NEW: %s   (%s state=%s)",
                t - P.t, novel, where(), petro_state()))
            P.results[#P.results+1] = string.format("aimed %+0.0f -> %s",
                BEARINGS[P.i], novel)
        end
        if t - P.t > DWELL_S then
            log(string.format("    after %.0fs: %s state=%s", DWELL_S, where(), petro_state()))
            log(string.format("    aimed at %s, sight now at %s%s",
                tostring(P.aimed), az_deg(),
                (next(P.seen) == nil) and "   (no new detections)" or ""))
            P.phase = "next" ; P.t = t
        end

    elseif P.phase == "report" then
        log("")
        log("=========================================================")
        if #P.results == 0 then
            log("No bearing produced new detections after designating.")
            log("  Either the designation does not come from the sight, or it")
            log("  does nothing observable from here.")
        else
            for _, r in ipairs(P.results) do log("   " .. r) end
        end
        log("  Compare, for each bearing, where we aimed against where the")
        log("  sight ended up. Following our aim => the point comes from the")
        log("  SIGHT (case b, BL-6 solved). Going elsewhere, especially toward")
        log("  where the pilot was looking => it comes from the VIEW (case a).")
        log("=========================================================")
        P.phase = "done"

    elseif P.phase == "done" then
    end
end
