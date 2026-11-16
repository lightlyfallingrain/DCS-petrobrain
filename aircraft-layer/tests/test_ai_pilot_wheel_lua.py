"""BL-16 mode 2, Stage P1 takeover/stabilisation revision (`plans/
flight-control/plan.md`, "Revised 2026-11-16") -- the pure Lua functions
`run_ai_pilot_wheel`/`update_ai_pilot_wheel_overlay` are built from, run
against a real Lua interpreter and checked against the overlay's known
text shapes, not just read:

- `parse_helperai_overlay_fields` -- the flattening parser against the
  overlay readback research note's own observed text
  (`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md`
  section 3: `mode_text`/`course_text`/`alt_text`/`alt_add_text`/
  `speed_text`, the `R`/`B` altitude-reference suffix).
- `ai_pilot_park_rising` -- the park signal's rising-edge detection on
  arg 852 **alone** (952 dropped from detection, this revision's point 1
  -- it is 852's own mirror, not a second park sensor).
- `ai_pilot_correction_direction`/`ai_pilot_quick_path_eligible` -- the
  correction loop's own pure decisions (replacing the old one-shot
  `ai_pilot_should_nudge_altitude`, removed outright per the plan).
- `ai_pilot_parse_altitude_text`/`ai_pilot_actual_altitude_m` -- read-back
  parsing, unchanged from the original Stage P1 build.
- The full takeover sequence end to end (`TestTakeoverSequence`), against
  a `GetDevice` mock -- detection -> blind reference toggle -> menu open
  -> the three correction paths (`none`/`quick`/`hold`) -> unpark.

Same extraction technique as `test_sight_servo_lua.py`'s own
`_extract_lua_function` (duplicated rather than imported across test
modules, this project's own convention): slice the named `local function
... end` out of the real, currently-deployed `Export.lua` and execute it
standalone. Skips cleanly without a Lua interpreter on `PATH`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_PETROBRAIN_DIR = Path(__file__).resolve().parent.parent / "dcs-export" / "Petrobrain"
_CORE_LUA = _PETROBRAIN_DIR / "core.lua"
_AI_PILOT_WHEEL_LUA = _PETROBRAIN_DIR / "ai_pilot_wheel.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(path: Path, name: str) -> str:
    """Slice `local function {name}(...) ... end` out of `path` --
    `function`/`if`/`for`/`while`/`end` as block openers/closer (`parse_
    helperai_overlay_fields` nests a `local function` with its own
    `while` loop, so `for`/`while` must count the same way
    `test_payload_lua.py`'s own copy of this helper widened for), with
    `--` line comments skipped while counting (`test_sight_servo_lua.
    py`'s own refinement -- a bare word match on these keywords also
    fires inside ordinary prose in a comment)."""
    text = path.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in {path.name}"
    token_re = re.compile(r"--[^\n]*|\b(function|if|for|while|end)\b")
    depth = 1
    for token_match in token_re.finditer(text, start_match.end()):
        keyword = token_match.group(1)
        if keyword is None:
            continue  # a `--` line comment, not a real token
        if keyword == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


def _extract_lua_constant(path: Path, name: str) -> str:
    """Slice one `local {name} = <value>` line out of `path` -- the
    correction functions close over several module-level constants
    declared outside their own bodies, so extracting the function alone
    is not enough; this pulls the real value rather than hand-copying it,
    so the two cannot silently drift."""
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^local {name} = (.+)$", text, re.MULTILINE)
    assert match is not None, f"{name} not found in {path.name}"
    return f"local {name} = {match.group(1)}"


#: Constants `ai_pilot_correction_direction`/`ai_pilot_quick_path_eligible`/
#: `ai_pilot_park_rising` close over -- extracted, not duplicated, see
#: `_extract_lua_constant`.
_AI_PILOT_WHEEL_CONSTANTS = (
    "AI_PILOT_ALT_TOLERANCE_M",
    "AI_PILOT_PARK_THRESHOLD",
    "AI_PILOT_QUICK_PATH_MAX_AGL_M",
    "AI_WHEEL_UP",
    "AI_WHEEL_DOWN",
)


def _run_lua(functions: list[str], script_tail: str) -> str:
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")
    constants = "\n".join(
        _extract_lua_constant(_AI_PILOT_WHEEL_LUA, name)
        for name in _AI_PILOT_WHEEL_CONSTANTS
    )
    body = "\n".join(
        _extract_lua_function(_AI_PILOT_WHEEL_LUA, name) for name in functions
    )
    script = constants + "\n" + body + "\n" + script_tail
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
    return result.stdout


class TestParseHelperaiOverlayFields:
    def _parse(self, raw: str) -> dict[str, str]:
        # Lua multi-line strings can't hold embedded `]]`, and the real
        # payload is plain text -- pass it through as a JSON string
        # literal (double-quoted, escapes handled) rather than a Lua
        # long-bracket string, decoded back to a table with a tiny
        # hand-rolled unescaper (no JSON library in this harness).
        lua_literal = json.dumps(raw)
        tail = f"""
        local fields = parse_helperai_overlay_fields({lua_literal})
        local parts = {{}}
        local order = {{"mode_text", "course_text", "alt_text", "alt_add_text", "speed_text"}}
        for _, name in ipairs(order) do
            local v = fields[name]
            table.insert(parts, name .. "=" .. (v == nil and "<nil>" or v))
        end
        print(table.concat(parts, "|"))
        """
        out = _run_lua(["parse_helperai_overlay_fields"], tail)
        result: dict[str, str] = {}
        for part in out.strip().split("|"):
            name, _, value = part.partition("=")
            result[name] = None if value == "<nil>" else value  # type: ignore[assignment]
        return result

    def test_flt_mode_overlay(self) -> None:
        """Shapes observed live, `2026-11-14-mi24p-ai-pilot-wheel-layout.
        md` section 3: `mode_text` "FLT", `alt_text`/`alt_add_text`
        "196"/"R", `speed_text` "60", `course_text` "71"."""
        raw = (
            "-----------------------------------------\n"
            "mode_text\n"
            "FLT\n"
            "children are {\n"
            "}\n"
            "-----------------------------------------\n"
            "course_text\n"
            "71\n"
            "children are {\n"
            "}\n"
            "-----------------------------------------\n"
            "alt_text\n"
            "196\n"
            "children are {\n"
            "}\n"
            "-----------------------------------------\n"
            "alt_add_text\n"
            "R\n"
            "children are {\n"
            "}\n"
            "-----------------------------------------\n"
            "speed_text\n"
            "60\n"
            "children are {\n"
            "}\n"
        )
        fields = self._parse(raw)
        assert fields["mode_text"] == "FLT"
        assert fields["course_text"] == "71"
        assert fields["alt_text"] == "196"
        assert fields["alt_add_text"] == "R"
        assert fields["speed_text"] == "60"

    def test_baro_reference_suffix(self) -> None:
        raw = (
            "-----------------------------------------\n"
            "alt_text\n"
            "948\n"
            "children are {\n"
            "}\n"
            "-----------------------------------------\n"
            "alt_add_text\n"
            "B\n"
            "children are {\n"
            "}\n"
        )
        fields = self._parse(raw)
        assert fields["alt_text"] == "948"
        assert fields["alt_add_text"] == "B"

    def test_a_childless_block_with_no_value_is_not_a_field(self) -> None:
        """Mirrors the Python parser's own confirmed-live behaviour (the
        `crosshair` subtree, `children are {}` with no value line) --
        present, no children, never flattened into the result."""
        raw = (
            "-----------------------------------------\ncrosshair\nchildren are {\n}\n"
        )
        fields = self._parse(raw)
        assert fields.get("crosshair") is None

    def test_a_nested_block_is_still_flattened(self) -> None:
        raw = (
            "-----------------------------------------\n"
            "outer\n"
            "children are {\n"
            "-----------------------------------------\n"
            "mode_text\n"
            "HVR\n"
            "children are {\n"
            "}\n"
            "}\n"
        )
        fields = self._parse(raw)
        assert fields["mode_text"] == "HVR"

    def test_hvrt_mode(self) -> None:
        raw = (
            "-----------------------------------------\n"
            "mode_text\n"
            "HVRT\n"
            "children are {\n"
            "}\n"
        )
        fields = self._parse(raw)
        assert fields["mode_text"] == "HVRT"


class TestAiPilotParkRising:
    def _rising(self, prev_parked: bool, stick: str) -> tuple[bool, bool]:
        tail = f"""
        local now, rising = ai_pilot_park_rising({str(prev_parked).lower()}, {stick})
        print(tostring(now) .. "," .. tostring(rising))
        """
        out = _run_lua(["ai_pilot_park_rising"], tail)
        now_s, rising_s = out.strip().split(",")
        return now_s == "true", rising_s == "true"

    def test_unparked_to_unparked_is_no_edge(self) -> None:
        now, rising = self._rising(False, "0.0")
        assert now is False
        assert rising is False

    def test_crossing_the_threshold_is_a_rising_edge(self) -> None:
        now, rising = self._rising(False, "0.95")
        assert now is True
        assert rising is True

    def test_already_parked_is_not_a_second_rising_edge(self) -> None:
        now, rising = self._rising(True, "0.95")
        assert now is True
        assert rising is False

    def test_nil_reading_is_not_parked(self) -> None:
        now, rising = self._rising(False, "nil")
        assert now is False
        assert rising is False


class TestAiPilotCorrectionDirection:
    """Replaces `ai_pilot_should_nudge_altitude` (removed outright per
    the plan's point 8 -- this revision's correction loop needs a
    direction, not a boolean)."""

    def _direction(self, held: str, target: str) -> str | None:
        tail = f"""
        local dir = ai_pilot_correction_direction({held}, {target})
        print(tostring(dir))
        """
        out = _run_lua(["ai_pilot_correction_direction"], tail).strip()
        return None if out == "nil" else out

    def test_within_tolerance_needs_no_correction(self) -> None:
        assert self._direction("196", "200.0") is None

    def test_held_above_target_presses_down(self) -> None:
        assert self._direction("1650", "900.0") == "3005"  # AI_WHEEL_DOWN

    def test_held_below_target_presses_up(self) -> None:
        assert self._direction("500", "900.0") == "3004"  # AI_WHEEL_UP

    def test_a_missing_reading_never_counts_as_needing_correction(self) -> None:
        assert self._direction("nil", "196.0") is None
        assert self._direction("196", "nil") is None


class TestAiPilotQuickPathEligible:
    def _eligible(self, agl: str) -> bool:
        tail = f"""
        print(tostring(ai_pilot_quick_path_eligible({agl})))
        """
        out = _run_lua(["ai_pilot_quick_path_eligible"], tail)
        return out.strip() == "true"

    def test_below_the_cap_is_eligible(self) -> None:
        assert self._eligible("500.0") is True

    def test_at_or_above_the_cap_is_not_eligible(self) -> None:
        assert self._eligible("700.0") is False
        assert self._eligible("900.0") is False

    def test_unreadable_agl_is_not_eligible(self) -> None:
        assert self._eligible("nil") is False


class TestAiPilotAltitudeTextParsing:
    def test_parse_altitude_text(self) -> None:
        tail = """
        print(tostring(ai_pilot_parse_altitude_text("196")))
        print(tostring(ai_pilot_parse_altitude_text(nil)))
        print(tostring(ai_pilot_parse_altitude_text("not-a-number")))
        """
        out = _run_lua(["ai_pilot_parse_altitude_text"], tail)
        assert out.strip().split("\n") == ["196", "nil", "nil"]

    def test_actual_altitude_picks_the_displayed_reference(self) -> None:
        tail = """
        print(tostring(ai_pilot_actual_altitude_m("R", 100.0, 150.0)))
        print(tostring(ai_pilot_actual_altitude_m("B", 100.0, 150.0)))
        print(tostring(ai_pilot_actual_altitude_m(nil, 100.0, 150.0)))
        """
        out = _run_lua(["ai_pilot_actual_altitude_m"], tail)
        assert out.strip().split("\n") == ["100", "150", "nil"]


#: `run_ai_pilot_wheel`/`update_ai_pilot_wheel_overlay` close over several
#: more module-level constants than the pure functions above (the press
#: shapes and the device-30 command ids), extracted the same way.
_AI_PILOT_WHEEL_INTEGRATION_CONSTANTS = (
    "AI_PILOT_PARK_THRESHOLD",
    "AI_PILOT_ALT_TOLERANCE_M",
    "AI_PILOT_REFERENCE_TOGGLE_DELAY_S",
    "MODE_READ_SETTLE_S",
    "SHORT_PULSE_S",
    "AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S",
    "AI_PILOT_QUICK_PATH_MAX_AGL_M",
    "ARG_STICK_PARK",
    "ARG_PEDALS_PARK",
    "AI_WHEEL_UP",
    "AI_WHEEL_DOWN",
)

#: `WHEEL_CENTER_BUTTON`/`WHEEL_MENU_BUTTON` are owned by `core.lua`, not
#: `ai_pilot_wheel.lua` (shared with `petrovich.lua`, same physical
#: device -- see `core.lua`'s own header comment), so they are extracted
#: from a different path than `_AI_PILOT_WHEEL_INTEGRATION_CONSTANTS`.
_CORE_INTEGRATION_CONSTANTS = (
    "WHEEL_CENTER_BUTTON",
    "WHEEL_MENU_BUTTON",
)


def _overlay_raw(
    alt_text: str | None, alt_add_text: str | None, mode_text: str = "FLT"
) -> str:
    """Builds a `list_indication` dump carrying only the leaves the
    takeover sequence reads -- same shape as the live overlay (research
    note section 3), trimmed to what each scenario needs. `None` omits
    that leaf entirely (absent, not an empty value), matching how the
    real overlay drops a field it is not currently showing."""
    parts = []
    if mode_text is not None:
        parts.append(
            f"-----------------------------------------\nmode_text\n{mode_text}\nchildren are {{\n}}\n"
        )
    if alt_text is not None:
        parts.append(
            f"-----------------------------------------\nalt_text\n{alt_text}\nchildren are {{\n}}\n"
        )
    if alt_add_text is not None:
        parts.append(
            f"-----------------------------------------\nalt_add_text\n{alt_add_text}\nchildren are {{\n}}\n"
        )
    return "".join(parts)


_EMPTY_RAW = ""


def _run_ai_pilot_wheel_integration(script_body: str) -> str:
    """Runs the real takeover-sequence functions together against a
    minimal `GetDevice` mock (device 0's park arg, device 30's
    `performClickableAction` press log) and stubbed altitude readings, in
    one Lua process so module-level state (`ai_pilot_parked_active`,
    `ai_pilot_takeover`, the overlay text fields, ...) persists across
    calls exactly as it does across real per-frame calls and 5 Hz ticks.
    `script_body` is the test-specific sequence of mock-state writes/
    calls/`print`s, appended after the shared preamble and the real
    functions' extracted bodies. The `ai_pilot_takeover` table mirrors
    production's own (see its module-docstring comment in
    `ai_pilot_wheel.lua` for why it is one table, not a dozen locals)."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    constants = (
        "\n".join(
            _extract_lua_constant(_AI_PILOT_WHEEL_LUA, name)
            for name in _AI_PILOT_WHEEL_INTEGRATION_CONSTANTS
        )
        + "\n"
        + "\n".join(
            _extract_lua_constant(_CORE_LUA, name)
            for name in _CORE_INTEGRATION_CONSTANTS
        )
    )
    preamble = """
local ai_pilot_parked_active = false
local ai_pilot_mode_text = nil
local ai_pilot_course_text = nil
local ai_pilot_alt_text = nil
local ai_pilot_alt_add_text = nil
local ai_pilot_speed_text = nil
local ai_pilot_last_press = nil
local ai_wheel_pending_release_t = nil
local ai_wheel_pending_cmd = nil

local ai_pilot_takeover = {
    stage = nil,
    t = nil,
    handover_altitude_m = nil,
    menu_open = false,
    menu_open_at_t = nil,
    menu_closed_since_t = nil,
    awaiting_correction_decision = false,
    correction_path = nil,
    correction_substage = nil,
    correction_phase = nil,
    correction_hold_cmd = nil,
    raw_arg852 = nil,
    raw_arg952 = nil,
    AI_PILOT_MENU_OPEN_DELAY_S = 0.5,
}

local stick_park_value = 0.0
local pedals_park_value = 0.0
local agl_value = nil
local msl_value = nil
local press_log = {}

local function GetDevice(id)
    if id == 0 then
        return {
            get_argument_value = function(self, arg)
                if arg == ARG_STICK_PARK then return stick_park_value end
                if arg == ARG_PEDALS_PARK then return pedals_park_value end
                return nil
            end,
        }
    elseif id == 30 then
        return {
            performClickableAction = function(self, cmd, value)
                table.insert(press_log, cmd .. ":" .. tostring(value))
            end,
        }
    end
    return nil
end

local function LoGetAltitudeAboveGroundLevel()
    return agl_value
end

local function LoGetAltitudeAboveSeaLevel()
    return msl_value
end
"""
    functions = "\n".join(
        _extract_lua_function(path, name)
        for path, name in (
            (_CORE_LUA, "safe_call"),
            (_AI_PILOT_WHEEL_LUA, "parse_helperai_overlay_fields"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_correction_direction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_quick_path_eligible"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_parse_altitude_text"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_actual_altitude_m"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_park_rising"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_tap30"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_open_hold"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_begin_hold_phase"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_decide_correction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_check_hold_convergence"),
            (_AI_PILOT_WHEEL_LUA, "run_ai_pilot_wheel"),
            (_AI_PILOT_WHEEL_LUA, "update_ai_pilot_wheel_overlay"),
        )
    )
    script = constants + "\n" + preamble + "\n" + functions + "\n" + script_body

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
    return result.stdout


