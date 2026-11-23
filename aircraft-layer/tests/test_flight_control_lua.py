"""BL-16 mode 1 (unparked, raw axes), Stage M1 (`plans/flight-control/
plan.md`, "Revised 2026-11-18") -- `Petrobrain/flight_control.lua` run
against a real Lua interpreter, not just parsed.

**Technique**: rather than `test_sight_servo_lua.py`'s per-function
`_extract_lua_function` (flight_control.lua's functions close over many
module-level locals -- `fc_mode`, `fc_limits`, `SEAT_ARGS`, the captured-
axis table -- that per-function extraction would lose), this wraps the
**entire source file** in `local flight_control = (function() <file>
end)()` and calls the module through its own `M.*` table, the real
source verbatim, never a hand-copied duplicate. Every DCS global the
module reads (`GetDevice`, `LoSetCommand`, `LoGetADIPitchBankYaw`,
`LoGetIndicatedAirSpeed`, `LoGetAltitudeAboveGroundLevel`,
`LoGetSelfData`, `LoGetRadarAltimeter`) and the `ai_pilot_wheel`
cross-module global (Decision 25's `is_parked`/`player_seat` getters)
are mocked; `core.lua`'s own helper functions (`safe_call`,
`extract_json_number_field`, `extract_json_string_field`,
`is_finite_number`, `fmt_num_or_null`, `fmt_int_or_null`,
`json_escape_string`) are extracted from the real `core.lua`, same
technique `test_ai_pilot_wheel_lua.py` already uses.

Internal state (`fc_mode`/`fc_release_reason`/`fc_refuse_cause`/...) is
never exported directly -- the test reads it the same way body-layer
does, through `push_flight_control_state`'s own wire line, parsed back
with the same flat-field regex `core.lua`'s own extractors use. Per-frame
`LoSetCommand` writes are captured via a mock DCS control surface.

Skips cleanly without a Lua interpreter on `PATH`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from schema.flight_control import FlightControlState

_PETROBRAIN_DIR = Path(__file__).resolve().parent.parent / "dcs-export" / "Petrobrain"
_CORE_LUA = _PETROBRAIN_DIR / "core.lua"
_FLIGHT_CONTROL_LUA = _PETROBRAIN_DIR / "flight_control.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(path: Path, name: str) -> str:
    """Identical technique to `test_ai_pilot_wheel_lua.py`'s own copy of
    this helper (duplicated across test files, this project's own
    convention -- see that file's docstring)."""
    text = path.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in {path.name}"
    token_re = re.compile(r"--[^\n]*|\b(function|if|for|while|end)\b")
    depth = 1
    for token_match in token_re.finditer(text, start_match.end()):
        keyword = token_match.group(1)
        if keyword is None:
            continue
        if keyword == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


#: `core.lua` helpers `flight_control.lua` reads as bare globals
#: (`core.lua`'s own header comment on why: `dofile`-loaded chunks share
#: no locals, only `_G`).
_CORE_HELPERS: tuple[str, ...] = (
    "safe_call",
    "extract_json_number_field",
    "extract_json_string_field",
    # `is_finite_number` must precede `fmt_num_or_null`/`fmt_int_or_null`
    # in this tuple -- both call it as a bare name, and the harness below
    # concatenates these extracted bodies into one chunk in tuple order,
    # same local-before-use rule `core.lua` itself follows.
    "is_finite_number",
    "fmt_num_or_null",
    "fmt_int_or_null",
    "json_escape_string",
)

#: Mock DCS surface + cross-module globals. `ias_mps`/`bank_rad`/`agl_m`/
#: `heading_rad`/`radar_dist`/`radar_valid`/`self_data_present` are
#: mutable Lua globals the driver script sets before each `run_flight_
#: control`/`push_flight_control_state` call; `pilot_args`/`operator_
#: args` are per-axis tables (`{pitch=, roll=, pedals=, collective=}`);
#: `written` accumulates every `LoSetCommand` call since the test driver
#: last cleared it (one entry per command code, last write wins -- the
#: same per-frame-overwrite shape a real cockpit axis has); `ap_parked`/
#: `ap_seat` back `ai_pilot_wheel.is_parked`/`player_seat`.
_PREAMBLE = """
local pilot_args = { pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }
local operator_args = { pitch = 0.0, roll = 0.0, pedals = 0.0, collective = 0.0 }
local ias_mps = 150.0 / 3.6
local tas_mps = nil  -- nil means "same as ias_mps", set per-test to diverge
local bank_rad = 0.0
local pitch_rad = 0.0
local agl_m = 200.0
local asl_m = nil  -- nil means "same as agl_m"
local vs_mps = 0.0
local ang_x, ang_y, ang_z = 0.0, 0.0, 0.0  -- roll/yaw/pitch rate, rad/s
local heading_rad = 0.0
local radar_dist, radar_valid = 200.0, true
local self_data_present = true
local written = {}
local sent_lines = {}

-- Slip-ball calibration readout mocks (`fc_slip_ball_*`, sortie
-- 2026-11-20) -- `nil` by default (no legitimate real-world reading
-- has a fixed default, unlike the seat axis args above which are
-- genuinely centred at 0.0), set per-test.
local slip_ball_pilot_raw = nil
local slip_ball_operator_raw = nil
local slip_ball_lo_api = nil

local SEAT_ARG_NUM = {
    [1100] = "pilot.pitch", [1101] = "pilot.roll",
    [1102] = "pilot.collective", [1103] = "pilot.pedals",
    [1110] = "operator.pitch", [1111] = "operator.roll",
    [1112] = "operator.collective", [1113] = "operator.pedals",
}

local function arg_value(n)
    if n == 943 then return slip_ball_pilot_raw end
    if n == 784 then return slip_ball_operator_raw end
    local key = SEAT_ARG_NUM[n]
    if key == nil then return nil end
    local seat, axis = key:match("(%a+)%.(%a+)")
    if seat == "pilot" then return pilot_args[axis] end
    return operator_args[axis]
end

function GetDevice(id)
    return {
        get_argument_value = function(self, arg) return arg_value(arg) end,
    }
end

function LoGetSlipBallPosition()
    return slip_ball_lo_api
end

function LoSetCommand(cmd, value)
    written[cmd] = value
end

function LoGetADIPitchBankYaw()
    return pitch_rad, bank_rad, 0.0
end

function LoGetIndicatedAirSpeed()
    return ias_mps
end

function LoGetTrueAirSpeed()
    if tas_mps == nil then return ias_mps end
    return tas_mps
end

function LoGetVerticalVelocity()
    return vs_mps
end

function LoGetAngularVelocity()
    return { x = ang_x, y = ang_y, z = ang_z }
end

function LoGetAltitudeAboveGroundLevel()
    return agl_m
end

function LoGetAltitudeAboveSeaLevel()
    if asl_m == nil then return agl_m end
    return asl_m
end

function LoGetRadarAltimeter()
    return radar_dist, radar_valid
end

function LoGetSelfData()
    if not self_data_present then return nil end
    return { Heading = heading_rad }
end

local function debug_log(msg) end

-- BL-16 lift-vector law, Stage LV-0 (`plans/flight-lift-vector/plan.md`)
-- -- `flight_control.lua`'s own orchestration code (`run_active_frame`/
-- `request_take`) now reads `flight_profile.ACTIVE` at every `law_*`
-- call site, the same cross-module-global pattern as `flight_desired`/
-- `ai_pilot_wheel` below. Values copied verbatim from `flight_profile.
-- lua`'s own `PROFILES["Mi-24P"]` table -- this harness exercises the
-- whole module end to end (`run_flight_control`), so a mismatched value
-- here would show up as a changed `fc_*` wire field, not a Lua error.
flight_profile = {
    ACTIVE = {
        law_zeta = 1.0,
        omega_heading = 0.3,
        omega_alt = 0.5,
        omega_speed = 0.15,
        t_roll = 2.0,
        heading_accel_cap_deg_s2 = 6.0,
        k_heading_track = 0.3,
        alt_accel_cap_mps2 = 1.0,
        speed_accel_cap_mps2 = 0.5,
        k_vs_error = 0.3,
        k_alt_error = 0.05,
        k_speed_error = 0.2,
        k_collective = 0.08,
        k_tilt_from_ax = 0.04,
        k_tilt_from_az_saturated = 0.03,
        theta_min_deg = -15.0,
        theta_max_deg = 15.0,
        k_bank_increment = 0.5,
        k_theta = 0.03,
        k_theta_i = 0.015,
        k_q = 0.01,
        k_phi = 0.03,
        k_phi_i = 0.015,
        k_p = 0.01,
        k_pedal_from_collective_rate = 0.25,
        pedal_limit_positive = 0.5,
        pedal_limit_negative = -1.0,
        pedal_near_limit_margin = 0.1,
        collective_rate_cap_near_pedal_limit = 0.3,
        rotor_rpm_near_floor_margin_pct = 5.0,
        collective_rate_cap_near_rpm_floor = 0.0,
        retreating_blade_stall_margin_kmh = 20.0,
        collective_rate_cap_near_blade_stall = 0.0,
        k_break_pedal_bias = 0.2,
        k_turn_coord_pedal = 0.02,
        tau_accel_filter_s = 0.3,
        turn_settle_deg_s = 0.3,
        law_hz = 30.0,
        velocity_source = "position",
        w_v_s = 0.1,
        w_a_s = 0.2,
        w_a2_s = 0.1,
        w_b = 0.2,
        ball_centre = 0.03,
        ball_usable_range = 0.5,
    },
}

ai_pilot_wheel = {
    is_parked = function()
        if ap_parked == nil then return nil end
        return ap_parked
    end,
    player_seat = function() return ap_seat end,
    stick_park_raw = function() return ap_stick_park_raw end,
    -- BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`) -- the
    -- unpark-take's own seed source. `ap_held` is a driver-set Lua
    -- table (or nil); every field defaults nil, same as a mission
    -- where the AI-wheel overlay was never read.
    held_targets = function()
        local held = ap_held or {}
        return {
            heading_deg = held.heading_deg,
            alt_m = held.alt_m,
            alt_ref = held.alt_ref,
            speed_kmh = held.speed_kmh,
        }
    end,
}

client = {
    send = function(self, line)
        table.insert(sent_lines, line)
        return true
    end,
}

-- BL-16 Stage 3 (`plans/flight-desired-state/plan.md`) -- the one
-- desired-state mirror `flight_control.lua` now reads (`apply_desired_
-- changes_to_law`/`build_take_seed`) instead of the retired `fc_goal_*`
-- push-at-receipt locals. `fd_heading_ref` (default "true", no
-- conversion) is a driver-settable global so the heading-reference
-- tests can flip it to "mag"; `desired`'s own fields are set directly
-- by the driver (mirroring exactly what a numbered `set` request would
-- have written into `flight_desired.lua`'s real module).
local fd_heading_ref = "true"
local desired = {
    hdg_mode = nil, heading_deg = nil, turn_dir = nil, turn_rate_deg_s = nil,
    turn_style = "normal", alt_m = nil, alt_ref = nil, ias_kmh = nil,
    stamp_hdg = nil, stamp_alt = nil, stamp_spd = nil,
}

-- `LoGetMagneticYaw` backs the heading-reference conversion's own live
-- variation read -- a driver-settable global, `nil` by default (no
-- conversion exercised unless a test sets both this and `fd_heading_
-- ref = "mag"`). Declared (and the DCS function defined) BEFORE `flight_
-- desired`'s own closures below reference it -- Lua has no hoisting, so
-- a `local` declared after a closure that reads the name would leave
-- that closure reading the global instead (the project's own
-- no-hoisting gotcha, `aircraft-layer/CLAUDE.md`).
local fd_mag_heading_deg = nil
function LoGetMagneticYaw()
    return fd_mag_heading_deg
end

flight_desired = {
    get = function()
        local copy = {}
        for k, v in pairs(desired) do copy[k] = v end
        return copy
    end,
    heading_ref = function() return fd_heading_ref end,
    to_true_heading = function(ref_heading_deg, measured_true_deg)
        if ref_heading_deg == nil then return ref_heading_deg end
        if fd_heading_ref ~= "mag" then return ref_heading_deg end
        local variation = measured_true_deg - fd_mag_heading_deg
        local r = (ref_heading_deg + variation) % 360.0
        if r < 0 then r = r + 360.0 end
        return r
    end,
    from_true_heading = function(true_heading_deg, measured_true_deg)
        if true_heading_deg == nil then return true_heading_deg end
        if fd_heading_ref ~= "mag" then return true_heading_deg end
        local variation = measured_true_deg - fd_mag_heading_deg
        local r = (true_heading_deg - variation) % 360.0
        if r < 0 then r = r + 360.0 end
        return r
    end,
    write_internal = function(parts)
        parts = parts or {}
        if parts.heading_deg ~= nil then
            desired.hdg_mode = "heading"
            desired.heading_deg = parts.heading_deg
            desired.turn_dir = nil
        end
        if parts.clear_turn_rate then
            desired.turn_rate_deg_s = nil
            desired.turn_style = "normal"
        end
        if parts.alt_m ~= nil then desired.alt_m = parts.alt_m end
        if parts.alt_ref ~= nil then desired.alt_ref = parts.alt_ref end
        if parts.ias_kmh ~= nil then desired.ias_kmh = parts.ias_kmh end
    end,
}

-- Test-driver helper: writes a `set`-shaped request straight into the
-- mock `desired` table above, stamped with `seq` -- the same effect a
-- real numbered `flight` request would have on `flight_desired.lua`'s
-- own `desired`, without needing that module's own dispatch here.
local function set_desired(seq, fields)
    if fields.heading_deg ~= nil then
        desired.hdg_mode = "heading"
        desired.heading_deg = fields.heading_deg
        desired.turn_dir = nil
        desired.turn_rate_deg_s = fields.turn_rate_deg_s
        desired.turn_style = fields.turn_style or "normal"
        desired.stamp_hdg = seq
    end
    if fields.turn ~= nil then
        desired.hdg_mode = "turn"
        desired.turn_dir = fields.turn
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
        desired.stamp_hdg = seq
    end
    if fields.alt_m ~= nil then
        desired.alt_m = fields.alt_m
        desired.stamp_alt = seq
    end
    if fields.alt_ref ~= nil then desired.alt_ref = fields.alt_ref end
    if fields.ias_kmh ~= nil then
        desired.ias_kmh = fields.ias_kmh
        desired.stamp_spd = seq
    end
end
"""


def _run(driver: str, *, rotor_rpm_source: str | None = None) -> list[str]:
    """Assembles core-helper extraction + the mock preamble + the whole
    of `flight_control.lua` (wrapped as an immediately-invoked function
    expression so its own `return M` becomes this expression's value)
    + `driver` (which may print lines), and returns stdout split into
    lines. Skips cleanly without a Lua interpreter on `PATH`.

    `rotor_rpm_source` (mode-1 batch) patches the module's own
    `ROTOR_RPM_SOURCE` default (`"dummy"`) to `"arg_proxy"` for
    `TestReadRotorRpmPct` below -- the one module-level constant no
    test needs to flip otherwise, so a one-line source-text substitution
    is simpler than threading a new mock global through every other
    test in this file."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    core_helpers = "\n".join(
        _extract_lua_function(_CORE_LUA, name) for name in _CORE_HELPERS
    )
    module_source = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
    if rotor_rpm_source is not None:
        needle = 'local ROTOR_RPM_SOURCE = "dummy"'
        assert needle in module_source, "ROTOR_RPM_SOURCE default line moved/renamed"
        module_source = module_source.replace(
            needle, f'local ROTOR_RPM_SOURCE = "{rotor_rpm_source}"'
        )
    script = (
        _PREAMBLE
        + "\n"
        + core_helpers
        + "\nlocal flight_control = (function()\n"
        + module_source
        + "\nend)()\n"
        + driver
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".lua", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(script)
        script_path = handle.name
    try:
        result = subprocess.run(
            [exe, script_path], capture_output=True, text=True, check=False
        )
    finally:
        Path(script_path).unlink(missing_ok=True)

    assert result.returncode == 0, f"Lua harness failed (exe={exe}): {result.stderr}"
    # `push_flight_control_state`'s own wire line carries a trailing
    # `"\n"` (the newline-delimited-JSON wire convention every other
    # per-frame feed in this codebase also uses) -- printing that string
    # verbatim therefore emits a blank line right after it (the string's
    # own "\n" plus `print`'s own terminator). Drop blank lines rather
    # than asking every driver script to strip it -- no legitimate
    # driver output here is ever an empty line.
    return [line for line in result.stdout.splitlines() if line != ""]


def _field(line: str, name: str) -> str | None:
    """Pulls one bare (unquoted) or quoted JSON field's raw text back
    out of a `push_flight_control_state` line, for assertions -- the
    same flat regex idiom `core.lua`'s own extractors use, generalised
    to strings/bools/numbers/null since the test needs to read all four
    kinds back."""
    match = re.search(rf'"{name}":("[^"]*"|-?[0-9.]+|true|false|null)', line)
    assert match is not None, f"{name!r} not found in line: {line!r}"
    token = match.group(1)
    if token == "null":
        return None
    return token.strip('"')


class TestCaptureIsBitExact:
    def test_voice_take_captures_the_seat_set_exactly(self) -> None:
        driver = """
pilot_args.pitch = 0.321
pilot_args.roll = -0.154
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2001]))
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        status_line, pitch_written, roll_written = lines[0], lines[1], lines[2]
        assert _field(status_line, "fc_mode") == "active"
        # Output = captured + wobble, sign-mapped: pitch/roll SIGN is 1.0
        # (module's own table), wobble magnitude 0.001, so the written
        # value is within the wobble band of the exact captured arg --
        # "bit-exact" means the *capture*, not the wobble-perturbed
        # write, so this checks the written value is the captured one
        # plus or minus exactly one wobble step.
        assert abs(float(pitch_written) - 0.321) <= 0.0011
        assert abs(float(roll_written) - (-0.154)) <= 0.0011

    def test_collective_capture_writes_with_the_measured_sign(self) -> None:
        """Sortie 2026-11-20: `FC_AXES_ENABLED.collective` now defaults
        `true`, so a take actually writes the collective axis (2087),
        not just the internal law state -- same bit-exact-at-capture
        contract as pitch/roll/pedal above. `SIGN.collective = -1.0`
        (M0-C, flight 6): the written command is `-captured_arg`."""
        driver = """
pilot_args.collective = 0.3
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
print(string.format("%.6f", written[2087]))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - (-0.3)) <= 0.0011

    def test_pedal_capture_writes_with_the_measured_sign(self) -> None:
        """M0-B (2026-11-18): `SIGN.pedals = -1.0` -- the written command
        is `-captured_arg` (plus wobble), not the raw arg value."""
        driver = """
