--[[
PILOT PTT / SPU-8 PROBE -- not the production script.

Answers the one open question behind srs-adapter Slice 3's push-to-talk gate:
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
  1. Get in the Mi-24P pilot seat, engines running or not (doesn't matter).
  2. Leave the controls alone for the first ~5s (log settles).
  3. Pull the trigger to the INTERCOM half-press stop, hold ~1s, release.
  4. Pull the trigger to the full/radio press, hold ~1s, release.
  5. Do one deliberately SHORT press (<200ms) of each stage, to test whether
     a brief press is ever missed at this poll rate.
  6. Cycle the SPU-8 selector through a couple of positions.
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
local ARG_SPU8_MODE = 455
local ARG_SPU8_EXT = 456

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
local sample_count = 0
local SAMPLE_LIMIT = 4000 -- ~13 min at every-frame logging on change only; bounded log size

function LuaExportStart()
    log("=== probe-ptt start ===")
end

function LuaExportAfterNextFrame()
    if sample_count >= SAMPLE_LIMIT then
        return
    end
    local ptt = read_arg(ARG_PTT)
    -- Always log the very first sample, then only on change -- a
    -- continuous-value arg logged every frame would flood the file, but a
    -- missed transition would be exactly the bug this probe exists to catch.
    if last_ptt == nil or ptt == nil or math.abs((ptt or -999) - (last_ptt or -999)) > 0.001 then
        local spu8_mode = read_arg(ARG_SPU8_MODE)
        local spu8_ext = read_arg(ARG_SPU8_EXT)
        sample_count = sample_count + 1
        log(string.format(
            "#%d t_model=%s ptt(738)=%s spu8_mode(455)=%s spu8_ext(456)=%s",
            sample_count,
            tostring(safe_model_time()),
            tostring(ptt),
            tostring(spu8_mode),
            tostring(spu8_ext)
        ))
        last_ptt = ptt
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
