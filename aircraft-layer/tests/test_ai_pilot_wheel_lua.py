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
    "SEAT_BOUNDARY_FWD_M",
    "SEAT_CAMERA_MIN_FWD_M",
    "SEAT_CAMERA_MAX_FWD_M",
    "SEAT_CAMERA_MAX_OFFAXIS_M",
    "AI_PILOT_ALT_TOLERANCE_M",
    "AI_PILOT_PARK_THRESHOLD",
    "AI_PILOT_QUICK_PATH_MAX_AGL_M",
    "AI_WHEEL_UP",
    "AI_WHEEL_DOWN",
    # Stage P2a/P2b's own pure decisions close over these too.
    "AI_WHEEL_LEFT",
    "AI_WHEEL_RIGHT",
    "AI_PILOT_HEADING_TOLERANCE_DEG",
    "AI_PILOT_SPEED_TOP_STEP_KMH",
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


class TestAiPilotGoalModeReady:
    """Stage P2a's own pure decisions (`plans/flight-control/plan.md`,
    "Stage P2 ready to build")."""

    def _ready(self, mode_text: str) -> bool:
        tail = f"print(tostring(ai_pilot_goal_mode_ready({mode_text})))"
        return _run_lua(["ai_pilot_goal_mode_ready"], tail).strip() == "true"

    def test_flt_and_hvr_are_both_ready(self) -> None:
        assert self._ready('"FLT"') is True
        assert self._ready('"HVR"') is True

    def test_cbtm_hvrt_and_unknown_are_not_ready(self) -> None:
        assert self._ready('"CBTM"') is False
        assert self._ready('"HVRT"') is False
        assert self._ready("nil") is False


class TestAiPilotGoalHeadingDirection:
    def _direction(self, held: str, target: str) -> str | None:
        tail = f"""
        local dir = ai_pilot_goal_heading_direction({held}, {target})
        print(tostring(dir))
        """
        out = _run_lua(["ai_pilot_goal_heading_direction"], tail).strip()
        return None if out == "nil" else out

    def test_within_tolerance_needs_no_correction(self) -> None:
        assert self._direction("90.0", "92.0") is None

    def test_shortest_path_turns_right(self) -> None:
        assert self._direction("10.0", "20.0") == "3002"  # AI_WHEEL_RIGHT

    def test_shortest_path_turns_left(self) -> None:
        assert self._direction("20.0", "10.0") == "3003"  # AI_WHEEL_LEFT

    def test_wraps_across_north_the_short_way(self) -> None:
        # 350 -> 10 is a 20 deg turn right through north, not a 340 deg
        # turn left the long way around.
        assert self._direction("350.0", "10.0") == "3002"  # AI_WHEEL_RIGHT
        assert self._direction("10.0", "350.0") == "3003"  # AI_WHEEL_LEFT

    def test_a_missing_reading_never_counts_as_needing_correction(self) -> None:
        assert self._direction("nil", "90.0") is None
        assert self._direction("90.0", "nil") is None


class TestAiPilotGoalAltitudeRefMismatch:
    def _mismatch(self, ref: str, current: str) -> bool:
        tail = f"print(tostring(ai_pilot_goal_altitude_ref_mismatch({ref}, {current})))"
        return (
            _run_lua(
                ["ai_pilot_goal_ref_letter", "ai_pilot_goal_altitude_ref_mismatch"],
                tail,
            ).strip()
            == "true"
        )

    def test_radar_wanted_but_currently_barometric_is_a_mismatch(self) -> None:
        assert self._mismatch('"radar"', '"B"') is True

    def test_barometric_wanted_but_currently_radar_is_a_mismatch(self) -> None:
        assert self._mismatch('"barometric"', '"R"') is True

    def test_matching_reference_is_not_a_mismatch(self) -> None:
        assert self._mismatch('"radar"', '"R"') is False
        assert self._mismatch('"barometric"', '"B"') is False

    def test_a_missing_goal_reference_is_never_a_mismatch(self) -> None:
        assert self._mismatch("nil", '"R"') is False

    def test_an_unreadable_current_reference_is_never_a_mismatch(self) -> None:
        assert self._mismatch('"radar"', "nil") is False


class TestAiPilotGoalSpeedTapDirection:
    def _direction(self, speed_text: str, target: str) -> str | None:
        tail = f"""
        local dir = ai_pilot_goal_speed_tap_direction({speed_text}, {target})
        print(tostring(dir))
        """
        out = _run_lua(["ai_pilot_goal_speed_tap_direction"], tail).strip()
        return None if out == "nil" else out

    def test_already_at_the_target_step_needs_no_tap(self) -> None:
        assert self._direction('"150"', "150.0") is None

    def test_below_target_taps_up(self) -> None:
        assert self._direction('"120"', "150.0") == "3004"  # AI_WHEEL_UP

    def test_above_target_taps_down(self) -> None:
        assert self._direction('"200"', "150.0") == "3005"  # AI_WHEEL_DOWN

    def test_a_target_above_the_top_step_aims_for_max(self) -> None:
        assert self._direction('"200"', "1000000.0") == "3004"  # AI_WHEEL_UP

    def test_already_at_max_and_wanting_max_needs_no_tap(self) -> None:
        assert self._direction('"MAX"', "1000000.0") is None

    def test_at_max_but_wanting_a_real_step_taps_down(self) -> None:
        assert self._direction('"MAX"', "150.0") == "3005"  # AI_WHEEL_DOWN

    def test_an_unreadable_speed_text_never_counts_as_needing_a_tap(self) -> None:
        assert self._direction("nil", "150.0") is None

    def test_a_missing_target_never_counts_as_needing_a_tap(self) -> None:
        assert self._direction('"150"', "nil") is None