pilot_args.pedals = 0.4
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
print(string.format("%.6f", written[2003]))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - (-0.4)) <= 0.0011

    def test_unpark_take_succeeds_with_the_flag_on_by_default(self) -> None:
        """`UNPARK_TAKE_ENABLED` now defaults **on** -- M0-J (flight 9)
        passed with the last-fully-stowed capture fix below -- so an
        unpark from `armed` takes rather than refusing. The driver here
        never holds a frame at `stick_park_raw() >= STOWED_THRESHOLD`
        before unparking, so there is no tracked snapshot yet and the
        take falls back to a fresh read of the pilot set (1100-1103),
        never the operator set the camera happens to be in -- `TestM0J
        CaptureFixes` below covers the tracked-snapshot and cross-fade
        cases this fallback exists for."""
        driver = """
pilot_args.pitch = 0.42
operator_args.pitch = -0.9
ap_seat = "operator"
ap_parked = true
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2001]))
"""
        lines = _run(driver)
        status_line, pitch_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        assert _field(status_line, "fc_refuse_cause") is None
        # Captured the pilot set (0.42), never the operator set (-0.9)
        # the camera happened to be in.
        assert abs(float(pitch_written) - 0.42) <= 0.0011


class TestReleaseClearsHeldGoalsAcrossRetake:
    def test_release_then_retake_reports_no_held_goal(self) -> None:
        """review-m1.md Required Fix 1: a held heading/altitude/speed
        goal from a prior session must not survive into the next take --
        `current_crew_state`'s HOLD-until-known gates rely on `held_*`
        reading `None` until a fresh goal is commanded this activation."""
        driver = """
pilot_args.pitch = 0.1
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
set_desired(2, { heading_deg = 90.0, alt_m = 500.0, alt_ref = "baro", ias_kmh = 150.0 })
flight_control.run_flight_control(0.2)
flight_control.request_release(3)
flight_control.run_flight_control(0.3)
flight_control.request_take(4, 0.4)
flight_control.run_flight_control(0.4)
-- BL-16 Stage 3: the SAME stamp (2) the first session already applied
-- is still sitting in the (shared, test-only) mock `desired` after the
-- retake -- if `request_release` left `fc_applied_stamp_hdg` un-
-- cleared, this frame's `apply_desired_changes_to_law` would treat
-- stamp 2 as already-applied and never seed the fresh session's law
-- from it at all, even though it is seeded fresh from `desired`
-- directly at the take itself (`build_take_seed`) -- so this checks
-- the *next* frame's poll does not clobber that seed by skipping a
-- stamp it has (wrongly) already seen.
flight_control.run_flight_control(0.5)
flight_control.push_flight_control_state(0.5)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        retaken_line = lines[0]
        # The fresh take's own law carries `desired.heading_deg` (90.0,
        # stamped 2, from `build_take_seed`, never a stale previous-
        # session value) all the way through, confirmed via the
        # measured telemetry fallback being bypassed in favour of it --
        # `fc_mode` alone over two more frames is the simplest available
        # signal this mock can observe (the mock exposes no `fc_goal_*`
        # wire mirror any more; that concern moved to `flight_desired.
        # lua`'s own `clear_desired()`, covered by `test_flight_desired_
        # lua.py`'s `TestEdgeSeeding`/`TestResetAndStop`).
        assert _field(retaken_line, "fc_mode") == "active"


# BL-16 Stage 3 (`plans/flight-desired-state/plan.md`): `fc_take_seq`/
# `fc_goal_seq`/`fc_last_cmd_seq` are gone from this module's wire line
# entirely -- the staleness floor (`fd_epoch`/`fd_last_seq`) and the ack
# ring (`fd_acks`) live in `flight_desired.lua` now, which `request_
# take`/`request_release` are called FROM, never duplicating that check
# at this layer. The tests that used to pin that floor here
# (`TestRepeatedTakeWhileAlreadyFlyingStillAcks`, `TestBadBoundRejects
# WholeMessage`'s stale-seq case, `TestLastCmdSeqEchoSurvivesOnStop`) are
# removed -- their own concern is now `test_flight_desired_lua.py`'s
# `TestSetRequest` (epoch/seq/stale/bounds refusal) and `handle_flight_
# command`'s own dedup. `TestBadBoundRejectsWholeMessage`'s `limits`-
# bounds case moved to the lease (`TestStage2SelfArmAndLease` already
# covers `handle_flight_lease_command`'s own `AC-B14` rejection).


class TestBodyLayerStartReset:
    """BL-16 sortie 2026-11-20 (`docs/acceptance/
    2026-11-20-sortie-feedback.md`) -- `flight_control.reset`, the
    body-layer process-start reset."""

    def test_reset_releases_axes_and_echoes_the_epoch(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
flight_control.reset(99)
written = {}
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines - 1])
print(sent_lines[#sent_lines])
print(written[2001] == nil)
"""
        lines = _run(driver)
        before_reset_line, after_reset_line, nothing_written = (
            lines[0],
            lines[1],
            lines[2],
        )
        # Before the reset: mode 1 is genuinely flying, no epoch echoed
        # yet.
        assert _field(before_reset_line, "fc_mode") == "active"
        assert _field(before_reset_line, "fc_reset_epoch") is None
        # After `reset(99)`: mode off (axes released -- confirmed below
        # by `run_flight_control` writing nothing further), and the
        # epoch echoed back.
        assert _field(after_reset_line, "fc_mode") == "off"
        assert _field(after_reset_line, "fc_reset_epoch") == "99"
        # `run_flight_control` after the reset writes nothing -- the
        # same "release stops writing" behaviour `TestReleaseStopsWrites
        # SameFrame` already proves for an ordinary release.
        assert nothing_written == "true"

    def test_reset_is_idempotent_and_freely_resendable(self) -> None:
        """Body-layer resends the reset while unconfirmed -- applying
        the same epoch twice must have no further effect."""
        driver = """
ap_parked = false
ap_seat = "pilot"
flight_control.reset(5)
flight_control.reset(5)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "off"
        assert _field(lines[0], "fc_reset_epoch") == "5"


class TestReleaseStopsWritesSameFrame:
    def test_release_stops_writing_in_the_same_frame(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
written = {}
flight_control.request_release(2)
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
print(written[2001] == nil)
"""
        lines = _run(driver)
        status_line, nothing_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "off"
        assert _field(status_line, "fc_release_reason") == "stop"
        assert nothing_written == "true"


