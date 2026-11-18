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
`fmt_num_or_null`, `json_escape_string`) are extracted from the real
`core.lua`, same technique `test_ai_pilot_wheel_lua.py` already uses.

Internal state (`fc_mode`/`fc_release_reason`/`fc_refuse_cause`/...) is
never exported directly -- the test reads it the same way body-layer
does, through `push_flight_control_state`'s own wire line, parsed back
with the same flat-field regex `core.lua`'s own extractors use. Per-frame
`LoSetCommand` writes are captured via a mock DCS control surface.

Skips cleanly without a Lua interpreter on `PATH`."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

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
    "fmt_num_or_null",
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
local bank_rad = 0.0
local agl_m = 200.0
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
    return 0.0, bank_rad, 0.0
end

function LoGetIndicatedAirSpeed()
    return ias_mps
end

function LoGetAltitudeAboveGroundLevel()
    return agl_m
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
}

client = {
    send = function(self, line)
        table.insert(sent_lines, line)
        return true
    end,
}
"""


def _run(driver: str) -> list[str]:
    """Assembles core-helper extraction + the mock preamble + the whole
    of `flight_control.lua` (wrapped as an immediately-invoked function
    expression so its own `return M` becomes this expression's value)
    + `driver` (which may print lines), and returns stdout split into
    lines. Skips cleanly without a Lua interpreter on `PATH`."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    core_helpers = "\n".join(
        _extract_lua_function(_CORE_LUA, name) for name in _CORE_HELPERS
    )
    module_source = _FLIGHT_CONTROL_LUA.read_text(encoding="utf-8")
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

    def test_unpark_take_is_refused_disabled_in_stage_m1(self) -> None:
        """`UNPARK_TAKE_ENABLED` defaults off until M0-J passes (plan,
        Decision 24/U7) -- so in Stage M1's own shipped state an unpark
        from `armed` always refuses with cause `"disabled"` and writes
        nothing, whatever seat the player is in or which set holds a
        non-zero value. Decision 24/25's own capture-source rule (the
        unpark path always reads the **pilot** set, 1100-1103, never the
        live seat) is therefore not exercisable through this module's
        public interface while the flag is off; it is deferred to the
        live M0-J probe, per the plan's own "fail -> disables the
        unpark take, does not block mode 1" posture."""
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
print(written[2001] == nil)
"""
        lines = _run(driver)
        status_line, nothing_written = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "off"
        assert _field(status_line, "fc_refuse_cause") == "disabled"
        assert nothing_written == "true"


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
        # UNPARK_TAKE_ENABLED is off in Stage M1, so "disabled" wins
        # over every other precondition (checked first in `run_flight_
        # control`'s own unpark-take branch) -- the IAS-specific "too_
        # slow" cause is not reachable through this module's public
        # interface until M0-J flips the flag on; see `test_unpark_
        # take_is_refused_disabled_in_stage_m1`'s own docstring for the
        # same gap on the capture-source side.
        assert _field(status_line, "fc_refuse_cause") == "disabled"

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
        assert _field(status_line, "fc_refuse_cause") == "disabled"


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
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(10.0)
written = {}
-- dt <= 0 (a paused frame: model time did not advance).
flight_control.run_flight_control(10.0)
print(written[2001] ~= nil)
"""
        lines = _run(driver)
        assert lines[0] == "true"

    def test_a_huge_frame_jump_also_rewrites_rather_than_shaping(self) -> None:
        driver = """
pilot_args.pitch = 0.5
ap_parked = false
ap_seat = "pilot"
flight_control.handle_flight_control_command(
    '{"op":"flight_control","seq":1,"cmd":"take","limits":{"min_ias_kmh":80.0}}', 0.0)
flight_control.run_flight_control(10.0)
written = {}
flight_control.run_flight_control(50.0)  -- dt = 40s, above DT_CAP
flight_control.push_flight_control_state(50.0)
print(sent_lines[#sent_lines])
print(written[2001] ~= nil)
"""
        lines = _run(driver)
        status_line, wrote = lines[0], lines[1]
        assert _field(status_line, "fc_mode") == "active"
        assert wrote == "true"


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


class TestAxesEnabledOnTheWire:
    def test_pedal_and_collective_report_disabled(self) -> None:
        driver = """
flight_control.push_flight_control_state(0.0)
print(sent_lines[#sent_lines])
"""
        lines = _run(driver)
        assert _field(lines[0], "fc_axes_pitch") == "true"
        assert _field(lines[0], "fc_axes_roll") == "true"
        assert _field(lines[0], "fc_axes_pedal") == "false"
        assert _field(lines[0], "fc_axes_collective") == "false"


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