class TestAiPilotGoalHvrtDirectionCmd:
    def _cmd(self, direction: str) -> str | None:
        tail = f"print(tostring(ai_pilot_goal_hvrt_direction_cmd({direction})))"
        out = _run_lua(["ai_pilot_goal_hvrt_direction_cmd"], tail).strip()
        return None if out == "nil" else out

    def test_every_direction_maps_to_its_own_ring_button(self) -> None:
        assert self._cmd('"left"') == "3003"  # AI_WHEEL_LEFT
        assert self._cmd('"right"') == "3002"  # AI_WHEEL_RIGHT
        assert self._cmd('"forward"') == "3004"  # AI_WHEEL_UP
        assert self._cmd('"back"') == "3005"  # AI_WHEEL_DOWN

    def test_an_unrecognised_direction_is_nil(self) -> None:
        assert self._cmd('"up"') is None
        assert self._cmd("nil") is None


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
    # Stage P2a/P2b's own additions -- `update_ai_pilot_wheel_overlay`
    # now transitively calls the goal/HVRT tick chain, which closes over
    # all of these.
    "AI_WHEEL_LEFT",
    "AI_WHEEL_RIGHT",
    "AI_PILOT_HEADING_TOLERANCE_DEG",
    "AI_PILOT_SPEED_TOP_STEP_KMH",
    "MODE_CYCLE_MAX_ATTEMPTS",
    "HVRT_TRANSLATE_MAX_HOLD_S",
    # fix/ai-wheel-pilot-seat-gate -- `run_ai_pilot_wheel` now calls
    # `ai_pilot_update_seat`, which closes over these.
    "SEAT_BOUNDARY_FWD_M",
    "SEAT_CAMERA_MIN_FWD_M",
    "SEAT_CAMERA_MAX_FWD_M",
    "SEAT_CAMERA_MAX_OFFAXIS_M",
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
local ai_pilot_player_seat = nil
local ai_pilot_cam_fwd_m = nil
local ai_pilot_mode_text = nil
local ai_pilot_course_text = nil
local ai_pilot_alt_text = nil
local ai_pilot_alt_add_text = nil
local ai_pilot_speed_text = nil
local ai_pilot_last_press = nil
local ai_wheel_pending_release_t = nil
local ai_wheel_pending_cmd = nil

-- Stage P2a/P2b's own pending-release pair and co-moving state --
-- mirrors production's own initial values (`ai_pilot_wheel.lua`'s own
-- declarations), needed here because `update_ai_pilot_wheel_overlay`
-- now transitively calls the goal/HVRT tick chain which reads and
-- writes both.
local ai_wheel_goal_pending_release_t = nil
local ai_wheel_goal_pending_cmd = nil
local ai_pilot_goal = {
    param = nil,
    heading_target_deg = nil,
    altitude_target_m = nil,
    altitude_target_ref = nil,
    speed_target_kmh = nil,
    goal_seq = 0,
    progress = "idle",
    mode_cycle_attempts = 0,
    hold_cmd = nil,
    toggling_reference = false,
    hvrt_direction = nil,
    hvrt_hold_cmd = nil,
    hvrt_started_t = nil,
}

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

-- Seat mocks: ownship at the origin heading north (+x), level; the
-- camera defaults to the operator's eye point (`Views.lua` x = 4.65), so
-- every takeover scenario runs with the player in the copilot seat
-- unless a test moves `camera_fwd`. `camera_fwd = nil` = no camera.
local camera_fwd = 4.65
local function LoGetCameraPosition()
    if camera_fwd == nil then return nil end
    return {p = {x = camera_fwd, y = 0.5, z = 0.0}}
end
local function LoGetSelfData()
    return {Position = {x = 0.0, y = 0.0, z = 0.0}, Heading = 0.0}
end
local function LoGetADIPitchBankYaw()
    return 0.0, 0.0, 0.0
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
            # Stage P2a/P2b's own pure decisions, in the same relative
            # order as the real file (Lua has no hoisting).
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_mode_ready"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_heading_direction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_ref_letter"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_altitude_ref_mismatch"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_speed_tap_direction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_hvrt_direction_cmd"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_park_rising"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_seat_from_camera"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_update_seat"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_tap30"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_open_hold"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_release_hold"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_open_hold"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_begin_hold_phase"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_decide_correction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_check_hold_convergence"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_heading"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_altitude"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_speed"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_hvrt"),
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


