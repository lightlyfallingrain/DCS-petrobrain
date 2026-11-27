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
import math
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

-- BL-16 lift-vector law, Stage LV-3 -- without a `Position`, `read_
-- estimator_raw`'s own `pos_valid` is always `false`, so the real
-- estimator's `v_g`/`v_g_f`/`v_g_r` (and therefore `lambda`) never
-- move off their reset value regardless of the mocked `ias_mps` --
-- every scenario in this file would silently run in "hover" (lambda
-- = 0) once LV-3's regime blend existed, no matter what speed it set.
-- `_mock_t`/`_mock_last_t`/`_mock_pos_n`/`_mock_pos_e` (set by the
-- `run_flight_control` wrapper just below the module load, `_run`'s
-- own assembly) make `Position` advance by `ias_mps` along the
-- current `heading_rad` for whatever real sim-time elapsed since the
-- last read -- the same "IAS is ground truth" assumption every
-- pre-existing test here already makes for the IAS channel itself.
_mock_t = 0.0
local _mock_last_t = 0.0
local _mock_pos_n, _mock_pos_e = 0.0, 0.0

function LoGetSelfData()
    if not self_data_present then return nil end
    local dt = _mock_t - _mock_last_t
    if dt > 0 then
        _mock_pos_n = _mock_pos_n + ias_mps * math.cos(heading_rad) * dt
        _mock_pos_e = _mock_pos_e + ias_mps * math.sin(heading_rad) * dt
        _mock_last_t = _mock_t
    end
    return {
        Heading = heading_rad,
        Position = { x = _mock_pos_n, y = 0.0, z = _mock_pos_e },
    }
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
        schedule_gain_min = 0.3,
        schedule_full_speed_kmh = 150.0,
        c_theta = 0.5,
        k_phi_trim = 0.02,
        k_theta_trim = 0.02,
        trim_hold_attitude_err_deg = 10.0,
        phi_i_bound_deg = 8.0,
        k_theta_speed_give = 0.5,
        speed_give_capacity = 0.05,
        k_phi_give = 4.0,
        phi_ff_min_scale = 0.3,
        k_collective_speed_give = 0.1,
        collective_speed_give_max_a_f_d_mps2 = 3.0,
        k_lift_ff = 0.05,
        k_collective = 0.08,
        theta_min_deg = -15.0,
        theta_max_deg = 15.0,
        k_theta = 0.03,
        k_theta_i = 0.015,
        k_q = 0.01,
        k_phi = 0.03,
        k_phi_i = 0.015,
        k_p = 0.01,
        -- Positive pedal command = RIGHT pedal (`plans/flight-lift-
        -- vector/debug-2026-11-24b.md`) -- mirrors `flight_profile.lua`.
        k_ball_pedal = 0.3,
        -- LV-1 amendment (2026-11-24, fourth re-fly) -- new fields,
        -- mirroring `flight_profile.lua`.
        k_ball_pedal_p = 0.3,
        k_pedal_from_collective_rate = 0.25,
        spooled_rpm_pct = 93.0,
        engine_rpm_gentle_floor_pct = 74.0,
        collective_rate_gentle_min_per_s = 0.2,
        rotor_dir = 1.0,
        k_turn_coord_pedal = 0.02,
        -- LV-3 amendment, U13 -- full pedal range, mirrors `flight_
        -- profile.lua`.
        pedal_limit_positive = 1.0,
        pedal_limit_negative = -1.0,
        -- Write bias (debug-2026-11-24c, finding 1) -- mirrors
        -- `flight_profile.lua`.
        write_bias_seed = { pedals = 0.32 },
        write_bias_bound = 0.5,
        write_bias_tau_s = 3.0,
        write_bias_settle_s = 1.0,
        write_bias_settle_band = 0.02,
        pedal_near_limit_margin = 0.1,
        collective_rate_cap_near_pedal_limit = 0.3,
        rotor_rpm_warning_pct = 88.0,
        collective_ease_rate_near_rpm_warning = -0.3,
        retreating_blade_stall_margin_kmh = 20.0,
        collective_rate_cap_near_blade_stall = 0.0,
        turn_settle_deg_s = 0.3,
        law_hz = 30.0,
        velocity_source = "position",
        w_v_s = 0.1,
        w_a_s = 0.2,
        w_a2_s = 0.1,
        w_b = 0.2,
        ball_centre = 0.03,
        ball_usable_range = 0.5,
        -- LV-3 amendment -- mirrors `flight_profile.lua`.
        lambda_hover_kmh = 25.0,
        lambda_forward_kmh = 80.0,
        k_yaw_damp = 0.03,
        yaw_damp_max = 0.25,
        yaw_damp_v_floor_mps = 5.0,
        k_yaw_rate_i = 0.03,
        hover_omega_heading = 0.7,
        hover_yaw_rate_max_deg_s = 8.0,
        k_drift_hold = 0.3,
        speed_band_min_mps = 1.0,
        hover_pedal_band = 0.3,
        hover_pedal_band_forward = 2.0,
        goal_jerk_hover_mps3 = 0.5,
        goal_jerk_edge_mps3 = 5.0,
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


