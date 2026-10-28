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

import itertools
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


#: Production's own margin-reduced call (`run_sight_servo`'s "v3:
#: `field_target`" comment) -- the property test below pins this exact
#: bound, not the raw field half-angle. Elevation's up/down insets use
#: round numbers rather than production's own measured 2026-10-28
#: values (~4.1/~14.4) since this property test is about the clip
#: function's own shape, not a production-constant regression pin.
_FIELD_HALF_INSET_DEG = 4.3 - 0.5
_FIELD_EL_UP_INSET_DEG = 5.0 - 0.5
_FIELD_EL_DOWN_INSET_DEG = 15.0 - 0.5


class TestSightClipToFieldBodyDeg:
    """v3's `sight_clip_to_field_body_deg` -- the standard ray-to-box
    clip (`plans/9k113-sight-pointing/plan.md` v3's own Lua snippet).
    Elevation's two bounds (`field_el_up_deg`/`field_el_down_deg`) became
    independent 2026-10-28 once flight measured them as asymmetric; a
    symmetric call passes the same value for both, which these existing
    (pre-asymmetry) cases do, and the dedicated asymmetric-elevation
    tests below pass different ones."""

    def test_inside_field_is_unclipped(self) -> None:
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                "(select(1, sight_clip_to_field_body_deg(2.0, 1.0, 4.3, 4.3, 4.3)))",
                "(select(2, sight_clip_to_field_body_deg(2.0, 1.0, 4.3, 4.3, 4.3)))",
                "(select(3, sight_clip_to_field_body_deg(2.0, 1.0, 4.3, 4.3, 4.3)) and 1 or 0)",
            ],
        )
        assert az == pytest.approx(2.0)
        assert el == pytest.approx(1.0)
        assert bool(clipped) is False

    def test_azimuth_only_clip_lands_exactly_on_the_edge(self) -> None:
        call = "sight_clip_to_field_body_deg(20.0, 0.0, 4.3, 4.3, 4.3)"
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                f"(select(1, {call}))",
                f"(select(2, {call}))",
                f"(select(3, {call}) and 1 or 0)",
            ],
        )
        assert az == pytest.approx(4.3)
        assert el == pytest.approx(0.0)
        assert bool(clipped) is True

    def test_whichever_axis_hits_its_own_edge_first_wins(self) -> None:
        # az alone would allow scale = 4.3/10 = 0.43; el alone would allow
        # scale = 2.0/10 = 0.2 -- the smaller (el's) must be the one used,
        # landing el exactly on its own edge and az short of its own.
        call = "sight_clip_to_field_body_deg(10.0, 10.0, 4.3, 2.0, 2.0)"
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                f"(select(1, {call}))",
                f"(select(2, {call}))",
                f"(select(3, {call}) and 1 or 0)",
            ],
        )
        assert el == pytest.approx(2.0)
        assert az == pytest.approx(2.0)  # same scale (0.2) applied to both
        assert az < 4.3
        assert bool(clipped) is True

    def test_setpoint_above_the_up_bound_lands_on_the_up_edge(self) -> None:
        # Asymmetric elevation (up=5.0, down=15.0): a setpoint well above
        # the up bound must clip there, never at the (much larger) down
        # bound.
        call = "sight_clip_to_field_body_deg(0.0, 20.0, 4.3, 5.0, 15.0)"
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                f"(select(1, {call}))",
                f"(select(2, {call}))",
                f"(select(3, {call}) and 1 or 0)",
            ],
        )
        assert az == pytest.approx(0.0)
        assert el == pytest.approx(5.0)
        assert bool(clipped) is True

    def test_setpoint_below_the_down_bound_lands_on_the_down_edge(self) -> None:
        # Same asymmetric field, mirrored: a setpoint well below the down
        # bound clips at -15.0, not at -5.0.
        call = "sight_clip_to_field_body_deg(0.0, -30.0, 4.3, 5.0, 15.0)"
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                f"(select(1, {call}))",
                f"(select(2, {call}))",
                f"(select(3, {call}) and 1 or 0)",
            ],
        )
        assert az == pytest.approx(0.0)
        assert el == pytest.approx(-15.0)
        assert bool(clipped) is True

    def test_setpoint_inside_the_asymmetric_field_is_unchanged(self) -> None:
        # -10.0 is inside the down bound (15.0) despite being outside the
        # up bound (5.0) -- the sign, not the magnitude alone, selects
        # which bound applies.
        call = "sight_clip_to_field_body_deg(0.0, -10.0, 4.3, 5.0, 15.0)"
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                f"(select(1, {call}))",
                f"(select(2, {call}))",
                f"(select(3, {call}) and 1 or 0)",
            ],
        )
        assert az == pytest.approx(0.0)
        assert el == pytest.approx(-10.0)
        assert bool(clipped) is False

    def test_diagonal_setpoint_below_the_down_bound_still_clips_azimuth_too(
        self,
    ) -> None:
        # Diagonal case: az alone would allow scale = 4.3/8 = 0.5375; the
        # down bound alone would allow scale = 15.0/24 = 0.625 -- az is
        # the smaller, so it wins and el lands short of its own edge.
        call = "sight_clip_to_field_body_deg(8.0, -24.0, 4.3, 5.0, 15.0)"
        az, el, clipped = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [
                f"(select(1, {call}))",
                f"(select(2, {call}))",
                f"(select(3, {call}) and 1 or 0)",
            ],
        )
        assert az == pytest.approx(4.3)
        assert el == pytest.approx(-12.9, abs=1e-6)  # -24 * (4.3/8)
        assert el > -15.0
        assert bool(clipped) is True

    @pytest.mark.parametrize(
        "set_az_deg,set_el_deg",
        [
            (0.0, 0.0),
            (1.0, 1.0),
            (4.3, 0.0),
            (0.0, 4.3),
            (10.0, 0.0),
            (0.0, 10.0),
            (10.0, 10.0),
            (60.0, 20.0),
            (-60.0, -15.0),
            (3.0, 3.0),
            (0.001, 90.0),
        ],
    )
    def test_property_never_exceeds_the_margin_inset_field(
        self, set_az_deg: float, set_el_deg: float
    ) -> None:
        """The property test the plan names: for any sampled setpoint
        magnitude up to the full gimbal range, `field_target` never lands
        outside the margin-inset field on either axis -- production's own
        call shape (`run_sight_servo`), not the raw field bounds."""
        call = (
            f"sight_clip_to_field_body_deg({set_az_deg}, {set_el_deg}, "
            f"{_FIELD_HALF_INSET_DEG}, {_FIELD_EL_UP_INSET_DEG}, {_FIELD_EL_DOWN_INSET_DEG})"
        )
        az, el = _run_lua(
            ["sight_clip_to_field_body_deg"],
            [f"(select(1, {call}))", f"(select(2, {call}))"],
        )
        assert abs(az) <= _FIELD_HALF_INSET_DEG + 1e-9
        assert el <= _FIELD_EL_UP_INSET_DEG + 1e-9
        assert el >= -_FIELD_EL_DOWN_INSET_DEG - 1e-9


