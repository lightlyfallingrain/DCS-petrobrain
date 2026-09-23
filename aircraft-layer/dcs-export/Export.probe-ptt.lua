-- SCOPE WIDENED (user, 2026-09-19): the Mi-24P has TWO half-trigger bindings in
-- DCS -- one opens the radio menu, one is VOIP PTT -- and this project binds to
-- the VOIP one, because the radio-menu half-trigger is already spoken for by the
-- F10 command path. So this probe must not just confirm arg 738 moves; it must
-- establish WHICH readable argument corresponds to the VOIP half-trigger
-- specifically.
--
-- Method: with the log running, press each binding in turn and note the time,
-- then match against the samples below. Press the radio-menu half-trigger
-- several times, pause, then the VOIP half-trigger several times. If both drive
-- the same argument, the two cannot be told apart by value alone and the plan's
-- `listen`-token fallback comes back into play -- record that result plainly
-- rather than picking whichever looks convenient.

--[[
PILOT PTT / SPU-8 PROBE -- not the production script.

Answers the one open question behind audio-adapter Slice 3's push-to-talk gate:
does GetDevice(0):get_argument_value(738) actually reflect the pilot's
two-stage intercom/radio trigger on THIS installed DCS version, and does it
behave as a continuous "held" value (not an edge-triggered pulse) at the
frame rate LuaExportAfterNextFrame runs at?

WHERE THIS CAME FROM
  DCS-SimpleRadioStandalone's own shipped exporter for this airframe
  (Scripts/DCS-SRS/Scripts/DCS-SRS-Modules/Mi24P.lua, fetched live from
  github.com/ciribob/DCS-SimpleRadioStandalone this session) reads the
  pilot's trigger as:
      local _pilotPTT = SR.getButtonPosition(738)
      -- SR.getButtonPosition(_args) = GetDevice(0):get_argument_value(_args)
  with observed values 0 (released), 0.5 (half-press -> intercom), and
  presumably ~1.0 (full press -> selected radio). GetDevice(0) is the same
  mainpanel object this project's own Export.lua/probes already use live
  (device 0, arg 874 for the 9K113 sight azimuth -- see
  aircraft-layer/research/2026-09-11-petrovich-detection-readout.md).
  Arg 738 itself is NOT in this project's own primary-source clickabledata
  dump (aircraft-layer/research/mi24p-command-surface.md) -- plausibly
  because it is HOTAS/axis-driven (a real trigger button), not a
  mouse-clickable cockpit element, so it never appears in a PTR/clickable
  enumeration. This probe is the live check that closes that gap.

  SRS also reads the SPU-8 mode selector at arg 455
  (SR.getSelectorPosition(455, 0.2)) and the hot-mic switch at arg 456
  (SR.getButtonPosition(456) >= 1.0) -- BOTH already independently confirmed
  present in this project's own clickabledata dump (SPU8-MODE-PTR = 455,
  SPU8-EXT-PTR = 456), which is strong cross-validation that the SRS source
  read for this session is accurate for this DCS version. This probe logs
  455/456 too, as a sanity check that the whole read is wired correctly
  before trusting the 738 reading.

HOW TO FLY IT
  0. PILOT SEAT. Arg 738 is the pilot's stick trigger
     (crew_member_access = {0}); the operator's is 856 and is logged
     separately below. From the front seat 738 reads 0 forever and the
     log looks identical to a dead argument.
  1. Get in the Mi-24P pilot seat, engines running or not (doesn't matter).
  2. Leave the controls alone for the first ~5s (log settles). The
     heartbeat below proves the read is alive while nothing is moving --
     without it, "nobody pressed anything" and "this argument does not
     exist" produce the same file.
  3. MOUSE FIRST, HOTAS SECOND. These test two different things and the
     probe cannot tell them apart afterwards:
       a. In the 3D cockpit, RIGHT-click the stick trigger, hold ~1s.
          Then LEFT-click it, hold ~1s. clickabledata declares
          STICK-PTT-PTR as arg 738 with LMB = 1.0 and RMB = 0.5, so this
          tests THE ARGUMENT with no binding involved.
       b. Then the same two presses on the HOTAS. This tests YOUR
          BINDING -- whether the key you press drives that cockpit
          control at all, or is a DCS game action that never animates it.
     If (a) moves 738 and (b) does not, the argument is right and the
     binding is the problem, which is a completely different fix from
     re-deriving the argument number.
  4. Do one deliberately SHORT press (<200ms) of each stage, to test whether
     a brief press is ever missed at this poll rate.
  5. Cycle the SPU-8 selector through a couple of positions.
  6. Stay in the mission at least a minute. A 15-second run answers
     nothing.
  Bring back Logs\aircraft_layer_probe_ptt.log.

WHAT TO LOOK FOR
  - Does arg 738 move at all? (If it never leaves 0.000, the arg number is
    wrong for this version/seat and needs re-derivation.)
  - Does it read ~0.5 during the intercom half-press and a different value
    (SRS assumes ~1.0) during the full press?
  - Is every deliberate press (including the short one) represented by at
    least one non-zero sample? (This is the momentary-control / tick-rate
    question -- LuaExportAfterNextFrame runs every DCS frame, so even a
    ~150ms press should span several samples; only a press shorter than one
    frame could be missed entirely, and this probe's short-press step is
    still comfortably longer than that.)
]]