#: The pedal write-bias seed the harness's `flight_profile` mirror
#: carries (`write_bias_seed.pedals`) -- a take writes the captured
#: pedal command plus this (debug-2026-11-24c, finding 1).
_PEDAL_BIAS_SEED = 0.32


def _run(
    driver: str,
    *,
    rotor_rpm_source: str | None = None,
    patches: dict[str, str] | None = None,
) -> list[str]:
    """Assembles core-helper extraction + the mock preamble + the whole
    of `flight_control.lua` (wrapped as an immediately-invoked function
    expression so its own `return M` becomes this expression's value)
    + `driver` (which may print lines), and returns stdout split into
    lines. Skips cleanly without a Lua interpreter on `PATH`.

    `rotor_rpm_source` (mode-1 batch) patches the module's own
    `ROTOR_RPM_SOURCE` default -- calibrated and live (`"arg_proxy"`)
    since 2026-11-25 -- to whichever value `TestReadRotorRpmPct` below
    needs, including back to `"dummy"` for the one test that still
    wants the dummy fallback -- the one module-level constant no test
    needs to flip otherwise, so a one-line source-text substitution is
    simpler than threading a new mock global through every other test
    in this file."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    core_helpers = "\n".join(
        _extract_lua_function(_CORE_LUA, name) for name in _CORE_HELPERS
    )
    module_source = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
    if rotor_rpm_source is not None:
        needle = 'local ROTOR_RPM_SOURCE = "arg_proxy"'
        assert needle in module_source, "ROTOR_RPM_SOURCE default line moved/renamed"
        module_source = module_source.replace(
            needle, f'local ROTOR_RPM_SOURCE = "{rotor_rpm_source}"'
        )
    # `patches`: further exact source-text substitutions, each asserted
    # present so a renamed line fails loudly instead of silently testing
    # the unpatched module.
    for needle, replacement in (patches or {}).items():
        assert needle in module_source, f"patch target moved/renamed: {needle!r}"
        module_source = module_source.replace(needle, replacement)
    script = (
        _PREAMBLE
        + "\n"
        + core_helpers
        + "\nlocal flight_control = (function()\n"
        + module_source
        + "\nend)()\n"
        # LV-3 -- every driver calls `flight_control.run_flight_control(t)`
        # directly with its own `t`; this one-time wrap (rather than
        # threading `_mock_t` through every call site in this file) is
        # what lets `LoGetSelfData`'s own `Position` mock (`_PREAMBLE`)
        # advance by real elapsed sim time.
        + "local _real_run_flight_control = flight_control.run_flight_control\n"
        + "flight_control.run_flight_control = function(t)\n"
        + "    _mock_t = t\n"
        + "    return _real_run_flight_control(t)\n"
        + "end\n"
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
        """M0-B (2026-11-18): `SIGN.pedals = -1.0` -- the intended command
        is `-captured_arg`, not the raw arg value. Since debug-2026-11-24c
        the take frame writes that plus the pedal write-bias seed (0.32,
        `write_bias_seed`), so the pedal itself stays where it was."""
        driver = """
pilot_args.pedals = 0.4
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
print(string.format("%.6f", written[2003]))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - (-0.4 + _PEDAL_BIAS_SEED)) <= 0.0011

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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    def test_accepted_below_80_kmh_no_hand_back(self) -> None:
        """BL-16 lift-vector law, Stage LV-1 (U1/U8): the 80 km/h
        unpark-take refusal is gone entirely -- `check_unpark_
        preconditions` no longer reads IAS at all. An unpark at any
        airspeed is accepted; only on-ground still refuses."""
        driver = """
ap_parked = true
ap_seat = "operator"
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
        assert _field(status_line, "fc_mode") == "active"
        assert _field(status_line, "fc_refuse_cause") is None

    def test_refused_with_a_stale_lease(self) -> None:
        driver = """