class TestSeatFromCamera:
    """fix/ai-wheel-pilot-seat-gate: which seat the camera is in, from
    `Views.lua`'s eye points (pilot x = 3.15, operator x = 4.65)."""

    def _seat(self, cam: str, own: str, heading: str, pitch: str = "0.0") -> str:
        tail = f"""
        local seat, fwd = ai_pilot_seat_from_camera({cam}, {own}, {heading}, {pitch})
        print(tostring(seat) .. "|" .. (fwd and string.format("%.2f", fwd) or "nil"))
        """
        return _run_lua(["ai_pilot_seat_from_camera"], tail).strip()

    def test_pilot_and_operator_eye_points_heading_north(self) -> None:
        own = "{x = 100, y = 50, z = 200}"
        assert (
            self._seat("{x = 103.15, y = 50.57, z = 200}", own, "0.0") == "pilot|3.15"
        )
        assert (
            self._seat("{x = 104.65, y = 49.95, z = 200}", own, "0.0")
            == "operator|4.65"
        )

    def test_projection_follows_heading_east(self) -> None:
        """Heading pi/2 (east, +z): the operator eye sits 4.65 m along +z."""
        own = "{x = 0, y = 0, z = 0}"
        assert self._seat("{x = 0, y = 0, z = 4.65}", own, "math.pi / 2").startswith(
            "operator"
        )
        assert self._seat("{x = 0, y = 0, z = 3.15}", own, "math.pi / 2").startswith(
            "pilot"
        )

    def test_projection_follows_pitch(self) -> None:
        """20 deg nose-up: the operator eye is up and forward along the tilted axis."""
        own = "{x = 0, y = 0, z = 0}"
        cam = "{x = 4.65 * math.cos(math.rad(20)), y = 4.65 * math.sin(math.rad(20)), z = 0}"
        assert self._seat(cam, own, "0.0", "math.rad(20)") == "operator|4.65"

    def test_head_travel_limits_stay_on_their_side(self) -> None:
        """6DOF x travel -0.1..+0.5: pilot leaning fully forward (3.65)
        and operator leaning fully back (4.55) still read their own seat."""
        own = "{x = 0, y = 0, z = 0}"
        assert self._seat("{x = 3.65, y = 0.57, z = 0}", own, "0.0").startswith("pilot")
        assert self._seat("{x = 4.55, y = 0, z = 0}", own, "0.0").startswith("operator")

    def test_external_camera_is_no_reading(self) -> None:
        own = "{x = 0, y = 0, z = 0}"
        assert self._seat("{x = -20, y = 5, z = 0}", own, "0.0").startswith("nil|")
        assert self._seat("{x = 4.65, y = 0, z = 6}", own, "0.0").startswith("nil|")

    def test_missing_inputs_are_no_reading(self) -> None:
        own = "{x = 0, y = 0, z = 0}"
        assert self._seat("nil", own, "0.0") == "nil|nil"
        assert self._seat("{x = 4.65, y = 0, z = 0}", own, "nil") == "nil|nil"


