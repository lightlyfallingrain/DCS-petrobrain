"""`core.lua`'s number-formatting helpers (`is_finite_number`,
`fmt_num_or_null`, `fmt_int_or_null`), run against a real Lua
interpreter -- not just read.

`fmt_int_or_null` is the fix for `plans/flight-control/debug.md`
"Common root cause, both modes" (2026-11-19): `fmt_num_or_null` formats
every number `%.5f`, which is correct for a measurement but turns a
sequence counter into `"-1.00000"` on the wire -- valid JSON, but a
`float`, which every schema field that demands a whole number (`fc_
take_seq`/`fc_goal_seq`/`fc_last_cmd_seq`, `apw_goal_seq`/`apw_cbtm_
seq`) then rejects, dropping the entire line. `fmt_int_or_null` is the
same contract with `%d` on a `math.floor`ed value instead.

Also covers the non-finite guard both formatters now share: `nan`/`inf`/
`-inf` are not valid JSON tokens, so a non-finite number must format as
`null` rather than emit something `json.loads` cannot parse at all --
unlike the type-only check either formatter had before, which only
caught a non-`number` value, never a `number` that just cannot ride on
the wire.

Same extraction technique as `test_sight_servo_lua.py`'s own
`_extract_lua_function` (duplicated rather than imported across test
modules, this project's own convention): slice the named `local
function ... end` out of the real, currently-deployed `core.lua` and
execute it standalone. Skips cleanly without a Lua interpreter on
`PATH`."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_PETROBRAIN_DIR = Path(__file__).resolve().parent.parent / "dcs-export" / "Petrobrain"
_CORE_LUA = _PETROBRAIN_DIR / "core.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(path: Path, name: str) -> str:
    """Identical technique to `test_sight_servo_lua.py`'s own copy of
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


def _run(driver: str) -> list[str]:
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    # `is_finite_number` must precede `fmt_num_or_null`/`fmt_int_or_null`
    # -- both call it as a bare name, and this concatenates the
    # extracted bodies into one chunk in this order, same
    # local-before-use rule `core.lua` itself follows.
    functions = "\n".join(
        _extract_lua_function(_CORE_LUA, name)
        for name in ("is_finite_number", "fmt_num_or_null", "fmt_int_or_null")
    )
    script = functions + "\n" + driver
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
    return [line for line in result.stdout.splitlines() if line != ""]


class TestFmtNumOrNull:
    def test_ordinary_float(self) -> None:
        assert _run("print(fmt_num_or_null(3.5))") == ["3.50000"]

    def test_nil_is_null(self) -> None:
        assert _run("print(fmt_num_or_null(nil))") == ["null"]

    def test_non_number_is_null(self) -> None:
        assert _run('print(fmt_num_or_null("x"))') == ["null"]

    def test_nan_is_null(self) -> None:
        """`0/0` is the portable way to construct NaN across Lua 5.1/
        5.5/LuaJIT without a library -- `%.5f` of NaN is not a valid
        JSON token (`"nan"`/`"-nan"`, interpreter-dependent), so this
        must format as `null` instead."""
        assert _run("print(fmt_num_or_null(0/0))") == ["null"]

    def test_positive_infinity_is_null(self) -> None:
        assert _run("print(fmt_num_or_null(math.huge))") == ["null"]

    def test_negative_infinity_is_null(self) -> None:
        assert _run("print(fmt_num_or_null(-math.huge))") == ["null"]


class TestFmtIntOrNull:
    def test_whole_number_formats_without_a_decimal_point(self) -> None:
        """The exact defect: `fmt_num_or_null(3)` would have emitted
        `"3.00000"`, a JSON float every strict-int schema field
        rejects. `fmt_int_or_null` must emit a bare `"3"`."""
        assert _run("print(fmt_int_or_null(3))") == ["3"]

    def test_negative_sentinel_formats_without_a_decimal_point(self) -> None:
        """`fc_last_cmd_seq`'s own `-1` sentinel (never-yet-accepted-a-
        command) -- the value that was dropping every single flight-
        control line, take or no take."""
        assert _run("print(fmt_int_or_null(-1))") == ["-1"]

    def test_value_past_2_pow_31_is_exact(self) -> None:
        """The millisecond reset epoch (~1.8e12). Lua 5.1's `%d` goes
        through C `long`, 32-bit on Windows, and would wrap it; `%.0f`
        does not. This interpreter's `long` is 64-bit, so the test pins
        the output rather than reproducing the Windows wrap."""
        assert _run("print(fmt_int_or_null(1795129850123))") == ["1795129850123"]

    def test_nil_is_null(self) -> None:
        assert _run("print(fmt_int_or_null(nil))") == ["null"]

    def test_non_number_is_null(self) -> None:
        assert _run('print(fmt_int_or_null("x"))') == ["null"]

    def test_nan_is_null(self) -> None:
        assert _run("print(fmt_int_or_null(0/0))") == ["null"]

    def test_positive_infinity_is_null(self) -> None:
        assert _run("print(fmt_int_or_null(math.huge))") == ["null"]

    def test_negative_infinity_is_null(self) -> None:
        assert _run("print(fmt_int_or_null(-math.huge))") == ["null"]


def test_file_parses_without_a_lua_interpreter_too() -> None:
    """`luac5.1 -p` sanity, independent of whether a runtime interpreter
    is on `PATH` -- mirrors `test_dcs_export_lua_syntax.py`'s own check."""
    exe = shutil.which("luac5.1")
    if exe is None:
        pytest.skip("no luac5.1 on PATH")
    result = subprocess.run(
        [exe, "-p", str(_CORE_LUA)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