local LOG_PATH = lfs.writedir() .. "Logs\\aircraft_layer_probe_ptt.log"

local log_file = nil
local function log(msg)
    if log_file == nil then
        local ok, f = pcall(io.open, LOG_PATH, "a")
        if not ok or f == nil then
            return
        end
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

local DEV_MAINPANEL = 0
local ARG_PTT = 738
local ARG_PTT_OPERATOR = 856
local ARG_SPU8_MODE = 455
local ARG_SPU8_EXT = 456

-- Log a line this often even when nothing changes. The first run of this
-- probe produced a single sample and a stop, which is exactly what a dead
-- argument, an empty cockpit and a 15-second session all look like when
-- the file only records transitions. A heartbeat makes "alive and reading
-- zero" a visible state.
local HEARTBEAT_S = 5.0

local function read_arg(arg)
    local mp = try("GetDevice(0)", GetDevice, DEV_MAINPANEL)
    if mp == nil then
        return nil
    end
    local fn = mp.get_argument_value
    if type(fn) ~= "function" then
        return nil
    end
    return try("get_argument_value(" .. arg .. ")", fn, mp, arg)
end

local last_ptt = nil
local last_heartbeat = nil
local sample_count = 0
local SAMPLE_LIMIT = 4000 -- ~13 min at every-frame logging on change only; bounded log size

function LuaExportStart()
    log("=== probe-ptt start ===")
    log("    pilot seat required -- 738 is crew_member_access {0}; 856 is the operator's")
    log("    mouse-click the 3D trigger first (RMB = 0.5, LMB = 1.0), then the HOTAS")
end

function LuaExportAfterNextFrame()
    if sample_count >= SAMPLE_LIMIT then
        return
    end
    local ptt = read_arg(ARG_PTT)
    local now = safe_model_time() or 0
    local changed = last_ptt == nil or ptt == nil
        or math.abs((ptt or -999) - (last_ptt or -999)) > 0.001
    local beat = last_heartbeat == nil or (now - last_heartbeat) >= HEARTBEAT_S
    -- Log every change, plus a heartbeat. A continuous-value arg logged
    -- every frame would flood the file; a missed transition would be the
    -- bug this probe exists to catch; and a file with no heartbeat cannot
    -- distinguish a dead argument from an uneventful session.
    if changed or beat then
        local ptt_op = read_arg(ARG_PTT_OPERATOR)
        local spu8_mode = read_arg(ARG_SPU8_MODE)
        local spu8_ext = read_arg(ARG_SPU8_EXT)
        sample_count = sample_count + 1
        log(string.format(
            "#%d %s t_model=%s ptt(738)=%s op_ptt(856)=%s spu8_mode(455)=%s spu8_ext(456)=%s",
            sample_count,
            changed and "CHANGE " or "beat   ",
            tostring(now),
            tostring(ptt),
            tostring(ptt_op),
            tostring(spu8_mode),
            tostring(spu8_ext)
        ))
        last_ptt = ptt
        if beat then
            last_heartbeat = now
        end
    end
end

function safe_model_time()
    local ok, t = pcall(LoGetModelTime)
    if not ok then
        return nil
    end
    return t
end

function LuaExportStop()
    log("=== probe-ptt stop ===")
end
