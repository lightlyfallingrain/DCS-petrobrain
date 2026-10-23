"""`[[BL-B80]]` v2's pure-math Lua functions (`plans/9k113-sight-pointing/
plan.md`, Stage 4) -- `sight_world_to_body`, `sight_rate_limit_step`, and
`sight_mark_to_body_deg` -- run against a real Lua interpreter and
checked against Python reference vectors, not just parsed.

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