class TestSightMarkIsClipped:
    """v3's `sight_mark_is_clipped` -- the root-cause fix: checks the
    mark's own raw reading against the ASP-17's own clip bound, not the
    setpoint against the gimbal limits (the old, wrongly-sized check).
    `field_up_deg`/`field_down_deg` became independent 2026-10-28 once
    flight measured elevation as asymmetric; a symmetric call (azimuth)
    passes the same value for both."""

    _BORESIGHT = 0.500
    _DEG_PER_UNIT = 1.0 / 0.039
    _FIELD_HALF_DEG = 4.3
    _MARGIN_DEG = 0.5

    def _clipped(
        self,
        mark_raw: float,
        *,
        field_up_deg: float | None = None,
        field_down_deg: float | None = None,
    ) -> bool:
        up = self._FIELD_HALF_DEG if field_up_deg is None else field_up_deg
        down = self._FIELD_HALF_DEG if field_down_deg is None else field_down_deg
        call = (
            f"sight_mark_is_clipped({mark_raw}, {self._BORESIGHT}, "
            f"{up}, {down}, {self._DEG_PER_UNIT}, {self._MARGIN_DEG})"
        )
        (result,) = _run_lua(["sight_mark_is_clipped"], [f"({call} and 1 or 0)"])
        return bool(result)

    def test_well_inside_is_not_clipped(self) -> None:
        # body_deg = 3.0, well under the 3.8 threshold (4.3 - 0.5).
        mark_raw = self._BORESIGHT + 3.0 / self._DEG_PER_UNIT
        assert self._clipped(mark_raw) is False

    def test_at_the_threshold_is_clipped(self) -> None:
        # body_deg = 3.8 exactly -- the boundary itself counts as clipped
        # (">="), the known churn risk the plan's own Risks section names.
        mark_raw = self._BORESIGHT + 3.8 / self._DEG_PER_UNIT
        assert self._clipped(mark_raw) is True

    def test_negative_edge_is_also_clipped(self) -> None:
        mark_raw = self._BORESIGHT - 3.8 / self._DEG_PER_UNIT
        assert self._clipped(mark_raw) is True

    def test_near_clip_value_from_the_probe_is_clipped(self) -> None:
        # 0.667 is the plan's own worked example of a near-clip-edge raw
        # reading (v3's "Tests" section, "mark reading held exactly at
        # the clip edge (566 = 0.667)").
        assert self._clipped(0.667) is True

    def test_asymmetric_up_bound_clips_independently_of_the_down_bound(
        self,
    ) -> None:
        # up=5.0, down=15.0: a reading 4.6 deg above boresight is clipped
        # against the (smaller) up bound, even though the same magnitude
        # would be well inside the down bound.
        mark_raw_up = self._BORESIGHT + 4.6 / self._DEG_PER_UNIT
        mark_raw_down = self._BORESIGHT - 4.6 / self._DEG_PER_UNIT
        assert self._clipped(mark_raw_up, field_up_deg=5.0, field_down_deg=15.0) is True
        assert (
            self._clipped(mark_raw_down, field_up_deg=5.0, field_down_deg=15.0) is False
        )

    def test_asymmetric_down_bound_clips_independently_of_the_up_bound(
        self,
    ) -> None:
        # Mirror of the above: a reading 14.6 deg below boresight clips
        # against the down bound (15.0), where the same magnitude above
        # boresight would already have cleared the (smaller) up bound.
        mark_raw = self._BORESIGHT - 14.6 / self._DEG_PER_UNIT
        assert self._clipped(mark_raw, field_up_deg=5.0, field_down_deg=15.0) is True


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