ap_parked = true
ap_seat = "operator"
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":1.0}}',
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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

    def test_both_seats_live_captures_the_players_own_seat_not_a_snapshot(
        self,
    ) -> None:
        """User rule, 2026-11-24 (`plans/flight-lift-vector/debug-2026-
        11-24b.md`): "controls must be read and written from which ever
        seat player is in". Replaces the M0-J test that preferred the
        last-steady snapshot when both seats read live: with the
        player's seat known and live, its own current values are
        captured, never an older snapshot and never the other seat."""
        driver = """
pilot_args.pitch = 0.3
pilot_args.pedals = 0.0
operator_args.pitch = 0.0
ap_seat = "pilot"
ap_parked = false
-- A steady frame: only the pilot set is live. Snapshot tracked.
flight_control.run_flight_control(0.0)
-- Now both read live and the player's (pilot) pedals have moved since
-- the snapshot; the take lands on this frame.
pilot_args.pitch = 0.15
pilot_args.pedals = 0.3
operator_args.pitch = 0.2
operator_args.pedals = 0.1
flight_control.request_take(1, 0.1)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
print(string.format("%.6f", written[2001]))
print(string.format("%.6f", written[2003]))
"""
        lines = _run(driver)
        status_line, pitch_written, pedal_written = lines[0], lines[1], lines[2]
        assert _field(status_line, "fc_mode") == "active"
        # The pilot set as it reads now (0.15 / 0.3), not the snapshot
        # (0.3 / 0.0) and not the operator set (0.2 / 0.1).
        assert abs(float(pitch_written) - 0.15) <= 0.0011
        # Pedal command = SIGN.pedals (-1) * captured arg, plus the
        # write-bias seed (debug-2026-11-24c).
        assert abs(float(pedal_written) - (-0.3 + _PEDAL_BIAS_SEED)) <= 0.0011

    def test_player_in_operator_seat_with_live_controls_captures_the_operator_set(
        self,
    ) -> None:
        driver = """
pilot_args.pitch = 0.25
pilot_args.pedals = 0.2
operator_args.pitch = 0.1
operator_args.pedals = -0.05
ap_seat = "operator"
ap_parked = false
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
print(string.format("%.6f", written[2001]))
print(string.format("%.6f", written[2003]))
"""
        lines = _run(driver)
        assert abs(float(lines[0]) - 0.1) <= 0.0011
        assert abs(float(lines[1]) - (0.05 + _PEDAL_BIAS_SEED)) <= 0.0011

    def test_take_debug_line_names_seat_source_and_both_seats_args(self) -> None:
        """Testing aid (`debug-2026-11-24b.md`, question 4): with the
        flight-trace flag on, a take logs the player's seat, the capture
        branch, the captured values and both seats' raw args."""
        driver = """
lfs = { writedir = function() return "/nonexistent-petrobrain-test/" end }
pilot_args.pitch = 0.2
pilot_args.pedals = 0.3
ap_seat = "pilot"
ap_parked = false
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.1)
"""
        lines = _run(
            driver,
            patches={
                "local FLIGHT_TRACE_ENABLED = flight_trace_ok and flight_trace_check == true": (
                    "local FLIGHT_TRACE_ENABLED = true"
                ),
                '            debug_log(string.format(\n                "flight take': (
                    '            print(string.format(\n                "flight take'
                ),
            },
        )
        take_lines = [line for line in lines if line.startswith("flight take")]
        assert len(take_lines) == 1
        line = take_lines[0]
        assert "player_seat=pilot" in line
        assert "source=player_seat_pilot" in line
        assert "a1103=0.3000" in line
        assert "a1113=0.0000" in line


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

    def test_the_resume_frame_after_a_huge_jump_takes_no_giant_law_step(self) -> None:
        """BL-16 lift-vector law, Stage LV-1 fix (review-lv1.md, required
        fix 1, plan amendment "Pause... no integrator step on the resume
        frame beyond the existing DT_CAP rule"). `law_update` now runs on
        its own schedule with `dt` = time since it last ran -- without a
        guard, a huge jump that happens AFTER `law_update` has already
        run at least once (so `fc_law_last_update_t` is a real, stale
        timestamp going into the jump -- the jump frame itself is frozen,
        covered by the test above, and never touches it) would feed that
        whole multi-second gap into the very next `law_update` call as
        its own `dt`.

        Confirmed as a real defect by running this exact driver with the
        guard removed before writing this test, instrumented with
        `debug_scheduling_counts()`: `law_update` does not fire on the
        very first resume frame -- the jump also re-primes the
        (unrelated, pre-existing) un-primed-estimator gate, which defers
        `law_update`'s own first post-jump call by several frames while
        the estimator re-primes -- but once it does fire, pitch jumps
        from ~0.499 to ~0.53 in that one step and keeps climbing, where
        the guarded version stays flat at ~0.499-0.501 (wobble only)
        throughout. This driver therefore runs enough resume frames to
        reach past that deferred first call, not just the first one."""
        driver = """
pilot_args.pitch = 0.5
pilot_args.roll = 0.2
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(10.0)
set_desired(2, { heading_deg = 90.0 })
-- A few ordinary frames first, so `law_update` actually runs at least
-- once and `fc_law_last_update_t` holds a real (soon-to-be-stale)
-- timestamp -- the take frame itself never calls `law_update` (bit-
-- exact), so without this, the jump below would hit a `nil` schedule
-- and never exercise the guard at all.
local t = 10.0
for _ = 1, 20 do
    t = t + 1.0 / 140.0
    flight_control.run_flight_control(t)
end
local before_pitch = written[2001]
local before_roll = written[2002]
written = {}
-- The jump: dt = 40s, above DT_CAP, frozen (the test above covers this
-- frame itself). `fc_law_last_update_t` is untouched -- now 40s stale.
t = t + 40.0
flight_control.run_flight_control(t)
written = {}
-- Ten ordinary resume frames (~1/140 s each) -- enough to get past the
-- few frames the (unrelated) un-primed-estimator gate defers `law_
-- update`'s own first post-jump call by. Without the DT_CAP guard on
-- `law_dt`, that first call sees `law_dt` ~= 40s instead of ~1/140 s.
for _ = 1, 10 do
    t = t + 1.0 / 140.0
    flight_control.run_flight_control(t)
end
print(string.format("%.6f", before_pitch))
print(string.format("%.6f", written[2001]))
print(string.format("%.6f", before_roll))
print(string.format("%.6f", written[2002]))
"""
        lines = _run(driver)
        before_pitch, after_pitch, before_roll, after_roll = (float(v) for v in lines)
        # Ten ordinary ~1/140 s steps can move the output by at most a
        # few frames' worth of the rate limiter (`OUTPUT_RATE_LIMIT_
        # PER_S * dt`, 4.0 * 1/140 ~= 0.0286 each) plus the wobble step
        # -- a tight bound that still passes with the guard (measured
        # delta ~0.002) and fails without it (measured ~0.03-0.04 and
        # still climbing).
        assert abs(after_pitch - before_pitch) <= 0.01
        assert abs(after_roll - before_roll) <= 0.01


