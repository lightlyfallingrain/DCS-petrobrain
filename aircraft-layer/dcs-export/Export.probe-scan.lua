--[[
SCAN-AT-BEARING PROBE v4 -- not the production export script.
Log: Logs\aircraft_layer_probe_scan.log   Deploy to Saved Games\DCS\Scripts\Export.lua

WHAT CHANGED IN v4
  Run 3 hammered "OBSERV. OFF" endlessly. The pilot's diagnosis: when the
  contact list is displayed, Up/Down SCROLL THE LIST rather than driving the
  wheel -- so the press was being consumed and nothing checked whether it had
  had any effect. v4 therefore:
   * VERIFIES every press (records the slot label before, reports "took effect"
     or "NO EFFECT", and refuses after 3 attempts, so nothing can loop);
   * IDENTIFIES the page (search / target / cm) from the centre and down slot
     labels and interprets key meaning accordingly;
   * ENUMERATES the contact list by scrolling NEXT TGT until the rows stop
     changing -- which terminates, since the list ends rather than wraps.
     Scrolling moves the selection, so this is not read-only.

WHAT CHANGED IN v3
  Run 2 was void because of three faults of mine:
   a. When the exact option was absent the probe fell back to a SUBSTRING
      search over slots using pairs(), whose order is undefined -- so the
      PINNED round pressed SRCH PILOT LOS and the FREE round pressed
      SRCH 9K113 LOS. The two conditions were INVERTED.
   b. SRCH BRST lives in the CENTRE slot, which has no direction key and so
      is not pressable at all by the known mapping. How the centre option is
      selected is still unknown; v3 does not depend on it.
   c. State was read from the down slot regardless of page -- but that slot is
      Petrovich's state only on the search page, and "NEXT TGT" on the target
      page.
  v3 presses an EXACT NAMED SLOT, having first verified that slot's
  current label; enables observation before expecting the sight-line search to
  appear (run 2 established SRCH 9K113 LOS is only offered once OBSERV. is ON);
  and reads state only when the search page is up.

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

-- Which centre-slot search to use. SRCH BRST (boresight) only finds what the
-- nose is already pointed at; SRCH FWD sweeps forward and finds targets that
-- are in view but off-axis, which is what we want for detection testing.
local CENTRE_SEARCH_OPTION = "SRCH FWD"

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
-- helperai_commands, with the labels DCS shows in its key-binding list.
-- Note these live in the Mi_24P_op / Mi_24P_pilot profiles, NOT in
-- Input/Mi_24P_AI_Menu/ -- searching only the AI_Menu profile is what hid
-- the centre command for several probe iterations.
local CMD = {
    ShowMenu = 3001, Right = 3002, Left = 3003, Up = 3004, Down = 3005,
    Centre   = 3015,   -- Select_or_fireEXT = "AI Wheel - Center"
}
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
    -- the centre slot carries two options: short press and long press
    wheel_text_center    = {CMD.Centre, SHORT_HOLD},
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

-- The centre slot carries TWO options separated by a SHORT dash divider:
--     wheel_text_center
--     SRCH BRST
--     --------          <- 8 dashes: an intra-slot divider, NOT a separator
--     SRCH FWD
-- The element separator is a much longer dash run (~41). v4 matched "^%-%-%-"
-- for both, so it kept "SRCH BRST" and silently DROPPED "SRCH FWD".
-- Distinguish by length. Extra options land in vals2[slot] (the long-press one).
local SEPARATOR_MIN_DASHES = 20
local vals2 = {}

local function wheel_slots()
    local s = tostring(try("li", list_indication, IND_WHEEL))
    if #s < 70 then return nil end
    local vals, cur, seen_divider = {}, nil, false
    vals2 = {}
    for line in s:gmatch("[^\n]*") do
        local n = line:match("^(wheel_text_[a-z_]+)%s*$")
        if n then
            cur = n ; seen_divider = false
            vals[cur] = vals[cur] or ""
        elseif cur then
            local dashes = line:match("^(%-+)%s*$")
            if dashes and #dashes >= SEPARATOR_MIN_DASHES then
                cur = nil
            elseif dashes then
                seen_divider = true          -- intra-slot: what follows is option 2
            elseif line:match("^}") then
                cur = nil
            elseif line:match("%S") then
                if seen_divider then
                    vals2[cur] = (vals2[cur] == nil or vals2[cur] == "")
                        and line or (vals2[cur] .. " " .. line)
                else
                    vals[cur] = (vals[cur] == "" and line or (vals[cur] .. " " .. line))
                end
            end
        end
    end
    return vals
end

-- The centre slot's second (long-press) option, if any.
local function centre_long_option()
    wheel_slots()
    return vals2["wheel_text_center"]
end
local function wheel_str()
    local v = wheel_slots()
    if v == nil then return "<closed>" end
    local out = {}
    for _, k in ipairs(SLOT_ORDER) do
        if v[k] and v[k] ~= "" then
            local txt = v[k]
            if vals2[k] and vals2[k] ~= "" then txt = txt .. " | " .. vals2[k] end
            out[#out+1] = SLOT_ABBR[k] .. "=" .. txt
        end
    end
    return #out > 0 and table.concat(out, "  ") or "<open, empty>"
end
-- The down slot carries Petrovich's state ONLY on the search page; on the
-- target page it is "NEXT TGT". Report it as unknown elsewhere.
local function on_search_page_v()
    local v = wheel_slots()
    if v == nil then return false, nil end
    local c = v["wheel_text_center"]
    return (c ~= nil and c:upper():find("SRCH", 1, true) ~= nil), v
end
local function petro_state()
    local ok, v = on_search_page_v()
    if not ok then return "<not search page>" end
    return v["wheel_text_down"] or "?"
end

-- Look up one NAMED slot's current label. Never scans -- run 2's fault was a
-- substring search over pairs(), whose undefined order inverted the two test
-- conditions.
local function slot_label(slot)
    local v = wheel_slots()
    if v == nil then return nil end
    local t = v[slot]
    if t == nil or t == "" then return nil end
    return t:upper()
end

-- Is `slot` currently offering `expect`? Only then is it safe to press.
local function slot_offers(slot, expect)
    local l = slot_label(slot)
    return (l ~= nil) and (l:find(expect, 1, true) ~= nil)
end

-- ---------------------------------------------------- page identification
-- The pilot's observation, which explains run 3's loop: when the contact list
-- is displayed, Up/Down SCROLL THE LIST instead of operating the wheel. So the
-- same key means different things depending on the page, and any press must
-- know which page is up.
--   search page : centre shows SRCH...   Up/Down are wheel actions
--   target page : centre shows MARK TGT  Up/Down are PREV/NEXT TGT (scroll)
local function page_kind()
    local v = wheel_slots()
    if v == nil then return "closed" end
    local c = (v["wheel_text_center"] or ""):upper()
    if c:find("SRCH", 1, true) then return "search" end
    if c:find("MARK", 1, true) then return "target" end
    local d = (v["wheel_text_down"] or ""):upper()
    if d:find("NEXT TGT", 1, true) then return "target" end
    if d:find("CM ", 1, true) or (v["wheel_text_left"] or ""):upper():find("CLOSE CM", 1, true) then
        return "cm"
    end
    return "other"
end

-- Dump indicator 6 RAW whenever it changes. The scan probes only ever ran the
-- parser over it and reported "no contacts", which was indistinguishable from
-- "the parser does not match this layout". The parser has since been verified
-- correct against the working detection-run text, so an empty result now means
-- the indicator really is empty -- but only a raw dump proves that, so dump it.
local last_ind6 = nil
local function dump_ind6_if_changed(t)
    local raw = tostring(try("li6raw", list_indication, IND_HAI))
    if raw == last_ind6 then return end
    last_ind6 = raw
    log(string.format("  ### t=%.0f indicator 6 RAW changed [%d bytes] page=%s",
                      t, #raw, page_kind()))
    if #raw > 2500 then raw = raw:sub(1, 2500) .. "\n...<truncated>" end
    log(raw)
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
-- Attempt bookkeeping: a press that does not change its own slot label is a
-- press that did nothing. Run 3 hammered "OBSERV. OFF" forever because nothing
-- checked. Every press now records the label it was trying to change, and the
-- caller must consult press_took() before assuming it worked.
local press = {active=false, phase=nil, t=0, cmd=nil, hold=0, label="", slot="",
               before="", before_label=nil, took=nil}
local attempts = {}
local function attempt_key(slot, expect) return tostring(slot) .. "|" .. tostring(expect) end
local function press_took() return press.took end
-- TARGET PAGE semantics (pilot, 2026-09-11):
--   up/down  = scroll the list / change selected target
--   right    = SELECT TGT  -- Petrovich tracks it, and fires when in parameters
--                             if weapons are free
--   left     = CLOSE LIST
--   centre   = MARK TGT    -- believed to mark several targets for engagement
--
-- This is a simulator, so these are STATE-MUTATING, not dangerous, and during
-- investigation we press them deliberately to learn what they do. MARK TGT's
-- semantics in particular are unknown and worth establishing.
--
-- The distinction that matters is for the PRODUCTION code, not the probe:
-- observation and engagement are different acts, and a body-layer
-- list_contacts() must not quietly select or mark while merely reading. That
-- belongs in the BL-6 design, not in a guard here.

-- Which hold fires which centre option? The centre slot shows two labels,
-- "<short> | <long>", so resolve it from the text rather than hard-coding.
-- Returns the hold time, or nil if that option is not currently offered.
local function centre_hold_for(want)
    local v = wheel_slots() or {}
    local short_opt = (v["wheel_text_center"] or ""):upper()
    local long_opt  = (centre_long_option() or ""):upper()
    if short_opt:find(want, 1, true) then return SHORT_HOLD, short_opt end
    if long_opt:find(want, 1, true) then return LONG_HOLD, long_opt end
    return nil
end

-- Press an EXACT slot, but only after confirming it currently shows `expect`.
-- Refuses after MAX_ATTEMPTS so a press that does nothing cannot loop forever.
local MAX_ATTEMPTS = 3
local function press_start(slot, expect, why)
    local k = attempt_key(slot, expect)
    if (attempts[k] or 0) >= MAX_ATTEMPTS then
        log(string.format("    !! giving up on %s=%q after %d attempts",
            SLOT_ABBR[slot] or tostring(slot), expect, attempts[k]))
        return false
    end
    local map = SLOT_KEY[slot]
    if map == nil then
        log(string.format("    !! slot %s has no direction key (centre?)", tostring(slot)))
        return false
    end
    if not slot_offers(slot, expect) then
        log(string.format("    !! %s does not offer %q (shows %q) -- not pressing",
            SLOT_ABBR[slot], expect, tostring(slot_label(slot))))
        return false
    end
    local cmd, hold = map[1], map[2]
    log(string.format("    press %s=%q  [%s press]  %s",
        SLOT_ABBR[slot], expect, (hold >= LONG_HOLD) and "LONG" or "short", why or ""))
    press.active, press.phase, press.t = true, "down", 0
    press.cmd, press.hold, press.label, press.slot = cmd, hold, expect, slot
    press.before = wheel_str()
    press.before_label = slot_label(slot)
    press.took = nil
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
            local after = slot_label(press.slot)
            press.took = (after ~= press.before_label)
            local k = attempt_key(press.slot, press.label)
            attempts[k] = (attempts[k] or 0) + 1
            log(string.format("      -> %s   [%s, attempt %d]",
                wheel_str(),
                press.took and "took effect" or "NO EFFECT on that slot",
                attempts[k]))
            press.active = false
            return true
        end
    end
    return false
end

-- Make sure we are on the root/search page: if a SRCH option is visible we are.
local function on_search_page() return (on_search_page_v()) end


-- ======================================================= LIST ENUMERATION
-- Requested 2026-09-11: when a group is bigger than the five visible rows, can
-- we walk the whole list? The pilot confirmed the list is TERMINATED and does
-- not wrap, so scrolling down until the rows stop changing enumerates it.
-- Scrolling moves Petrovich's selected target, so this is not read-only.
local SLOT_NEXT_TGT = "wheel_text_down"    -- on the TARGET page
local SLOT_PREV_TGT = "wheel_text_up"

local L = {phase="idle", t=0, steps=0, seen={}, order={}, last_rows=nil,
           rowsets={}, done=false}

local function record_rows(why)
    local c = contacts()
    if c == nil then return false end
    local isnew = false
    for row in c:gmatch("[^,]+") do
        local val = row:match("=%s*(.+)$")
        if val then
            val = val:gsub("^%s+", ""):gsub("%s+$", "")
            if val ~= "" and L.seen[val] == nil then
                L.seen[val] = true
                L.order[#L.order + 1] = val
                isnew = true
            end
        end
    end
    log(string.format("    [list %s] rows: %s", why, c))
    return isnew
end

local function list_enumerate(t)
    if L.phase == "idle" then
        if page_kind() ~= "target" then return true end   -- nothing to do
        log("")
        log("========== LIST ENUMERATION (target page is up) ==========")
        log("    will scroll with NEXT TGT, then probe MARK TGT and SELECT TGT")
        log("    to establish what they do -- state-mutating, which is fine here.")
        L.steps, L.seen, L.order, L.rowsets = 0, {}, {}, {}
        record_rows("initial")
        L.last_rows = contacts()
        if L.last_rows then L.rowsets[L.last_rows] = true end
        L.phase = "scroll" ; L.t = t

    elseif L.phase == "scroll" then
        if press.active then press_update(t) return false end
        if L.steps >= 12 then
            log("    stopping: 12 scroll steps without wrapping")
            L.phase = "probe_actions" ; L.t = t ; return false
        end
        if page_kind() ~= "target" then
            log("    left the target page; stopping enumeration")
            L.phase = "probe_actions" ; L.t = t ; return false
        end
        L.steps = L.steps + 1
        -- NEXT TGT's own label never changes when it scrolls, so the generic
        -- "did the slot label change" effect test reports NO EFFECT every time
        -- and the attempt cap kills the walk after 3 steps. Reset the counter
        -- for this press and judge its effect by whether the ROWS moved.
        attempts[attempt_key(SLOT_NEXT_TGT, "NEXT TGT")] = 0
        if not press_start(SLOT_NEXT_TGT, "NEXT TGT", "scrolling the list") then
            L.phase = "report" ; return false
        end
        L.phase = "settle" ; L.t = t

    elseif L.phase == "settle" then
        if press.active then press_update(t) return false end
        if t - L.t > 0.6 then
            local rows = contacts()
            record_rows("after step " .. L.steps)
            -- CORRECTION (pilot, 2026-09-11): the DISPLAY does not wrap, but
            -- TRAVERSAL DOES -- pressing down on the last item jumps back to
            -- the first. So "rows stopped changing" is the wrong terminator;
            -- it would either never fire or fire on a coincidence. Terminate on
            -- a REPEAT of a previously seen row-set instead.
            if rows == nil then
                log("    no rows readable; stopping")
                L.phase = "probe_actions" ; L.t = t
            elseif L.rowsets[rows] then
                log("    row-set already seen -> traversal has wrapped; full circle")
                L.phase = "probe_actions" ; L.t = t
            else
                L.rowsets[rows] = true
                L.last_rows = rows
                L.phase = "scroll"
            end
        end

    elseif L.phase == "probe_actions" then
        -- Establish what MARK TGT (centre) and SELECT TGT (right) actually do.
        -- Both mutate state; that is the point. Record wheel + indicator 6 +
        -- sight azimuth around each, since SELECT TGT should make Petrovich
        -- track -- which would show up as the sight moving on its own.
        if press.active then press_update(t) return false end
        if t - L.t < 2.0 then return false end
        L.act = (L.act or 0) + 1
        local a = ({
            {"wheel_text_center", "MARK",   "MARK TGT -- unknown semantics"},
            {"wheel_text_right",  "SELECT", "SELECT TGT -- expect tracking"},
        })[L.act]
        if a == nil then L.phase = "report" ; return false end
        if page_kind() ~= "target" then
            log("    left the target page; skipping action probe")
            L.phase = "report" ; return false
        end
        log(string.format("    -- probing %s --", a[3]))
        log(string.format("       before: az=%s  rows=%s", az_deg(), tostring(contacts())))
        attempts[attempt_key(a[1], a[2])] = 0
        if not press_start(a[1], a[2], a[3]) then
            log("       slot does not offer it; skipping")
        end
        L.t = t
        return false

    elseif L.phase == "report" then
        log(string.format("    ==> enumerated %d distinct entries in %d scroll steps:",
                          #L.order, L.steps))
        for i, v in ipairs(L.order) do log(string.format("        %2d. %s", i, v)) end
        log(string.format("    after action probes: az=%s  rows=%s  wheel=%s",
            az_deg(), tostring(contacts()), wheel_str()))
        log("    NOTE: scrolling moved the selection. Traversal wraps, so the")
        log("          selection is wherever the walk stopped, not necessarily home.")
        L.done = true
        L.phase = "idle"
        return true
    end
    return false
end

-- ======================================================= CENTRE-SLOT TEST
-- The centre button IS bindable and we had simply been looking in the wrong
-- profile: helperai_commands.Select_or_fireEXT (3015) is labelled
-- "AI Wheel - Center" in Mi_24P_op and Mi_24P_pilot. Earlier probes grepped
-- only Input/Mi_24P_AI_Menu/, which binds just ShowMenu and the four
-- directions, so the centre looked unreachable.
--
-- The centre slot shows two options split by a short divider, e.g.
-- "SRCH BRST | SRCH FWD". Short press should fire one, long press the other;
-- which is which is unknown, so this tests both and reports what each did.
local C = {phase="idle", t=0, i=0, before=nil, results={}}
-- LONG first: run 3 tested SHORT first, which consumed the idle->WAITING
-- transition, so the LONG press had no room left to show an effect and came
-- back inconclusive. Testing from the cleaner state first avoids that.
local CENTRE_TRIES = {
    {"centre LONG",  LONG_HOLD},
    {"centre SHORT", SHORT_HOLD},
}

local function centre_try(t)
    if C.phase == "idle" then
        local v = wheel_slots() or {}
        log("")
        log("========== CENTRE SLOT TEST (cmd 3015, AI Wheel - Center) ==========")
        log(string.format("  centre offers: %q  |  %q",
            tostring(v["wheel_text_center"]), tostring(centre_long_option())))
        C.i = 0 ; C.phase = "next" ; C.t = t

    elseif C.phase == "next" then
        if t - C.t < 2.0 then return false end
        C.i = C.i + 1
        local try_ = CENTRE_TRIES[C.i]
        if try_ == nil then
            log("  --- centre results ---")
            for _, r in ipairs(C.results) do log("    " .. r) end
            C.phase = "done"
            return true
        end
        if page_kind() ~= "search" then
            log("  not on search page; skipping centre test")
            C.phase = "done" ; return true
        end
        C.before = petro_state()
        log(string.format("  [%d/%d] %s   (state before: %s)",
            C.i, #CENTRE_TRIES, try_[1], tostring(C.before)))
        dev(DEV_HAI, "performClickableAction", CMD.Centre, 1)
        C.phase = "hold" ; C.t = t

    elseif C.phase == "hold" then
        if t - C.t > CENTRE_TRIES[C.i][2] then
            dev(DEV_HAI, "performClickableAction", CMD.Centre, 0)
            C.phase = "settle" ; C.t = t
        end

    elseif C.phase == "settle" then
        if t - C.t > 2.0 then
            local after = petro_state()
            local changed = (after ~= C.before)
            log(string.format("        state %s -> %s   %s", tostring(C.before),
                tostring(after), changed and "<== CHANGED" or "(no change)"))
            log("        wheel: " .. wheel_str())
            C.results[#C.results+1] = string.format("%s : %s -> %s%s",
                CENTRE_TRIES[C.i][1], tostring(C.before), tostring(after),
                changed and "" or "   (no effect)")
            C.phase = "next" ; C.t = t
        end

    elseif C.phase == "done" then
        return true
    end
    return false
end

-- ============================================================== PART B
local PHASE_S = 25.0
local SLOT_SEARCH_LOS  = "wheel_text_far_down"   -- SRCH 9K113 LOS  (long press)
local SLOT_SEARCH_FREE = "wheel_text_up"         -- SRCH PILOT LOS  (short press)
local SLOT_OBSERV      = "wheel_text_down"       -- OBSERV. ON/OFF  (short press)
local SLOT_CLOSE_LIST  = "wheel_text_left"       -- CLOSE LIST      (short press)

local B = {phase="open", t=0, round=0, pinned=false, seen={}, n=0}

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

    if B.phase == "open" then
        if press.active then press_update(t) return end
        if wheel_slots() == nil then
            log("  wheel closed; opening")
            press.active, press.phase, press.cmd, press.hold = true, "down", CMD.ShowMenu, SHORT_HOLD
            press.before = ""
            return
        end
        B.phase = "sync" ; B.t = t

    elseif B.phase == "sync" then
        if press.active then press_update(t) return end
        local kind = page_kind()
        if kind == "target" then
            -- the contact list is up: Up/Down scroll it rather than driving the
            -- wheel. Enumerate it once (it is what we want anyway), then leave.
            if not L.done then
                if not list_enumerate(t) then return end
            end
            log("  target page up; closing the list to regain wheel control")
            if not press_start(SLOT_CLOSE_LIST, "CLOSE", "close list") then
                B.phase = "round" ; B.t = t
            end
            return
        elseif kind ~= "search" then
            log("  on page '" .. kind .. "': " .. wheel_str())
            if not press_start(SLOT_CLOSE_LIST, "CLOSE", "leaving submenu") then
                B.phase = "round" ; B.t = t
            end
            return
        end
        log("  search page: " .. wheel_str())
        B.phase = "centre" ; B.t = t

    elseif B.phase == "centre" then
        if C.phase ~= "done" then
            if not centre_try(t) then return end
        end
        B.phase = "observ" ; B.t = t

    elseif B.phase == "observ" then
        -- The observation toggle repeatedly reported NO EFFECT last run, while
        -- a CENTRE short press moved OBSERV. OFF -> WAITING cleanly. So prefer
        -- the centre press to get Petrovich searching, and treat the D-slot
        -- toggle as a fallback only.
        if press.active then
            if press_update(t) then B.phase = "round" ; B.t = t end
            return
        end
        if page_kind() == "search" and slot_offers(SLOT_OBSERV, "OBSERV. OFF")
           and not slot_offers(SLOT_SEARCH_LOS, "SRCH 9K113") then
            -- SRCH FWD, not SRCH BRST (pilot, 2026-09-11): boresight search only
            -- finds what the nose already points at, so it misses targets that
            -- are in view but off-axis. Forward search sweeps and finds them.
            local hold, label = centre_hold_for(CENTRE_SEARCH_OPTION)
            if hold == nil then
                log("  centre does not offer " .. CENTRE_SEARCH_OPTION
                    .. " right now: " .. wheel_str())
                B.phase = "observ_old" ; B.t = t
                return
            end
            log(string.format("  starting search: centre %s press -> %q",
                (hold >= LONG_HOLD) and "LONG" or "short", label))
            dev(DEV_HAI, "performClickableAction", CMD.Centre, 1)
            press.active, press.phase, press.t = true, "hold", t
            press.cmd, press.hold = CMD.Centre, hold
            press.slot, press.label = "wheel_text_center", "CENTRE"
            press.before_label = slot_label("wheel_text_center")
            press.took = nil
            return
        end
        B.phase = "observ_old" ; B.t = t

    elseif B.phase == "observ_old" then
        -- run 2 established SRCH 9K113 LOS is only offered once observation is ON.
        -- run 3 then hammered OBSERV. OFF forever because nothing verified the
        -- press; press_start now caps attempts and press_took() reports effect.
        if press.active then
            if press_update(t) and press.slot == SLOT_OBSERV and press_took() == false then
                -- exactly run 3's failure mode: the toggle did nothing. Most
                -- likely Up/Down were being consumed by a visible contact list.
                log("  !! observation toggle had NO EFFECT (page=" .. page_kind() .. ")")
                log("     Up/Down are probably being consumed by the contact list.")
                B.phase = "sync" ; B.t = t
            end
            return
        end
        if page_kind() ~= "search" then B.phase = "sync" ; return end
        if slot_offers(SLOT_OBSERV, "OBSERV. OFF") then
            if not press_start(SLOT_OBSERV, "OBSERV. OFF", "enabling observation") then
                log("  !! cannot enable observation -- continuing without it")
                B.phase = "round" ; B.t = t
            end
            return
        end
        if not slot_offers(SLOT_SEARCH_LOS, "SRCH 9K113") then
            if t - B.t > 15.0 then
                log("  !! SRCH 9K113 LOS never appeared; state=" .. petro_state())
                log("     wheel: " .. wheel_str())
                B.phase = "round" ; B.t = t
            end
            return
        end
        log("  SRCH 9K113 LOS is available: " .. wheel_str())
        B.phase = "round" ; B.t = t

    elseif B.phase == "round" then
        if press.active then
            if press_update(t) then B.phase = "running" ; B.t = t end
            return
        end
        if B.round >= 6 then B.phase = "restore" ; B.t = t return end
        if not on_search_page() then B.phase = "sync" ; return end
        B.round = B.round + 1
        B.pinned = not B.pinned
        B.seen, B.n = {}, 0
        tag = B.pinned and "PINNED" or "FREE"
        log("")
        log(string.format("========== round %d: %s ==========", B.round, tag))
        log("    wheel: " .. wheel_str())
        log(string.format("    state=%s az=%s", petro_state(), az_deg()))

        local ok
        if B.pinned then
            point_sight(SCAN_BEARING_DEG)
            ok = press_start(SLOT_SEARCH_LOS, "SRCH 9K113",
                             "search along OUR pinned sight line")
        else
            ok = press_start(SLOT_SEARCH_FREE, "SRCH PILOT LOS",
                             "his own search, sight released")
        end
        if not ok then
            log("    round skipped -- option unavailable this cycle")
            B.phase = "gap" ; B.t = t
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
        if t - B.t > 6.0 then B.phase = "sync" ; B.t = t end

    elseif B.phase == "restore" then
        if press.active then if press_update(t) then B.phase = "done" end return end
        if slot_offers("wheel_text_far_up", "FREE FIRE") then
            press_start("wheel_text_far_up", "FREE FIRE", "restoring weapons hold")
        else
            log("")
            log("  done. HOLD FIRE already set.")
            B.phase = "done"
        end

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
    -- and the raw tree, so an empty parse is never again indistinguishable
    -- from a parser that does not match the current layout
    dump_ind6_if_changed(t)

    -- the contact list being up is itself an opportunity: enumerate it once
    if page_kind() == "target" and not L.done and not press.active then
        if not list_enumerate(t) then return end
    end
    part_b(t)
end