#: One reading in `TestRunSightServoFieldPark`'s mock-run sequences --
#: all fields optional except `t`. `setpoint` forces both the setpoint
#: and the goal to the same world-frame value with `t_sim = t` (age 0),
#: so the rate limiter is a no-op (delta 0) regardless of `dt` -- the
#: harness's own trick for landing exactly on a chosen setpoint every
#: frame without needing a multi-frame ramp. `rate` only feeds the
#: feed-forward term (age 0 means it never perturbs `goal_world_*`
#: itself) -- set it to something that deliberately does not match
#: `field_target`'s own frame-to-frame motion to exercise part 3's fix.
#: `m566`/`m555` are the raw mark args; omit both to simulate a missing
#: mark (`mark_types_ok == false`).
class _FieldParkFrame:
    def __init__(
        self,
        t: float,
        *,
        setpoint: tuple[float, float] | None = None,
        rate: tuple[float, float] = (0.0, 0.0),
        m566: float | None = None,
        m555: float | None = None,
        observe: bool = True,
        align: bool = True,
    ) -> None:
        self.t = t
        self.setpoint = setpoint
        self.rate = rate
        self.m566 = m566
        self.m555 = m555
        self.observe = observe
        self.align = align


class _FieldParkResult:
    def __init__(self, row: str) -> None:
        parts = row.split("|")
        assert len(parts) == 10, f"unexpected row shape: {row!r}"
        (
            mode,
            field_target_az,
            field_target_el,
            mark_clipped,
            error_az,
            error_el,
            stalled,
            stall_count,
            az_write,
            el_write,
        ) = parts
        self.mode = mode
        self.field_target_az = (
            None if field_target_az == "nil" else float(field_target_az)
        )
        self.field_target_el = (
            None if field_target_el == "nil" else float(field_target_el)
        )
        self.mark_clipped = mark_clipped == "true"
        self.error_az = None if error_az == "nil" else float(error_az)
        self.error_el = None if error_el == "nil" else float(error_el)
        self.stalled = stalled == "true"
        self.stall_count = int(stall_count)
        self.az_write = None if az_write == "none" else float(az_write)
        self.el_write = None if el_write == "none" else float(el_write)