class TestSeatGate:
    """The user's bug, 2026-11-16: in the pilot seat arg 852 reads stowed
    (copilot controls parked) with the AI not flying, and the takeover
    sequence pressed centre and toggled the overlay forever. "Petrobrain
    must not operate AI wheel when AI is not flying."""

    def test_pilot_seat_with_stowed_stick_never_presses(self) -> None:
        script = f"""
        camera_fwd = 3.15
        msl_value = 900.0
        agl_value = 300.0
        stick_park_value = 1.0
        local t = 0.0
        while t < 10.0 do
            run_ai_pilot_wheel(t)
            if math.floor(t * 5 + 0.5) == t * 5 then
                update_ai_pilot_wheel_overlay({json.dumps(_EMPTY_RAW)}, t)
            end
            t = t + 0.1
        end
        print("presses=" .. #press_log)
        print("parked=" .. tostring(ai_pilot_parked_active))
        print("seat=" .. tostring(ai_pilot_player_seat))
        print("stage=" .. tostring(ai_pilot_takeover.stage))
        """
        values = dict(
            line.split("=", 1)
            for line in _run_ai_pilot_wheel_integration(script).strip().splitlines()
        )
        assert values["presses"] == "0"
        assert values["parked"] == "false"
        assert values["seat"] == "pilot"
        assert values["stage"] == "nil"

    def test_no_seat_known_yet_never_presses(self) -> None:
        """Camera unreadable from the start (no seat known): not flying."""
        script = """
        camera_fwd = nil
        stick_park_value = 1.0
        msl_value = 900.0
        for i = 0, 20 do run_ai_pilot_wheel(i * 0.1) end
        print("presses=" .. #press_log)
        print("parked=" .. tostring(ai_pilot_parked_active))
        """
        values = dict(
            line.split("=", 1)
            for line in _run_ai_pilot_wheel_integration(script).strip().splitlines()
        )
        assert values["presses"] == "0"
        assert values["parked"] == "false"

    def test_switch_to_pilot_seat_mid_hold_releases_without_menu_tap(self) -> None:
        """AI flying from the operator seat, a hold open, then the player
        moves to the pilot seat (852 stays stowed): the held press is
        released, but no menu tap -- it would land on the pilot seat's own
        wheel -- and the takeover state is dropped."""
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

        camera_fwd = 3.15
        stick_park_value = 1.0
        run_ai_pilot_wheel(1.2)
        local after = {{}}
        for i = before + 1, #press_log do table.insert(after, press_log[i]) end
        print("switch_presses=" .. table.concat(after, ","))
        print("parked=" .. tostring(ai_pilot_parked_active))
        print("menu_open=" .. tostring(ai_pilot_takeover.menu_open))
        print("stage=" .. tostring(ai_pilot_takeover.stage))

        local n = #press_log
        for i = 13, 60 do
            run_ai_pilot_wheel(i * 0.1)
            update_ai_pilot_wheel_overlay({json.dumps(_EMPTY_RAW)}, i * 0.1)
        end
        print("later_presses=" .. (#press_log - n))
        """
        values = dict(
            line.split("=", 1)
            for line in _run_ai_pilot_wheel_integration(script).strip().splitlines()
        )
        assert values["holding"] == "3005"
        assert values["switch_presses"] == "3005:0"
        assert values["parked"] == "false"
        assert values["menu_open"] == "false"
        assert values["stage"] == "nil"
        assert values["later_presses"] == "0"

    def test_goal_hold_releases_without_new_press_on_switch_to_pilot_seat(
        self,
    ) -> None:
        """Same rule, for the goal channel (Stage P2a/P2b merge, not the
        takeover correction above): a heading-goal hold open while flying
        from the operator seat, then the player moves to the pilot seat --
        the held press releases, the goal state drops to idle, and nothing
        presses again while the seat stays pilot."""
        script = """
        msl_value = 900.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        print("parked_before=" .. tostring(ai_pilot_parked_active))

        -- Simulate an open heading-goal hold directly, the same shape
        -- `ai_pilot_goal_open_hold` leaves it in.
        ai_wheel_goal_pending_cmd = 3002  -- AI_WHEEL_RIGHT
        ai_wheel_goal_pending_release_t = 999.0
        ai_pilot_goal.param = "heading"
        ai_pilot_goal.heading_target_deg = 90.0
        ai_pilot_goal.progress = "pressing"
        ai_pilot_goal.hold_cmd = 3002
        local before = #press_log

        camera_fwd = 3.15
        stick_park_value = 1.0
        run_ai_pilot_wheel(0.1)
        local released = {}
        for i = before + 1, #press_log do table.insert(released, press_log[i]) end
        print("released_presses=" .. table.concat(released, ","))
        print("parked_after=" .. tostring(ai_pilot_parked_active))
        print("goal_progress_after=" .. tostring(ai_pilot_goal.progress))
        print("goal_hold_cmd_after=" .. tostring(ai_pilot_goal.hold_cmd))
        print("menu_open_after=" .. tostring(ai_pilot_takeover.menu_open))

        local n = #press_log
        for i = 2, 30 do run_ai_pilot_wheel(i * 0.1) end
        print("later_presses=" .. (#press_log - n))
        """
        values = dict(
            line.split("=", 1)
            for line in _run_ai_pilot_wheel_integration(script).strip().splitlines()
        )
        assert values["parked_before"] == "true"
        assert values["released_presses"] == "3002:0"
        assert values["parked_after"] == "false"
        assert values["goal_progress_after"] == "idle"
        assert values["goal_hold_cmd_after"] == "nil"
        assert values["menu_open_after"] == "false"
        assert values["later_presses"] == "0"

    def test_entering_operator_seat_with_stick_still_stowed_presses_nothing(
        self,
    ) -> None:
        """Pilot -> operator switch: the camera reaches the operator seat
        while arg 852 still reads stowed for a moment (the player retakes
        the copilot stick; un-stow lag). That brief false rising edge must
        be absorbed by the 0.5 s reference-toggle delay -- no press, and
        the takeover dropped once 852 falls."""
        script = """
        camera_fwd = 3.15
        stick_park_value = 1.0
        msl_value = 900.0
        agl_value = 300.0
        run_ai_pilot_wheel(0.0)          -- pilot seat, stowed: not flying
        camera_fwd = 4.65                -- seat switch
        run_ai_pilot_wheel(0.1)          -- false rising edge
        print("stage_at_edge=" .. tostring(ai_pilot_takeover.stage))
        stick_park_value = 0.5           -- un-stow under way
        run_ai_pilot_wheel(0.2)
        stick_park_value = 0.0
        for i = 3, 30 do run_ai_pilot_wheel(i * 0.1) end
        print("presses=" .. #press_log)
        print("stage=" .. tostring(ai_pilot_takeover.stage))
        print("parked=" .. tostring(ai_pilot_parked_active))
        """
        values = dict(
            line.split("=", 1)
            for line in _run_ai_pilot_wheel_integration(script).strip().splitlines()
        )
        assert values["stage_at_edge"] == "toggling_reference"
        assert values["presses"] == "0"
        assert values["stage"] == "nil"
        assert values["parked"] == "false"

    def test_external_view_keeps_the_operator_seat(self) -> None:
        """Camera leaves the cockpit (F2 / map) while the AI flies: the
        last known seat holds, the takeover is not dropped."""
        script = """
        msl_value = 900.0
        agl_value = 300.0
        stick_park_value = 0.95
        run_ai_pilot_wheel(0.0)
        camera_fwd = -25.0
        run_ai_pilot_wheel(0.1)
        print("parked=" .. tostring(ai_pilot_parked_active))
        print("seat=" .. tostring(ai_pilot_player_seat))
        print("stage=" .. tostring(ai_pilot_takeover.stage))
        """
        values = dict(
            line.split("=", 1)
            for line in _run_ai_pilot_wheel_integration(script).strip().splitlines()
        )
        assert values["parked"] == "true"
        assert values["seat"] == "operator"
        assert values["stage"] == "toggling_reference"


def _run_on_stop(
    pending_cmd: str,
    goal_hold_cmd: str = "nil",
    hvrt_hold_cmd: str = "nil",
) -> dict[str, str]:
    """`AC-B13`'s own test (plan Stage 6): runs the real, extracted
    `on_stop` against a minimal `GetDevice` mock for device 30's
    `performClickableAction`, with `ai_wheel_pending_cmd` preset to
    `pending_cmd` (an `AI_WHEEL_UP`/`AI_WHEEL_DOWN` command id as a Lua
    literal, or `"nil"` for no open press) and `ai_pilot_takeover`
    populated as a hold in progress would leave it. `goal_hold_cmd`/
    `hvrt_hold_cmd` (Stage P2a/P2b's own addition to this fix, same
    proactive-close-the-gap reasoning as `AC-B13` itself) are the
    equivalent presets for `ai_pilot_goal.hold_cmd`/`.hvrt_hold_cmd`.
    Returns every printed `key=value` line as a dict."""
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
local ai_wheel_goal_pending_release_t = 42.0
local ai_wheel_goal_pending_cmd = {goal_hold_cmd}
local ai_pilot_goal = {{
    param = "altitude",
    heading_target_deg = nil,
    altitude_target_m = 300.0,
    altitude_target_ref = "barometric",
    speed_target_kmh = nil,
    goal_seq = 5,
    progress = "pressing",
    mode_cycle_attempts = 0,
    hold_cmd = {goal_hold_cmd},
    toggling_reference = false,
    hvrt_direction = "left",
    hvrt_hold_cmd = {hvrt_hold_cmd},
    hvrt_started_t = 2.0,
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
        'print("raw_arg952=" .. tostring(ai_pilot_takeover.raw_arg952))\n'
        'print("goal_pending_release_t=" .. tostring(ai_wheel_goal_pending_release_t))\n'
        'print("goal_pending_cmd=" .. tostring(ai_wheel_goal_pending_cmd))\n'
        'print("goal_param=" .. tostring(ai_pilot_goal.param))\n'
        'print("goal_altitude_target_m=" .. tostring(ai_pilot_goal.altitude_target_m))\n'
        'print("goal_progress=" .. tostring(ai_pilot_goal.progress))\n'
        'print("goal_hold_cmd=" .. tostring(ai_pilot_goal.hold_cmd))\n'
        'print("goal_hvrt_direction=" .. tostring(ai_pilot_goal.hvrt_direction))\n'
        'print("goal_hvrt_hold_cmd=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))\n'
        'print("goal_hvrt_started_t=" .. tostring(ai_pilot_goal.hvrt_started_t))'
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
        # Stage P2a/P2b's own co-moving state -- always cleared, even
        # with no goal hold or HVRT press open this call (the default
        # `goal_hold_cmd`/`hvrt_hold_cmd` of `"nil"`).
        assert values["goal_pending_release_t"] == "nil"
        assert values["goal_pending_cmd"] == "nil"
        assert values["goal_param"] == "nil"
        assert values["goal_altitude_target_m"] == "nil"
        assert values["goal_progress"] == "idle"
        assert values["goal_hold_cmd"] == "nil"
        assert values["goal_hvrt_direction"] == "nil"
        assert values["goal_hvrt_hold_cmd"] == "nil"
        assert values["goal_hvrt_started_t"] == "nil"

    def test_open_goal_hold_and_hvrt_press_are_both_released(self) -> None:
        """Stage P2a/P2b's own addition to the `AC-B13` fix, applied
        proactively: an open altitude/heading goal hold and an open HVRT
        translate press are each released exactly once, same as the
        takeover correction's own open press."""
        values = _run_on_stop(
            "nil", goal_hold_cmd="3005", hvrt_hold_cmd="3003"
        )  # AI_WHEEL_DOWN, AI_WHEEL_LEFT
        assert values["press_log"] == "3005:0,3003:0"
        assert values["goal_pending_release_t"] == "nil"
        assert values["goal_pending_cmd"] == "nil"
        assert values["goal_hold_cmd"] == "nil"
        assert values["goal_hvrt_hold_cmd"] == "nil"
        assert values["goal_hvrt_started_t"] == "nil"
        assert values["goal_hvrt_direction"] == "nil"
        assert values["goal_progress"] == "idle"

    def test_no_open_press_releases_nothing_but_still_clears_state(self) -> None:
        """No stale press to release (`ai_wheel_pending_cmd` already
        `nil`) -- no spurious release call, but every takeover field is
        still cleared."""
        values = _run_on_stop("nil")
        assert values["press_log"] == ""
        assert values["stage"] == "nil"
        assert values["correction_hold_cmd"] == "nil"


#: Stage P2a/P2b's own integration harness -- a fresh, self-contained
#: `GetDevice`/overlay mock (not `_run_ai_pilot_wheel_integration`'s own,
#: which is built around the takeover correction's `GetDevice(0)`/MSL/AGL
#: stubs this stage does not need): the goal/HVRT tick chain and
#: `handle_ai_pilot_goal_command` only ever touch device 30 and the
#: already-parsed overlay text locals.
_GOAL_INTEGRATION_CONSTANTS = (
    "AI_PILOT_ALT_TOLERANCE_M",
    "AI_PILOT_HEADING_TOLERANCE_DEG",
    "AI_PILOT_SPEED_TOP_STEP_KMH",
    "AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S",
    "MODE_CYCLE_MAX_ATTEMPTS",
    "HVRT_TRANSLATE_MAX_HOLD_S",
    "SHORT_PULSE_S",
    "AI_WHEEL_UP",
    "AI_WHEEL_DOWN",
    "AI_WHEEL_LEFT",
    "AI_WHEEL_RIGHT",
)


def _run_goal_integration(script_body: str) -> str:
    """Runs the real goal/HVRT tick chain plus `handle_ai_pilot_goal_
    command` together against a minimal device-30 press-log mock, in one
    Lua process so `ai_pilot_goal`/the overlay text locals persist across
    calls exactly as they do across real ticks."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    constants = (
        "\n".join(
            _extract_lua_constant(_AI_PILOT_WHEEL_LUA, name)
            for name in _GOAL_INTEGRATION_CONSTANTS
        )
        + "\n"
        + _extract_lua_constant(_CORE_LUA, "WHEEL_CENTER_BUTTON")
    )

    preamble = """
local ai_pilot_mode_text = nil
local ai_pilot_course_text = nil
local ai_pilot_alt_text = nil
local ai_pilot_alt_add_text = nil
local ai_pilot_speed_text = nil
local ai_pilot_last_press = nil
local ai_wheel_pending_release_t = nil
local ai_wheel_pending_cmd = nil
local ai_wheel_goal_pending_release_t = nil
local ai_wheel_goal_pending_cmd = nil
local ai_pilot_goal = {
    param = nil,
    heading_target_deg = nil,
    altitude_target_m = nil,
    altitude_target_ref = nil,
    speed_target_kmh = nil,
    goal_seq = 0,
    progress = "idle",
    mode_cycle_attempts = 0,
    hold_cmd = nil,
    toggling_reference = false,
    hvrt_direction = nil,
    hvrt_hold_cmd = nil,
    hvrt_started_t = nil,
}

local press_log = {}

local function GetDevice(id)
    if id == 30 then
        return {
            performClickableAction = function(self, cmd, value)
                table.insert(press_log, cmd .. ":" .. tostring(value))
            end,
        }
    end
    return nil
end
"""
    functions = "\n".join(
        _extract_lua_function(path, name)
        for path, name in (
            (_CORE_LUA, "safe_call"),
            (_CORE_LUA, "extract_json_string_field"),
            (_CORE_LUA, "extract_json_number_field"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_correction_direction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_parse_altitude_text"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_mode_ready"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_heading_direction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_ref_letter"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_altitude_ref_mismatch"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_speed_tap_direction"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_hvrt_direction_cmd"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_tap30"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_open_hold"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_release_hold"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_heading"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_altitude"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_speed"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick"),
            (_AI_PILOT_WHEEL_LUA, "ai_pilot_goal_tick_hvrt"),
            (_AI_PILOT_WHEEL_LUA, "handle_ai_pilot_goal_command"),
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


class TestAiPilotGoalTick:
    """Stage P2a: the per-tick dispatcher (`ai_pilot_goal_tick`) --
    mode-cycle-then-press, and the `"mode_blocked"` bound."""

    def test_heading_goal_holds_then_settles(self) -> None:
        script = """
        ai_pilot_mode_text = "FLT"
        ai_pilot_course_text = "10"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": "heading", '
            .. '"heading_target_deg": 90.0, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null}', 0.0)
        ai_pilot_goal_tick(0.0)
        print("hold_cmd=" .. tostring(ai_pilot_goal.hold_cmd))
        print("progress=" .. tostring(ai_pilot_goal.progress))

        -- Readback crosses into tolerance -- the hold releases.
        ai_pilot_course_text = "91"
        ai_pilot_goal_tick(0.2)
        print("hold_cmd_after=" .. tostring(ai_pilot_goal.hold_cmd))
        print("progress_after=" .. tostring(ai_pilot_goal.progress))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["hold_cmd"] == "3002"  # AI_WHEEL_RIGHT (10 -> 90)
        assert values["progress"] == "pressing"
        assert values["hold_cmd_after"] == "nil"
        assert values["progress_after"] == "settled"

    def test_mode_cycles_before_pressing_then_blocks_after_the_bound(self) -> None:
        """Mode stuck on `CBTM` (never reads back `FLT`/`HVR`) -- bounded
        by `MODE_CYCLE_MAX_ATTEMPTS`, reported `"mode_blocked"`, the goal
        itself never dropped."""
        script = """
        ai_pilot_mode_text = "CBTM"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": "speed", '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": 150.0, '
            .. '"hvrt_direction": null}', 0.0)
        ai_pilot_goal_tick(0.0)
        ai_pilot_goal_tick(0.2)
        ai_pilot_goal_tick(0.4)
        print("attempts=" .. tostring(ai_pilot_goal.mode_cycle_attempts))
        print("progress=" .. tostring(ai_pilot_goal.progress))
        print("press_count=" .. #press_log)
        -- A 4th tick: the bound is checked *before* a new attempt is
        -- spent, so this is the tick that actually reports
        -- `"mode_blocked"`, with no 4th press issued.
        ai_pilot_goal_tick(0.6)
        print("attempts_after=" .. tostring(ai_pilot_goal.mode_cycle_attempts))
        print("progress_after=" .. tostring(ai_pilot_goal.progress))
        print("press_count_after=" .. #press_log)
        print("speed_target=" .. tostring(ai_pilot_goal.speed_target_kmh))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        # 3 ticks, 3 mode-cycle taps (press+release each -- `ai_pilot_
        # tap30`), still trying.
        assert values["attempts"] == "3"
        assert values["progress"] == "cycling_mode"
        assert values["press_count"] == "6"
        # 4th tick: bound reached, reported, no 4th tap.
        assert values["attempts_after"] == "3"
        assert values["progress_after"] == "mode_blocked"
        assert values["press_count_after"] == "6"  # no further tap issued
        assert values["speed_target"] == "150"  # goal kept, never dropped

    def test_altitude_goal_toggles_reference_before_holding(self) -> None:
        script = """
        ai_pilot_mode_text = "FLT"
        ai_pilot_alt_text = "500"
        ai_pilot_alt_add_text = "R"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": "altitude", '
            .. '"heading_target_deg": null, "altitude_target_m": 900.0, '
            .. '"altitude_target_ref": "barometric", "speed_target_kmh": null, '
            .. '"hvrt_direction": null}', 0.0)
        ai_pilot_goal_tick(0.0)
        print("toggling=" .. tostring(ai_pilot_goal.toggling_reference))
        print("press_1=" .. table.concat(press_log, ","))

        -- Reference has switched to B -- the pulse's own release already
        -- happened via `run_ai_pilot_wheel`'s own deadline check in
        -- production; this test drives the tick directly, so it sets
        -- the overlay forward by hand and re-ticks.
        ai_pilot_alt_add_text = "B"
        ai_pilot_alt_text = "500"
        ai_pilot_goal_tick(0.3)
        print("toggling_after=" .. tostring(ai_pilot_goal.toggling_reference))
        print("hold_cmd=" .. tostring(ai_pilot_goal.hold_cmd))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["toggling"] == "true"
        assert values["press_1"] == "3015:1"  # WHEEL_CENTER_BUTTON pressed
        assert values["toggling_after"] == "false"
        assert values["hold_cmd"] == "3004"  # AI_WHEEL_UP (500 -> 900)

    def test_speed_goal_taps_once_per_tick_until_settled(self) -> None:
        script = """
        ai_pilot_mode_text = "FLT"
        ai_pilot_speed_text = "120"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": "speed", '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": 150.0, '
            .. '"hvrt_direction": null}', 0.0)
        ai_pilot_goal_tick(0.0)
        print("press_1=" .. table.concat(press_log, ","))
        print("progress_1=" .. tostring(ai_pilot_goal.progress))

        ai_pilot_speed_text = "150"
        ai_pilot_goal_tick(0.2)
        print("press_2=" .. table.concat(press_log, ","))
        print("progress_2=" .. tostring(ai_pilot_goal.progress))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["press_1"] == "3004:1,3004:0"  # one short tap, UP
        assert values["progress_1"] == "pressing"
        assert values["press_2"] == "3004:1,3004:0"  # no new press
        assert values["progress_2"] == "settled"


class TestHandleAiPilotGoalCommand:
    def test_a_different_param_releases_any_open_hold(self) -> None:
        """`heading_target_deg` is deliberately sent **non-null** in the
        second message too, simulating a still-queued heading goal
        riding alongside the newly-active speed one (plan: "only the
        fields matching `param` are meaningful" -- the wire can
        legitimately carry a non-active target). The hold still
        releases (an active-param change, not a value change), and the
        stale heading field is simply never read while
        `.param == "speed"` -- harmless, not acted on."""
        script = """
        ai_pilot_mode_text = "FLT"
        ai_pilot_course_text = "10"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": "heading", '
            .. '"heading_target_deg": 90.0, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null}', 0.0)
        ai_pilot_goal_tick(0.0)
        print("hold_before=" .. tostring(ai_pilot_goal.hold_cmd))

        handle_ai_pilot_goal_command('{"goal_seq": 2, "param": "speed", '
            .. '"heading_target_deg": 90.0, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": 150.0, '
            .. '"hvrt_direction": null}', 0.2)
        print("hold_after=" .. tostring(ai_pilot_goal.hold_cmd))
        print("param_after=" .. tostring(ai_pilot_goal.param))
        print("heading_target_after=" .. tostring(ai_pilot_goal.heading_target_deg))

        -- A tick now must act on speed only -- never re-open a heading
        -- hold just because the stale field is still non-null.
        ai_pilot_speed_text = "120"
        ai_pilot_goal_tick(0.4)
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["hold_before"] == "3002"  # AI_WHEEL_RIGHT
        assert values["hold_after"] == "nil"
        assert values["param_after"] == "speed"
        assert values["heading_target_after"] == "90"
        # A speed tap (UP), never a heading hold (3002/3003).
        assert values["press_log"] == "3002:1,3002:0,3004:1,3004:0"

    def test_the_idle_message_clears_progress(self) -> None:
        script = """
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": "heading", '
            .. '"heading_target_deg": 90.0, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null}', 0.0)
        handle_ai_pilot_goal_command('{"goal_seq": 2, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null}', 0.2)
        print("param=" .. tostring(ai_pilot_goal.param))
        print("progress=" .. tostring(ai_pilot_goal.progress))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["param"] == "nil"
        assert values["progress"] == "idle"


class TestHandleAiPilotGoalCommandHvrtStep:
    """`hvrt_step`'s own one-shot-trigger behaviour -- acted on exactly
    once per distinct `goal_seq`, never sticky state."""

    def test_taps_once_on_a_fresh_goal_seq(self) -> None:
        script = """
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null, "hvrt_step": "up"}', 0.0)
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["press_log"] == "3004:1,3004:0"  # AI_WHEEL_UP, one tap

    def test_a_re_delivered_message_with_the_same_goal_seq_does_not_tap_again(
        self,
    ) -> None:
        script = """
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null, "hvrt_step": "up"}', 0.0)
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null, "hvrt_step": "up"}', 0.2)
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["press_log"] == "3004:1,3004:0"  # only the first call tapped

    def test_a_new_goal_seq_taps_again(self) -> None:
        script = """
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null, "hvrt_step": "down"}', 0.0)
        handle_ai_pilot_goal_command('{"goal_seq": 2, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null, "hvrt_step": "down"}', 0.2)
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["press_log"] == "3005:1,3005:0,3005:1,3005:0"