class TestParkMovesActiveToArmedWithNoWrite:
    def test_park_edge_while_active_self_arms_with_no_write(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
written = {}
ap_parked = true
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
print(written[2001] == nil)
"""
        lines = _run(driver)
        status_line, nothing_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "armed"
        assert nothing_written == "true"


class TestUnparkTakeRefusals:
    def test_refused_below_min_ias(self) -> None:
        driver = """
ap_parked = true
ap_seat = "operator"
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.05)
ias_mps = 20.0 / 3.6
ap_parked = false
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        status_line = lines[0]
        assert _field(status_line, "fc_mode") == "off"
        # `UNPARK_TAKE_ENABLED` now defaults on (M0-J passed), so the
        # ordinary preconditions are reachable again: below `min_ias_
        # kmh` refuses with cause "too_slow".
        assert _field(status_line, "fc_refuse_cause") == "too_slow"

    def test_refused_with_a_stale_lease(self) -> None:
        driver = """
ap_parked = true
ap_seat = "operator"
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":1.0}}',
    0.0)
flight_control.run_flight_control(0.05)
ap_parked = false
flight_control.run_flight_control(5.0)  -- well past the 1 s lease
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        status_line = lines[0]
        assert _field(status_line, "fc_mode") == "off"
        assert _field(status_line, "fc_refuse_cause") == "lease"

    def test_refusal_still_available_via_the_flag(self) -> None:
        """The `UNPARK_TAKE_ENABLED` kill-switch itself is kept, not
        deleted (coordinator direction, 2026-11-18) -- this pins that the
        "disabled" cause still exists as a value `fc_refuse_cause` can
        take, by reading it straight off the module source rather than
        through a test seam (the constant is a true Lua local, with no
        exported setter, and none should be added for a one-line flag
        this project may want to flip back from live DCS evidence
        without a deploy)."""
        source = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
        assert 'fc_refuse_cause = "disabled"' in source
        assert re.search(r"local UNPARK_TAKE_ENABLED\s*=\s*true", source) is not None


class TestUnparkTakeCaptureTiming:
    """M0-J (flight 9): the `parked_active` falling edge arrives after
    the two arg sets have already begun their ~1.5 s cross-fade, so a
    capture taken at the edge itself (or a sum of both sets at the
    edge) rolls/pitches the aircraft -- flight 9's J1/J2. The fix tracks
    the pilot set every frame while armed and only overwrites the
    tracked snapshot on a frame reading fully stowed (`stick_park_raw()
    >= STOWED_THRESHOLD`); the unpark-take reads that snapshot, never a
    fresh capture at the edge."""

    def test_captures_the_last_fully_stowed_frame_not_the_faded_edge(self) -> None:
        driver = """
