"""`[[BL-B80]]` v2's pure-math Lua functions (`plans/9k113-sight-pointing/
plan.md`, Stage 4) -- `sight_world_to_body`, `sight_rate_limit_step`, and
`sight_mark_to_body_deg` -- run against a real Lua interpreter and
checked against Python reference vectors, not just parsed.

Also `sight_observ_transition` (F1 fix, `docs/acceptance/2026-10-24-
sortie-feedback.md`): the pure on->off edge decision factored out of
`run_sight_servo` so the "write zero once, then stop" rule is testable
without a DCS environment, plus an end-to-end check of `run_sight_servo`
itself (`TestRunSightServoObservOffWrites`) against a minimal `GetDevice`
mock, confirming the axis-write side effect actually follows the pure
decision.

Same extraction technique as `test_exponent_float_fix.py`'s
`_extract_lua_function`: slice the named `local function ... end` out of
the real, currently-deployed `Export.lua` and execute it standalone, so
this exercises the actual source rather than a hand-copied duplicate that
could drift from it. Skips cleanly without a Lua interpreter on `PATH`,
same posture as `test_dcs_export_lua_syntax.py`/`test_exponent_float_fix.
py`.

**Reference vectors are computed directly here with the stdlib `math`
module**, not imported from `body-layer`'s `perception.geometry` --
module independence (root `CLAUDE.md`'s "Subprojects": aircraft-layer has
no world-model/body-layer seam at all). `sight_world_to_body` mirrors
`perception.geometry.body_relative_direction`'s own rotation, given a
unit-range target built from the world `(az, el)`; the formula is
reproduced inline rather than imported."""

from __future__ import annotations

