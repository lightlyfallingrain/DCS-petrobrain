"""`push_payload_state` (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md`
Stage 4) run against a real Lua interpreter, not just read -- the
encoding, the `LoGetNameByType` failure fallback ("?"), and the
change-gate signature (send only when something differs from the last
line sent).

Same extraction technique as `test_sight_servo_lua.py`'s
`_extract_lua_function`/`_lua_executable` (duplicated rather than
imported across test modules, this project's own convention -- see that
module's docstring): slice the named `local function ... end` out of the
real, currently-deployed `Export.lua` and execute it standalone, so this
exercises the actual source rather than a hand-copied duplicate that
could drift from it. Skips cleanly without a Lua interpreter on `PATH`."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_EXPORT_LUA = Path(__file__).resolve().parent.parent / "dcs-export" / "Export.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")

#: Separates per-frame results in the harness's own stdout -- not a
#: newline, since the encoded payload line can legitimately be printed
#: with no embedded newline of its own but the overall output needs a
#: delimiter that can never appear inside a JSON line.
_FRAME_SEP = "\x02"
_NONE_SENTINEL = "\x01NONE\x01"


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(name: str) -> str:
    """Slice `local function {name}(...) ... end` out of `Export.lua` --
    same technique as `test_sight_servo_lua.py`'s own helper, **widened to
    also count `for`/`while`** as block openers (not just `function`/
    `if`): `push_payload_state` contains a `for` loop, which
    `test_sight_servo_lua.py`'s own copy of this helper never had to
    handle (its own extracted functions have none), so its narrower
    opener set would stop at the `for` loop's own closing `end` rather
    than the function's. `repeat`/`until` blocks are not in this file's
    style and are not handled."""
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in Export.lua"
    token_re = re.compile(r"\b(function|if|for|while|end)\b")
    depth = 1
    for token_match in token_re.finditer(text, start_match.end()):
        if token_match.group(1) == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


def _run_payload_frames(frames: list[str]) -> list[str | None]:
    """Each entry in `frames` is a Lua statement block that sets the
    globals `PAYLOAD_VALUE`/`NAME_FN` (consumed by the mocked
    `LoGetPayloadInfo`/`LoGetNameByType` below) before `push_payload_
    state(1.5)` is called. Returns, per frame, the line actually sent to
    the mocked `client` this call (stripped of its trailing newline), or
    `None` if nothing was sent that call -- `payload_last_signature`
    persists across frames exactly as it does across real polls, since
    all frames run in one Lua process."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    preamble = """
local sent_lines = {}
client = {
    send = function(self, line)
        table.insert(sent_lines, line)
        return true
    end,
}

PAYLOAD_VALUE = nil
NAME_FN = nil

function LoGetPayloadInfo()
    if PAYLOAD_VALUE == "ERROR" then
        error("simulated LoGetPayloadInfo failure")
    end
    return PAYLOAD_VALUE
end

function LoGetNameByType(a, b, c, d)
    return NAME_FN(a, b, c, d)
end

local function debug_log(msg) end
"""
    lines = [preamble]
    lines.extend(
        _extract_lua_function(name)
        for name in ("json_escape_string", "push_payload_state")
    )
    lines.append("local out = {}")
    for frame in frames:
        lines.append(f"local before = #sent_lines\n{frame}\npush_payload_state(1.5)")
        lines.append(
            "if #sent_lines > before then\n"
            "    table.insert(out, (sent_lines[#sent_lines]:gsub('\\n$', '')))\n"
            "else\n"
            f"    table.insert(out, '{_NONE_SENTINEL}')\n"
            "end"
        )
    lines.append(f"print(table.concat(out, '{_FRAME_SEP}'))")
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
    output = result.stdout.rstrip("\n")
    return [
        None if part == _NONE_SENTINEL else part for part in output.split(_FRAME_SEP)
    ]


class TestPushPayloadState:
    def test_encodes_current_station_and_stations(self) -> None:
        frame = """
        PAYLOAD_VALUE = {
            CurrentStation = 1,
            Stations = {
                [1] = { container = false, weapon = {1, 2, 3, 4}, count = 4 },
            },
        }
        NAME_FN = function(a, b, c, d) return "9M114" end
        """
        (line,) = _run_payload_frames([frame])
        assert line == (
            '{"t":1.500,"current_station":1,"stations":'
            '[{"index":1,"name":"9M114","count":4,"container":false}]}'
        )

    def test_name_lookup_failure_falls_back_to_placeholder(self) -> None:
        frame = """
        PAYLOAD_VALUE = {
            CurrentStation = 2,
            Stations = {
                [1] = { container = true, weapon = {9, 9, 9, 9}, count = 2 },
            },
        }
        NAME_FN = function(a, b, c, d) error("unknown weapon code") end
        """
        (line,) = _run_payload_frames([frame])
        assert '"name":"?"' in line
        assert '"count":2' in line
        assert '"container":true' in line

    def test_non_string_name_result_falls_back_to_placeholder(self) -> None:
        frame = """
        PAYLOAD_VALUE = {
            CurrentStation = 1,
            Stations = { [1] = { container = false, weapon = {1,1,1,1}, count = 1 } },
        }
        NAME_FN = function(a, b, c, d) return 42 end
        """
        (line,) = _run_payload_frames([frame])
        assert '"name":"?"' in line

    def test_empty_stations_table_encodes_an_empty_array(self) -> None:
        frame = """
        PAYLOAD_VALUE = { CurrentStation = 0, Stations = {} }
        """
        (line,) = _run_payload_frames([frame])
        assert line == '{"t":1.500,"current_station":0,"stations":[]}'

    def test_a_failed_lo_get_payload_info_call_sends_nothing(self) -> None:
        frame = 'PAYLOAD_VALUE = "ERROR"'
        (line,) = _run_payload_frames([frame])
        assert line is None

    def test_a_non_table_result_sends_nothing(self) -> None:
        frame = "PAYLOAD_VALUE = 7"
        (line,) = _run_payload_frames([frame])
        assert line is None

    def test_a_missing_current_station_sends_nothing(self) -> None:
        frame = "PAYLOAD_VALUE = { Stations = {} }"
        (line,) = _run_payload_frames([frame])
        assert line is None

    def test_unchanged_signature_sends_only_once(self) -> None:
        frame = """
        PAYLOAD_VALUE = {
            CurrentStation = 1,
            Stations = { [1] = { container = false, weapon = {1,1,1,1}, count = 4 } },
        }
        NAME_FN = function(a, b, c, d) return "9M114" end
        """
        first, second = _run_payload_frames([frame, frame])
        assert first is not None
        assert second is None

    def test_a_count_change_resends(self) -> None:
        base = """
        PAYLOAD_VALUE = {
            CurrentStation = 1,
            Stations = { [1] = { container = false, weapon = {1,1,1,1}, count = %d } },
        }
        NAME_FN = function(a, b, c, d) return "9M114" end
        """
        first, second = _run_payload_frames([base % 4, base % 3])
        assert first is not None
        assert second is not None
        assert '"count":4' in first
        assert '"count":3' in second

    def test_a_current_station_change_resends_even_with_the_same_stations(self) -> None:
        base = """
        PAYLOAD_VALUE = {
            CurrentStation = %d,
            Stations = { [1] = { container = false, weapon = {1,1,1,1}, count = 4 } },
        }
        NAME_FN = function(a, b, c, d) return "9M114" end
        """
        first, second = _run_payload_frames([base % 1, base % 2])
        assert first is not None
        assert second is not None