pilot_args.roll = 0.133
ap_seat = "pilot"
ap_parked = true
ap_stick_park_raw = 1.0
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
-- Self-arms this frame (off -> armed) -- that transition itself
-- consumes the whole frame (BL-16 Stage 2's own self-arm branch
-- `return`s immediately), so the stowed-capture tracking below needs
-- one more frame before it ever runs.
flight_control.run_flight_control(0.1)
-- A frame fully stowed: tracked.
flight_control.run_flight_control(0.15)
-- The fade begins: the arg set and the raw stow value both fall
-- together, exactly as flight 9 measured (roll 0.133 -> 0.086, raw
-- 1.0 -> 0.85) -- and the edge (`is_parked() == false`) lands here.
pilot_args.roll = 0.086
ap_stick_park_raw = 0.85
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        status_line, roll_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        assert _field(status_line, "fc_refuse_cause") is None
        # The tracked 0.133, not the faded 0.086 read at the edge frame.
        assert abs(float(roll_written) - 0.133) <= 0.0011

    def test_a_seat_gate_edge_has_no_fade_and_gets_the_same_value(self) -> None:
        """J3: a seat-gate edge (operator -> pilot while parked) has no
        fade -- `stick_park_raw()` stays at 1.0 throughout, so the
        tracked snapshot and an edge-frame read are the same value. No
        special-case code exists for this; this pins that the one
        tracking mechanism already covers it."""
        driver = """
pilot_args.roll = 0.222
ap_seat = "pilot"
ap_parked = true
ap_stick_park_raw = 1.0
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
-- No fade -- raw852 stays at 1.0 through the edge.
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        status_line, roll_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        assert abs(float(roll_written) - 0.222) <= 0.0011

    def test_tracked_capture_does_not_leak_into_the_next_armed_session(self) -> None:
        """The same leak class `fc_goal_*`'s release fix guards against
        (review-m1.md Required Fix 1): a stale stowed-pilot snapshot
        from one armed session must not survive into the next one that
        never itself reached the stowed threshold."""
        driver = """