class TestEnvelopeRelease:
    """BL-16 lift-vector law, Stage LV-1 (U1/U8): the low-IAS envelope
    release is gone entirely -- `check_envelope` only ever releases on
    `"dead"`/`"nan"` any more. What used to be `TestEnvelopeRelease`'s
    own positive case (`test_sustained_low_ias_releases_after_the_hold`)
    is now the negative one below."""

    def test_sustained_low_ias_never_releases_no_hand_back(self) -> None:
        # Every frame advances by 0.2 s (well under `DT_CAP`, so no
        # frame is ever treated as a pause), well past what used to be
        # `ENV_HOLD_S` (3.0 s) of sustained low IAS -- LV-1 has no
        # release left to trigger here at all.
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
        assert _field(lines[0], "fc_mode") == "active"
        assert _field(lines[0], "fc_release_reason") is None

    def test_sustained_high_bank_never_releases(self) -> None:
        """F-M1 (mode-1 batch): "remove the 30 degree limit. Set no
        limit for now" -- there is no bank-triggered release any more
        at all. A bank well past the old 30 deg ceiling, held for well
        past the old `ENV_HOLD_S`, never releases."""
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
        lines = _run(driver, rotor_rpm_source="dummy")
        assert float(lines[0]) == 90.0
        assert lines[1] == "true"

    def test_arg_proxy_scales_a_good_read(self) -> None:
        """Calibrated 2026-11-25 (RPM calibration flight): gauge % =
        arg x 110, not x100 -- the 2026-11-19 guess corrected."""
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
        assert abs(float(lines[0]) - 80.3) < 1e-6
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":1.0}}',
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
    '{"op":"flight_lease","epoch":1,"limits":{"max_ias_kmh":999.0}}', 0.0)
