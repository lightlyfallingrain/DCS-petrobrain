--[[
PETROVICH 9K113 HUD ELEVATION LIMITS PROBE -- not the production script.

Deploy by copying over Saved Games\DCS\Scripts\Export.lua; restore the
production Export.lua afterwards. Card:
docs/acceptance/2026-10-27-9k113-hud-elevation-limits-probe.md.

WHY (plan.md v3, "Elevation - measure in flight", ANSWERED 2026-10-26)
  The ASP-17 HUD field's azimuth clip is measured (565/566, ~+-4.3 deg,
  docs/acceptance/2026-10-22-9k113-ai-latency-probe.md line 423). Its
  elevation clip (555/556) never has been -- v3's edge-park design ships a
  placeholder half-angle on that axis pending this flight. User request,
  verbatim: "create a probe for measuring the HUD elevation limits. slew up
  until limit, then down until limit and log the values. That'll then be
  super easy to measure."

  Open-loop AI-axis elevation command (CMD_AI_ELEV, 3060), one direction at
  a time, slow enough (EL_RATE_CMD below) to locate the plateau to within
  about 0.05 deg. Every command keeps the value changing every frame
  (flicker dither) because DCS intermittently ignores a held value
  otherwise (same ai-latency-probe doc, runs 6-8). Each direction pushes a
  margin past the first plateau to rule out a momentary stall (DCS
  ignoring the axis, not a true field edge), then reverses through
  boresight to the opposite edge. The whole up/down sweep repeats
  CYCLES times: a true edge repeats at the same 555 value every cycle; a
  stall does not -- except that the same ai-latency-probe doc also records
  the AI-axis gate holding for the *entire* flight at least once (run 8),
  in which case every cycle would plateau at the same near-zero-travel
  value and a cycle-consistency check alone cannot tell that apart from a
  real edge (reviewer, 2026-10-27: see
  .claude/agent-memory/reviewer/feedback_9k113_stall_vs_clip_margin_too_short.md).
  So a plateau is only ever accepted if its travel from the seek's own
  starting value is plausible given how long the axis has been commanded
  (MIN_TRAVEL_FRACTION below) and it is not suspiciously close to
  boresight (MIN_TRAVEL_EL) -- otherwise it is logged SUSPECT, never
  accepted, and the probe keeps pushing/retrying rather than taking the
  gate's frozen value as the field edge.

  The script does not know which signed command direction is visually "up"
  on the ASP-17 glass -- that mapping has never been nailed down in this
  project (ai-latency-probe doc, run 2: "sign-inverted, so probably down").
  Phases are logged by command sign only ("POS"/"NEG"); the test card asks
  the pilot which one they saw rise and which fell.

  Overlay OFF. Pilot seat throughout, no 9K113 view, no operator axes
  bound. The only writes are the AI elevation (and a matching tiny-flicker
  AI azimuth) axis.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_9k113_hud_elevation_limits.log"

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
local DEV_I9K113 = 7
local ARG_OBSERVE = 886
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060

-- Mark pair (ASP-17 crosshair): 565/566 horizontal, 555/556 vertical
-- (docs/acceptance/2026-10-22-9k113-ai-latency-probe.md). Both of a pair
-- read identically; both are logged so a divergence would be visible.
local ARG_AZ, ARG_AZ2 = 565, 566
local ARG_EL, ARG_EL2 = 555, 556

-- Л5 "ROLL SYNC TR UNCAGE" (alignment done), READY, LAUNCH PERMITTED --
-- context lamps, not control inputs to this probe.
local LAMP_ARGS = { { 898, "L5_ALIGN" }, { 960, "READY" }, { 962, "LAUNCH_PERM" } }
local LAMP_EPS = 0.1

local OBSERV_DEBOUNCE_S = 0.5
local START_DELAY_S = 20.0

--: AI-axis elevation command unit, open loop. Devices_specs/9K113.lua:
--: v_axis_velocity = 10 deg/s, so commanded rate = EL_RATE_CMD * 10 deg/s.
--: 0.05 -> 0.5 deg/s, slow enough that a 0.05 deg edge shows across several
--: frames rather than one, at any plausible DCS frame rate.
local EL_RATE_CMD = 0.05

--: per-frame dither amplitude added to both AI axes so DCS does not
--: intermittently ignore a held command value (confirmed necessary,
--: docs/acceptance/2026-10-22-9k113-ai-latency-probe.md runs 6-8; the
--: BL-B80 v2 calibration probe uses the same trick, flicker 1e-4).
local FLICKER_EPS = 1e-4

--: rough 555-per-degree scale, from the BL-B80 v2 calibration probe
--: (never itself confirmed against a measured elevation range) -- used
--: only to print a degrees estimate alongside the raw summary; the raw
--: 555 values are the measurement that matters.
local MARK_PER_DEG_EL = 0.028

--: a window of this many seconds with 555 flat to within PLATEAU_EPS,
--: while still commanding motion, counts as "stopped" -- about 0.05 deg
--: of travel at EL_RATE_CMD's rate, so the window is long enough to not
--: trigger on dither noise alone (dither moves 555 by ~1e-4 ESH an order
--: below PLATEAU_EPS) and short enough to not blur past a real edge.
local PLATEAU_WINDOW_S = 0.6

--: 555 units; ~0.05 deg at MARK_PER_DEG_EL. The flat-window threshold.
local PLATEAU_EPS = 0.0015

--: once a plateau is seen, keep commanding into it this much longer to
--: rule out a momentary stall rather than a true field edge -- if 555
--: moves again during this window it was a stall, not an edge, and the
--: seek resumes. Set above the AI-axis gate windows documented in
--: docs/acceptance/2026-10-22-9k113-ai-latency-probe.md runs 6-8 (4-18 s
--: typical) -- a 3 s margin (the original value) is shorter than nearly
--: every one of those windows and so cannot, by itself, rule them out
--: (reviewer, 2026-10-27). The travel check below is the primary defence;
--: this margin is the secondary one.
local MARGIN_S = 20.0

--: the final open-loop nudge back toward centre (RETURN phase) uses its
--: own short duration rather than MARGIN_S -- reusing MARGIN_S here (the
--: original design) meant raising MARGIN_S for the stall margin above
--: would also make the nudge overshoot many degrees past centre, which is
--: not what the nudge is for.
local RETURN_NUDGE_S = 3.0

--: safety cap per direction per cycle, in case the axis never plateaus
--: (e.g. a genuine, long-lived command stall) -- the probe logs a timeout
--: and moves on rather than hanging the whole run. Measured from
--: phase_start (set once per direction, not reset by a SUSPECT retry), and
--: sized to comfortably fit a real seek plus the now-longer MARGIN_S hold.
local MAX_PHASE_S = 60.0

--: a plateau is accepted as a real field/gimbal edge only if its travel
--: from the seek's own starting value is at least this fraction of what
--: EL_RATE_CMD's rate times the elapsed seek time would predict for
--: continuous, ungated motion. Well under this (the AI-axis gate holding
--: the command from the very start of the seek) means the mark has barely
--: moved despite being commanded the whole time -- the signature of the
--: gate documented in ai-latency-probe runs 6-8, not a true edge, however
--: long the plateau holds.
local MIN_TRAVEL_FRACTION = 0.5

--: absolute floor (555 units, ~0.2 deg) below which a plateau is flagged
--: as suspiciously close to boresight on its own, even if travel-from-
--: start happens to clear MIN_TRAVEL_FRACTION (e.g. a seek that itself
--: began a hair off boresight) -- a real elevation clip this close to
--: centre would be surprising given azimuth's already-measured ~4.3 deg.
local MIN_TRAVEL_EL = 0.006

--: expected 555-units-per-second of real motion at EL_RATE_CMD's full rate
--: (0.5 deg/s, Devices_specs/9K113.lua) times MARK_PER_DEG_EL's rough scale
--: -- used only to judge whether a plateau's travel is plausible, not as a
--: precise conversion.
local MARK_RATE_PER_S = EL_RATE_CMD * 10.0 * MARK_PER_DEG_EL

--: number of full pos/neg sweeps. A true edge reads the same 555 value
--: every cycle; a stall (DCS ignoring the command) does not -- see WHY.
local CYCLES = 3

--: cycle-to-cycle plateau values within this spread (555 units, ~0.36 deg)
--: count as the same edge, for the final summary's consistency check.
local CONSISTENCY_EPS = 0.01

-- ---------------------------------------------------------------- helpers
local function fmt(v)
    if type(v) ~= "number" then return tostring(v) end
    return string.format("%.5f", v)
end

local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    local fn = safe_index(mp, "get_argument_value")
    if type(fn) ~= "function" then return nil end
    return try("get_argument_value", fn, mp, arg)
end

local function set_quiet(cmd, value)
    local dev = GetDevice(DEV_I9K113)
    if dev == nil then return end
    pcall(dev.SetCommand, dev, cmd, value)
end

local function centre_all()
    set_quiet(CMD_AI_AZ, 0.0)
    set_quiet(CMD_AI_ELEV, 0.0)
end

local flick_parity = false
local function flicker()
    flick_parity = not flick_parity
    return flick_parity and FLICKER_EPS or -FLICKER_EPS
end

-- Writes both AI axes every frame: elevation carries the seek/return
-- command, azimuth carries only the shared dither so it does not drift
-- and so DCS sees a per-frame change on both axes alike.
local function write_axes(el_cmd)
    local f = flicker()
    set_quiet(CMD_AI_AZ, f)
    set_quiet(CMD_AI_ELEV, el_cmd + f)
end

local lamp_last = {}
local function log_lamp_changes(dt)
    for _, e in ipairs(LAMP_ARGS) do
        local v = read_arg(e[1])
        if type(v) == "number" then
            local prev = lamp_last[e[1]]
            if prev == nil then
                log(string.format("  lamp %d %s = %s (initial) t=%7.3f", e[1], e[2], fmt(v), dt))
                lamp_last[e[1]] = v
            elseif math.abs(v - prev) >= LAMP_EPS then
                log(string.format("  lamp %d %s %s -> %s  t=%7.3f", e[1], e[2], fmt(prev), fmt(v), dt))
                lamp_last[e[1]] = v
            end
        end
    end
end

local total_frames = 0
local function log_row(dt, seg, el_cmd)
    total_frames = total_frames + 1
    log(string.format(
        "  . f=%6d t=%8.3f seg=%-16s el_cmd=%+.5f  555=%s 556=%s 566=%s 565=%s 886=%s",
        total_frames, dt, seg, el_cmd,
        fmt(read_arg(ARG_EL)), fmt(read_arg(ARG_EL2)), fmt(read_arg(ARG_AZ2)), fmt(read_arg(ARG_AZ)),
        fmt(read_arg(ARG_OBSERVE))))
    return total_frames
end

-- ---------------------------------------------------------------- state
local started, t0 = false, nil
local phase = "WAIT_OBSERV"
local observ_on_since = nil
local delay_start = nil
local last_heartbeat_t = -1e9
local aborted = false

-- CYCLE state: dir "POS"/"NEG", sub "SEEK"/"MARGIN".
local cycle = 1
local dir = "POS"
local sub = "SEEK"
local seek_start = nil
local margin_start = nil
local hist = {}          -- { {t, m}, ... } over the last PLATEAU_WINDOW_S
local plateau_value = nil
local plateau_frame = nil

-- phase_start: set once per direction attempt, not reset by a SUSPECT
-- retry -- MAX_PHASE_S is measured from here so a gate that keeps
-- restarting the SEEK sub-phase cannot also keep resetting its own cap.
local phase_start = nil
-- seek_start_value: 555 at the moment this SEEK attempt (post-retry)
-- began; nil until the first frame's read lands.
local seek_start_value = nil
-- suspect_logged: throttles the SUSPECT log line to once per flat-window
-- episode rather than once per frame while the gate holds.
local suspect_logged = false

-- results[dir][cycle] = { value = number-or-nil, frame = number-or-nil }
local results = { POS = {}, NEG = {} }

local function push_hist(t, m)
    hist[#hist + 1] = { t, m }
    while #hist > 1 and hist[1][1] <= t - PLATEAU_WINDOW_S do table.remove(hist, 1) end
end

local function window_flat(t)
    if #hist < 2 or hist[1][1] > t - PLATEAU_WINDOW_S then return false, nil, nil end
    local lo, hi = 1e9, -1e9
    for _, s in ipairs(hist) do
        lo = math.min(lo, s[2])
        hi = math.max(hi, s[2])
    end
    return (hi - lo) <= PLATEAU_EPS, lo, hi
end

local function el_cmd_for(d)
    return (d == "POS") and EL_RATE_CMD or -EL_RATE_CMD
end

local function start_seek(dt)
    sub = "SEEK"
    seek_start = dt
    seek_start_value = nil
    hist = {}
    plateau_value, plateau_frame = nil, nil
    suspect_logged = false
    log(string.format("=== cycle %d/%d  %s seek  t=%7.3f  el_cmd=%+.5f", cycle, CYCLES, dir, dt, el_cmd_for(dir)))
end

local function finish_phase(dt, timed_out)
    results[dir][cycle] = { value = plateau_value, frame = plateau_frame }
    if timed_out then
        log(string.format("  ... cycle %d %s: TIMEOUT after %.1f s, no plateau found", cycle, dir, MAX_PHASE_S))
    else
        log(string.format("  ... cycle %d %s: plateau 555=%s confirmed at frame %s (margin %.1f s held)",
            cycle, dir, fmt(plateau_value), tostring(plateau_frame), MARGIN_S))
    end
    if dir == "POS" then
        dir = "NEG"
        phase_start = dt
        start_seek(dt)
    else
        dir = "POS"
        cycle = cycle + 1
        if cycle > CYCLES then
            phase = "RETURN"
            seek_start = dt
        else
            phase_start = dt
            start_seek(dt)
        end
    end
end

-- ---------------------------------------------------------------- driver
function LuaExportStart()
    log("")
    log("#########################################################")
    log("9K113 HUD ELEVATION LIMITS PROBE")
    local v = try("LoGetVersionInfo", LoGetVersionInfo)
    if type(v) == "table" then
        local function ver(x)
            if type(x) ~= "table" then return tostring(x) end
            local p = {}
            for _, n in ipairs(x) do p[#p + 1] = tostring(n) end
            return table.concat(p, ".")
        end
        log("  DCS version: file=" .. ver(v.FileVersion) .. " product=" .. ver(v.ProductVersion))
    end
    log("  DCS AI Petrovich overlay must stay OFF throughout. Waiting for OBSERV (arg 886) on.")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("9k113 hud elevation limits probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started or aborted then return end
    local ok, err = pcall(function()
        local t = try("LoGetModelTime", LoGetModelTime)
        if type(t) ~= "number" then return end
        if t0 == nil then t0 = t end
        local dt = t - t0

        log_lamp_changes(dt)

        if phase == "WAIT_OBSERV" then
            local observe = read_arg(ARG_OBSERVE)
            if type(observe) == "number" and observe >= 0.5 then
                if observ_on_since == nil then observ_on_since = dt end
                if (dt - observ_on_since) >= OBSERV_DEBOUNCE_S then
                    log(string.format("  OBSERV on at t=%7.3f = T+0. Steps in %.0f s. Go to the PILOT seat and stay there (no 9K113 view).",
                                      observ_on_since, START_DELAY_S))
                    phase = "DELAY"
                    delay_start = observ_on_since
                end
            else
                observ_on_since = nil
            end
            return
        end

        if phase == "DELAY" then
            if (dt - last_heartbeat_t) >= 5.0 then
                log(string.format("  . steps in %.0f s", START_DELAY_S - (dt - delay_start)))
                last_heartbeat_t = dt
            end
            if (dt - delay_start) >= START_DELAY_S then
                phase = "CYCLE"
                phase_start = dt
                start_seek(dt)
            end
            return
        end

        if phase == "CYCLE" then
            local el_cmd = el_cmd_for(dir)
            write_axes(el_cmd)
            local m = read_arg(ARG_EL)
            if sub == "SEEK" then
                if type(m) == "number" then
                    if seek_start_value == nil then seek_start_value = m end
                    push_hist(dt, m)
                    local flat, lo, hi = window_flat(dt)
                    if flat then
                        local candidate = (lo + hi) / 2
                        local elapsed_seek = dt - seek_start
                        local expected_travel = MARK_RATE_PER_S * elapsed_seek
                        local travel = math.abs(candidate - seek_start_value)
                        local suspect = (travel < MIN_TRAVEL_FRACTION * expected_travel) or (math.abs(candidate) < MIN_TRAVEL_EL)
                        if suspect then
                            if not suspect_logged then
                                log(string.format(
                                    "  ... cycle %d %s: SUSPECT -- near-zero travel (travel=%.5f from start=%.5f, expected>=%.5f over %.1f s) -- matches the known AI-axis gate (ai-latency-probe runs 6-8), NOT accepted as a plateau, continuing to seek",
                                    cycle, dir, travel, seek_start_value, expected_travel, elapsed_seek))
                                suspect_logged = true
                            end
                        else
                            plateau_value = candidate
                            plateau_frame = log_row(dt, cycle .. "/" .. dir .. "-SEEK", el_cmd)
                            sub = "MARGIN"
                            margin_start = dt
                            log(string.format("  ... cycle %d %s: plateau candidate 555=%.5f at t=%.3f (window flat within %.5f, travel=%.5f from start=%.5f)",
                                cycle, dir, plateau_value, dt, hi - lo, travel, seek_start_value))
                        end
                    end
                end
                if plateau_value == nil then
                    log_row(dt, cycle .. "/" .. dir .. "-SEEK", el_cmd)
                    if (dt - phase_start) >= MAX_PHASE_S then
                        finish_phase(dt, true)
                    end
                end
                return
            end

            if sub == "MARGIN" then
                log_row(dt, cycle .. "/" .. dir .. "-MARGIN", el_cmd)
                if type(m) == "number" and math.abs(m - plateau_value) > PLATEAU_EPS then
                    log(string.format("  ... cycle %d %s: STALL not a clip -- resumed moving (555 %.5f -> %.5f), continuing to seek",
                        cycle, dir, plateau_value, m))
                    start_seek(dt)
                    return
                end
                if (dt - margin_start) >= MARGIN_S then
                    finish_phase(dt, false)
                end
                return
            end
            return
        end

        if phase == "RETURN" then
            -- Open-loop nudge back toward whichever edge was reached last
            -- (direction NEG was always the final sweep of the last cycle,
            -- so return in the POS direction); not a precise re-centre,
            -- just so the real sight is not left parked at a field edge.
            local el_cmd = -el_cmd_for("NEG")
            write_axes(el_cmd)
            log_row(dt, "RETURN", el_cmd)
            if seek_start == nil then seek_start = dt end
            if (dt - seek_start) >= RETURN_NUDGE_S then
                centre_all()
                log("=== SUMMARY per direction")
                for _, d in ipairs({ "POS", "NEG" }) do
                    local vals, frames = {}, {}
                    for c = 1, CYCLES do
                        local r = results[d][c]
                        if r ~= nil and r.value ~= nil then
                            vals[#vals + 1] = r.value
                            frames[#frames + 1] = r.frame
                        end
                    end
                    if #vals == 0 then
                        log(string.format("  %s: no plateau found in any cycle", d))
                    else
                        local lo, hi = vals[1], vals[1]
                        for _, v in ipairs(vals) do lo, hi = math.min(lo, v), math.max(hi, v) end
                        local consistent = (hi - lo) <= CONSISTENCY_EPS
                        local mean = 0.0
                        for _, v in ipairs(vals) do mean = mean + v end
                        mean = mean / #vals
                        local vs, fs = {}, {}
                        for i, v in ipairs(vals) do vs[#vs + 1] = fmt(v) fs[#fs + 1] = tostring(frames[i]) end
                        log(string.format("  %s: %s  555 = %s  (per-cycle: %s, frames %s, spread %.5f)",
                            d, consistent and "CONSISTENT (real clip)" or "INCONSISTENT (check per-cycle log, may include a stall)",
                            fmt(mean), table.concat(vs, " "), table.concat(fs, " "), hi - lo))
                    end
                end
                log(string.format("=== ELEVATION LIMITS (raw 555, rough deg at %.3f/deg): see SUMMARY lines above", MARK_PER_DEG_EL))
                log("  PROBE DONE. Re-copy the production Export.lua afterwards.")
                phase = "FINISHED"
            end
            return
        end
    end)
    if not ok then
        aborted = true
        log("  UNCAUGHT ERROR in frame callback: " .. tostring(err))
        pcall(centre_all)
    end
end