pilot_args.roll = 0.5
ap_seat = "pilot"
ap_parked = true
ap_stick_park_raw = 1.0
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
-- Release, then re-arm without ever reaching the stowed threshold this
-- session -- and the player has since moved the stick.
flight_control.request_release(2)
flight_control.run_flight_control(0.3)
pilot_args.roll = 0.9
ap_parked = true
ap_stick_park_raw = 0.5
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.4)
flight_control.run_flight_control(0.4)
ap_parked = false
flight_control.run_flight_control(0.5)
flight_control.push_flight_control_state(0.5)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        status_line, roll_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        # The fresh read (0.9), never the first session's tracked 0.5.
        assert abs(float(roll_written) - 0.9) <= 0.0011


class TestUnparkTakeSeedsFromMode2SetTargets:
    """BL-16 sortie 2026-11-20 (`plans/flight-control/debug.md`) -- the
    crash this report diagnoses: an unpark mid-break with no seed reads
    the AI-wheel's own held heading as if it were a raw-stick bank the
    pilot had just rolled into on purpose. **BL-16 Stage 3**: the fix
    now reads `flight_desired.get()` (the one `desired` table) for an
    unpark take only, never a voice take -- `build_take_seed`'s own
    verbatim-carry branch (`fc_take_origin == "unpark"`), replacing the
    pre-Stage-3 direct `ai_pilot_wheel.held_targets()` read
    (`test_flight_control_law.py`'s own `TestUnparkTakeSeedFromMode2
    SetTargets` exercises the resulting law state directly, including
    the no-physics fallback; this covers the wiring end to end through
    `run_flight_control`, using `fc_in_band_heading` as the one wire
    field that reflects the law's internal heading mode/goal)."""

    def test_unpark_take_adopts_the_held_heading_not_the_measured_one(self) -> None:
        """`in_band_heading` starts `false` unconditionally at
        `law_init_at_take` (it is `law_update`'s own computation) --
        several frames at a constant measured heading let it settle
        before either assertion, the same way the toy-plant suite runs
        the law forward rather than reading the take frame alone."""
        driver = """
heading_rad = math.rad(123.0)
bank_rad = math.rad(2.0)  -- well under the 5 deg takeover threshold
ap_seat = "operator"
ap_parked = true
ap_held = { heading_deg = 45.0 }
-- BL-16 Stage 3: the unpark-take seed now comes from `flight_desired.
-- get()`, never `ai_pilot_wheel.held_targets()` directly -- in the real
-- module this is populated by `flight_desired.lua`'s own `reseed_from_
-- overlay` at the off->m2 edge; this mock stands in for that same
-- effect directly on the shared `desired` table.
set_desired(1, { heading_deg = 45.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
for i = 1, 50 do
    flight_control.run_flight_control(0.2 + i * 0.05)
end
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        status_line = lines[0]
        assert _field(status_line, "fc_mode") == "active"
        # Heading mode converges to the *held* 45, not the *measured*
        # 123 -- a 78 deg error is nowhere near the 5 deg band, even
        # though bank alone would have picked heading mode either way,
        # and the mock's own `heading_rad` never moves on its own.
        assert _field(status_line, "fc_in_band_heading") == "false"

    def test_voice_take_ignores_the_held_heading(self) -> None:
        """Same held value, same measured heading, but a voice take --
        Decision 24's own bank-at-capture rule still governs, unaffected
        by whatever the AI wheel happens to be set to, so the goal is
        the measured heading and the error settles at zero."""
        driver = """
heading_rad = math.rad(123.0)
bank_rad = math.rad(2.0)
ap_seat = "pilot"
ap_parked = false
ap_held = { heading_deg = 45.0 }
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
for i = 1, 50 do
    flight_control.run_flight_control(0.1 + i * 0.05)
end
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        status_line = lines[0]
        assert _field(status_line, "fc_mode") == "active"
        assert _field(status_line, "fc_in_band_heading") == "true"


class TestVoiceTakeSetDuringTakingSurvivesTheSeed:
    """Review-fix round (`plans/flight-desired-state/review-s3.md`
    Required Fix 2): the plan's own Stage 3 test, "a set during `taking`
    survives the seed" (`build_take_seed`'s voice-take branch, `desired.
    stamp_hdg/alt/spd > take_seq`) -- a command given in the same breath
    as "you have controls." Driven by sending `set_desired` with a
    higher `seq` *while* `fc_mode == "taking"`, i.e. after `request_
    take` but before the `run_flight_control` call that resolves it --
    the window no existing driver in this file exercises (every other
    `request_take` driver either resolves in the same call or sends its
    `set_desired` only once the take has already resolved)."""

    def test_a_heading_set_during_taking_survives_the_seed(self) -> None:
        """Measured heading stays at 123 for the whole run (the mock
        never moves it); `law_init_at_take`'s own fallback would adopt
        that measured value with no seed. If the seed set during
        `taking` is adopted instead, the law's goal (45) and the
        unmoving measured value (123) never agree, so `fc_in_band_
        heading` stays `false` even after settling -- the same
        differentiating assertion `TestUnparkTakeSeedsFromMode2
        SetTargets` already uses for its own seed-adoption check."""
        driver = """
heading_rad = math.rad(123.0)
bank_rad = math.rad(2.0)  -- under the 5 deg takeover threshold
ap_seat = "pilot"
ap_parked = false
flight_control.request_take(1, 0.0)
-- Sent while fc_mode == "taking" (not yet resolved) -- "you have
-- controls, heading 045" in one breath. `seq=2 > take_seq=1`.
set_desired(2, { heading_deg = 45.0 })
flight_control.run_flight_control(0.1)
for i = 1, 50 do
    flight_control.run_flight_control(0.1 + i * 0.05)
end
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        status_line = lines[0]
        assert _field(status_line, "fc_mode") == "active"
        assert _field(status_line, "fc_in_band_heading") == "false"

    def test_a_set_stamped_at_or_before_take_seq_does_not_survive(self) -> None:
        """Control: `seq == take_seq` (not strictly after it) is the
        pre-existing desired value at the moment of take, not a
        same-breath command -- `build_take_seed`'s own `>` comparison
        excludes it, so the law falls back to the measured default and
        converges in-band."""
        driver = """
heading_rad = math.rad(123.0)
bank_rad = math.rad(2.0)
ap_seat = "pilot"
ap_parked = false
set_desired(1, { heading_deg = 45.0 })
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
for i = 1, 50 do
    flight_control.run_flight_control(0.1 + i * 0.05)