class TestTakeoverSequence:
    """End to end against the real state machine: detect -> 0.5 s blind
    reference toggle -> open menu -> one of the three correction paths
    -> (eventually) resolved, plus unpark. Mirrors the takeover rehearsal
    probe's own steps (`Export.probe-ai-pilot-takeover.lua`) but against
    production code, not the probe."""

    def test_detect_toggle_open_then_none_needed(self) -> None:
        """Handover altitude already matches the AI's held altitude --
        no correction path runs."""
        raw = _overlay_raw(alt_text="900", alt_add_text="B")
        script = f"""
        -- Rising edge at t=0, handover snapshot = 900.
        msl_value = 900.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        print("stage_at_rise=" .. tostring(ai_pilot_takeover.stage))
        print("handover=" .. tostring(ai_pilot_takeover.handover_altitude_m))
        print("presses_at_rise=" .. #press_log)

        -- Before the 0.5s delay: nothing happens yet.
        run_ai_pilot_wheel(0.3)
        print("presses_before_delay=" .. #press_log)

        -- Delay elapses: blind reference toggle only -- the menu-open tap
        -- is gapped AI_PILOT_MENU_OPEN_DELAY_S later, not the same frame
        -- (main-loop timing decision, 2026-11-16 review-fix round --
        -- matches the gap the rehearsal probe actually flew).
        run_ai_pilot_wheel(0.5)
        print("stage_after_toggle=" .. tostring(ai_pilot_takeover.stage))
        print("presses_after_toggle=" .. #press_log)

        -- Still within the gap: nothing further happens yet.
        run_ai_pilot_wheel(0.9)
        print("presses_within_gap=" .. #press_log)

        -- Gap elapses: menu-open tap issued.
        run_ai_pilot_wheel(1.0)
        print("stage_after_delay=" .. tostring(ai_pilot_takeover.stage))
        print("menu_open=" .. tostring(ai_pilot_takeover.menu_open))
        print("presses_after_delay=" .. #press_log)
        print("awaiting=" .. tostring(ai_pilot_takeover.awaiting_correction_decision))

        -- First post-open read: held (900) already matches handover (900).
        update_ai_pilot_wheel_overlay({json.dumps(raw)}, 1.1)
        print("correction_path=" .. tostring(ai_pilot_takeover.correction_path))
        print("stage_after_decision=" .. tostring(ai_pilot_takeover.stage))
        print("presses_after_decision=" .. #press_log)
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["stage_at_rise"] == "toggling_reference"
        assert values["handover"] == "900"
        assert values["presses_at_rise"] == "0"
        assert values["presses_before_delay"] == "0"
        assert values["stage_after_toggle"] == "opening_menu"
        assert values["presses_after_toggle"] == "2"  # blind centre tap (press+release)
        assert values["presses_within_gap"] == "2"
        assert values["stage_after_delay"] == "correcting_altitude"
        assert values["menu_open"] == "true"
        # blind centre tap (press+release) + menu-open tap (press+release)
        assert values["presses_after_delay"] == "4"
        assert values["awaiting"] == "true"
        assert values["correction_path"] == "none"
        assert values["stage_after_decision"] == "nil"
        assert values["presses_after_decision"] == "4"

    def test_hold_path_two_phases(self) -> None:
        """AGL too high for the quick path -- the two-phase hold chases
        live altitude first (stopping the drift), then the handover
        snapshot."""
        script = f"""
        msl_value = 920.0
        agl_value = 750.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)   -- handover snapshot = 920
        msl_value = 1000.0        -- aircraft climbed during the sequence
        run_ai_pilot_wheel(0.5)   -- blind toggle
        run_ai_pilot_wheel(1.0)   -- menu open, gapped 0.5 s after the toggle

        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1650", alt_add_text="B"))}, 1.1)
        print("path=" .. tostring(ai_pilot_takeover.correction_path))
        print("phase_1=" .. tostring(ai_pilot_takeover.correction_phase))
        print("hold_cmd_1=" .. tostring(ai_pilot_takeover.correction_hold_cmd))

        -- Phase 1 converges toward live (1000): held reads 1010.
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1010", alt_add_text="B"))}, 1.3)
        print("phase_2=" .. tostring(ai_pilot_takeover.correction_phase))
        print("hold_cmd_2=" .. tostring(ai_pilot_takeover.correction_hold_cmd))

        -- Phase 2 converges toward handover (920): held reads 925.
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="925", alt_add_text="B"))}, 1.5)
        print("stage_done=" .. tostring(ai_pilot_takeover.stage))
        print("phase_done=" .. tostring(ai_pilot_takeover.correction_phase))
        print("path_done=" .. tostring(ai_pilot_takeover.correction_path))
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["path"] == "hold"
        assert values["phase_1"] == "phase1"
        assert values["hold_cmd_1"] == "3005"  # AI_WHEEL_DOWN (1650 > 1000)
        assert values["phase_2"] == "phase2"
        assert values["hold_cmd_2"] == "3005"  # AI_WHEEL_DOWN (1010 > 920)
        assert values["stage_done"] == "nil"
        assert values["phase_done"] == "nil"
        assert values["path_done"] == "hold"
        presses = values["press_log"].split(",")
        # centre tap(1,0), menu tap(1,0), phase1 DOWN:1, phase1 DOWN:0 (release),
        # phase2 DOWN:1, phase2 DOWN:0 (release).
        assert presses.count("3005:1") == 2
        assert presses.count("3005:0") == 2

    def test_hold_path_skips_phase1_when_already_at_live(self) -> None:
        """Skip the phase that is already within tolerance (plan: "skip
        phases that are already within tolerance") -- held is already
        close to the aircraft's *live* altitude (so phase 1 has nothing
        to do) but still far from the handover snapshot, so the loop
        opens phase 2 directly rather than opening and immediately
        releasing a no-op phase 1 hold."""
        script = f"""
        msl_value = 700.0
        agl_value = 750.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)   -- handover = 700
        msl_value = 1000.0       -- aircraft climbed during the sequence
        run_ai_pilot_wheel(0.5)  -- toggle
        run_ai_pilot_wheel(1.0)  -- menu open, gapped 0.5 s after the toggle

        -- held (1010) is within tolerance of live (1000) but far from
        -- the handover snapshot (700).
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1010", alt_add_text="B"))}, 1.1)
        print("phase=" .. tostring(ai_pilot_takeover.correction_phase))
        print("hold_cmd=" .. tostring(ai_pilot_takeover.correction_hold_cmd))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["phase"] == "phase2"
        assert values["hold_cmd"] == "3005"  # AI_WHEEL_DOWN (1010 > 700)

    def test_quick_path_success(self) -> None:
        """AGL below the cap: two pulses, resolves without ever entering
        a hold."""
        script = f"""
        msl_value = 1084.0
        agl_value = 500.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)    -- handover = 1084
        run_ai_pilot_wheel(0.5)    -- toggle
        run_ai_pilot_wheel(1.0)    -- menu open, gapped 0.5 s after the toggle

        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1824", alt_add_text="B"))}, 1.1)
        print("path_after_decision=" .. tostring(ai_pilot_takeover.correction_path))
        print("substage_after_decision=" .. tostring(ai_pilot_takeover.correction_substage))

        -- Pulse 1's release (0.15s later), then the next tick's read: the
        -- reference flipped to R.
        run_ai_pilot_wheel(1.26)
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="500", alt_add_text="R"))}, 1.3)
        print("substage_after_read1=" .. tostring(ai_pilot_takeover.correction_substage))

        -- Pulse 2's release, then the final read: back on B, corrected.
        run_ai_pilot_wheel(1.46)
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1080", alt_add_text="B"))}, 1.5)
        print("stage_done=" .. tostring(ai_pilot_takeover.stage))
        print("path_done=" .. tostring(ai_pilot_takeover.correction_path))
        print("hold_cmd=" .. tostring(ai_pilot_takeover.correction_hold_cmd))
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["path_after_decision"] == "quick"
        assert values["substage_after_decision"] == "quick_read1"
        assert values["substage_after_read1"] == "quick_read2"
        assert values["stage_done"] == "nil"
        assert values["path_done"] == "quick"
        assert values["hold_cmd"] == "nil"
        # Never opens AI_WHEEL_UP/DOWN -- only centre pulses (3015).
        presses = values["press_log"].split(",")
        assert all(
            not p.startswith("3004") and not p.startswith("3005") for p in presses
        )
        assert presses.count("3015:1") == 3  # blind toggle + 2 pulses
        assert presses.count("3015:0") == 3

    def test_quick_path_falls_back_to_hold_when_still_baro(self) -> None:
        """If the first pulse is refused (radar capped at 700 m AGL, or
        any other reason) the reference still reads B -- fall back to
        the two-phase hold rather than retry the pulse."""
        script = f"""
        msl_value = 1084.0
        agl_value = 500.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        run_ai_pilot_wheel(0.5)
        run_ai_pilot_wheel(1.0)

        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1824", alt_add_text="B"))}, 1.1)
        run_ai_pilot_wheel(1.26)
        -- Pulse 1 refused: still reads B.
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1824", alt_add_text="B"))}, 1.3)
        print("path=" .. tostring(ai_pilot_takeover.correction_path))
        print("substage=" .. tostring(ai_pilot_takeover.correction_substage))
        print("phase=" .. tostring(ai_pilot_takeover.correction_phase))
        print("hold_cmd=" .. tostring(ai_pilot_takeover.correction_hold_cmd))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["path"] == "hold"
        assert values["substage"] == "nil"
        assert values["phase"] == "phase1"
        assert values["hold_cmd"] == "3005"  # AI_WHEEL_DOWN (1824 > live 1084)

    def test_quick_path_falls_back_to_hold_when_pulse2_still_wrong(self) -> None:
        """Both pulses complete (reference flips to R then back to B) but
        the readback is still outside tolerance of the handover snapshot
        -- the second toggle is not trusted blindly (review fix,
        2026-11-16: the plan never said it could be, and the first
        toggle's own measured error is not known to be absent on the
        second). Falls back to the two-phase hold, the same shape the
        first pulse's own refusal uses -- never resolves to `"none"` on
        an unchecked target, and never retries a third pulse."""
        script = f"""
        msl_value = 1084.0
        agl_value = 500.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        run_ai_pilot_wheel(0.5)
        run_ai_pilot_wheel(1.0)

        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1824", alt_add_text="B"))}, 1.1)
        run_ai_pilot_wheel(1.26)
        -- Pulse 1 succeeds: reference flips to R.
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="500", alt_add_text="R"))}, 1.3)
        run_ai_pilot_wheel(1.46)

        -- Aircraft's own altitude moved on while the pulses ran.
        msl_value = 1100.0

        -- Pulse 2 completes, back on B -- but still wrong.
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1824", alt_add_text="B"))}, 1.5)
        print("path=" .. tostring(ai_pilot_takeover.correction_path))
        print("substage=" .. tostring(ai_pilot_takeover.correction_substage))
        print("phase=" .. tostring(ai_pilot_takeover.correction_phase))
        print("hold_cmd=" .. tostring(ai_pilot_takeover.correction_hold_cmd))
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["path"] == "hold"
        assert values["substage"] == "nil"
        assert values["phase"] == "phase1"
        assert values["hold_cmd"] == "3005"  # AI_WHEEL_DOWN (1824 > live 1100)
        presses = values["press_log"].split(",")
        # blind toggle + 2 pulses, never a third -- then the hold opens.
        assert presses.count("3015:1") == 3
        assert presses.count("3015:0") == 3
        assert presses.count("3005:1") == 1

    def test_menu_reopens_after_the_settle_window(self) -> None:
        """Keep-open: a hand-closed menu (overlay reads all-`nil`) is
        reopened once it has read closed for longer than `MODE_READ_
        SETTLE_S` -- not on the first stale-looking tick (which would
        flap it shut again)."""
        script = f"""
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        ai_pilot_takeover.menu_open = true
        local before = #press_log

        -- First all-nil tick: starts the settle timer, no press yet.
        update_ai_pilot_wheel_overlay({json.dumps(_EMPTY_RAW)}, 1.0)
        print("presses_first_closed=" .. (#press_log - before))

        -- Still within the settle window.
        update_ai_pilot_wheel_overlay({json.dumps(_EMPTY_RAW)}, 1.5)
        print("presses_within_settle=" .. (#press_log - before))

        -- Past the settle window: reopen tap issued.
        update_ai_pilot_wheel_overlay({json.dumps(_EMPTY_RAW)}, 2.1)
        print("presses_after_settle=" .. (#press_log - before))
        print("menu_open=" .. tostring(ai_pilot_takeover.menu_open))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["presses_first_closed"] == "0"
        assert values["presses_within_settle"] == "0"
        assert values["presses_after_settle"] == "2"  # one tap: press + release
        assert values["menu_open"] == "true"

    def test_unpark_releases_and_drops_all_state_mid_hold(self) -> None:
        """E-P10: unpark releases any open press immediately, closes the
        menu if this sequence opened it, and drops every takeover field
        -- nothing resumes on the next park. Mirrors the original Stage
        P1 test's own E-P10 coverage, now against a hold in progress."""
        script = f"""
        msl_value = 920.0
        agl_value = 750.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        run_ai_pilot_wheel(0.5)
        run_ai_pilot_wheel(1.0)
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1650", alt_add_text="B"))}, 1.1)
        print("holding=" .. tostring(ai_pilot_takeover.correction_hold_cmd))
        local before = #press_log

        stick_park_value = 0.0
        run_ai_pilot_wheel(1.2)
        local unpark_presses = {{}}
        for i = before + 1, #press_log do
            table.insert(unpark_presses, press_log[i])
        end
        print("unpark_presses=" .. table.concat(unpark_presses, ","))
        print("parked_after_unpark=" .. tostring(ai_pilot_parked_active))
        print("stage_after_unpark=" .. tostring(ai_pilot_takeover.stage))
        print("hold_cmd_after_unpark=" .. tostring(ai_pilot_takeover.correction_hold_cmd))
        print("menu_open_after_unpark=" .. tostring(ai_pilot_takeover.menu_open))
        local after_unpark = #press_log

        -- A stale read arriving after unpark must no-op.
        update_ai_pilot_wheel_overlay(
            {json.dumps(_overlay_raw(alt_text="1650", alt_add_text="B"))}, 1.3)
        print("presses_after_stale_tick=" .. (#press_log - after_unpark))
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["holding"] == "3005"  # AI_WHEEL_DOWN
        # The open hold is released first (same frame unpark is noticed),
        # then the menu (opened by this sequence) is closed.
        assert values["unpark_presses"] == "3005:0,3001:1,3001:0"
        assert values["parked_after_unpark"] == "false"
        assert values["stage_after_unpark"] == "nil"
        assert values["hold_cmd_after_unpark"] == "nil"
        assert values["menu_open_after_unpark"] == "false"
        assert values["presses_after_stale_tick"] == "0"


def _run_on_stop(pending_cmd: str) -> dict[str, str]:
    """`AC-B13`'s own test (plan Stage 6): runs the real, extracted
    `on_stop` against a minimal `GetDevice` mock for device 30's
    `performClickableAction`, with `ai_wheel_pending_cmd` preset to
    `pending_cmd` (an `AI_WHEEL_UP`/`AI_WHEEL_DOWN` command id as a Lua
    literal, or `"nil"` for no open press) and `ai_pilot_takeover`
    populated as a hold in progress would leave it. Returns every
    printed `key=value` line as a dict."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    preamble = f"""
