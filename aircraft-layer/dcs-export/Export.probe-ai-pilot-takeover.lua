--[[
BL-16 PARKED MODE -- TAKEOVER REHEARSAL PROBE. Not the production script.

Deploy: copy this file over `Saved Games\DCS\Scripts\Export.lua`; restore
the real `Export.lua` afterwards. Self-contained -- does NOT need the
collector. Appends to `Logs\aircraft_layer_probe_ai_pilot_takeover.log`.

WHY: rehearses the takeover sequence the pilot settled on 2026-11-16
(`docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`, "Explore, round
2"), end to end, and measures the two numbers the plan still lacks.

  T1  takeover: arg 852 rising (operator-seat "Request Aircraft Control";
      arg 952 is only its mirror) -> CENTRE_PRESS_DELAY_S later one centre
      press with the menu CLOSED (radar -> baro, stops ED's sink) -> open
      the command menu -> read the baro target against actual MSL.
  T2  correct: if the target is more than TARGET_TOLERANCE_M off actual
      MSL, hold UP or DOWN and watch the readback every frame; release on
      reaching the target (or crossing it). Then a 20 s altitude trace.
  T3  hold rate: hold UP HOLD_RATE_S, then DOWN HOLD_RATE_S, readback
      sampled every HOLD_SAMPLE_S -- does a held press accelerate?
      Then T2 again to put the target back on actual.
  T4  centre press with the menu OPEN, as a real SHORT_PULSE_S pulse (the
      first re-fly's same-frame press did not toggle with the menu open).
      Whatever happens, ends back on baro (close -> centre -> reopen if
      needed) and runs T2 again.
  T5  keep-open: from here until you take control back, whenever the
      menu reads closed for MENU_CLOSED_FRAMES frames the probe reopens
      it and logs how long that took. **Close the menu by hand a few
      times once you see the AI settle** -- that is the test.

HOW TO FLY IT: air start, straight and level, operator seat. Wait ~10 s,
then "Request Aircraft Control". Hands off; T1-T4 take about two
minutes, mostly T2 waiting on the AI. Then close the menu by hand 2-3
times, a few seconds apart. Take control back to end; that aborts
cleanly at any point and releases any held press.

Never presses short right (HDG LOS, E-P6). Device 30 commands as in the
P0 probe: ShowMenu 3001, Up 3004, Down 3005, centre 3015.
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_ai_pilot_takeover.log"

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

-- ---------------------------------------------------------------- constants
local DEV_MAINPANEL = 0
local DEV_HELPER_AI = 30
local HELPERAI_DEVICE_ID = 6

local WHEEL_SHOW_MENU = 3001
local WHEEL_UP = 3004
local WHEEL_DOWN = 3005
local WHEEL_CENTRE = 3015

local ARG_STICK_PARK = 852
local ARG_PEDALS_PARK = 952
local PARK_THRESHOLD = 0.9

local START_DELAY_S = 5.0
local CENTRE_PRESS_DELAY_S = 0.5      -- pilot: "I'd put a half second delay there"
local MENU_OPEN_DELAY_S = 1.0         -- after takeover; centre press goes first
local SETTLE_S = 1.0                  -- readback settle before a decision read
local TARGET_TOLERANCE_M = 20.0       -- same 20 m as production's nudge epsilon
local CORRECT_TIMEOUT_S = 90.0
local CORRECT_TRACE_EVERY_S = 0.5
local AFTER_CORRECT_TRACE_S = 20.0
local HOLD_RATE_S = 5.0
local HOLD_SAMPLE_S = 0.25
local SHORT_PULSE_S = 0.15
local MENU_CLOSED_FRAMES = 3

-- ------------------------------------------------------------ overlay parse
-- Same flattening as production `parse_helperai_overlay_fields` and the P0
-- probe, duplicated because this file is deployed standalone.
local function parse_overlay_fields(raw)
    local lines = {}
    for line in (raw .. "\n"):gmatch("([^\n]*)\n") do
        lines[#lines + 1] = line
    end
    local n = #lines
    local fields = {}

    local function parse_nodes(start)
        local i = start
        while i <= n do
            local line = lines[i]
            if line == "" then
                i = i + 1
            elseif line == "}" then
                return i
            elseif line ~= "-----------------------------------------" then
                i = i + 1
            else
                i = i + 1
                if i > n then break end
                local name = lines[i]
                i = i + 1
                local value = nil
                if i <= n and lines[i] == "children are {" then
                    i = i + 1
                elseif i <= n then
                    value = lines[i]
                    i = i + 1
                    if i <= n and lines[i] == "children are {" then
                        i = i + 1
                    end
                end
                if value ~= nil then
                    fields[name] = value
                end
                i = parse_nodes(i)
                if i <= n and lines[i] == "}" then
                    i = i + 1
                end
            end
        end
        return i
    end

    parse_nodes(1)
    return fields
end

local function read_overlay()
    local raw = try("list_indication", list_indication, HELPERAI_DEVICE_ID)
    if raw == nil then return {} end
    return parse_overlay_fields(raw)
end

local function overlay_summary(f)
    return string.format("mode=%s course=%s alt=%s alt_ref=%s speed=%s",
        tostring(f.mode_text), tostring(f.course_text), tostring(f.alt_text),
        tostring(f.alt_add_text), tostring(f.speed_text))
end

local function menu_reads_open(f)
    return f.mode_text ~= nil
end

local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then return nil end
    return try("get_argument_value", mp.get_argument_value, mp, arg)
end

local function is_parked()
    local v = read_arg(ARG_STICK_PARK)
    return type(v) == "number" and v >= PARK_THRESHOLD
end

local function msl()
    return try("LoGetAltitudeAboveSeaLevel", LoGetAltitudeAboveSeaLevel)
end

local function agl()
    return try("LoGetAltitudeAboveGroundLevel", LoGetAltitudeAboveGroundLevel)
end

local function press(cmd, value)
    local dev = try("GetDevice(30)", GetDevice, DEV_HELPER_AI)
    if dev == nil then return end
    try("performClickableAction", dev.performClickableAction, dev, cmd, value)
end

-- Same-frame press/release: proven to toggle ALT REF with the menu closed
-- and to open/close the menu (P0 re-fly).
local function tap(cmd)
    press(cmd, 1)
    press(cmd, 0)
end

-- ------------------------------------------------------------- held press
local held_cmd = nil

local function hold_start(cmd)
    press(cmd, 1)
    held_cmd = cmd
end

local function hold_release()
    if held_cmd ~= nil then
        press(held_cmd, 0)
        held_cmd = nil
    end
end

local function hold_name(cmd)
    if cmd == WHEEL_UP then return "UP" end
    if cmd == WHEEL_DOWN then return "DOWN" end
    return tostring(cmd)
end

-- ================================================================ steps
-- Each step is a table with `run(st, t)` returning true when done; `st`
-- is that step's own fresh state, `st.t0` its start time.

local function banner(title)
    log("")
    log("=========================================================")
    log(title)
    log("=========================================================")
end

-- --- T1: takeover sequence.
local function run_takeover(st, t)
    local e = t - st.t0
    if st.stage == nil then
        banner("T1: takeover -- centre press (menu closed), then open menu")
        log(string.format("  on takeover: %s  agl=%s msl=%s  arg852=%s arg952=%s",
            overlay_summary(read_overlay()), tostring(agl()), tostring(msl()),
            tostring(read_arg(ARG_STICK_PARK)), tostring(read_arg(ARG_PEDALS_PARK))))
        st.stage = "wait_centre"
        return false
    end
    if st.stage == "wait_centre" and e >= CENTRE_PRESS_DELAY_S then
        tap(WHEEL_CENTRE)
        log(string.format("  +%.2fs centre tap (menu closed)  msl=%s", e, tostring(msl())))
        st.stage = "wait_open"
        return false
    end
    if st.stage == "wait_open" and e >= MENU_OPEN_DELAY_S then
        -- ShowMenu is a toggle: only press it if the menu is not already
        -- open, or it would close it.
        if menu_reads_open(read_overlay()) then
            log(string.format("  +%.2fs menu already open -- not toggling", e))
        else
            tap(WHEEL_SHOW_MENU)
            log(string.format("  +%.2fs menu toggle (opening)", e))
        end
        st.stage = "wait_read"
        st.t_open = t
        return false
    end
    if st.stage == "wait_read" and t - st.t_open >= SETTLE_S then
        local f = read_overlay()
        local m = msl()
        log(string.format("  +%.2fs read: %s  actual msl=%s", e, overlay_summary(f), tostring(m)))
        if not menu_reads_open(f) then
            log("  WARNING: menu does not read open")
        end
        local target = tonumber(f.alt_text)
        if target ~= nil and type(m) == "number" then
            log(string.format("  baro target error: %+.0f m (target %.0f, actual %.0f)",
                target - m, target, m))
        end
        return true
    end
    return false
end

-- --- T2: drive the baro target to actual MSL by a held press.
local function run_correct(st, t)
    local e = t - st.t0
    local f = read_overlay()
    local target = tonumber(f.alt_text)
    local m = msl()
    if st.stage == nil then
        banner("T2: correct the baro target to actual MSL (closed-loop hold)")
        if target == nil or type(m) ~= "number" then
            log("  cannot read target/actual -- skipping: " .. overlay_summary(f))
            return true
        end
        if f.alt_add_text ~= "B" then
            log("  WARNING: reference is " .. tostring(f.alt_add_text) .. ", not B")
        end
        local err = target - m
        log(string.format("  start: target=%.0f actual=%.0f error=%+.0f m", target, m, err))
        if math.abs(err) <= TARGET_TOLERANCE_M then
            log("  within tolerance -- no hold needed")
            st.stage = "trace"
            st.t_trace = t
            st.samples = {}
            return false
        end
        st.dir = (err > 0) and WHEEL_DOWN or WHEEL_UP
        st.sign = (err > 0) and 1 or -1
        st.start_target = target
        st.trace = {}
        st.last_trace_e = -1
        hold_start(st.dir)
        log(string.format("  holding %s", hold_name(st.dir)))
        st.t_hold = t
        st.stage = "holding"
        return false
    end
    if st.stage == "holding" then
        local he = t - st.t_hold
        if target ~= nil and he - st.last_trace_e >= CORRECT_TRACE_EVERY_S then
            st.trace[#st.trace + 1] = string.format("%.1fs:%.0f", he, target)
            st.last_trace_e = he
        end
        local done_reason = nil
        if target ~= nil and type(m) == "number" then
            local err = target - m
            if math.abs(err) <= TARGET_TOLERANCE_M then
                done_reason = "reached tolerance"
            elseif err * st.sign < 0 then
                done_reason = "crossed actual"
            end
        end
        if he >= CORRECT_TIMEOUT_S then
            done_reason = "timeout"
        end
        if done_reason ~= nil then
            hold_release()
            log(string.format("  released after %.2fs: %s", he, done_reason))
            log("  target while held: " .. table.concat(st.trace, " "))
            if target ~= nil then
                log(string.format("  mean rate while held: %.1f m/s",
                    math.abs(target - st.start_target) / math.max(he, 0.001)))
            end
            st.stage = "settle"
            st.t_settle = t
        end
        return false
    end
    if st.stage == "settle" then
        if t - st.t_settle < SETTLE_S then return false end
        log(string.format("  after release: %s  actual msl=%s", overlay_summary(f), tostring(m)))
        st.stage = "trace"
        st.t_trace = t
        st.samples = {}
        return false
    end
    if st.stage == "trace" then
        local te = t - st.t_trace
        if #st.samples == 0 or te - st.samples[#st.samples].t >= 2.0 then
            st.samples[#st.samples + 1] = { t = te, msl = m, target = target }
        end
        if te < AFTER_CORRECT_TRACE_S then return false end
        local parts = {}
        for _, s in ipairs(st.samples) do
            parts[#parts + 1] = string.format("%.0fs:%.0f/%s", s.t, tonumber(s.msl) or -1,
                tostring(s.target))
        end
        log("  20s trace (actual msl / target): " .. table.concat(parts, " "))
        return true
    end
    return false
end

-- --- T3: hold rate, UP then DOWN.
local function run_hold_rate(st, t)
    local f = read_overlay()
    local target = tonumber(f.alt_text)
    if st.stage == nil then
        banner(string.format("T3: hold rate -- UP %.0fs, then DOWN %.0fs", HOLD_RATE_S, HOLD_RATE_S))
        st.stage = "up"
        st.samples = {}
        st.t_hold = t
        st.last = -1
        hold_start(WHEEL_UP)
        return false
    end
    local he = t - st.t_hold
    if (st.stage == "up" or st.stage == "down") then
        if target ~= nil and he - st.last >= HOLD_SAMPLE_S then
            st.samples[#st.samples + 1] = string.format("%.2fs:%.0f", he, target)
            st.last = he
        end
        if he >= HOLD_RATE_S then
            hold_release()
            log(string.format("  %s held %.2fs: %s", string.upper(st.stage), he,
                table.concat(st.samples, " ")))
            st.next = (st.stage == "up") and "down" or "done"
            st.stage = "settle"
            st.t_settle = t
        end
        return false
    end
    if st.stage == "settle" then
        if t - st.t_settle < SETTLE_S then return false end
        log("  after release: " .. overlay_summary(f))
        if st.next == "done" then return true end
        st.stage = "down"
        st.samples = {}
        st.t_hold = t
        st.last = -1
        hold_start(WHEEL_DOWN)
        return false
    end
    return false
end

-- --- T4: centre press with the menu open, as a real pulse.
local function run_open_centre(st, t)
    local f = read_overlay()
    if st.stage == nil then
        banner(string.format("T4: centre press, menu OPEN, %.2fs pulse", SHORT_PULSE_S))
        st.before_ref = f.alt_add_text
        log("  before: " .. overlay_summary(f))
        press(WHEEL_CENTRE, 1)
        st.t_press = t
        st.stage = "pressing"
        return false
    end
    if st.stage == "pressing" then
        if t - st.t_press < SHORT_PULSE_S then return false end
        press(WHEEL_CENTRE, 0)
        st.stage = "settle"
        st.t_settle = t
        return false
    end
    if st.stage == "settle" then
        if t - st.t_settle < SETTLE_S then return false end
        log("  after pulse: " .. overlay_summary(f))
        if f.alt_add_text ~= st.before_ref then
            log("  RESULT: open-menu centre pulse DID toggle ALT REF")
        else
            log("  RESULT: open-menu centre pulse did NOT toggle ALT REF")
        end
        if f.alt_add_text == "B" then
            return true
        end
        -- Back to baro the proven way: close, same-frame centre, reopen.
        log("  restoring baro: close menu, centre tap, reopen")
        tap(WHEEL_SHOW_MENU)
        st.stage = "closed"
        st.t_step = t
        return false
    end
    if st.stage == "closed" then
        if t - st.t_step < SETTLE_S then return false end
        tap(WHEEL_CENTRE)
        st.stage = "toggled"
        st.t_step = t
        return false
    end
    if st.stage == "toggled" then
        if t - st.t_step < SETTLE_S then return false end
        tap(WHEEL_SHOW_MENU)
        st.stage = "reopened"
        st.t_step = t
        return false
    end
    if st.stage == "reopened" then
        if t - st.t_step < SETTLE_S then return false end
        log("  after restore: " .. overlay_summary(f))
        return true
    end
    return false
end

-- --- T5: keep the menu open until the pilot takes control back.
local function run_keep_open(st, t)
    if st.stage == nil then
        banner("T5: keep-open -- close the menu by hand; the probe reopens it")
        st.stage = "watch"
        st.closed_frames = 0
        st.reopens = 0
        return false
    end
    local f = read_overlay()
    if st.stage == "watch" then
        if menu_reads_open(f) then
            st.closed_frames = 0
            return false
        end
        st.closed_frames = st.closed_frames + 1
        if st.closed_frames == 1 then
            st.t_closed = t
        end
        if st.closed_frames >= MENU_CLOSED_FRAMES then
            tap(WHEEL_SHOW_MENU)
            st.reopens = st.reopens + 1
            st.t_reopen = t
            st.stage = "reopening"
            log(string.format("  reopen #%d: closed seen for %d frames (%.3fs), toggling open",
                st.reopens, st.closed_frames, t - st.t_closed))
        end
        return false
    end
    if st.stage == "reopening" then
        if menu_reads_open(f) then
            log(string.format("  reopen #%d: reads open %.3fs after the toggle (%.3fs after close)",
                st.reopens, t - st.t_reopen, t - st.t_closed))
            st.stage = "watch"
            st.closed_frames = 0
        elseif t - st.t_reopen > 2.0 then
            log(string.format("  reopen #%d: still reads closed 2s after the toggle", st.reopens))
            st.stage = "watch"
            st.closed_frames = 0
        end
        return false
    end
    return false  -- runs until the pilot takes control back
end

-- ============================================================== driver
local STEPS = {
    { name = "takeover", run = run_takeover },
    { name = "correct", run = run_correct },
    { name = "hold_rate", run = run_hold_rate },
    { name = "correct", run = run_correct },
    { name = "open_centre", run = run_open_centre },
    { name = "correct", run = run_correct },
    { name = "keep_open", run = run_keep_open },
}

local started, t0 = false, nil
local phase = "wait_park"   -- wait_park | steps | aborted
local was_parked = false
local last_args = nil
local step_idx, step_state = 1, nil

function LuaExportStart()
    log("")
    log("#########################################################")
    log("BL-16 TAKEOVER REHEARSAL PROBE")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    hold_release()
    log("takeover probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log(string.format("  waiting %.0fs to settle, then for Request Aircraft Control", START_DELAY_S))
        return
    end
    if t - t0 < START_DELAY_S then return end

    if phase == "wait_park" then
        local a852, a952 = read_arg(ARG_STICK_PARK), read_arg(ARG_PEDALS_PARK)
        local args = string.format("arg852=%s arg952=%s", tostring(a852), tostring(a952))
        if args ~= last_args and (last_args == nil or is_parked()) then
            log(string.format("  t=%.1f: %s", t, args))
        end
        last_args = args
        local parked_now = is_parked()
        if parked_now and not was_parked then
            log(string.format("  t=%.1f: takeover (arg 852 >= %.1f)", t, PARK_THRESHOLD))
            phase = "steps"
            step_idx = 1
            step_state = { t0 = t }
        end
        was_parked = parked_now
        return
    end

    if phase == "aborted" then return end

    if not is_parked() then
        hold_release()
        phase = "aborted"
        log("")
        log(string.format("*** t=%.1f: control taken back -- held press released, probe idle ***", t))
        return
    end

    local step = STEPS[step_idx]
    if step == nil then return end
    if step.run(step_state, t) then
        step_idx = step_idx + 1
        step_state = { t0 = t }
        if STEPS[step_idx] == nil then
            log("")
            log("SEQUENCE COMPLETE")
        end
    end
end