end
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        status_line = lines[0]
        assert _field(status_line, "fc_mode") == "active"
        assert _field(status_line, "fc_in_band_heading") == "true"


class TestVoiceTakeLiveSeatCapture:
    """M0-J (flight 9): the camera seat is not the live-controls seat --
    the operator set can read zero while the player sits there, before
    requesting control, with the pilot set holding the live inputs. The
    fix captures the live (non-zero) set regardless of camera seat, and
    the last steady set if both read live (a cross-fade)."""

    def test_captures_the_live_pilot_set_with_the_camera_in_the_operator_seat(
        self,
    ) -> None:
        driver = """
pilot_args.pitch = 0.229
operator_args.pitch = 0.0
ap_seat = "operator"
ap_parked = false
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2001]))
"""
        lines = _run(driver)
        status_line, pitch_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        # The live pilot set (0.229), never the all-zero operator set
        # the camera happened to be in.
        assert abs(float(pitch_written) - 0.229) <= 0.0011

    def test_a_cross_fade_at_the_moment_of_take_uses_the_last_steady_set(self) -> None:
        """Both seats read live at once (a cross-fade in progress) --
        uses the last frame exactly one of them was live, not either
        set's own partly-faded current value."""
        driver = """
pilot_args.pitch = 0.3
operator_args.pitch = 0.0
ap_seat = "pilot"
ap_parked = false
-- A steady frame: only the pilot set is live. Tracked.
flight_control.run_flight_control(0.0)
-- Now both read live at once (the fade in progress) and the take lands
-- on this very frame.
pilot_args.pitch = 0.15
operator_args.pitch = 0.2
flight_control.request_take(1, 0.1)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2001]))
"""
        lines = _run(driver)
        status_line, pitch_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        # The last steady pilot value (0.3), neither of this frame's
        # own partly-faded reads (0.15/0.2).
        assert abs(float(pitch_written) - 0.3) <= 0.0011


class TestUnparkWhileOffWritesNothing:
    def test_unpark_while_off_writes_nothing(self) -> None:
        driver = """
pilot_args.pitch = 0.9
ap_parked = true
flight_control.run_flight_control(0.0)
ap_parked = false
written = {}
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
print(written[2001] == nil)
"""
        lines = _run(driver)
        status_line, nothing_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "off"
        assert nothing_written == "true"


class TestPauseRowHolds:
    def test_a_paused_frame_rewrites_outputs_unchanged(self) -> None:
        """review-m2.md Required Fix 2: a goal applied right before the
        paused frame gives the shaper a real tracking error to move
        against if it were (wrongly) advanced -- a bare `~= nil` check
        cannot tell a frozen rewrite from an un-frozen one, since both
        write *something*. Written values differ frame to frame by
        exactly one wobble step even when correctly frozen (`write_
        outputs`'s alternating parity), so the two samples are compared
        within two wobble steps of each other, not for exact equality."""
        driver = """
pilot_args.pitch = 0.5
pilot_args.roll = 0.2
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(10.0)
-- A goal that disagrees with the captured heading: if the pause branch
-- wrongly advanced the law instead of freezing it, this is what the
-- shaper would move against -- deliberately only written into the mock
-- `desired` here, not yet applied (`apply_desired_changes_to_law` only
-- runs on a non-paused active frame, same as the real module).
set_desired(2, { heading_deg = 90.0 })
local before_pitch = written[2001]
local before_roll = written[2002]
written = {}
-- dt <= 0 (a paused frame: model time did not advance).
flight_control.run_flight_control(10.0)
print(string.format("%.6f", before_pitch))
print(string.format("%.6f", written[2001]))
print(string.format("%.6f", before_roll))
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        before_pitch, after_pitch, before_roll, after_roll = (float(v) for v in lines)
        assert abs(after_pitch - before_pitch) <= 0.0021
        assert abs(after_roll - before_roll) <= 0.0021

    def test_a_huge_frame_jump_also_rewrites_rather_than_shaping(self) -> None:
        driver = """
