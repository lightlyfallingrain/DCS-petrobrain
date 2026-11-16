"""`push_ptt_state` (`plans/flight-control/plan.md`, Stage P-ICS) run
against a real Lua interpreter, not just read -- the debounce-on-either-
change behaviour: a line is sent when the pilot's trigger (arg 738)
moves, when the operator's (arg 856) moves, when both move on the same
frame, and not sent when neither has moved since the last send.

Same extraction technique as `test_payload_lua.py`'s own
`_extract_lua_function`/`_run_payload_frames` shape (duplicated rather
than imported across test modules, this project's own convention): slice
the real, currently-deployed `Export.lua` and execute it standalone, so
this exercises the actual source rather than a hand-copied duplicate
that could drift from it. Skips cleanly without a Lua interpreter on
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
_PTT_ICS_LUA = _PETROBRAIN_DIR / "ptt_ics.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")

_FRAME_SEP = "\x02"
_NONE_SENTINEL = "\x01NONE\x01"


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(path: Path, name: str) -> str:
    """Same technique as `test_payload_lua.py`'s own helper -- counts
    `function`/`if`/`for`/`while`/`end` as block openers/closer, `--`
    line comments skipped while counting (`test_sight_servo_lua.py`'s
    refinement)."""
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


def _extract_lua_constant(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(rf"^local {name} = (.+)$", text, re.MULTILINE)
    assert match is not None, f"{name} not found in {path.name}"
    return f"local {name} = {match.group(1)}"


def _run_ptt_frames(frames: list[str]) -> list[str | None]:
    """Each entry in `frames` is a Lua statement block that sets the
    globals `PTT_VALUE`/`PTT_OP_VALUE` (consumed by the mocked
    `GetDevice(0):get_argument_value`) before `push_ptt_state(1.5)` is
    called. Returns, per frame, the line actually sent to the mocked
    `client` this call (stripped of its trailing newline), or `None` if
    nothing was sent -- `last_ptt_sent`/`last_ptt_op_sent` persist across
    frames exactly as they do across real polls, since all frames run in
    one Lua process."""
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

PTT_VALUE = 0.0
PTT_OP_VALUE = 0.0

local DEVICE = {
    get_argument_value = function(self, arg)
        if arg == ARG_PILOT_PTT then
            return PTT_VALUE
        elseif arg == ARG_OPERATOR_PTT then
            return PTT_OP_VALUE
        end
        error("unexpected arg " .. tostring(arg))
    end,
}

function GetDevice(id)
    return DEVICE
end

local function debug_log(msg) end
"""
    constants = "\n".join(
        _extract_lua_constant(_PTT_ICS_LUA, name)
        for name in ("ARG_PILOT_PTT", "ARG_OPERATOR_PTT", "PTT_EPSILON")
    )
    lines = [constants, preamble]
    lines.extend(
        _extract_lua_function(path, name)
        for path, name in (
            (_CORE_LUA, "safe_call"),
            (_PTT_ICS_LUA, "push_ptt_state"),
        )
    )
    lines.append("local out = {}")
    for frame in frames:
        lines.append(f"local before = #sent_lines\n{frame}\npush_ptt_state(1.5)")
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


class TestPushPttStateDebounce:
    def test_first_frame_always_sends(self) -> None:
        (line,) = _run_ptt_frames(["PTT_VALUE = 0.0\nPTT_OP_VALUE = 0.0"])
        assert line == '{"t":1.500,"ptt":0.000,"ptt_op":0.000}'

    def test_neither_moved_sends_nothing(self) -> None:
        frame = "PTT_VALUE = 0.0\nPTT_OP_VALUE = 0.0"
        first, second = _run_ptt_frames([frame, frame])
        assert first is not None
        assert second is None

    def test_pilot_only_moved_still_sends(self) -> None:
        first = "PTT_VALUE = 0.0\nPTT_OP_VALUE = 0.0"
        second = "PTT_VALUE = 0.5\nPTT_OP_VALUE = 0.0"
        _, line = _run_ptt_frames([first, second])
        assert line == '{"t":1.500,"ptt":0.500,"ptt_op":0.000}'

    def test_operator_only_moved_still_sends(self) -> None:
        """The pilot's trigger never moved this frame; the operator's
        alone must still trigger a send -- Stage P-ICS's "treat them
        equally"."""
        first = "PTT_VALUE = 0.0\nPTT_OP_VALUE = 0.0"
        second = "PTT_VALUE = 0.0\nPTT_OP_VALUE = 0.5"
        _, line = _run_ptt_frames([first, second])
        assert line == '{"t":1.500,"ptt":0.000,"ptt_op":0.500}'

    def test_both_moving_on_the_same_frame_sends_once(self) -> None:
        first = "PTT_VALUE = 0.0\nPTT_OP_VALUE = 0.0"
        second = "PTT_VALUE = 1.0\nPTT_OP_VALUE = 0.5"
        _, line = _run_ptt_frames([first, second])
        assert line == '{"t":1.500,"ptt":1.000,"ptt_op":0.500}'

    def test_a_wobble_within_epsilon_does_not_resend(self) -> None:
        first = "PTT_VALUE = 0.500\nPTT_OP_VALUE = 0.000"
        second = "PTT_VALUE = 0.505\nPTT_OP_VALUE = 0.000"
        _, line = _run_ptt_frames([first, second])
        assert line is None