ap_parked = true
ias_mps = 150.0 / 3.6
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        # The out-of-bounds `max_ias_kmh` (LV-1 removed `min_ias_kmh`
        # from `FC_LIMIT_BOUNDS` entirely, U8) rejected the whole lease
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    """BL-16 Stage 2: a voice take re-checks AGL itself (`check_unpark_
    preconditions`), rather than trusting body-layer's own pre-send
    refusal alone. **LV-1 (U1/U8)**: the IAS half of that check is gone
    -- a voice take is accepted at any airspeed now."""

    def test_a_voice_take_below_80_kmh_is_accepted_no_hand_back(self) -> None:
        driver = """
ias_mps = 20.0 / 3.6
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.push_flight_control_state(0.0)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        assert _field(line, "fc_mode") == "taking"
        assert _field(line, "fc_refuse_cause") is None

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
    .. '"limits":{"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
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
    -- `build_take_seed`'s unpark branch clamps the speed seed to `fc_
    limits.max_ias_kmh` (the altitude seed keeps its own `floor_agl_m`
    clamp, unaffected by this stage). **LV-1 (U1/U8): the speed seed's
    own lower bound (`min_ias_kmh`) is gone entirely** -- a carried
    speed below 0 is impossible, but any low, carried speed now flies
    exactly as commanded, no floor. `desired` itself is never touched,
    only the seed fed to `law_init_at_take`."""

    def test_speed_0_in_m2_then_unpark_flies_exactly_0_no_floor(self) -> None:
        """The plan's own worked example, U8's final answer: measured
        IAS is set to exactly 0 so the (unclamped) seed and the
        (unmoving, mocked) measured value agree immediately -- `fc_in_
        band_speed` only reads `true` here if the seed was flown
        exactly as commanded, with no floor clamping it up.

        BL-16 lift-vector law, Stage LV-1 fix (review-lv1.md, required
        fix 1): `law_update` (which computes `in_band_speed`) no longer
        runs every frame -- at this driver's own 0.1 s step (coarser
        than `law_hz`'s own ~0.033 s period), the estimator and the law
        are due on the same call every time, so the first post-take
        ordinary frame always defers the law once (never the same frame
        as the estimator step, the fix's own guarantee) and a *second*
        ordinary frame is where it actually runs. One extra `run_flight_
        control` call over the pre-fix version of this test."""
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ias_mps = 0.0
ap_seat = "operator"
ap_parked = true
set_desired(1, { ias_kmh = 0.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"max_ias_kmh":280.0,'
    .. '"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.run_flight_control(0.3)
flight_control.run_flight_control(0.4)
flight_control.push_flight_control_state(0.4)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_in_band_speed") == "true"

    def test_speed_above_the_ceiling_in_m2_then_unpark_flies_the_ceiling(
        self,
    ) -> None:
        """BL-16 lift-vector law, Stage LV-1 fix (review-lv1.md, required
        fix 1) -- see the extra `run_flight_control` call's own comment
        on the sibling test above (same reason, same fix)."""
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ias_mps = 280.0 / 3.6
ap_seat = "operator"
ap_parked = true
set_desired(1, { ias_kmh = 400.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"max_ias_kmh":280.0,'
    .. '"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.run_flight_control(0.3)
flight_control.run_flight_control(0.4)
flight_control.push_flight_control_state(0.4)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_in_band_speed") == "true"

    def test_an_in_range_speed_is_carried_unclamped(self) -> None:
        """Control: a value already inside `[0, max_ias_kmh]` is seeded
        verbatim, same as before this fix. BL-16 lift-vector law, Stage
        LV-1 fix (review-lv1.md, required fix 1) -- see the extra `run_
        flight_control` call's own comment on the first test in this
        class (same reason, same fix)."""
        driver = """
heading_rad = math.rad(0.0)
bank_rad = math.rad(2.0)
ias_mps = 150.0 / 3.6
ap_seat = "operator"
ap_parked = true
set_desired(1, { ias_kmh = 150.0 })
flight_control.handle_flight_lease_command(
    '{"op":"flight_lease","epoch":1,'
    .. '"limits":{"max_ias_kmh":280.0,'
    .. '"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
flight_control.run_flight_control(0.3)
flight_control.run_flight_control(0.4)
flight_control.push_flight_control_state(0.4)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "active"
        assert _field(line, "fc_in_band_speed") == "true"


class TestEstimatorStatusFields:
    """BL-16 lift-vector law, Stage LV-0 (`plans/flight-lift-vector/
    plan.md`) -- the estimator runs every frame in every mode, so its
    `fc_est_*` status fields must show up on the wire even while
    `fc_mode == "off"` (no take ever requested), the thing the toy-plant
    harness (`test_flight_control_law.py`/`test_flight_control_
    estimator.py`) cannot exercise since it never drives the whole
    module end to end."""

    def test_est_fields_are_present_and_finite_while_off(self) -> None:
        driver = """
heading_rad = math.rad(0.0)
flight_control.run_flight_control(0.0)
flight_control.run_flight_control(0.033)
flight_control.run_flight_control(0.066)
flight_control.push_flight_control_state(0.066)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "off"
        for field in (
            "fc_est_a_f",
            "fc_est_a_r",
            "fc_est_a_u",
            "fc_est_v_g",
            "fc_est_v_g_f",
            "fc_est_phi_dot",
            "fc_est_theta_dot",
            "fc_est_psi_dot",
            "fc_est_ball",
            "fc_est_lambda",
        ):
            value = _field(line, field)
            assert value is not None, f"{field} was null"
            assert math.isfinite(float(value))

    def test_est_v_g_tracks_a_straight_northbound_leg_while_off(self) -> None:
        """The estimator does not need `fc_mode == "active"` to produce
        a real reading -- a pilot-flown calibration leg (no take ever
        requested) must still show ground speed, the same "works in
        every mode, including a pilot flying it" posture the slip-ball
        readout already has."""
        driver = """
heading_rad = math.rad(0.0)
for i = 0, 30 do
    local t = i * (1.0 / 30.0)
    flight_control.run_flight_control(t)
end
flight_control.push_flight_control_state(1.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        line = lines[0]
        assert _field(line, "fc_mode") == "off"
        # No real `LoGetSelfData().Position` is ever supplied by this
        # mock (it reads a `Heading` only, same shape as before LV-0 --
        # see `_PREAMBLE`'s own `LoGetSelfData`) -- so this only pins
        # that the field is present, finite, and non-negative (a
        # magnitude), not a specific value the mock cannot produce.
        v_g = float(_field(line, "fc_est_v_g"))
        assert v_g >= 0.0


#: Toy pedal plant for `TestPedalWriteBias` (debug-2026-11-24c, finding
#: 1): what the 2026-11-24 data flight measured -- in flight the pedal
#: arg settles at `PLANT_OFFSET - command`, first order with the pedal's
#: own ~0.25 s lag (M0-B). Holds still while nothing is written. Every
#: pedal-moving law term is zeroed so the law's intended pedal is the
#: captured one for the whole run; the test then reads only the write
#: stage.
_PEDAL_PLANT = """
local PLANT_OFFSET = 0.32
local PLANT_TAU = 0.25
flight_profile.ACTIVE.k_ball_pedal = 0.0
flight_profile.ACTIVE.k_pedal_from_collective_rate = 0.0
flight_profile.ACTIVE.k_turn_coord_pedal = 0.0
local function plant_step(dt)
    local cmd = written[2003]
    if cmd == nil then return end
    local target = PLANT_OFFSET - cmd
    pilot_args.pedals = pilot_args.pedals
        + (target - pilot_args.pedals) * (1.0 - math.exp(-dt / PLANT_TAU))
end
-- Runs frames from t0 for `seconds` at `hz`; returns the end time and the
-- largest |pedal arg - ref| seen within the first `window_s`.
local function fly(t0, seconds, hz, ref, window_s)
    local dt = 1.0 / hz
    local t = t0
    local worst = 0.0
    while t < t0 + seconds do
        t = t + dt
        flight_control.run_flight_control(t)
        plant_step(dt)
        if t - t0 <= window_s then
            worst = math.max(worst, math.abs(pilot_args.pedals - ref))
        end
    end
    return t, worst
end
ap_parked = false
ap_seat = "pilot"
pilot_args.pitch = 0.1
pilot_args.collective = 0.3
"""


class TestPedalWriteBias:
    """Debug-2026-11-24c, finding 1: the in-flight pedal write lands 0.32
    left of the command. The output stage writes `intended + bias`,
    seeded from `flight_profile`'s `write_bias_seed` and learnt online,
    so the pedal stays where the player held it at the take."""

    def test_seeded_bias_makes_the_take_bumpless_on_the_actual_pedal(self) -> None:
        driver = (
            _PEDAL_PLANT
            + """
pilot_args.pedals = 0.15
flight_control.request_take(1, 0.0)
local _, worst = fly(0.0, 3.0, 140.0, 0.15, 3.0)
print(string.format("%.6f", worst))
"""
        )
        worst = float(_run(driver)[0])
        # Without the bias the pedal settles 0.32 away (the kick).
        assert worst < 0.01, worst

    def test_a_wrong_seed_kicks_then_the_bias_is_learnt(self) -> None:
        driver = (
            _PEDAL_PLANT
            + """
flight_profile.ACTIVE.write_bias_seed = { pedals = 0.0 }
pilot_args.pedals = 0.15
flight_control.request_take(1, 0.0)
local _, early = fly(0.0, 25.0, 60.0, 0.15, 1.5)
print(string.format("%.6f", early))
print(string.format("%.6f", pilot_args.pedals))
print(string.format("%.6f", written[2003]))
"""
        )
        early, final_arg, final_written = (float(x) for x in _run(driver))
        # The toy plant does kick with a zero seed -- the test bites.
        assert early > 0.25, early
        # ...and the learnt bias brings the pedal back to where it was.
        assert abs(final_arg - 0.15) < 0.02, final_arg
        # written = intended (-0.15) + learnt bias (~0.32).
        assert abs(final_written - (-0.15 + 0.32)) < 0.025, final_written

    def test_the_learnt_bias_carries_into_the_next_take_and_on_stop_clears_it(
        self,
    ) -> None:
        driver = (
            _PEDAL_PLANT
            + """
flight_profile.ACTIVE.write_bias_seed = { pedals = 0.0 }
pilot_args.pedals = 0.15
flight_control.request_take(1, 0.0)
local t = fly(0.0, 25.0, 60.0, 0.15, 0.0)
-- Release: writes stop, the pedal holds (M0-F).
flight_control.request_release(2)
written = {}
t = fly(t, 1.0, 60.0, 0.0, 0.0)
local held = pilot_args.pedals
flight_control.request_take(3, t)
local t2, worst_retake = fly(t, 3.0, 60.0, held, 3.0)
print(string.format("%.6f", worst_retake))
-- Mission stop: the learnt bias goes back to the (zero) seed.
flight_control.on_stop()
written = {}
held = pilot_args.pedals
flight_control.request_take(4, t2 + 1.0)
local _, worst_after_stop = fly(t2 + 1.0, 1.5, 60.0, held, 1.5)
print(string.format("%.6f", worst_after_stop))
"""
        )
        worst_retake, worst_after_stop = (float(x) for x in _run(driver))
        assert worst_retake < 0.03, worst_retake
        assert worst_after_stop > 0.25, worst_after_stop


class TestCollectiveLawDirection:
    """Debug-2026-11-24c, finding 2: the law's collective is positive =
    up (`LAW_DIR`), command 2087 positive = down (`SIGN.collective` -1,
    arg 1102 positive = up). Climbing at the take, the altitude shaper
    asks to arrest the climb, so the lever must go DOWN -- the arg falls,
    the written command rises. Before the fix it ran to full up."""

    def test_arresting_a_climb_lowers_the_collective(self) -> None:
        driver = """
ap_parked = false
ap_seat = "pilot"
pilot_args.pitch = 0.1
pilot_args.collective = 0.3
vs_mps = 5.0
flight_control.request_take(1, 0.0)
local t = 0.0
for _ = 1, 3 * 60 do
    t = t + 1.0 / 60.0
    flight_control.run_flight_control(t)
end
print(string.format("%.6f", written[2087]))
"""
        written_collective = float(_run(driver)[0])
        # Captured command is -0.3; down is a rising command.
        assert written_collective > -0.3 + 0.05, written_collective


class TestPitchLawDirection:
    """Third re-fly, 2026-11-24 (`docs/acceptance/2026-11-24-sortie-
    feedback.md`, "Third re-fly"; `plans/flight-lift-vector/debug-
    2026-11-24c.md`, superseded section): the law's pitch is positive =
    nose up (`LAW_DIR`), and command 2001 positive is ALSO nose up
    (`SIGN.pitch = 1.0`, arg 1100 positive = stick aft/nose up -- the
    `LAW_DIR.pitch = -1.0` main-loop finding this test originally
    encoded was flown and made the loop positive feedback; reverted,
    `aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.
    md`). The toy plant fact driving this test's assertion -- independent
    of the law's own internal domain convention -- is that very same
    arg-1100 reading: a positive written 2001 command moves the real
    aircraft's pitch UP. So with the aircraft's actual pitch driven
    below the held `theta_d` (nose too low, the law wants more nose-up),
    the written command must rise, never fall."""

    def test_pitch_below_theta_d_raises_the_written_command(self) -> None:
        driver = """
ap_parked = false
ap_seat = "pilot"
pilot_args.pitch = 0.0
pitch_rad = 0.0
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.0)
local captured = written[2001]
-- Plant fact (not the law's own convention): arg 1100/command 2001
-- positive drives pitch up, so a nose-low aircraft relative to the
-- held `theta_d` is modelled here as the measured pitch falling below
-- the take value -- an external disturbance, never written by this
-- module.
pitch_rad = pitch_rad - math.rad(5.0)
local t = 0.0
for _ = 1, 3 * 60 do
    t = t + 1.0 / 60.0
    flight_control.run_flight_control(t)
end
print(string.format("%.6f", captured))
print(string.format("%.6f", written[2001]))
"""
        captured, after = (float(x) for x in _run(driver))
        # Pitch sits below theta_d (wants more nose-up): the written
        # command must rise, not fall.
        assert after > captured + 0.001, (captured, after)

    def test_take_stays_bit_exact_on_pitch(self) -> None:
        """The flip (`LAW_DIR.pitch`) and its inverse (`law_domain` on
        the captured command, at `law_init_at_take`) must cancel exactly
        at the take frame, same guarantee `TestCollectiveLawDirection`'s
        sibling bit-exact tests rely on elsewhere in this file."""
        driver = """
ap_parked = false
ap_seat = "pilot"
pilot_args.pitch = 0.23
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.0)
print(string.format("%.6f", written[2001]))
"""
        written_pitch = float(_run(driver)[0])
        assert abs(written_pitch - 0.23) <= 0.0011


class TestLawHzScheduling:
    """BL-16 lift-vector law, Stage LV-1 fix (`plans/flight-lift-vector/
    review-lv1.md`, required fix 1) -- `law_update` itself now runs only
    at `profile.law_hz` (not every frame), on a different frame from the
    estimator step every time the two would otherwise land together.
    `flight_control.debug_scheduling_counts()` (diagnostic-only, not on
    any wire) observes the real decision `run_flight_control`/`run_
    active_frame` made each actual frame -- not inferred indirectly from
    a wire-level side effect, which `law_outputs`' own per-frame write
    and the pause/wobble logic would make fragile to read."""

    def test_law_update_runs_near_law_hz_and_never_the_same_frame_as_the_estimator(
        self,
    ) -> None:
        driver = """
ap_parked = false
ap_seat = "pilot"
flight_control.request_take(1, 0.0)
flight_control.run_flight_control(0.0)
local baseline = flight_control.debug_scheduling_counts()
local prev_est, prev_law = baseline.estimator_sample, baseline.law_update
local same_frame_collisions = 0
-- 140 Hz DCS frame rate (the project's own typical measured rate,
-- `aircraft-layer/CLAUDE.md`) for exactly 1 simulated second -- the
-- required fix's own wording ("a 140 Hz frame rate... ~LAW_HZ times
-- per simulated second").
local FRAME_DT = 1.0 / 140.0
local t = 0.0
for _ = 1, 140 do
    t = t + FRAME_DT
    flight_control.run_flight_control(t)
    local counts = flight_control.debug_scheduling_counts()
    local estimator_ran = counts.estimator_sample > prev_est
    local law_ran = counts.law_update > prev_law
    if estimator_ran and law_ran then
        same_frame_collisions = same_frame_collisions + 1
    end
    prev_est, prev_law = counts.estimator_sample, counts.law_update
end
print(same_frame_collisions)
print(prev_law)
print(prev_est)
"""
        lines = _run(driver)
        collisions, law_calls, estimator_calls = (
            int(lines[0]),
            int(lines[1]),
            int(lines[2]),
        )
        # The one property the fix exists for: no single frame ever
        # carries both steps.
        assert collisions == 0
        # ~30 (`law_hz`) over the 1 s window -- loose bounds since the
        # estimator needs two samples (~5 frames) to prime before the
        # law may run at all (the pre-existing un-primed-estimator
        # gate, unchanged by this fix), and the one-frame defer on a
        # would-be collision nudges a tick later by construction.
        assert 20 <= law_calls <= 34, law_calls
        assert 25 <= estimator_calls <= 34, estimator_calls


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