def _run_field_park_sequence(frames: list[_FieldParkFrame]) -> list[_FieldParkResult]:
    """Runs the real `run_sight_servo` (v3) against a `GetDevice` mock
    covering device 0's `ARG_OBSERVE`/`ARG_ALIGN_LAMP`/566/555 and device
    `DEV_I9K113`'s `SetCommand`, plus `LoGetSelfData`/`LoGetADIPitchBankYaw`
    mocked to level flight (heading/pitch/bank all 0, so world == body
    directly and `_FieldParkFrame.setpoint` can be given in body degrees
    without a rotation). Every constant `run_sight_servo` reads
    (`GIMBAL_*`, `ASP17_FIELD_*`, `KP`, `FF_GAIN`, `HOMING_SAT_DEG`,
    `STALL_*`, `MARK_BORESIGHT_*`, `MARK_DEG_PER_UNIT_*`,
    `STALE_TARGET_TIMEOUT_S`, `EXTRAPOLATION_CAP_S`) is defined here as a
    plain global (not extracted from `Export.lua`, same reasoning
    `_run_servo_off_sequence` already relies on: an undeclared name
    referenced inside an extracted function body compiles as a global in
    this fresh chunk) with the same value as the real file.
    **`DITHER_AZ_DEG`/`DITHER_EL_DEG`/`FLICKER_EPS` are deliberately
    zeroed here** -- these tests are about the field-park/homing logic
    and the feed-forward rate, not the wobble mechanism (already covered
    elsewhere), and a zeroed wobble lets `az_write`/`el_write` read back
    as the bare commanded correction with no reconstruction needed."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    preamble = """
local ARG_OBSERVE = 886
local ARG_ALIGN_LAMP = 898
local DEV_I9K113 = 7
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060

