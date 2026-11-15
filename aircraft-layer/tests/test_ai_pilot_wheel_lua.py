"""BL-16 mode 2, Stage P1 (`plans/flight-control/plan.md`) -- the pure Lua
functions `run_ai_pilot_wheel` is built from, run against a real Lua
interpreter and checked against the overlay's known text shapes, not just
read:

- `parse_helperai_overlay_fields` -- the flattening parser against the
  overlay readback research note's own observed text
  (`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md`
  section 3: `mode_text`/`course_text`/`alt_text`/`alt_add_text`/
  `speed_text`, the `R`/`B` altitude-reference suffix).
- `ai_pilot_park_rising` -- the park signal's rising-edge detection
  (arg 852/952 >= threshold).
- `ai_pilot_should_nudge_altitude`/`ai_pilot_parse_altitude_text`/
  `ai_pilot_actual_altitude_m` -- the park-sink nudge's "equal" decision.
- `run_ai_pilot_wheel`/`update_ai_pilot_wheel_overlay` together, against a
  `GetDevice` mock (`TestNudgeDrivenFromCachedParse`) -- the perf fix
  (`plans/flight-control/perf-batch-a.md`) that moves the overlay parse
  and the altitude-nudge decision off the per-frame path and onto the
  5 Hz tick: the rising edge only arms `ai_pilot_pending_nudge`, the
  press itself happens only once `update_ai_pilot_wheel_overlay` runs
  against that tick's parsed fields, and unparking before that tick
  clears the armed flag so a stale parse can never fire a nudge for a
  park that already ended (E-P10).

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

_EXPORT_LUA = Path(__file__).resolve().parent.parent / "dcs-export" / "Export.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(name: str) -> str:
    """Slice `local function {name}(...) ... end` out of `Export.lua` --
    `function`/`if`/`for`/`while`/`end` as block openers/closer (`parse_
    helperai_overlay_fields` nests a `local function` with its own
    `while` loop, so `for`/`while` must count the same way
    `test_payload_lua.py`'s own copy of this helper widened for), with
    `--` line comments skipped while counting (`test_sight_servo_lua.
    py`'s own refinement -- a bare word match on these keywords also
    fires inside ordinary prose in a comment)."""
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in Export.lua"
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


def _extract_lua_constant(name: str) -> str:
    """Slice one `local {name} = <value>` line out of `Export.lua` --
    `ai_pilot_should_nudge_altitude`/`ai_pilot_park_rising` close over
    module-level constants (`AI_PILOT_NUDGE_EPSILON_M`, `AI_PILOT_PARK_
    THRESHOLD`) declared outside the function body itself, so extracting
    the function alone is not enough; this pulls the real value rather
    than hand-copying it, so the two cannot silently drift."""
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    match = re.search(rf"^local {name} = (.+)$", text, re.MULTILINE)
    assert match is not None, f"{name} not found in Export.lua"
    return f"local {name} = {match.group(1)}"


#: Constants `ai_pilot_should_nudge_altitude`/`ai_pilot_park_rising`
#: close over -- extracted, not duplicated, see `_extract_lua_constant`.
_AI_PILOT_WHEEL_CONSTANTS = ("AI_PILOT_NUDGE_EPSILON_M", "AI_PILOT_PARK_THRESHOLD")


def _run_lua(functions: list[str], script_tail: str) -> str:
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")
    constants = "\n".join(
        _extract_lua_constant(name) for name in _AI_PILOT_WHEEL_CONSTANTS
    )
    body = "\n".join(_extract_lua_function(name) for name in functions)
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
    def _rising(self, prev_parked: bool, stick: str, pedals: str) -> tuple[bool, bool]:
        tail = f"""
        local now, rising = ai_pilot_park_rising({str(prev_parked).lower()}, {stick}, {pedals})
        print(tostring(now) .. "," .. tostring(rising))
        """
        out = _run_lua(["ai_pilot_park_rising"], tail)
        now_s, rising_s = out.strip().split(",")
        return now_s == "true", rising_s == "true"

    def test_unparked_to_unparked_is_no_edge(self) -> None:
        now, rising = self._rising(False, "0.0", "0.0")
        assert now is False
        assert rising is False

    def test_crossing_the_threshold_is_a_rising_edge(self) -> None:
        now, rising = self._rising(False, "0.95", "0.0")
        assert now is True
        assert rising is True

    def test_already_parked_is_not_a_second_rising_edge(self) -> None:
        now, rising = self._rising(True, "0.95", "0.95")
        assert now is True
        assert rising is False

    def test_pedals_alone_above_threshold_also_reads_parked(self) -> None:
        """Either arg is enough (OR) -- the two animate off one lever."""
        now, rising = self._rising(False, "0.0", "0.95")
        assert now is True
        assert rising is True

    def test_nil_readings_are_not_parked(self) -> None:
        now, rising = self._rising(False, "nil", "nil")
        assert now is False
        assert rising is False


class TestAiPilotAltitudeNudge:
    def test_equal_altitudes_trigger_a_nudge(self) -> None:
        tail = """
        print(tostring(ai_pilot_should_nudge_altitude(196, 196.0)))
        """
        out = _run_lua(["ai_pilot_should_nudge_altitude"], tail)
        assert out.strip() == "true"

    def test_within_tolerance_still_counts_as_equal(self) -> None:
        tail = """
        print(tostring(ai_pilot_should_nudge_altitude(196, 200.0)))
        """
        out = _run_lua(["ai_pilot_should_nudge_altitude"], tail)
        assert out.strip() == "true"

    def test_a_real_difference_does_not_nudge(self) -> None:
        tail = """
        print(tostring(ai_pilot_should_nudge_altitude(196, 260.0)))
        """
        out = _run_lua(["ai_pilot_should_nudge_altitude"], tail)
        assert out.strip() == "false"

    def test_a_missing_reading_never_counts_as_equal(self) -> None:
        tail = """
        print(tostring(ai_pilot_should_nudge_altitude(nil, 196.0)))
        print(tostring(ai_pilot_should_nudge_altitude(196, nil)))
        """
        out = _run_lua(["ai_pilot_should_nudge_altitude"], tail)
        assert out.strip().split("\n") == ["false", "false"]

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
#: shape and the device-30 command), extracted the same way.
_AI_PILOT_WHEEL_INTEGRATION_CONSTANTS = (
    "AI_PILOT_PARK_THRESHOLD",
    "AI_PILOT_NUDGE_EPSILON_M",
    "LONG_PRESS_HOLD_S",
    "ARG_STICK_PARK",
    "ARG_PEDALS_PARK",
    "AI_WHEEL_UP",
)

#: `_ALT_196_R_RAW` -- `alt_text`/`alt_add_text` "196"/"R", the same
#: overlay shape `TestParseHelperaiOverlayFields.test_flt_mode_overlay`
#: observes live, trimmed to only the two leaves the nudge decision reads.
_ALT_196_R_RAW = (
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
)


def _run_ai_pilot_wheel_integration(script_body: str) -> str:
    """Runs the real `run_ai_pilot_wheel`/`update_ai_pilot_wheel_overlay`
    together against a minimal `GetDevice` mock (device 0's park args,
    device 30's `performClickableAction` press log) and stubbed altitude
    readings, in one Lua process so module-level state
    (`ai_pilot_parked_active`, `ai_pilot_pending_nudge`, the overlay text
    fields, ...) persists across calls exactly as it does across real
    per-frame calls and 5 Hz ticks. `script_body` is the test-specific
    sequence of mock-state writes/calls/`print`s, appended after the
    shared preamble and the two real functions' extracted bodies."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    constants = "\n".join(
        _extract_lua_constant(name) for name in _AI_PILOT_WHEEL_INTEGRATION_CONSTANTS
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
local ai_pilot_pending_nudge = false

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
        _extract_lua_function(name)
        for name in (
            "safe_call",
            "parse_helperai_overlay_fields",
            "ai_pilot_should_nudge_altitude",
            "ai_pilot_parse_altitude_text",
            "ai_pilot_actual_altitude_m",
            "ai_pilot_park_rising",
            "ai_pilot_press_altitude_up_long_hold",
            "run_ai_pilot_wheel",
            "update_ai_pilot_wheel_overlay",
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


class TestNudgeDrivenFromCachedParse:
    """Perf fix (`plans/flight-control/perf-batch-a.md`): the rising edge
    only arms `ai_pilot_pending_nudge`; the actual press only happens once
    `update_ai_pilot_wheel_overlay` runs against a 5 Hz tick's parsed
    fields, never on the rising frame itself."""

    def test_nudge_fires_only_once_the_cached_parse_resolves_it(self) -> None:
        raw_literal = json.dumps(_ALT_196_R_RAW)
        script = f"""
        stick_park_value = 0.0
        run_ai_pilot_wheel(0.0)

        -- Rising edge: pending-nudge armed, but no overlay has been
        -- parsed yet this park, so no press can have happened.
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.2)
        print("presses_at_rising=" .. #press_log)
        print("pending_at_rising=" .. tostring(ai_pilot_pending_nudge))

        -- A further per-frame call with no 5 Hz tick in between: still
        -- no overlay parse, still no press.
        run_ai_pilot_wheel(0.21)
        print("presses_before_tick=" .. #press_log)

        -- The 5 Hz tick: the cached parse (equal altitude) resolves the
        -- armed nudge into exactly one press.
        agl_value = 196.0
        update_ai_pilot_wheel_overlay({raw_literal}, 0.21)
        print("presses_after_tick=" .. #press_log)
        print("pending_after_tick=" .. tostring(ai_pilot_pending_nudge))

        -- A second tick with the same (now-settled) parse must not
        -- press again -- the flag was consumed, not re-armed.
        update_ai_pilot_wheel_overlay({raw_literal}, 0.22)
        print("presses_after_second_tick=" .. #press_log)
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["presses_at_rising"] == "0"
        assert values["pending_at_rising"] == "true"
        assert values["presses_before_tick"] == "0"
        assert values["presses_after_tick"] == "1"
        assert values["pending_after_tick"] == "false"
        assert values["presses_after_second_tick"] == "1"

    def test_unpark_before_the_next_tick_clears_the_pending_nudge(self) -> None:
        """E-P10: unpark drops AI-pilot-wheel state, including a still-
        armed nudge, the same frame -- a cached parse that arrives at the
        next 5 Hz tick for a park that already ended must never press."""
        raw_literal = json.dumps(_ALT_196_R_RAW)
        script = f"""
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        print("pending_after_rise=" .. tostring(ai_pilot_pending_nudge))

        stick_park_value = 0.0
        run_ai_pilot_wheel(0.1)
        print("pending_after_unpark=" .. tostring(ai_pilot_pending_nudge))
        print("parked_after_unpark=" .. tostring(ai_pilot_parked_active))

        -- A stale parse arriving at the next tick must no-op: not
        -- parked any more, regardless of what it would have decided.
        agl_value = 196.0
        update_ai_pilot_wheel_overlay({raw_literal}, 0.2)
        print("presses_after_stale_tick=" .. #press_log)
        """
        out = _run_ai_pilot_wheel_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["pending_after_rise"] == "true"
        assert values["pending_after_unpark"] == "false"
        assert values["parked_after_unpark"] == "false"
        assert values["presses_after_stale_tick"] == "0"