import math
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
    identical technique to `test_exponent_float_fix.py`'s own helper
    (duplicated rather than imported across test modules, same reasoning
    that module gives: it is small, self-contained, and importing across
    test files is not this project's convention)."""
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in Export.lua"
    token_re = re.compile(r"\b(function|if|end)\b")
    depth = 1
    for token_match in token_re.finditer(text, start_match.end()):
        if token_match.group(1) == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


def _run_lua(func_names: list[str], calls: list[str]) -> list[float]:
    """Extracts each of `func_names` from `Export.lua`, defines them in
    one script alongside `calls` (each a Lua expression producing one
    number), and returns the printed results as floats. Skips cleanly
    without a Lua interpreter on `PATH`."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    lines = [_extract_lua_function(name) for name in func_names]
    lines.append("local out = {}")
    for call in calls:
        lines.append(f"table.insert(out, string.format('%.10f', {call}))")
    lines.append('print(table.concat(out, "\\n"))')
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
    return [float(line) for line in result.stdout.splitlines()]


def _python_body_relative_direction(
    world_az_deg: float,
    world_el_deg: float,
    heading_deg: float,
    pitch_deg: float,
    bank_deg: float,
) -> tuple[float, float]:
    """The Python reference -- the same rotation `perception.geometry.
    body_relative_direction` performs, given a unit-range target built
    from the world direction (reproduced inline, see module docstring)."""
    az_rad = math.radians(world_az_deg)
    el_rad = math.radians(world_el_deg)
    north = math.cos(el_rad) * math.cos(az_rad)
    east = math.cos(el_rad) * math.sin(az_rad)
    up = math.sin(el_rad)

    heading_rad = math.radians(heading_deg)
    forward0 = north * math.cos(heading_rad) + east * math.sin(heading_rad)
    right0 = -north * math.sin(heading_rad) + east * math.cos(heading_rad)
    up0 = up

    pitch_rad = math.radians(pitch_deg)
    forward1 = forward0 * math.cos(pitch_rad) + up0 * math.sin(pitch_rad)
    up1 = -forward0 * math.sin(pitch_rad) + up0 * math.cos(pitch_rad)
    right1 = right0

    bank_rad = math.radians(bank_deg)
    right2 = right1 * math.cos(bank_rad) - up1 * math.sin(bank_rad)
    up2 = right1 * math.sin(bank_rad) + up1 * math.cos(bank_rad)

    body_az_deg = math.degrees(math.atan2(right2, forward1))
    body_el_deg = math.degrees(math.atan2(up2, math.hypot(forward1, right2)))
    return body_az_deg, body_el_deg


class TestSightWorldToBody:
    @pytest.mark.parametrize(
        "world_az_deg,world_el_deg,heading_deg,pitch_deg,bank_deg",
        [
            (0.0, 0.0, 0.0, 0.0, 0.0),
            (45.0, 10.0, 0.0, 0.0, 0.0),
            (90.0, 0.0, 90.0, 0.0, 0.0),
            (120.0, -15.0, 37.0, -8.0, 0.0),
            (200.0, 5.0, 10.0, 3.0, 25.0),
        ],
    )
    def test_matches_python_reference(
        self,
        world_az_deg: float,
        world_el_deg: float,
        heading_deg: float,
        pitch_deg: float,
        bank_deg: float,
    ) -> None:
        expected_az, expected_el = _python_body_relative_direction(
            world_az_deg, world_el_deg, heading_deg, pitch_deg, bank_deg
        )
        call = (
            f"sight_world_to_body({world_az_deg}, {world_el_deg}, "
            f"{heading_deg}, {pitch_deg}, {bank_deg})"
        )
        az_result, el_result = _run_lua(
            ["sight_world_to_body"],
            [f"({call})", f"select(2, {call})"],
        )
        assert az_result == pytest.approx(expected_az, abs=1e-6)
        assert el_result == pytest.approx(expected_el, abs=1e-6)


class TestSightRateLimitStep:
    def test_small_delta_lands_on_target(self) -> None:
        (result,) = _run_lua(
            ["sight_rate_limit_step"],
            ["sight_rate_limit_step(0.0, 1.0, 20.0, 1.0)"],
        )
        assert result == pytest.approx(1.0)

    def test_large_delta_is_rate_limited(self) -> None:
        (result,) = _run_lua(
            ["sight_rate_limit_step"],
            ["sight_rate_limit_step(0.0, 100.0, 20.0, 1.0)"],
        )
        assert result == pytest.approx(20.0)

    def test_negative_delta_is_rate_limited(self) -> None:
        (result,) = _run_lua(
            ["sight_rate_limit_step"],
            ["sight_rate_limit_step(0.0, -100.0, 20.0, 1.0)"],
        )
        assert result == pytest.approx(-20.0)


class TestSightMarkToBodyDeg:
    def test_affine_conversion(self) -> None:
        (result,) = _run_lua(
            ["sight_mark_to_body_deg"],
            ["sight_mark_to_body_deg(0.539, 0.500, 25.641025641)"],
        )
        assert result == pytest.approx((0.539 - 0.500) * (1.0 / 0.039), abs=1e-3)

    def test_at_boresight_is_zero(self) -> None:
        (result,) = _run_lua(
            ["sight_mark_to_body_deg"],
            ["sight_mark_to_body_deg(0.500, 0.500, 25.641025641)"],
        )
        assert result == pytest.approx(0.0, abs=1e-9)


class TestSightObservTransition:
    """F1: `sight_observ_transition(observ_on, was_on)` must return
    `write_zero = true` on exactly the on->off edge, and `false` on every
    other combination -- an off frame with no prior on (first frame, or
    OBSERV never switched on this mission) and every off frame after the
    edge already fired. `new_was_on` is just `observ_on`, carried so the
    caller can store it back into `sight_was_observ_on`."""

    @pytest.mark.parametrize(
        "observ_on,was_on,expected_write_zero,expected_new_was_on",
        [
            # Sustained on: never writes, tracks was_on = true.
            (True, False, False, True),
            (True, True, False, True),
            # The on->off edge: write zero exactly this once.
            (False, True, True, False),
            # Off with no prior on -- first frame ever, or OBSERV never
            # switched on this mission. Must NOT write (no stale command
            # to clear).
            (False, False, False, False),
        ],
    )
    def test_transition_decision(
        self,
        observ_on: bool,
        was_on: bool,
        expected_write_zero: bool,
        expected_new_was_on: bool,
    ) -> None:
        observ_arg = "true" if observ_on else "false"
        was_on_arg = "true" if was_on else "false"
        call = f"sight_observ_transition({observ_arg}, {was_on_arg})"
        write_zero, new_was_on = _run_lua(
            ["sight_observ_transition"],
            [
                f"(select(1, {call}) and 1 or 0)",
                f"(select(2, {call}) and 1 or 0)",
            ],
        )
        assert bool(write_zero) == expected_write_zero
        assert bool(new_was_on) == expected_new_was_on

    def test_rapid_off_on_off_each_edge_writes_exactly_once(self) -> None:
        """Mutation this catches: a version that writes on every off
        frame (not just the edge), or one that never writes at all.
        OBSERV toggled off -> on -> off -> on -> off should write on the
        1st and 3rd off frames only (frames 3 and 5 below), not frame 1
        (no prior on) and not a second time on any frame."""
        sequence = [False, True, False, True, False]
        was_on = False
        write_zero_flags: list[bool] = []
        for observ_on in sequence:
            observ_arg = "true" if observ_on else "false"
            was_on_arg = "true" if was_on else "false"
            call = f"sight_observ_transition({observ_arg}, {was_on_arg})"
            write_zero, new_was_on = _run_lua(
                ["sight_observ_transition"],
                [
                    f"(select(1, {call}) and 1 or 0)",
                    f"(select(2, {call}) and 1 or 0)",
                ],
            )
            write_zero_flags.append(bool(write_zero))
            was_on = bool(new_was_on)
        assert write_zero_flags == [False, False, True, False, True]


def _run_servo_off_sequence(frames: list[tuple[float, object]]) -> list[list[str]]:
    """Runs the real `run_sight_servo` against a minimal `GetDevice`
    mock (device 0's `ARG_OBSERVE` argument is each frame's `observe`
    value; device `DEV_I9K113`'s `SetCommand` is recorded) for each
    `(t, observe)` in `frames`, in one Lua process so module-level state
    (`sight_was_observ_on`, `sight_last_frame_t`, ...) persists across
    frames exactly as it does in a real sortie. Returns, per frame, the
    list of axis writes made that frame (e.g. `["az:0.000000",
    "el:0.000000"]`, or `[]` if none).

    `observe` may be a Lua number literal (on/off), or the string
    `"nil"`/`"'bad'"` to simulate a missing/non-number argument read --
    the caller passes it as a literal Lua expression, not a Python
    value, since `nil` and a Lua string both need to reach the script
    untouched."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    preamble = """
local ARG_OBSERVE = 886
local DEV_I9K113 = 7
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060

local observe_value = nil
local frame_log = {}

local function GetDevice(id)
    if id == 0 then
        return {
            get_argument_value = function(self, arg)
                if arg == ARG_OBSERVE then return observe_value end
                return nil
            end,
        }
    elseif id == DEV_I9K113 then
        return {
            SetCommand = function(self, cmd, value)
                if cmd == CMD_AI_AZ then
                    table.insert(frame_log, "az:" .. string.format("%.6f", value))
                elseif cmd == CMD_AI_ELEV then
                    table.insert(frame_log, "el:" .. string.format("%.6f", value))
                end
            end,
        }
    end
    return nil
end
"""
    lines = [preamble]
    lines.extend(
        _extract_lua_function(name)
        for name in (
            "safe_call",
            "sight_point_quiet",
            "sight_observ_transition",
            "run_sight_servo",
        )
    )
    lines.append("local out = {}")
    for t, observe_literal in frames:
        lines.append(f"observe_value = {observe_literal}")
        lines.append("frame_log = {}")
        lines.append(f"run_sight_servo({t})")
        lines.append('table.insert(out, table.concat(frame_log, ","))')
    lines.append('print(table.concat(out, "\\n"))')
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
    return [
        [] if line == "" else line.split(",") for line in result.stdout.splitlines()
    ]


class TestRunSightServoObservOffWrites:
    """F1 end-to-end: `run_sight_servo` itself, not just the pure
    decision, must write (0, 0) exactly once on the on->off edge and
    never otherwise -- exercised against a `GetDevice` mock rather than
    real DCS (no DCS environment available here)."""

    def test_first_frame_off_writes_nothing(self) -> None:
        # No prior frame at all, and OBSERV already off: no stale
        # command exists to clear, so nothing should be written --
        # named mutation "zero written on first frame with OBSERV off
        # and no prior on".
        frames = _run_servo_off_sequence([(0.0, "0.0")])
        assert frames == [[]]

    def test_on_then_off_writes_zero_once(self) -> None:
        frames = _run_servo_off_sequence([(0.0, "1.0"), (0.2, "0.0")])
        # Frame 1 (on, no align lamp mocked) is "caged": no writes.
        # Frame 2 is the edge: exactly one (0, 0) write.
        assert frames == [[], ["az:0.000000", "el:0.000000"]]

    def test_off_frame_after_edge_writes_nothing(self) -> None:
        # Named mutation "zero written every frame while off": a second
        # consecutive off frame must NOT write again.
        frames = _run_servo_off_sequence(
            [(0.0, "1.0"), (0.2, "0.0"), (0.4, "0.0"), (0.6, "0.0")]
        )
        assert frames == [[], ["az:0.000000", "el:0.000000"], [], []]

    def test_rapid_off_on_off_each_edge_writes_once(self) -> None:
        frames = _run_servo_off_sequence(
            [
                (0.0, "0.0"),
                (0.2, "1.0"),
                (0.4, "0.0"),
                (0.6, "1.0"),
                (0.8, "0.0"),
            ]
        )
        zero_write = ["az:0.000000", "el:0.000000"]
        assert frames == [[], [], zero_write, [], zero_write]

    def test_failed_arg_read_after_on_is_treated_as_off_and_writes_once(self) -> None:
        # `observe` not a number (e.g. a stale/failed GetDevice call) --
        # `type(observe) == "number"` is false, so `observ_on` is false
        # exactly like a genuine OFF read, same as every other `not
        # observ_on` branch in this function already treats it (this is
        # pre-existing behaviour, not new with this fix; see debug.md).
        frames = _run_servo_off_sequence([(0.0, "1.0"), (0.2, "nil")])
        assert frames == [[], ["az:0.000000", "el:0.000000"]]

    def test_mission_restart_does_not_replay_stale_edge(self) -> None:
        # A fresh `run_sight_servo` call sequence starting straight from
        # off, after `sight_was_observ_on` has been reset to `false` by
        # `LuaExportStop` (simulated here by simply starting the
        # sequence with no prior on-frame, which is what that reset
        # achieves) must not write -- same case as the first-frame test,
        # exercised explicitly for the restart scenario named in the
        # debug report.
        frames = _run_servo_off_sequence([(0.0, "0.0"), (0.2, "0.0")])
        assert frames == [[], []]
