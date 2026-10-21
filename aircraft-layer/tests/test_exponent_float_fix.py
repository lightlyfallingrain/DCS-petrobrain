"""BL-B80's exponent-float fix (`plans/9k113-sight-pointing/plan.md`,
`plans/9k113-sight-pointing/implementation.md`'s "Exponent-float fix"
section, 2026-10-22).

**The bug.** `CommandSender.send_sight_target`/`send_cockpit_switch`
built their datagram with `json.dumps`, which emits exponent notation for
small magnitudes (`json.dumps({"x": 0.00001})` -> `'{"x": 1e-05}'`).
`Export.lua`'s `extract_json_number_field` matched
`"field"%s*:%s*(-?%d+%.?%d*)` -- plain decimal digits only, no exponent --
so it silently stopped at the "e": `"1e-05"` parsed as `1` (a
60deg-equivalent sight-slew command from a near-zero intent), `"-3.3e-07"`
as `-3.3`. Any `|value| < 1e-4` was affected, a magnitude body-layer float
arithmetic near sight centre readily produces.

**Two halves, two test classes:**

- `TestSenderNeverEmitsExponentNotation` -- the Python side never emits
  the notation that triggered the bug, for tiny and negative-tiny values.
- `TestExportLuaExtractorAcceptsExponentAndRejectsNonFinite` -- the Lua
  side, run against a real Lua interpreter (not just parsed), proves the
  fixed extractor round-trips exactly the values the old one truncated,
  and rejects the overflow case a huge exponent can produce
  (`"1e999"` -> `inf` -> rejected, not silently accepted as a number).
  Skips cleanly when no interpreter is on `PATH` -- same posture as
  `test_dcs_export_lua_syntax.py`/`test_dcs_export_lua_local_order.py`,
  which this module's extraction/skip approach otherwise mirrors."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

#: Matches a number written in exponent notation (`1e-05`, `-3.3E+07`) --
#: a bare `"e" in text` substring check is wrong here, since field names
#: like `"device"` legitimately contain the letter.
_EXPONENT_NUMBER_RE = re.compile(r"\d[eE][-+]?\d")

from collector.command_sender import CommandSender, _format_fixed_point

_EXPORT_LUA = Path(__file__).resolve().parent.parent / "dcs-export" / "Export.lua"

#: Execution tools, in preference order. Unlike `test_dcs_export_lua_
#: syntax.py`'s parse-only tools, this *runs* the extracted function --
#: harmless here since `extract_json_number_field` is pure string/number
#: logic with no DCS API dependency, so a non-5.1 interpreter's semantics
#: (string patterns, `tonumber`, `math.huge`) are identical for this
#: purpose. `luajit` is preferred since it is 5.1-compatible, matching
#: DCS's embedded interpreter most closely.
_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(name: str) -> str:
    """Slice `local function {name}(...) ... end` out of `Export.lua` by
    counting block-opening keywords (`function`/`if`) against `end` --
    the function itself contains no `for`/`while`/`do` to confuse the
    count. Executed standalone so this test exercises the real,
    currently-deployed source rather than a hand-copied duplicate that
    could drift from it."""
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in Export.lua"
    token_re = re.compile(r"\b(function|if|end)\b")
    depth = 1  # the "function" keyword in `start_match` itself
    for token_match in token_re.finditer(text, start_match.end()):
        if token_match.group(1) == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


def _run_extractor(cases: list[tuple[str, str]]) -> list[str]:
    """Run `extract_json_number_field(json_text, field_name)` for each
    `(json_text, field_name)` pair against a real Lua interpreter,
    returning each result as `tostring(...)` (`"nil"` or a numeric
    string)."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    func_src = _extract_lua_function("extract_json_number_field")
    lines = [func_src, "", "local out = {}"]
    for json_text, field_name in cases:
        lines.append(
            "table.insert(out, tostring(extract_json_number_field("
            f"[[{json_text}]], [[{field_name}]])))"
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
            [exe, script_path],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(script_path).unlink(missing_ok=True)

    assert result.returncode == 0, (
        f"Lua extractor harness failed (exe={exe}): {result.stderr}"
    )
    return result.stdout.splitlines()


class TestSenderNeverEmitsExponentNotation:
    """`_format_fixed_point` (and the two `CommandSender` methods built on
    it) must never produce the notation that `json.dumps` did -- the
    other half of the fix."""

    @pytest.mark.parametrize(
        "value",
        [1e-05, -3.3e-07, 0.0, -0.0, 0.25, -0.5],
    )
    def test_format_fixed_point_never_emits_exponent(self, value: float) -> None:
        text = _format_fixed_point(value)
        assert not _EXPONENT_NUMBER_RE.search(text), f"{value!r} formatted as {text!r}"
        # And it must still round-trip to (approximately) the same value --
        # a fixed-point render that is merely exponent-free but wrong would
        # be a different, equally bad failure.
        assert float(text) == pytest.approx(value, abs=1e-9)

    def test_send_sight_target_datagram_has_no_exponent(self) -> None:
        captured: dict[str, bytes] = {}

        class _RecordingSocket:
            def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
                captured["payload"] = payload
                return len(payload)

            def close(self) -> None:
                pass

        sender = CommandSender(host="127.0.0.1", port=1)
        sender.open()
        sender._socket = _RecordingSocket()  # type: ignore[assignment]
        sender.send_sight_target(1e-05, -3.3e-07)

        text = captured["payload"].decode("utf-8")
        assert not _EXPONENT_NUMBER_RE.search(text), (
            f"datagram contained exponent notation: {text!r}"
        )

    def test_send_cockpit_switch_datagram_has_no_exponent(self) -> None:
        captured: dict[str, bytes] = {}

        class _RecordingSocket:
            def sendto(self, payload: bytes, address: tuple[str, int]) -> int:
                captured["payload"] = payload
                return len(payload)

            def close(self) -> None:
                pass

        sender = CommandSender(host="127.0.0.1", port=1)
        sender.open()
        sender._socket = _RecordingSocket()  # type: ignore[assignment]
        sender.send_cockpit_switch(773, 3001, -3.3e-07)

        text = captured["payload"].decode("utf-8")
        assert not _EXPONENT_NUMBER_RE.search(text), (
            f"datagram contained exponent notation: {text!r}"
        )


class TestExportLuaExtractorAcceptsExponentAndRejectsNonFinite:
    """The fixed `extract_json_number_field`, run against a real Lua
    interpreter -- never just parsed. Skips cleanly without one."""

    def test_small_and_negative_exponent_values_round_trip(self) -> None:
        results = _run_extractor(
            [
                ('{"x":1e-05}', "x"),
                ('{"x":-3.3e-07}', "x"),
                ('{"x":0.25}', "x"),
                ('{"x":-0.5}', "x"),
            ]
        )
        assert len(results) == 4
        assert float(results[0]) == pytest.approx(1e-05)
        assert float(results[1]) == pytest.approx(-3.3e-07)
        assert float(results[2]) == pytest.approx(0.25)
        assert float(results[3]) == pytest.approx(-0.5)

    def test_huge_exponent_overflow_is_rejected_as_non_finite(self) -> None:
        """`"1e999"` overflows `tonumber` to `inf` in Lua -- the extractor
        must reject it (`nil`), not hand a non-finite number to a caller
        that only guards for `nil`."""
        results = _run_extractor([('{"x":1e999}', "x")])
        assert results == ["nil"]
