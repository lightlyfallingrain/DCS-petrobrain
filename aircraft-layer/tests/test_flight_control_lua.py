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

local SEAT_ARG_NUM = {
    [1100] = "pilot.pitch", [1101] = "pilot.roll",
    [1102] = "pilot.collective", [1103] = "pilot.pedals",
    [1110] = "operator.pitch", [1111] = "operator.roll",
    [1112] = "operator.collective", [1113] = "operator.pedals",
}

local function arg_value(n)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"goal","limits":{},'
    .. '"heading_deg":90.0,"alt_m":500.0,"alt_ref":"baro","ias_kmh":150.0}', 0.1)
flight_control.run_flight_control(0.2)
flight_control.push_flight_control_state(0.2)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":3,"cmd":"release","limits":{}}', 0.3)
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":4,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.4)
flight_control.run_flight_control(0.4)
flight_control.push_flight_control_state(0.4)
print(sent_lines[#sent_lines - 2])
print(sent_lines[#sent_lines - 1])
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        held_line, released_line, retaken_line = lines[0], lines[1], lines[2]
        # Before release: the goal is held.
        assert _field(held_line, "fc_goal_heading") == "90.00000"
        assert _field(held_line, "fc_goal_altitude") == "500.00000"
        assert _field(held_line, "fc_goal_altitude_ref") == "baro"
        assert _field(held_line, "fc_goal_speed") == "150.00000"
        # After release: every goal field clears, matching `on_stop`.
        assert _field(released_line, "fc_mode") == "off"
        assert _field(released_line, "fc_goal_heading") is None
        assert _field(released_line, "fc_goal_altitude") is None
        assert _field(released_line, "fc_goal_altitude_ref") is None
        assert _field(released_line, "fc_goal_speed") is None
        # After the fresh re-take, with no goal commanded yet: still
        # None, not the previous session's stale values.
        assert _field(retaken_line, "fc_mode") == "active"
        assert _field(retaken_line, "fc_goal_heading") is None
        assert _field(retaken_line, "fc_goal_altitude") is None
        assert _field(retaken_line, "fc_goal_altitude_ref") is None
        assert _field(retaken_line, "fc_goal_speed") is None


class TestRepeatedTakeWhileAlreadyFlyingStillAcks:
    """BL-16 sortie 2026-11-20, defect B (`plans/flight-control/debug.md`):
    a second `take` sent while Lua's `fc_mode` is already `"active"` or
    `"taking"` is a no-op for the aircraft (no re-capture, no law reset
    -- the comment right above this branch says why), but must still
    move `fc_take_seq`/`fc_pending_take_seq` to the new message's own
    seq. Before the fix, `fc_last_cmd_seq` (bumped unconditionally by
    the bounds check, before this branch ever runs) advanced past the
    stale `fc_take_seq`, so belief's own ack match (`lua_take_seq ==
    take_seq`, set to the sent wire seq by `body.py`'s `_apply_flight_
    control`) could never succeed for that take -- "Unable, not ready,"
    forever, while Lua kept flying regardless."""

    def test_a_repeated_take_while_active_still_updates_take_seq(self) -> None:
        driver = """
pilot_args.pitch = 0.1
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.2)
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
print(sent_lines[#sent_lines - 1])
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        after_take_1, after_take_2 = lines[0], lines[1]
        assert _field(after_take_1, "fc_mode") == "active"
        assert _field(after_take_1, "fc_take_seq") == "1"
        assert _field(after_take_1, "fc_last_cmd_seq") == "1"
        # Before the fix: fc_mode stayed "active" (correct -- it is a
        # no-op for the aircraft), fc_last_cmd_seq advanced to 2 (the
        # bounds check bumps it unconditionally), but fc_take_seq
        # stayed 1 -- the defect.
        assert _field(after_take_2, "fc_mode") == "active"
        assert _field(after_take_2, "fc_last_cmd_seq") == "2"
        assert _field(after_take_2, "fc_take_seq") == "2"

    def test_a_repeated_take_while_still_taking_also_updates_take_seq(
        self,
    ) -> None:
        """Same defect, the `"taking"` half: a second `take` arrives
        before the first one's capture has resolved into `"active"` --
        `fc_pending_take_seq` (not `fc_take_seq` directly, which is only
        set once `run_flight_control`'s own `"taking"` branch completes
        the capture) must move to the new seq, or the eventual `active`
        transition reports the *first* take's seq, not the one belief
        is actually waiting on."""
        driver = """
ap_parked = false
ap_seat = "pilot"
-- No live stick deflection on either seat and no prior steady snapshot
-- -- `resolve_capture_values` falls through to the magnitude-compare
-- fallback, which still succeeds immediately (it never returns nil
-- here), so this is only to exercise the "taking" window itself, not
-- to actually stall the capture.
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "active"
        assert _field(lines[0], "fc_take_seq") == "2"
        assert _field(lines[0], "fc_last_cmd_seq") == "2"


class TestBadBoundRejectsWholeMessage:
    def test_an_out_of_bounds_limit_rejects_the_whole_message(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
-- min_ias_kmh = 9999 is above FC_LIMIT_BOUNDS' own hi=500 ceiling.
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":9999.0}}', 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        # The whole message (including the "take" itself) is rejected --
        # mode stays "off", not "taking"/"active".
        assert _field(lines[0], "fc_mode") == "off"

    def test_a_stale_seq_is_ignored(self) -> None:
        driver = """
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":5,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
-- A stale seq=3 "release" must be ignored -- the take must still be
-- live.
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":3,"cmd":"release","limits":{}}', 0.2)
flight_control.push_flight_control_state(0.2)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_mode") == "active"


class TestLastCmdSeqEchoSurvivesOnStop:
    def test_fc_last_cmd_seq_echoes_and_outlives_on_stop(self) -> None:
        """security-m1-m2.md Finding A, change-request round:
        `fc_last_cmd_seq` is echoed on the status push (added so body-
        layer can reconcile its own `wire_seq` against it after a
        restart) and must survive `on_stop` exactly like the rest of
        this module's "a stale, pre-restart command must still be seen
        as stale" posture -- `on_stop`'s own docstring already states
        this for the underlying counter; this is the first test that
        checks it via the wire echo a restarted body-layer would
        actually read."""
        driver = """
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
flight_control.push_flight_control_state(0.1)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":47,"cmd":"goal","limits":{},"heading_deg":90.0}', 0.1)
flight_control.push_flight_control_state(0.1)
-- `on_stop` (mission restart / LuaExportStop) must NOT reset the
-- counter -- a fresh body-layer process's own first send, reconciled
-- above it, must still be seen as newer than anything this session
-- already accepted.
flight_control.on_stop()
flight_control.push_flight_control_state(0.2)
-- A simulated reconciled resend (body-layer caught `wire_seq` up to
-- 47 from this same echo, so its next send is 48) must be accepted.
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":48,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.3)
flight_control.run_flight_control(0.3)
flight_control.push_flight_control_state(0.3)
print(sent_lines[#sent_lines - 2])
print(sent_lines[#sent_lines - 1])
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        after_goal_line, after_stop_line, after_resend_line = (
            lines[0],
            lines[1],
            lines[2],
        )
        # `plans/flight-control/debug.md` "Common root cause, both
        # modes": these three seq fields are now `fmt_int_or_null`, not
        # `fmt_num_or_null` -- a bare `"47"`, never `"47.00000"`, which
        # `json.loads` would parse as a float and every strict-`int`
        # schema field would then reject whole.
        assert _field(after_goal_line, "fc_last_cmd_seq") == "47"
        # on_stop resets fc_mode but not the staleness counter.
        assert _field(after_stop_line, "fc_mode") == "off"
        assert _field(after_stop_line, "fc_last_cmd_seq") == "47"
        # The reconciled seq=48 is accepted -- strictly greater than
        # the never-reset counter -- and advances it in turn.
        assert _field(after_resend_line, "fc_mode") == "active"
        assert _field(after_resend_line, "fc_last_cmd_seq") == "48"


class TestReleaseStopsWritesSameFrame:
    def test_release_stops_writing_in_the_same_frame(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
written = {}
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"release","limits":{}}', 0.2)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0,"arm_lease_s":3.0}}',
    0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":1.0}}',
    0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
-- A frame fully stowed: tracked.
flight_control.run_flight_control(0.1)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
flight_control.run_flight_control(0.1)
ap_parked = false
flight_control.run_flight_control(0.2)
-- Release, then re-arm without ever reaching the stowed threshold this
-- session -- and the player has since moved the stick.
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"release","limits":{}}', 0.3)
flight_control.run_flight_control(0.3)
pilot_args.roll = 0.9
ap_parked = true
ap_stick_park_raw = 0.5
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":3,"cmd":"arm",'
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
    pilot had just rolled into on purpose. The fix reads `ai_pilot_
    wheel.held_targets()` for an unpark take only, never a voice take
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"arm",'
    .. '"limits":{"min_ias_kmh":80.0,"on_ground_agl_threshold_m":10.0,"arm_lease_s":3.0}}',
    0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.1)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(10.0)
-- A goal that disagrees with the captured heading: if the pause branch
-- wrongly advanced the law instead of freezing it, this is what the
-- shaper would move against.
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"goal","limits":{"min_ias_kmh":80.0},"goal":{"heading_deg":90.0}}', 10.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(10.0)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"goal","limits":{"min_ias_kmh":80.0},"goal":{"heading_deg":90.0}}', 10.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
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


class TestSeqFieldsSurviveTheRealSchema:
    """`plans/flight-control/debug.md` "Common root cause, both modes"
    (2026-11-19): `core.lua`'s `fmt_num_or_null` formatted every number
    `%.5f`, so `fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` went out as
    e.g. `"-1.00000"` -- valid JSON, but a `float`, which `schema.
    flight_control.FlightControlState._optional_int` rejects, dropping
    the whole line. These tests run the real `push_flight_control_state`
    (not a hand-built JSON string) through the real schema's `from_dict`
    -- a weaker test built from a `%.5f`-style string by hand would not
    have caught this, since it would never emit what Lua actually does."""

    def test_default_seqs_parse_as_int_through_the_real_schema(self) -> None:
        """Before any command at all: `fc_take_seq`/`fc_goal_seq` are
        `nil` (`null` on the wire), `fc_last_cmd_seq` is `-1` -- the one
        value that was dropped on every single line, take or no take."""
        driver = """
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        state = FlightControlState.from_dict(
            json.loads(line), received_wall_clock_s=0.0
        )
        assert state.take_seq is None
        assert state.goal_seq is None
        assert state.last_cmd_seq == -1

    def test_seqs_after_a_take_and_a_goal_parse_as_int_through_the_real_schema(
        self,
    ) -> None:
        """A real take (`seq=1`) then a real goal (`seq=2`) -- the exact
        shape a live sortie's handover produces, with every seq field
        now holding a real non-sentinel integer."""
        driver = """
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(0.1)
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":2,"cmd":"goal","limits":{},"heading_deg":90.0}', 0.1)
flight_control.push_flight_control_state(0.1)
print(sent_lines[#sent_lines])
"""
        line = _run(driver)[0]
        state = FlightControlState.from_dict(
            json.loads(line), received_wall_clock_s=0.0
        )
        assert isinstance(state.take_seq, int)
        assert isinstance(state.goal_seq, int)
        assert isinstance(state.last_cmd_seq, int)
        assert state.last_cmd_seq == 2


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