class TestAiPilotGoalTickHvrt:
    """Stage P2b: HVRT translate's own hold/redirect/hold-clear/timeout."""

    def test_opens_the_press_once_in_hvrt_mode(self) -> None:
        script = """
        ai_pilot_mode_text = "HVRT"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": "left"}', 0.0)
        ai_pilot_goal_tick_hvrt(0.0)
        print("hvrt_hold_cmd=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["hvrt_hold_cmd"] == "3003"  # AI_WHEEL_LEFT
        assert values["press_log"] == "3003:1"

    def test_redirecting_releases_the_old_press_and_opens_the_new_one(self) -> None:
        script = """
        ai_pilot_mode_text = "HVRT"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": "left"}', 0.0)
        ai_pilot_goal_tick_hvrt(0.0)
        handle_ai_pilot_goal_command('{"goal_seq": 2, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": "right"}', 0.5)
        ai_pilot_goal_tick_hvrt(0.5)
        print("press_log=" .. table.concat(press_log, ","))
        print("hvrt_hold_cmd=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["press_log"] == "3003:1,3003:0,3002:1"
        assert values["hvrt_hold_cmd"] == "3002"  # AI_WHEEL_RIGHT

    def test_the_spoken_hold_releases_immediately(self) -> None:
        script = """
        ai_pilot_mode_text = "HVRT"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": "left"}', 0.0)
        ai_pilot_goal_tick_hvrt(0.0)
        handle_ai_pilot_goal_command('{"goal_seq": 2, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": null}', 1.0)
        ai_pilot_goal_tick_hvrt(1.0)
        print("press_log=" .. table.concat(press_log, ","))
        print("hvrt_hold_cmd=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["press_log"] == "3003:1,3003:0"
        assert values["hvrt_hold_cmd"] == "nil"

    def test_the_safety_timeout_releases_and_reports(self) -> None:
        script = """
        ai_pilot_mode_text = "HVRT"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": "forward"}', 0.0)
        ai_pilot_goal_tick_hvrt(0.0)
        -- Still held well short of the timeout.
        ai_pilot_goal_tick_hvrt(10.0)
        print("hold_cmd_mid=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))
        -- Past HVRT_TRANSLATE_MAX_HOLD_S (15 s).
        ai_pilot_goal_tick_hvrt(15.1)
        print("hold_cmd_after=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))
        print("direction_after=" .. tostring(ai_pilot_goal.hvrt_direction))
        print("progress_after=" .. tostring(ai_pilot_goal.progress))
        print("press_log=" .. table.concat(press_log, ","))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        assert values["hold_cmd_mid"] == "3004"  # AI_WHEEL_UP, still held
        assert values["hold_cmd_after"] == "nil"
        assert values["direction_after"] == "nil"
        assert values["progress_after"] == "released_timeout"
        assert values["press_log"] == "3004:1,3004:0"

    def test_mode_cycles_toward_hvrt_from_hvr_before_opening_the_press(self) -> None:
        """`"right"` (`AI_WHEEL_RIGHT`, 3002) is deliberately the
        direction under test, not `"left"` -- the mode cycle itself
        always presses `AI_WHEEL_LEFT` (3003), so a `"left"` translate
        would make the mode-cycle tap and the eventual real press
        indistinguishable on the wire."""
        script = """
        ai_pilot_mode_text = "HVR"
        handle_ai_pilot_goal_command('{"goal_seq": 1, "param": null, '
            .. '"heading_target_deg": null, "altitude_target_m": null, '
            .. '"altitude_target_ref": null, "speed_target_kmh": null, '
            .. '"hvrt_direction": "right"}', 0.0)
        ai_pilot_goal_tick_hvrt(0.0)
        print("press_log=" .. table.concat(press_log, ","))
        print("hvrt_hold_cmd=" .. tostring(ai_pilot_goal.hvrt_hold_cmd))
        """
        out = _run_goal_integration(script)
        values = dict(line.split("=", 1) for line in out.strip().splitlines())
        # A mode-cycle short-left tap, never the HVRT press itself (not
        # yet in HVRT this tick).
        assert values["press_log"] == "3003:1,3003:0"
        assert values["hvrt_hold_cmd"] == "nil"
