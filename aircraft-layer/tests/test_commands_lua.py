"""AC-B12 review fix (`plans/ac-b12-export-modules/review.md`, "Required
Fixes"): `commands.lua`'s dispatch table used to index
`petrovich`/`effectors`/`sight` directly at module-load time, so one of
those three modules failing to load raised a Lua error inside
`commands.lua`'s own top level -- which `load_module`'s `pcall` then
caught as *this* module failing, taking every op down with it, including
the ops owned by modules that loaded fine. The fix guards each table
entry on its owning module being non-`nil`, the same posture the
loader's own `call_if` already uses everywhere else.

Same `_extract_lua_function` technique as `test_ai_pilot_wheel_lua.py`'s
own copy (duplicated across test modules, this project's own
convention): slice real source out of the real, currently-deployed
files and run it standalone. The handlers-table construction itself is
not a function, so it is sliced by its own literal start/end markers
(`_extract_handlers_block` below) rather than the function/if/do/end
depth counter -- specific to this one file's shape, same ad hoc
precedent as `test_watched_args_lua.py`'s `_MODULE_CONSTANTS_PREAMBLE`.
Skips cleanly without a Lua interpreter on `PATH`."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

_PETROBRAIN_DIR = Path(__file__).resolve().parent.parent / "dcs-export" / "Petrobrain"
_CORE_LUA = _PETROBRAIN_DIR / "core.lua"
_COMMANDS_LUA = _PETROBRAIN_DIR / "commands.lua"

_EXEC_TOOLS: tuple[str, ...] = ("luajit", "lua5.5", "lua5.1", "lua")


def _lua_executable() -> str | None:
    for tool in _EXEC_TOOLS:
        found = shutil.which(tool)
        if found is not None:
            return found
    return None


def _extract_lua_function(path: Path, name: str) -> str:
    """Slice `local function {name}(...) ... end` out of `path` --
    `function`/`if`/`for`/`while`/`end` as block openers/closer, with
    `--` line comments skipped while counting (same refinement as
    `test_ai_pilot_wheel_lua.py`'s own copy of this helper)."""
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


def _extract_handlers_block() -> str:
    """Slices `commands.lua`'s `local handlers = {}` construction (the
    three `if <module> ~= nil then ... end` guards this fix adds) out of
    the real file, by its own literal start/end markers -- it is a
    sequence of independent `if` blocks, not one function, so the
    function/if/do/end depth counter above does not apply to it."""
    text = _COMMANDS_LUA.read_text(encoding="utf-8")
    start = text.index("local handlers = {}")
    end = text.index("-- Drains every command datagram")
    assert start != -1 and end != -1
    return text[start:end]


def _run_commands_lua(
    *,
    petrovich_present: bool,
    effectors_present: bool,
    sight_present: bool,
    ops: list[str],
) -> list[str]:
    """Builds the real `handlers` table and the real `poll_command_socket`
    against a fake `command_socket` that yields one datagram per entry in
    `ops`, with `petrovich`/`effectors`/`sight` either a fake handler
    table (recording its own calls into `dispatch_log`) or left as `nil`
    globals -- exactly the shape the loader's `load_module` leaves a
    failed-to-load module in. Returns `dispatch_log` plus every
    `debug_log` message, one per printed line."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    def fake_module(op_names: list[str]) -> str:
        entries = "\n".join(
            f'    {op} = function(data, t) table.insert(dispatch_log, "{op}") end,'
            for op in op_names
        )
        return "{\n" + entries + "\n}"

    preamble_parts = ["local dispatch_log = {}", "local debug_log_messages = {}"]
    preamble_parts.append(
        "local function debug_log(msg) table.insert(debug_log_messages, msg) end"
    )
    if petrovich_present:
        preamble_parts.append(
            "petrovich = " + fake_module(["handle_petrovich_search_command"])
        )
    if effectors_present:
        # Built inline, with op names rather than function names as the
        # `dispatch_log` entries, and `admit_read` on the same table as
        # the real file's own `effectors.admit_read(...)` call expects.
        preamble_parts.append(
            "effectors = {\n"
            "    handle_cockpit_switch_command = function(data, t) "
            'table.insert(dispatch_log, "cockpit_switch") end,\n'
            "    handle_watch_args_command = function(data, t) "
            'table.insert(dispatch_log, "watch_args") end,\n'
            "    handle_read_args_command = function(data, t) "
            'table.insert(dispatch_log, "read_args") end,\n'
            "    admit_read = function(n) return true end,\n"
            "}"
        )
    if sight_present:
        preamble_parts.append("sight = " + fake_module(["handle_sight_target_command"]))

    queue_literal = ", ".join(f"[[{op}]]" for op in ops)
    preamble_parts.append(
        "local _queue = {" + queue_literal + "}\n"
        "local _idx = 0\n"
        "command_socket = {\n"
        "    receivefrom = function(self)\n"
        "        _idx = _idx + 1\n"
        "        return _queue[_idx]\n"
        "    end,\n"
        "}"
    )

    lines = ["\n".join(preamble_parts)]
    lines.append(_extract_lua_function(_CORE_LUA, "extract_json_string_field"))
    lines.append(_extract_handlers_block())
    lines.append(_extract_lua_function(_COMMANDS_LUA, "poll_command_socket"))
    lines.append("poll_command_socket(0.0)")
    lines.append('io.write(table.concat(dispatch_log, ","))')
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

    assert result.returncode == 0, (
        f"Lua harness failed (exe={exe}): {result.stderr}\nscript:\n{script}"
    )
    return result.stdout.split(",") if result.stdout else []


class TestMissingHandlerOwningModule:
    """The required fix itself: `effectors` absent (simulating a failed
    module load) must not take `petrovich`/`sight`'s own ops down with
    it, and must not crash `poll_command_socket` at all."""

    def test_other_ops_still_dispatch_when_effectors_missing(self) -> None:
        dispatched = _run_commands_lua(
            petrovich_present=True,
            effectors_present=False,
            sight_present=True,
            ops=[
                '{"op":"petrovich_search","mode":"forward"}',
                '{"op":"cockpit_switch","device":55,"cmd":1,"value":1}',
                '{"op":"sight_target","goal_az_deg":1.0}',
                '{"op":"watch_args","args":[886]}',
                '{"op":"read_args","args":[886]}',
            ],
        )
        # The two modules that loaded fine still dispatch...
        assert "handle_petrovich_search_command" in dispatched
        assert "handle_sight_target_command" in dispatched
        # ...and every op owned by the missing module -- including
        # `read_args`, whose dispatch path also calls `effectors.
        # admit_read` -- is silently ignored rather than crashing the
        # whole poll (which a prior run with a non-zero Lua exit code
        # would already have failed on, per `_run_commands_lua`'s own
        # `returncode == 0` assertion).
        assert "cockpit_switch" not in dispatched
        assert "watch_args" not in dispatched
        assert "read_args" not in dispatched

    def test_mutation_unguarded_table_build_crashes_instead(self) -> None:
        """Counterfactual: indexing the missing module directly (the
        pre-fix shape) raises a Lua error building the table, which
        would make this whole harness exit non-zero -- confirming the
        test can actually tell a guarded build apart from an unguarded
        one, not just that nothing happened to fail."""
        exe = _lua_executable()
        if exe is None:
            pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")
        script = (
            "local handlers = {\n"
            "    cockpit_switch = effectors.handle_cockpit_switch_command,\n"
            "}\n"
        )
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
        assert result.returncode != 0
        assert "nil" in result.stderr


class TestAllModulesPresent:
    """Regression check on the modified `elseif op == "read_args"` guard
    line itself: with `effectors` present, dispatch through the real
    `commands.lua` source is unchanged from before this fix."""

    def test_every_op_dispatches_when_every_module_present(self) -> None:
        dispatched = _run_commands_lua(
            petrovich_present=True,
            effectors_present=True,
            sight_present=True,
            ops=[
                '{"op":"petrovich_search","mode":"forward"}',
                '{"op":"cockpit_switch","device":55,"cmd":1,"value":1}',
                '{"op":"sight_target","goal_az_deg":1.0}',
                '{"op":"watch_args","args":[886]}',
                '{"op":"read_args","args":[886]}',
            ],
        )
        assert dispatched == [
            "handle_petrovich_search_command",
            "cockpit_switch",
            "handle_sight_target_command",
            "watch_args",
            "read_args",
        ]