local press_log = {{}}

local function GetDevice(id)
    if id == 30 then
        return {{
            performClickableAction = function(self, cmd, value)
                table.insert(press_log, cmd .. ":" .. tostring(value))
            end,
        }}
    end
    return nil
end

local ai_wheel_pending_release_t = 42.0
local ai_wheel_pending_cmd = {pending_cmd}
local ai_pilot_takeover = {{
    stage = "correcting_altitude",
    t = 1.0,
    handover_altitude_m = 900.0,
    menu_open = true,
    menu_open_at_t = 1.5,
    menu_closed_since_t = nil,
    awaiting_correction_decision = false,
    correction_path = "hold",
    correction_substage = nil,
    correction_phase = "phase1",
    correction_hold_cmd = {pending_cmd},
    raw_arg852 = 0.95,
    raw_arg952 = 0.05,
    AI_PILOT_MENU_OPEN_DELAY_S = 0.5,
}}
"""
    lines = [preamble]
    lines.extend(
        _extract_lua_function(path, name)
        for path, name in (
            (_CORE_LUA, "safe_call"),
            (_AI_PILOT_WHEEL_LUA, "on_stop"),
        )
    )
    lines.append("on_stop()")
    lines.append(
        'print("press_log=" .. table.concat(press_log, ","))\n'
        'print("pending_release_t=" .. tostring(ai_wheel_pending_release_t))\n'
        'print("pending_cmd=" .. tostring(ai_wheel_pending_cmd))\n'
        'print("stage=" .. tostring(ai_pilot_takeover.stage))\n'
        'print("t=" .. tostring(ai_pilot_takeover.t))\n'
        'print("handover_altitude_m=" .. tostring(ai_pilot_takeover.handover_altitude_m))\n'
        'print("menu_open=" .. tostring(ai_pilot_takeover.menu_open))\n'
        'print("menu_open_at_t=" .. tostring(ai_pilot_takeover.menu_open_at_t))\n'
        'print("menu_closed_since_t=" .. tostring(ai_pilot_takeover.menu_closed_since_t))\n'
        'print("awaiting_correction_decision=" .. '
        "tostring(ai_pilot_takeover.awaiting_correction_decision))\n"
        'print("correction_path=" .. tostring(ai_pilot_takeover.correction_path))\n'
        'print("correction_substage=" .. tostring(ai_pilot_takeover.correction_substage))\n'
        'print("correction_phase=" .. tostring(ai_pilot_takeover.correction_phase))\n'
        'print("correction_hold_cmd=" .. tostring(ai_pilot_takeover.correction_hold_cmd))\n'
        'print("raw_arg852=" .. tostring(ai_pilot_takeover.raw_arg852))\n'
        'print("raw_arg952=" .. tostring(ai_pilot_takeover.raw_arg952))'
    )
    script = "\n".join(lines)

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
    return dict(line.split("=", 1) for line in result.stdout.strip().splitlines())


class TestOnStop:
    """`AC-B13` (`aircraft-layer/ROADMAP/AC-B13.md`): `LuaExportStop` never
    released an open AI-pilot-wheel press or cleared the takeover state --
    this module's own `on_stop` (new with the `AC-B12` split, there is no
    "move" for it) is the fix."""

    def test_open_hold_press_is_released_and_every_field_cleared(self) -> None:
        values = _run_on_stop("3005")  # AI_WHEEL_DOWN
        assert values["press_log"] == "3005:0"
        assert values["pending_release_t"] == "nil"
        assert values["pending_cmd"] == "nil"
        assert values["stage"] == "nil"
        assert values["t"] == "nil"
        assert values["handover_altitude_m"] == "nil"
        assert values["menu_open"] == "false"
        assert values["menu_open_at_t"] == "nil"
        assert values["menu_closed_since_t"] == "nil"
        assert values["awaiting_correction_decision"] == "false"
        assert values["correction_path"] == "nil"
        assert values["correction_substage"] == "nil"
        assert values["correction_phase"] == "nil"
        assert values["correction_hold_cmd"] == "nil"
        assert values["raw_arg852"] == "nil"
        assert values["raw_arg952"] == "nil"

    def test_no_open_press_releases_nothing_but_still_clears_state(self) -> None:
        """No stale press to release (`ai_wheel_pending_cmd` already
        `nil`) -- no spurious release call, but every takeover field is
        still cleared."""
        values = _run_on_stop("nil")
        assert values["press_log"] == ""
        assert values["stage"] == "nil"
        assert values["correction_hold_cmd"] == "nil"
