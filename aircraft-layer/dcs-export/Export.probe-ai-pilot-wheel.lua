--[[
BL-16 MODE 2 STAGE P0 PROBE -- AI-PILOT WHEEL MEASUREMENTS. Not the
production script.

Deploy: copy this file over `Saved Games\DCS\Scripts\Export.lua`; restore
the real `Export.lua` afterwards. Self-contained, like `Export.probe-
wheel.lua`/`Export.probe-9k113-flicker.lua` -- does NOT need the
collector. Appends to `Logs\aircraft_layer_probe_ai_pilot_wheel.log`.

PLAN: `plans/flight-control/plan.md`, "Revised 2026-11-15", Stage P0's
own table (P0-1..P0-7). Closes the handful of items the desk recon
(`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md`)
flags `[inference]`/unverified, with one short flight.

HOW TO FLY IT (`project_probes_flown_air_start`): **air start, straight
and level**, operator seat, ED's AI not yet flying. Let the aircraft
settle a few seconds, then hand control to the AI with the operator-seat
binding **"Request Aircraft Control"** (category "Petrovich AI Helper,
Multicrew") -- that is what moves arg 852; "Copilot Stick - PARK/UNPARK"
does nothing (user, 2026-11-16). The probe waits for that rising edge
before doing anything. Leave it alone after that; it runs every row
itself, one at a time, logging before/after readbacks. Stay handed over
throughout -- taking control back mid-sequence aborts it (see "ABORT").

REVISED 2026-11-16 after the first flight
(`docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`):
- The AI's readback is in `list_indication(6)` only with the command menu
  open (P0-1, measured). The first version closed the menu again after
  P0-1, so P0-2..P0-7 read nothing. P0-1 now ends with the menu OPEN and
  it stays open for P0-2..P0-7; a final step closes it.
- Presses work with the menu closed (pilot: the AI reacted), so P0-6 now
  tests the pilot's fix instead of re-measuring the sink: one centre
  press (ALT REF toggle) `P06_FIX_DELAY_S` after takeover, menu closed,
  then a 20 s trace of AGL and MSL. The pilot chose barometric, and the AI
  starts on radar, so one press should leave it holding current MSL.
- `ensure_mode` pressed up to three times in one frame without waiting
  for the readback; it is now one press per `MODE_READ_SETTLE_S`.
- P0-5 presses centre twice with the menu open, reading both flips.
- Args 852 and 952 are logged while waiting and through P0-6, to explain
  why production Batch A read "not parked" during the P1 flight.

**Never presses short right (3002 held < 0.5 s).** E-P6 (`HDG LOS` must
never be pressed by code) applies to this probe exactly as it does to
production: every row below either long-holds Right (heading CW, FLT/
HVR's outer-ring option) or never touches Right at all. If a row would
need the short-right press, it is skipped and logged as "skipped: would
need short-right, forbidden" rather than silently working around it.

ABORT: every phase checks the park signal (arg 852) each frame. If it
drops below the threshold, any open press is released immediately (the
same frame) and the whole sequence halts -- the probe keeps logging
passively but issues no further presses, so handing control back always
works regardless of which row was running.

WHEEL DEVICE: device 30 (HELPER_AI), the same device/commands Petrovich's
own search wheel already uses -- ShowMenu 3001, Right 3002, Left 3003,
Up 3004, Down 3005, centre (Select_or_fireEXT) 3015. Short press (<0.5s
hold) reaches the inner-ring option, long press/hold reaches the
outer-ring option (research note section 5).
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_ai_pilot_wheel.log"

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

local WHEEL_SHOW_MENU = 3001
local WHEEL_RIGHT = 3002
local WHEEL_LEFT = 3003
local WHEEL_UP = 3004
local WHEEL_DOWN = 3005
local WHEEL_CENTRE = 3015

local ARG_STICK_PARK = 852
local ARG_PEDALS_PARK = 952
local PARK_THRESHOLD = 0.9

-- The pilot's fix for ED's park sink (2026-11-16): "I'd put a half second
-- delay there" -- one centre press this long after takeover.
local P06_FIX_DELAY_S = 0.5

local HELPERAI_DEVICE_ID = 6

local LONG_PRESS_HOLD_S = 0.7
local SHORT_PRESS_PULSE_S = 0.15
local MODE_READ_SETTLE_S = 1.0
local MODE_CYCLE_MAX_ATTEMPTS = 3

local START_DELAY_S = 5.0

-- ------------------------------------------------------------ overlay parse
-- Same flattening algorithm as the production `parse_helperai_overlay_
-- fields` (mirrors `aircraft-layer/src/schema/petrovich_indication.py`'s
-- `parse_indication_text`) -- duplicated here rather than shared, since
-- this probe is deployed standalone and the production file is restored
-- afterwards (the two files never coexist as the deployed `Export.lua`).
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

local function overlay_summary(fields)
    return string.format(
        "mode=%s course=%s alt=%s alt_ref=%s speed=%s",
        tostring(fields.mode_text), tostring(fields.course_text),
        tostring(fields.alt_text), tostring(fields.alt_add_text),
        tostring(fields.speed_text))
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

local function press(cmd, value)
    local dev = try("GetDevice(30)", GetDevice, DEV_HELPER_AI)
    if dev == nil then return end
    try("performClickableAction", dev.performClickableAction, dev, cmd, value)
end

-- --------------------------------------------------------- abort machinery
-- Any long-hold press currently open (cmd, released by abort or by its
-- own timeout) -- a single slot, since this probe never opens two
-- presses at once.
local open_press_cmd = nil
local open_press_release_t = nil
local aborted = false

local function release_open_press()
    if open_press_cmd ~= nil then
        press(open_press_cmd, 0)
        open_press_cmd = nil
        open_press_release_t = nil
    end
end

local function open_long_hold(cmd, t)
    press(cmd, 1)
    open_press_cmd = cmd
    open_press_release_t = t + LONG_PRESS_HOLD_S
end

local function check_abort(t)
    if aborted then return true end
    if open_press_release_t ~= nil and t >= open_press_release_t then
        release_open_press()
    end
    if not is_parked() then
        release_open_press()
        aborted = true
        log("")
        log("*** ABORTED: controls unparked -- no further presses will be issued ***")
        return true
    end
    return false
end

local function fmt_arg(v)
    if type(v) ~= "number" then return tostring(v) end
    return string.format("%.2f", v)
end

local function park_args_summary()
    return string.format("arg852=%s arg952=%s",
        fmt_arg(read_arg(ARG_STICK_PARK)), fmt_arg(read_arg(ARG_PEDALS_PARK)))
end

-- ------------------------------------------------------- mode-cycle helper
-- Non-blocking, one call per frame: one short-left press, then wait
-- MODE_READ_SETTLE_S for the readback before reading it again, bounded by
-- MODE_CYCLE_MAX_ATTEMPTS. The first version pressed up to three times in
-- a single frame and read back before the overlay could change. Returns
-- true once the target mode is read, or once it gives up. `st` is the
-- calling row's own `{ attempts = 0 }` table.
local function step_ensure_mode(st, target_mode, t, phase_log_prefix)
    if st.done then return true end
    if st.press_t ~= nil and t - st.press_t < MODE_READ_SETTLE_S then
        return false
    end
    local fields = read_overlay()
    if fields.mode_text == target_mode then
        st.done = true
        return true
    end
    if st.attempts >= MODE_CYCLE_MAX_ATTEMPTS then
        log(string.format("%s WARNING: could not reach mode %s after %d attempts (now %s)",
            phase_log_prefix, target_mode, st.attempts, tostring(fields.mode_text)))
        st.done = true
        return true
    end
    log(string.format("%s mode is %s, cycling toward %s (attempt %d)",
        phase_log_prefix, tostring(fields.mode_text), target_mode, st.attempts + 1))
    press(WHEEL_LEFT, 1)
    press(WHEEL_LEFT, 0)
    st.press_t = t
    st.attempts = st.attempts + 1
    return false
end

-- =============================================================== sequence
-- One phase at a time; each phase's own `run` returns true when done.
-- `t_phase` is reset to the current `t` whenever a phase transition
-- happens, so each phase's own internal waits are relative to its start.
local phase = "wait_park"
local t_phase = nil

-- --- P0-6: the pilot's park-sink fix. Runs first -- the only row that
-- needs the takeover *transition* itself. One centre press (ALT REF
-- toggle) P06_FIX_DELAY_S after takeover, menu closed, then 20 s of AGL
-- and MSL. Pass: the reference it lands on stays flat (MSL if it flipped
-- radar -> baro), no sink. The first flight measured the unfixed sink
-- (190 -> 73 m AGL in 20 s), so it is not re-measured.
local p06 = { pressed = false, samples = {} }

local function run_p0_6(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("=========================================================")
        log(string.format("P0-6: park-sink fix -- centre press %.1fs after takeover, menu closed",
            P06_FIX_DELAY_S))
        log("=========================================================")
        local fields = read_overlay()
        local alt_agl = try("LoGetAltitudeAboveGroundLevel", LoGetAltitudeAboveGroundLevel)
        local alt_msl = try("LoGetAltitudeAboveSeaLevel", LoGetAltitudeAboveSeaLevel)
        log(string.format("  on takeover: overlay=%s  actual_agl=%s actual_msl=%s  %s",
            overlay_summary(fields), tostring(alt_agl), tostring(alt_msl), park_args_summary()))
        return false
    end

    local elapsed = t - t_phase
    if not p06.pressed and elapsed >= P06_FIX_DELAY_S then
        press(WHEEL_CENTRE, 1)
        press(WHEEL_CENTRE, 0)
        p06.pressed = true
        log(string.format("  centre press issued at +%.2fs (menu closed)", elapsed))
    end
    if elapsed <= 20.0 then
        if #p06.samples == 0 or elapsed - p06.samples[#p06.samples].t >= 1.0 then
            p06.samples[#p06.samples + 1] = {
                t = elapsed,
                agl = try("LoGetAltitudeAboveGroundLevel", LoGetAltitudeAboveGroundLevel),
                msl = try("LoGetAltitudeAboveSeaLevel", LoGetAltitudeAboveSeaLevel),
                args = park_args_summary(),
            }
        end
        return false
    end

    local alt_parts, arg_parts = {}, {}
    for _, s in ipairs(p06.samples) do
        alt_parts[#alt_parts + 1] = string.format("%.0fs:%.0f/%.0f",
            s.t, tonumber(s.agl) or -1, tonumber(s.msl) or -1)
        arg_parts[#arg_parts + 1] = string.format("%.0fs:%s", s.t, s.args)
    end
    log("  20s altitude trace (AGL/MSL m): " .. table.concat(alt_parts, " "))
    log("  20s park-arg trace: " .. table.concat(arg_parts, " | "))
    return true
end

-- --- P0-1: overlay content with the wheel closed vs open. Ends with the
-- menu OPEN, and P0-2..P0-7 rely on it staying open: the readback is in
-- `list_indication(6)` only while it is (first flight, 2026-11-16).
local p01 = { step = 0 }

local function toggle_menu()
    press(WHEEL_SHOW_MENU, 1)
    press(WHEEL_SHOW_MENU, 0)
end

local function run_p0_1(t)
    if t_phase == nil then t_phase = t end
    if t - t_phase < 1.0 then return false end
    if p01.step == 0 then
        local f = read_overlay()
        log("")
        log("=========================================================")
        log("P0-1: overlay content, wheel closed vs open (ends OPEN)")
        log("=========================================================")
        log("  as found (closed): " .. overlay_summary(f))
        toggle_menu()
        p01.step = 1
        t_phase = t
        return false
    elseif p01.step == 1 then
        if t - t_phase < MODE_READ_SETTLE_S then return false end
        log("  after one toggle (open): " .. overlay_summary(read_overlay()))
        toggle_menu()
        p01.step = 2
        t_phase = t
        return false
    elseif p01.step == 2 then
        if t - t_phase < MODE_READ_SETTLE_S then return false end
        log("  after second toggle (closed): " .. overlay_summary(read_overlay()))
        toggle_menu()
        p01.step = 3
        t_phase = t
        return false
    else
        if t - t_phase < MODE_READ_SETTLE_S then return false end
        local f = read_overlay()
        log("  after third toggle (open, held for P0-2..P0-7): " .. overlay_summary(f))
        if f.mode_text == nil then
            log("  WARNING: menu does not read as open -- later rows may read nil again")
        end
        return true
    end
end

-- --- P0-2: one held press (0.7s) on each outer-ring position in FLT.
local p02 = { idx = 0, holding = false, mode = { attempts = 0 } }
local P02_SEQ = {
    { "UP (altitude+)", WHEEL_UP },
    { "DOWN (altitude-)", WHEEL_DOWN },
    { "LEFT, long (heading CCW)", WHEEL_LEFT },
    { "RIGHT, long (heading CW)", WHEEL_RIGHT },
}

local function run_p0_2(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("=========================================================")
        log("P0-2: one 0.7s held press per outer position, in FLT")
        log("=========================================================")
        return false
    end
    if not step_ensure_mode(p02.mode, "FLT", t, "P0-2:") then
        return false
    end
    if not p02.holding then
        p02.idx = p02.idx + 1
        local row = P02_SEQ[p02.idx]
        if row == nil then return true end
        local before = read_overlay()
        log(string.format("  [%d] %s -- before: %s", p02.idx, row[1], overlay_summary(before)))
        open_long_hold(row[2], t)
        p02.holding = true
        t_phase = t
        return false
    end
    if open_press_release_t ~= nil and t < open_press_release_t then
        return false  -- still holding; check_abort's own timer releases it
    end
    if t - t_phase < LONG_PRESS_HOLD_S + MODE_READ_SETTLE_S then
        return false  -- wait for the overlay to settle after release
    end
    local after = read_overlay()
    log(string.format("      after:  %s", overlay_summary(after)))
    p02.holding = false
    t_phase = t
    return false
end

-- --- P0-3: speed tap sequence 0 .. MAX. Alternates press (sets
-- `press_t`) with a settled read (clears it) so each logged reading is
-- always at least `SHORT_PRESS_PULSE_S + MODE_READ_SETTLE_S` after its
-- own tap, never read back in the same frame it was pressed.
local p03 = { taps = 0, last_speed = nil, press_t = nil, started = false, mode = { attempts = 0 } }
local P03_MAX_TAPS = 10

local function run_p0_3(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("=========================================================")
        log("P0-3: speed tap sequence (short UP), reading speed_text")
        log("=========================================================")
        return false
    end
    if not step_ensure_mode(p03.mode, "FLT", t, "P0-3:") then
        return false
    end
    if not p03.started then
        p03.started = true
        p03.last_speed = read_overlay().speed_text
        log("  starting speed_text: " .. tostring(p03.last_speed))
        return false
    end
    if p03.press_t == nil then
        if p03.taps >= P03_MAX_TAPS then
            log("  stopped: reached the tap safety cap without the readback settling")
            return true
        end
        press(WHEEL_UP, 1)
        press(WHEEL_UP, 0)
        p03.press_t = t
        p03.taps = p03.taps + 1
        return false
    end
    if t - p03.press_t < SHORT_PRESS_PULSE_S + MODE_READ_SETTLE_S then
        return false
    end
    local f = read_overlay()
    log(string.format("  tap %d: speed_text = %s", p03.taps, tostring(f.speed_text)))
    if f.speed_text == p03.last_speed and p03.taps > 1 then
        log("  speed_text stopped changing -- taking this as MAX")
        return true
    end
    p03.last_speed = f.speed_text
    p03.press_t = nil
    return false
end

-- --- P0-4: press-release-to-readback-change latency.
local p04 = { pressed_t = nil, released_t = nil, before_speed = nil }

local function run_p0_4(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("=========================================================")
        log("P0-4: press-release-to-readback latency")
        log("=========================================================")
        local f = read_overlay()
        p04.before_speed = f.speed_text
        press(WHEEL_DOWN, 1)
        p04.pressed_t = t
        return false
    end
    if p04.released_t == nil then
        if t - p04.pressed_t >= SHORT_PRESS_PULSE_S then
            press(WHEEL_DOWN, 0)
            p04.released_t = t
        end
        return false
    end
    local f = read_overlay()
    if f.speed_text ~= p04.before_speed then
        log(string.format("  release -> readback change: %.3fs (before=%s after=%s)",
            t - p04.released_t, tostring(p04.before_speed), tostring(f.speed_text)))
        return true
    end
    if t - p04.released_t > 5.0 then
        log("  no readback change observed within 5s of release")
        return true
    end
    return false
end

-- --- P0-5: centre press (ALT REF toggle), twice, menu open -- reads both
-- flips and ends on the reference it started from.
local p05 = { presses = 0 }

local function run_p0_5(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("=========================================================")
        log("P0-5: centre press x2 (ALT REF radar/baro toggle), menu open")
        log("=========================================================")
        log("  before:        " .. overlay_summary(read_overlay()))
        press(WHEEL_CENTRE, 1)
        press(WHEEL_CENTRE, 0)
        p05.presses = 1
        return false
    end
    if t - t_phase < MODE_READ_SETTLE_S then return false end
    log(string.format("  after press %d: %s", p05.presses, overlay_summary(read_overlay())))
    if p05.presses >= 2 then
        return true
    end
    press(WHEEL_CENTRE, 1)
    press(WHEEL_CENTRE, 0)
    p05.presses = 2
    t_phase = t
    return false
end

-- --- P0-7: FLT -> HVR speed criterion. Same alternating press/settled-
-- read shape as P0-3 above.
local p07 = { taps = 0, press_t = nil, zero_since = nil, mode = { attempts = 0 } }
local P07_MAX_TAPS = 12

local function run_p0_7(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("=========================================================")
        log("P0-7: FLT -> HVR speed criterion (tap speed to 0, watch mode_text)")
        log("=========================================================")
        return false
    end
    if not step_ensure_mode(p07.mode, "FLT", t, "P0-7:") then
        return false
    end
    local f = read_overlay()
    if f.speed_text == "0" then
        if p07.zero_since == nil then p07.zero_since = t end
        if f.mode_text == "HVR" then
            log(string.format("  mode_text flipped to HVR %.1fs after speed reached 0",
                t - p07.zero_since))
            return true
        end
        if t - p07.zero_since > 15.0 then
            log("  speed at 0 for 15s with no automatic mode flip observed")
            return true
        end
        return false
    end
    if p07.press_t == nil then
        if p07.taps >= P07_MAX_TAPS then
            log("  stopped: reached the tap safety cap without reaching speed 0")
            return true
        end
        press(WHEEL_DOWN, 1)
        press(WHEEL_DOWN, 0)
        p07.press_t = t
        p07.taps = p07.taps + 1
        return false
    end
    if t - p07.press_t < SHORT_PRESS_PULSE_S + MODE_READ_SETTLE_S then
        return false
    end
    p07.press_t = nil
    return false
end

-- --- Final step: close the menu P0-1 left open, so the pilot is handed
-- back the normal view.
local function run_close_menu(t)
    if t_phase == nil then
        t_phase = t
        log("")
        log("closing the command menu (left open since P0-1)")
        toggle_menu()
        return false
    end
    if t - t_phase < MODE_READ_SETTLE_S then return false end
    log("  after close: " .. overlay_summary(read_overlay()))
    return true
end

-- ============================================================= driver
local SEQUENCE = {
    { name = "wait_park", run = nil },  -- handled specially below
    { name = "p0_6", run = run_p0_6 },
    { name = "p0_1", run = run_p0_1 },
    { name = "p0_2", run = run_p0_2 },
    { name = "p0_3", run = run_p0_3 },
    { name = "p0_4", run = run_p0_4 },
    { name = "p0_5", run = run_p0_5 },
    { name = "p0_7", run = run_p0_7 },
    { name = "close_menu", run = run_close_menu },
    { name = "done", run = nil },
}
local seq_idx = 1

local started, t0 = false, nil
local was_parked = false
-- Last logged park-arg readings while waiting, so a change is logged
-- once rather than every frame.
local last_args_logged = nil

function LuaExportStart()
    log("")
    log("#########################################################")
    log("BL-16 MODE 2 STAGE P0 PROBE -- AI-PILOT WHEEL")
    log("#########################################################")
    started = true
end

function LuaExportStop()
    log("ai-pilot-wheel probe: stopped.")
    if log_file then log_file:close() log_file = nil end
end

function LuaExportActivityNextEvent(t) return t + 1.0 end

function LuaExportAfterNextFrame()
    if not started then return end
    local t = try("LoGetModelTime", LoGetModelTime)
    if type(t) ~= "number" then return end
    if t0 == nil then
        t0 = t
        log(string.format("  waiting %.0fs to settle, then waiting for you to park",
            START_DELAY_S))
        return
    end
    if (t - t0) < START_DELAY_S then return end

    if SEQUENCE[seq_idx].name == "wait_park" then
        local args_now = park_args_summary()
        if args_now ~= last_args_logged then
            log(string.format("  t=%.1f: %s", t, args_now))
            last_args_logged = args_now
        end
        local parked_now = is_parked()
        if parked_now and not was_parked then
            log(string.format("  t=%.1f: park signal rising (arg 852) -- starting the sequence", t))
            seq_idx = seq_idx + 1
        end
        was_parked = parked_now
        return
    end

    if SEQUENCE[seq_idx].name == "done" then
        return
    end

    if check_abort(t) then
        return
    end

    local row = SEQUENCE[seq_idx]
    local done = row.run(t)
    if done then
        t_phase = nil
        seq_idx = seq_idx + 1
        if SEQUENCE[seq_idx].name == "done" then
            log("")
            log("#########################################################")
            log("SEQUENCE COMPLETE")
            log("#########################################################")
        end
    end
end