pilot_args.pitch = 0.5
pilot_args.roll = 0.2
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(10.0)
set_desired(2, { heading_deg = 90.0 })
local before_pitch = written[2001]
local before_roll = written[2002]
written = {}
flight_control.run_flight_control(50.0)  -- dt = 40s, above DT_CAP
flight_control.push_flight_control_state(50.0)
print(sent_lines[#sent_lines])
print(string.format("%.6f", before_pitch))
print(string.format("%.6f", written[2001]))
print(string.format("%.6f", before_roll))
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        status_line = lines[0]
        before_pitch, after_pitch, before_roll, after_roll = (
            float(v) for v in lines[1:]
        )
        assert _field(status_line, "fc_mode") == "active"
        assert abs(after_pitch - before_pitch) <= 0.0021
        assert abs(after_roll - before_roll) <= 0.0021


class TestEnvelopeRelease:
    def test_sustained_low_ias_releases_after_the_hold(self) -> None:
        # Every frame advances by 0.2 s (well under `DT_CAP`, so no
        # frame is ever treated as a pause) across more than `ENV_HOLD_S`
        # (3.0 s) of sustained low IAS -- a single large time jump would
        # hit the pause/huge-jump branch instead of the envelope check
        # (see `TestPauseRowHolds`), so this drives real small steps.
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
ias_mps = 20.0 / 3.6
for i = 1, 20 do
    flight_control.run_flight_control(0.1 + i * 0.2)
end
flight_control.push_flight_control_state(0.1 + 20 * 0.2)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "off"
        assert _field(lines[0], "fc_release_reason") == "envelope"

    def test_sustained_high_bank_never_releases(self) -> None:
        """F-M1 (mode-1 batch): "remove the 30 degree limit. Set no
        limit for now" -- there is no bank-triggered release any more
        at all. A bank well past the old 30 deg ceiling, held for well
        past `ENV_HOLD_S`, never releases -- IAS alone governs release
        now."""
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
ias_mps = 150.0 / 3.6
bank_rad = math.rad(50.0)
for i = 1, 20 do
    flight_control.run_flight_control(0.1 + i * 0.2)
end
flight_control.push_flight_control_state(0.1 + 20 * 0.2)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "active"
        assert _field(lines[0], "fc_release_reason") is None

    def test_momentary_low_ias_does_not_release(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
ias_mps = 20.0 / 3.6
flight_control.run_flight_control(0.2)
ias_mps = 150.0 / 3.6
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "active"


class TestReadRotorRpmPct:
    """Mode-1 batch, Decision 28 -- `read_rotor_rpm_pct()`, exported
    directly (`M.read_rotor_rpm_pct`) same as the law's own pure
    functions."""

    def test_dummy_source_returns_the_configured_dummy_value(self) -> None:
        driver = """
local pct, valid = flight_control.read_rotor_rpm_pct()
print(string.format("%.6f", pct))
print(tostring(valid))
"""
        lines = _run(driver)
        assert float(lines[0]) == 90.0
        assert lines[1] == "true"

    def test_arg_proxy_scales_a_good_read(self) -> None:
        driver = """
function GetDevice(id)
    return { get_argument_value = function(self, arg)
        if arg == 42 then return 0.73 end
        return nil
    end }
end
local pct, valid = flight_control.read_rotor_rpm_pct()
print(string.format("%.6f", pct))
print(tostring(valid))
"""
        lines = _run(driver, rotor_rpm_source="arg_proxy")
        assert abs(float(lines[0]) - 73.0) < 1e-6
        assert lines[1] == "true"

    def test_arg_proxy_falls_back_to_the_dummy_on_a_bad_read(self) -> None:
        """A failed/NaN `arg_proxy` read fails soft to the dummy value
        with `valid=false` -- `read_measured()`'s own caller treats
        this the same as every other fail-soft field (does not release
        the envelope on its own)."""
        driver = """
function GetDevice(id)
    return { get_argument_value = function(self, arg) return nil end }
end
local pct, valid = flight_control.read_rotor_rpm_pct()
print(string.format("%.6f", pct))
print(tostring(valid))
"""
        lines = _run(driver, rotor_rpm_source="arg_proxy")
        assert float(lines[0]) == 90.0
        assert lines[1] == "false"


class TestAxesEnabledOnTheWire:
    def test_all_four_axes_enabled(self) -> None:
        """M0-B (flown 2026-11-18) measured the pedal write (`SIGN.
        pedals = -1.0`), so it is enabled; M0-C (collective) had its
        sign/scale measured the same flight but was kept off pending its
        own lag/VS measurement -- enabled from sortie 2026-11-20 by user
        direction instead (`docs/acceptance/2026-11-20-sortie-
        feedback.md`, "absolutely yes. Now.")."""
        driver = """
flight_control.push_flight_control_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_axes_pitch") == "true"
        assert _field(lines[0], "fc_axes_roll") == "true"
        assert _field(lines[0], "fc_axes_pedal") == "true"
        assert _field(lines[0], "fc_axes_collective") == "true"


class TestSlipBallStatusReadout:
    """Sortie 2026-11-20 (`aircraft-layer/research/2026-11-20-slip-ball-
    recon.md`): the slip-ball calibration readout is sent in every
    `fc_mode`, including "off" -- no `take` is ever issued in these
    drivers."""

    def test_pilot_and_operator_raw_args_reach_the_status_line(self) -> None:
        driver = """
slip_ball_pilot_raw = 0.125
slip_ball_operator_raw = -0.25
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert float(_field(lines[0], "fc_slip_ball_pilot_raw")) == pytest.approx(0.125)
        assert float(_field(lines[0], "fc_slip_ball_operator_raw")) == pytest.approx(
            -0.25
        )

    def test_a_nil_lo_api_cross_check_reports_null(self) -> None:
        """`LoGetSlipBallPosition` has a documented history of returning
        `nil` for at least some aircraft/version combinations (the recon
        note's finding (a)) -- the status line must still carry the two
        draw-arg readings, with the cross-check field reporting `null`,
        not dropping the whole line."""
        driver = """
slip_ball_pilot_raw = 0.4
slip_ball_lo_api = nil
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_slip_ball_lo_api") is None
        assert float(_field(lines[0], "fc_slip_ball_pilot_raw")) == pytest.approx(0.4)

    def test_a_present_lo_api_cross_check_reaches_the_status_line(self) -> None:
        driver = """
slip_ball_lo_api = -0.6
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert float(_field(lines[0], "fc_slip_ball_lo_api")) == pytest.approx(-0.6)

    def test_the_readout_reaches_the_status_line_while_mode_is_off(self) -> None:
        """No take/handover at all -- `fc_mode` stays "off", and the
        readout is still carried (the recon note's own Reproducible
        Test step 1: "so a pilot-flown calibration flight can read them
        without Petrovich holding the controls")."""
        driver = """
slip_ball_pilot_raw = 0.2
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "off"
        assert float(_field(lines[0], "fc_slip_ball_pilot_raw")) == pytest.approx(0.2)

    def test_the_real_schema_parses_the_status_line(self) -> None:
        driver = """
slip_ball_pilot_raw = 0.33
slip_ball_operator_raw = -0.44
slip_ball_lo_api = 0.55
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        state = FlightControlState.from_dict(
            json.loads(line), received_wall_clock_s=0.0
        )
        assert state.slip_ball_pilot_raw == pytest.approx(0.33)
        assert state.slip_ball_operator_raw == pytest.approx(-0.44)
        assert state.slip_ball_lo_api == pytest.approx(0.55)


# BL-16 Stage 3: `TestSeqFieldsSurviveTheRealSchema` is removed --
# `fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` are gone from this wire
# line entirely (the plan's own deletions list), so the `%.5f`-vs-int
# schema hazard it pinned no longer has a field here to apply to.
# `test_flight_desired_api.py`'s own schema tests cover `fd_stamp_*`/
# `fd_epoch`/`fd_last_seq` (also `fmt_int_or_null`) on the module that
# replaced it.


class TestStage2SelfArmAndLease:
    """BL-16 Stage 2 (`plans/flight-desired-state/plan.md`, refinement
    3): the `"arm"` cmd is gone from `flight_control`; the lease moves
    to its own unnumbered `flight_lease` op, and self-arm reaches both
    `off -> armed` (new) and `active/taking -> armed` (unchanged)."""

    def test_no_lease_means_no_self_arm_from_off(self) -> None:
        """Parking with no lease ever sent leaves him `off` -- the
        player keeps the controls, same as today when no `arm` had ever
        arrived."""
        driver = """
ap_parked = true
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        assert _field(line, "fc_mode") == "off"

    def test_a_stale_lease_does_not_self_arm_from_off(self) -> None:
        driver = """
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":1.0}}',
    0.0)
ap_parked = true
flight_control.run_flight_control(5.0)  -- well past the 1 s lease
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        assert _field(line, "fc_mode") == "off"

    def test_lease_carries_limits_same_as_flight_control_did(self) -> None:
        """`handle_flight_lease_command` applies `limits` through the
        same `AC-B14` bounds-checked helper -- a value outside `FC_
        LIMIT_BOUNDS` rejects the whole lease message, never a partial
        apply."""
        driver = """
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,"limits":{"min_ias_kmh":999.0}}', 0.0)
ap_parked = true
ias_mps = 150.0 / 3.6
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        # The out-of-bounds `min_ias_kmh` rejected the whole lease
        # message, so `fc_arm_last_t` was never set by it -- off stays
        # off (no self-arm), same as "no lease ever sent".
        assert _field(line, "fc_mode") == "off"

    def test_reset_while_parked_does_not_rearm_until_the_next_park_edge(
        self,
    ) -> None:
        """Required Fix 2, `plans/flight-desired-state/review-s12.md`:
        the off->armed self-arm must be edge-triggered, not level-
        triggered -- Q6 ("after `reset(epoch)` while parked, armed is
        cleared and nothing re-arms it until the next park edge").
        Real reproduction, driven frame by frame: park with a fresh
        lease (self-arms), `reset` while still parked (back to `off`),
        a fresh lease arrives while STILL parked -- no unpark/re-park
        happened -- must stay `off`. Only an actual unpark then re-park
        is allowed to self-arm again."""
        driver = """
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
ap_parked = true
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])  -- [1] self-armed from the first park edge

flight_control.reset(2)
flight_control.push_flight_control_state(1.0)
print(sent_lines[#sent_lines])  -- [2] off again, still parked

flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":2,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    2.0)
-- still parked, no unpark edge in between
flight_control.run_flight_control(2.1)
flight_control.push_flight_control_state(2.1)
print(sent_lines[#sent_lines])  -- [3] must still be off (Q6)

ap_parked = false
flight_control.run_flight_control(2.2)
ap_parked = true
flight_control.run_flight_control(2.3)
flight_control.push_flight_control_state(2.3)
print(sent_lines[#sent_lines])  -- [4] a real unpark+re-park self-arms again
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "armed"
        assert _field(lines[1], "fc_mode") == "off"
        assert _field(lines[2], "fc_mode") == "off"
        assert _field(lines[3], "fc_mode") == "armed"

    # `test_unknown_cmd_arm_is_now_a_no_op` is removed: the `flight_
    # control` op (and its `cmd == "arm"` branch) is gone entirely this
    # stage, not just that one cmd -- there is nothing left at this
    # layer to send "arm" to.


class TestStage2VoiceTakePrecondition:
    """BL-16 Stage 2: a voice take now re-checks IAS/AGL itself
    (`check_unpark_preconditions`), rather than trusting body-layer's
    own pre-send refusal alone."""

    def test_a_voice_take_too_slow_is_refused_and_stays_off(self) -> None:
        driver = """
ias_mps = 20.0 / 3.6
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.push_flight_control_state(0.0)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        assert _field(line, "fc_mode") == "off"
        assert _field(line, "fc_refuse_cause") == "too_slow"

    def test_a_voice_take_on_the_ground_is_refused_and_stays_off(self) -> None:
        driver = """
agl_m = 5.0
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.push_flight_control_state(0.0)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        assert _field(line, "fc_mode") == "off"
        assert _field(line, "fc_refuse_cause") == "on_ground"

    def test_a_voice_take_clear_to_fly_still_takes(self) -> None:
        driver = """
ias_mps = 150.0 / 3.6
agl_m = 200.0
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_refuse_cause") is None


class TestHeadingReferenceConversion:
    """BL-16 Stage 3 (`plans/flight-desired-state/plan.md`, section 1,
    "Heading reference") -- `HEADING_REF="mag"` makes `desired.heading_
    deg` a magnetic reading; mode 1's law must fly it as true heading
    (`target_true = heading_deg + (measured_true - measured_mag)`)."""

    def test_heading_ref_mag_converts_a_set_to_true_before_flying_it(
        self,
    ) -> None:
        """090 magnetic with a steady +7.3 deg variation flies as 097.3
        true -- confirmed via `fc_in_band_heading` settling `true` only
        once the measured true heading (held fixed by the mock) actually
        reaches the converted target, never the raw 090."""
        driver = """
fd_heading_ref = "mag"
fd_mag_heading_deg = 82.7  -- true (90) - mag (82.7) = 7.3 deg variation
heading_rad = math.rad(90.0)
bank_rad = math.rad(2.0)
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
set_desired(2, { heading_deg = 90.0 })
for i = 1, 80 do
    flight_control.run_flight_control(0.1 + i * 0.05)
end
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        # heading_rad (true) never moves in this mock -- it sits at
        # 90.0 true throughout, which is 7.3 deg short of the converted
        # 97.3 true target, so the band must NOT have closed.
        assert _field(line, "fc_in_band_heading") == "false"

    def test_heading_ref_true_is_a_no_op_conversion(self) -> None:
        """The default (`HEADING_REF="true"`, this module's own
        unmeasured-placeholder default) flies the commanded value
        unconverted -- 90 true measured against a 90 true target closes
        the band."""
        driver = """
fd_heading_ref = "true"
heading_rad = math.rad(90.0)
bank_rad = math.rad(2.0)
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
set_desired(2, { heading_deg = 90.0 })
for i = 1, 80 do
    flight_control.run_flight_control(0.1 + i * 0.05)
end
flight_control.push_flight_control_state(5.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_in_band_heading") == "true"


class TestUnparkCarriesAStandingBreak:
    """BL-16 Stage 3, Decision 32/Q4 -- "the law is initialised with
    desired as the seed", including a standing break's own rate
    override and style, not just the plain heading: an unpark mid-break
    must finish the break (continue turning at the break's own rate)
    rather than snapping straight to the target heading."""

    def test_unpark_mid_break_keeps_turning_at_the_break_rate(self) -> None:
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ap_seat = "operator"
ap_parked = true
-- A standing break: heading target far away, a real rate override, and
-- the "break" style -- exactly what `desired` would hold mid-break
-- (`flight_desired.lua`'s own `apply_set`, section 1).
set_desired(1, { heading_deg = 90.0, turn_rate_deg_s = 20.0, turn_style = "break" })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        # The law seeded a non-zero turn rate (`r_ref` from the break's
        # own override), not the zero rate a plain heading-only carry
        # would have started from -- heading mode is active but not yet
        # in band, since the break is still turning toward 90.
        assert _field(line, "fc_in_band_heading") == "false"


class TestUnparkTakeSeedClampsToMode1Limits:
    """Review-fix round (`plans/flight-desired-state/review-s3.md`
    Required Fix 1, U2): mode 1 cannot fly every value mode 2 can hold
    -- `build_take_seed`'s unpark branch now clamps the seed to `fc_
    limits.min_ias_kmh`/`max_ias_kmh`/`floor_agl_m`, the same bounds
    `belief.flight_control.clamp_speed`/`clamp_altitude` enforce body-
    side. `desired` itself is never touched, only the seed fed to `law_
    init_at_take` -- the plan's own Q1a ("the desired state keeps the
    exact value; what's flown is clamped")."""

    def test_speed_0_in_m2_then_unpark_flies_the_minimum_not_zero(self) -> None:
        """The plan's own worked example. Measured IAS is set to exactly
        `min_ias_kmh` (80) so the clamped goal and the (unmoving, mocked)
        measured value agree immediately -- an unclamped goal of 0 would
        never agree with a measured 80, so `fc_in_band_speed` only reads
        `true` here if the seed was actually clamped up to 80."""
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ias_mps = 80.0 / 3.6
ap_seat = "operator"
ap_parked = true
set_desired(1, { ias_kmh = 0.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"max_ias_kmh":280.0,'
    .. '"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_in_band_speed") == "true"

    def test_speed_above_the_ceiling_in_m2_then_unpark_flies_the_ceiling(
        self,
    ) -> None:
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ias_mps = 280.0 / 3.6
ap_seat = "operator"
ap_parked = true
set_desired(1, { ias_kmh = 400.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"max_ias_kmh":280.0,'
    .. '"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_in_band_speed") == "true"

    def test_an_in_range_speed_is_carried_unclamped(self) -> None:
        """Control: a value already inside `[min_ias_kmh, max_ias_kmh]`
        is seeded verbatim, same as before this fix."""
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ias_mps = 150.0 / 3.6
ap_seat = "operator"
ap_parked = true
set_desired(1, { ias_kmh = 150.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"min_ias_kmh":80.0,"max_ias_kmh":280.0,'
    .. '"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_in_band_speed") == "true"


def test_file_parses_without_a_lua_interpreter_too() -> None:
    """`luac5.1 -p` sanity, independent of whether a runtime interpreter
    is on `PATH` -- mirrors `test_dcs_export_lua_syntax.py`'s own check,
    kept here too since this file's harness needs more than syntax."""
    exe = shutil.which("luac5.1")
    if exe is None:
        pytest.skip("no luac5.1 on PATH")
    result = subprocess.run(
        [exe, "-p", str(_FLIGHT_CONTROL_LUA)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