local GIMBAL_AZ_HALF_DEG = 60.0
local GIMBAL_EL_UP_DEG = 20.0
local GIMBAL_EL_DOWN_DEG = -15.0
local ASP17_FIELD_AZ_HALF_DEG = 4.3
local ASP17_FIELD_MARGIN_DEG = 0.5
local KP = 3.0
local FF_GAIN = 3.0
local HOMING_SAT_DEG = 6.0
local STALL_CMD_DEG = 1.5
local STALL_WINDOW_S = 0.4
local STALL_MOVE_EPS = 0.003
local MARK_BORESIGHT_AZ = 0.500
local MARK_DEG_PER_UNIT_AZ = 1.0 / 0.039
-- Matches production's measured 2026-10-28 calibration/field (`Export.
-- lua`'s own `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL`/`ASP17_FIELD_EL_
-- UP_DEG`/`ASP17_FIELD_EL_DOWN_DEG`), not extracted (same reasoning as
-- every other constant in this preamble).
local MARK_BORESIGHT_EL = 0.83
local MARK_DEG_PER_UNIT_EL = 1.0 / 0.037
local ASP17_FIELD_EL_UP_DEG = (1.0 - MARK_BORESIGHT_EL) * MARK_DEG_PER_UNIT_EL
local ASP17_FIELD_EL_DOWN_DEG = (MARK_BORESIGHT_EL - 0.278) * MARK_DEG_PER_UNIT_EL
local STALE_TARGET_TIMEOUT_S = 3.0
local EXTRAPOLATION_CAP_S = 2.0
local SERVO_WOBBLE = "dither"
local DITHER_AZ_DEG = 0.0
local DITHER_HZ = 8.0
local DITHER_EL_DEG = 0.0
local FLICKER_EPS = 0.0

local observe_value = nil
local align_value = nil
local m566_value = nil
local m555_value = nil
local frame_log = {}

-- `run_sight_servo`'s own per-frame state is not extracted (only its
-- function body is), so every name it reads without a `local` in this
-- fresh chunk is an implicit global -- same reasoning `_run_servo_off_
-- sequence` already relies on. The ones it mutates with arithmetic or a
-- boolean default (never just assigned a fresh value first) need an
-- explicit starting value here, or the first stall-counting frame fails
-- with "attempt to perform arithmetic on global 'sight_stall_count' (a
-- nil value)".
sight_stall_count = 0
sight_stalled = false
sight_flicker_parity = false
sight_last_write_az_cmd = 0.0
sight_last_write_el_cmd = 0.0
sight_was_observ_on = false

local function GetDevice(id)
    if id == 0 then
        return {
            get_argument_value = function(self, arg)
                if arg == ARG_OBSERVE then return observe_value end
                if arg == ARG_ALIGN_LAMP then return align_value end
                if arg == 566 then return m566_value end
                if arg == 555 then return m555_value end
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

function LoGetSelfData()
    return {Heading = 0.0}
end

function LoGetADIPitchBankYaw()
    return 0.0, 0.0, 0.0
end

local function enc(v)
    if v == nil then return "nil" end
    if type(v) == "boolean" then return tostring(v) end
    return string.format("%.6f", v)
end
"""
    lines = [preamble]
    lines.extend(
        _extract_lua_function(name)
        for name in (
            "safe_call",
            "sight_point_quiet",
            "sight_rate_limit_step",
            "sight_world_to_body",
            "sight_mark_to_body_deg",
            "sight_observ_transition",
            "sight_clip_to_field_body_deg",
            "sight_mark_is_clipped",
            "run_sight_servo",
        )
    )
    lines.append("local out = {}")
    for frame in frames:
        observe_literal = "1.0" if frame.observe else "0.0"
        align_literal = "1.0" if frame.align else "0.0"
        lines.append(f"observe_value = {observe_literal}")
        lines.append(f"align_value = {align_literal}")
        lines.append(f"m566_value = {frame.m566 if frame.m566 is not None else 'nil'}")
        lines.append(f"m555_value = {frame.m555 if frame.m555 is not None else 'nil'}")
        if frame.setpoint is not None:
            set_az, set_el = frame.setpoint
            rate_az, rate_el = frame.rate
            lines.append(f"sight_setpoint_body_az_deg = {set_az}")
            lines.append(f"sight_setpoint_body_el_deg = {set_el}")
            lines.append(f"sight_goal_az_deg = {set_az}")
            lines.append(f"sight_goal_el_deg = {set_el}")
            lines.append(f"sight_goal_rate_az_deg_s = {rate_az}")
            lines.append(f"sight_goal_rate_el_deg_s = {rate_el}")
            lines.append(f"sight_goal_t_sim = {frame.t}")
        lines.append("frame_log = {}")
        lines.append(f"run_sight_servo({frame.t})")
        lines.append(
            'local az_write, el_write = "none", "none"\n'
            "for _, entry in ipairs(frame_log) do\n"
            '    if entry:sub(1, 3) == "az:" then az_write = entry:sub(4) end\n'
            '    if entry:sub(1, 3) == "el:" then el_write = entry:sub(4) end\n'
            "end"
        )
        lines.append(
            "table.insert(out, table.concat({"
            "tostring(sight_mode), "
            "enc(sight_field_target_body_az_deg), "
            "enc(sight_field_target_body_el_deg), "
            "tostring(sight_mark_clipped), "
            "enc(sight_error_az_deg), "
            "enc(sight_error_el_deg), "
            "tostring(sight_stalled), "
            "tostring(sight_stall_count), "
            "az_write, el_write"
            '}, "|"))'
        )
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
    return [_FieldParkResult(line) for line in result.stdout.splitlines()]


def _mark_raw(
    body_deg: float, *, boresight: float = 0.500, scale: float = 0.039
) -> float:
    """Inverts `sight_mark_to_body_deg` for the given `1/MARK_DEG_PER_
    UNIT_*` -- builds a raw mark arg that will read back as `body_deg`
    once `run_sight_servo` converts it. Defaults (`boresight=0.500,
    scale=0.039`) match the harness's own azimuth constants; elevation
    callers pass `boresight=0.83, scale=0.037` to match the harness's
    (measured 2026-10-28) `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL`."""
    return boresight + body_deg * scale


class TestRunSightServoFieldPark:
    """v3's root-cause fix end-to-end (`plans/9k113-sight-pointing/
    plan.md`'s "Tests" section under v3) -- exercised against the real,
    extracted `run_sight_servo` body, not a reproduction."""

    def test_far_off_boresight_setpoint_converges_as_mark_approaches_field_target(
        self,
    ) -> None:
        """Named mutation this must catch: reverting `field_target` back
        to the raw setpoint (20 deg) reproduces the sortie's own
        symptom -- an unbounded-looking error against a mark that cannot
        move past the field edge. The real fix's error shrinks toward
        zero as the mark approaches the *projected* point (3.8 deg, not
        20); the reverted version would report an error around
        16-19 deg at every one of these mark positions, never shrinking
        below ~16."""
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    0.0,
                    setpoint=(20.0, 0.0),
                    m566=_mark_raw(1.0),
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
                _FieldParkFrame(
                    0.2,
                    setpoint=(20.0, 0.0),
                    m566=_mark_raw(3.0),
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
                _FieldParkFrame(
                    0.4,
                    setpoint=(20.0, 0.0),
                    m566=_mark_raw(3.7),
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
            ]
        )
        errors = [abs(r.error_az) for r in frames]  # type: ignore[arg-type]
        assert frames[0].mode == "closed"
        assert frames[0].field_target_az == pytest.approx(3.8, abs=1e-6)
        assert errors[0] < 5.0  # bounded by the field, not ~18 (20 - 1)
        assert errors[1] < errors[0]
        assert errors[2] < errors[1]
        assert errors[2] < 1.0

    def test_mark_at_clip_edge_with_field_target_inset_is_homing_not_closed(
        self,
    ) -> None:
        """The regression test for the root cause itself: the old gate
        checked the *setpoint* against the gimbal limits, so with the
        setpoint well inside them (as here) it reported `closed` no
        matter what the mark itself read -- this is the input that must
        now report `homing` instead. 0.667 is the plan's own named
        near-clip-edge example."""
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    0.0,
                    setpoint=(1.0, 0.0),
                    m566=0.667,
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
            ]
        )
        assert frames[0].field_target_az == pytest.approx(1.0, abs=1e-6)
        assert frames[0].mode == "homing"
        assert frames[0].mark_clipped is True

    def test_homing_recovers_to_closed_within_one_frame_once_the_mark_clears(
        self,
    ) -> None:
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    0.0,
                    setpoint=(1.0, 0.0),
                    m566=0.667,
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
                _FieldParkFrame(
                    0.2,
                    setpoint=(1.0, 0.0),
                    m566=_mark_raw(1.0),
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
            ]
        )
        assert [r.mode for r in frames] == ["homing", "closed"]

    def test_feed_forward_uses_field_target_rate_not_raw_goal_rate_while_sliding(
        self,
    ) -> None:
        """Named mutation this must catch: feeding `sight_goal_rate_*_
        deg_s` into `ff` unconditionally (reverting part 3 only, parts
        1-2 left fixed) produces a command of KP*0.8 + FF_GAIN*50 = 152.4
        deg here -- clamped hard at the write stage -- rather than the
        correct KP*0.8 + FF_GAIN*1.8 = 7.8 deg this test pins."""
        frames = _run_field_park_sequence(
            [
                # Establishes `sight_prev_field_target_body_az_deg = 2.0`
                # (unclipped: setpoint (2, 1) is inside the inset field).
                _FieldParkFrame(
                    0.0,
                    setpoint=(2.0, 1.0),
                    m566=_mark_raw(1.0),
                    m555=_mark_raw(0.5, boresight=0.83, scale=0.037),
                ),
                # field_target now (3.8, 3.04) (az-limited clip, az's own
                # inset edge still the smaller scale under the asymmetric
                # elevation field too -- 3.04 is well inside the up inset,
                # ~5.17); ff_az = (3.8 - 2.0) / 1.0 = 1.8, NOT the
                # deliberately-mismatched raw rate (50 deg/s) fed in via
                # `rate`.
                _FieldParkFrame(
                    1.0,
                    setpoint=(10.0, 8.0),
                    rate=(50.0, 0.0),
                    m566=_mark_raw(3.0),
                    m555=_mark_raw(1.0, boresight=0.83, scale=0.037),
                ),
            ]
        )
        assert frames[1].mode == "closed"
        assert frames[1].field_target_az == pytest.approx(3.8, abs=1e-6)
        assert frames[1].az_write == pytest.approx(7.8 / 60.0, abs=1e-4)

    def test_homing_capped_push_feeds_the_stall_detector(self) -> None:
        """Point D: the old open branch never fed the stall detector at
        all -- `homing` must, using the same mark-motion definition."""
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(0.2, setpoint=(1.0, 0.0), m566=0.667, m555=0.83),
                _FieldParkFrame(0.7, setpoint=(1.0, 0.0), m566=0.667, m555=0.83),
            ]
        )
        assert [r.mode for r in frames] == ["homing", "homing"]
        assert frames[1].stalled is True
        assert frames[1].stall_count == 1

    def test_continuous_tracking_never_sticks_at_one_value_while_the_setpoint_slides(
        self,
    ) -> None:
        """The pilot's clarification: `field_target` tracks the moving
        intersection point every frame, never a one-shot park. A setpoint
        swept smoothly in azimuth while held a few degrees outside the
        elevation field is a tangential slide along the az edge (az pins
        at the inset edge throughout; el is what visibly slides) --
        regression case for "parks once and freezes" (which would hold
        `field_target_el` at its first computed value forever instead of
        continuing to track)."""
        az_values = [10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    float(i), setpoint=(az, 4.2), m566=_mark_raw(0.0), m555=0.83
                )
                for i, az in enumerate(az_values)
            ]
        )
        el_targets = [r.field_target_el for r in frames]
        az_targets = [r.field_target_az for r in frames]
        for az_target in az_targets:
            assert az_target == pytest.approx(
                3.8, abs=1e-6
            )  # pinned at the az edge throughout
        for earlier, later in itertools.pairwise(el_targets):
            assert later is not None and earlier is not None
            assert (
                later < earlier
            )  # strictly decreasing -- never stuck, never jumping back up
        assert el_targets[0] != el_targets[-1]  # never "parks once and freezes"

    def test_stall_detector_does_not_trip_while_the_mark_cleanly_tracks_a_sliding_target(
        self,
    ) -> None:
        """Worth its own test precisely because it is easy to assume the
        stall detector needs touching for a moving `field_target` -- its
        definition is already in terms of *mark* motion, so a mark that
        genuinely follows a sliding target along must never trip it,
        however large the per-frame command."""
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    0.0,
                    setpoint=(10.0, 0.0),
                    m566=_mark_raw(3.8),
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
                _FieldParkFrame(
                    0.5,
                    setpoint=(20.0, 0.0),
                    m566=_mark_raw(3.79),  # still tracking, not fixed in place
                    m555=_mark_raw(0.0, boresight=0.83),
                ),
            ]
        )
        assert all(not r.stalled for r in frames)
        assert frames[0].stall_count == 0
        assert frames[1].stall_count == 0

    def test_elevation_field_target_clips_at_the_up_inset_edge(self) -> None:
        """End-to-end regression for the 2026-10-28 measured elevation
        field (`docs/acceptance/2026-10-28-sortie-feedback.md` §2-4): a
        setpoint far above boresight parks at the (small) up inset edge
        -- the asymmetry the old, superseded symmetric `ASP17_FIELD_EL_
        HALF_DEG` placeholder could never express."""
        up_inset = (1.0 - 0.83) * (1.0 / 0.037) - 0.5
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    0.0,
                    setpoint=(0.0, 30.0),
                    m566=_mark_raw(0.0),
                    m555=_mark_raw(0.0, boresight=0.83, scale=0.037),
                ),
            ]
        )
        assert frames[0].field_target_el == pytest.approx(up_inset, abs=1e-6)

    def test_elevation_field_target_clips_at_the_down_inset_edge(self) -> None:
        """With the gimbal-derived scale (1/0.037, 2026-10-28) the measured
        down bound (~14.9 deg, inset ~14.4) sits just inside the -15 deg
        gimbal, so the down side is reachable: a setpoint driven to the
        gimbal extent parks at the down inset edge, not at the gimbal.
        (Under the rejected 1/0.030 scale the bound was ~18.4 deg and this
        side was unreachable.)"""
        down_inset = (0.83 - 0.278) * (1.0 / 0.037) - 0.5
        frames = _run_field_park_sequence(
            [
                _FieldParkFrame(
                    0.0,
                    setpoint=(0.0, -40.0),
                    m566=_mark_raw(0.0),
                    m555=_mark_raw(0.0, boresight=0.83, scale=0.037),
                ),
            ]
        )
        assert frames[0].field_target_el == pytest.approx(-down_inset, abs=1e-6)
