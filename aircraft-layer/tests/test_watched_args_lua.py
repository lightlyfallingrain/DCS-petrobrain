"""`Export.lua`'s pure watched-args/read-args functions (`plans/
effector-sequences/plan.md` Stage 4) run against a real Lua interpreter,
not just parsed -- same `_extract_lua_function` technique as
`test_sight_servo_lua.py`/`test_exponent_float_fix.py`: slice the named
`local function ... end` out of the real, currently-deployed `Export.lua`
and execute it standalone, so this exercises the actual source rather
than a hand-copied duplicate that could drift from it. Skips cleanly
without a Lua interpreter on `PATH`.

L1 (`parse_arg_list`), L2 (`watched_args_changed`), L3
(`encode_watched_args_line`), L5 (`build_read_reply_line`'s pure core --
same shape as L3, so not duplicated as a separate test class), L6
(`admit_read`) from the plan's §S4.7 test list."""

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
    """Same slicing technique as `test_sight_servo_lua.py`'s own helper,
    **widened to also track `do`** (a bare `do...end` block, or the `do`
    that closes a `for`/`while` header) as a depth-increasing token --
    `parse_arg_list`/`encode_watched_args_line`/`build_read_reply_line`
    all contain a `for ... do ... end` loop, which the narrower
    `function`/`if`/`end`-only version used elsewhere in this test suite
    under-counts (it would treat the loop's own closing `end` as the
    function's, truncating mid-body). `elseif`/`\\bif\\b` cannot collide:
    a word-boundary `\\b` match on `if` never fires inside `elseif`."""
    text = _EXPORT_LUA.read_text(encoding="utf-8")
    start_match = re.search(rf"local function {name}\(", text)
    assert start_match is not None, f"{name} not found in Export.lua"
    token_re = re.compile(r"\b(function|if|do|end)\b")
    depth = 1
    for token_match in token_re.finditer(text, start_match.end()):
        if token_match.group(1) == "end":
            depth -= 1
            if depth == 0:
                return text[start_match.start() : token_match.end()]
        else:
            depth += 1
    raise AssertionError(f"unbalanced function body while extracting {name}")


#: `parse_arg_list`/`admit_read` close over module-level `local` constants
#: declared *outside* their own function body (`MAX_WATCHED_ARGS`,
#: `MAX_WATCHED_ARG_NUMBER`, `MAX_READS_PER_FRAME`) -- `_extract_lua_
#: function` only slices the named function itself, so a standalone
#: script must declare the same names (same values as `Export.lua`'s own,
#: so a drift there would not be caught by this constant, only by
#: `tests/test_export_lua_constants_parity.py`'s own byte-for-byte grep).
_MODULE_CONSTANTS_PREAMBLE = (
    "local MAX_WATCHED_ARGS = 64\n"
    "local MAX_WATCHED_ARG_NUMBER = 4095\n"
    "local MAX_READS_PER_FRAME = 4\n"
)


def _run_lua_lines(func_names: list[str], body: str) -> list[str]:
    """Extracts each of `func_names` from `Export.lua`, defines them
    (preceded by `_MODULE_CONSTANTS_PREAMBLE`, since two of them close
    over module-level constants declared outside their own body) alongside
    `body` (arbitrary Lua statements that `print` their own results, one
    per line), and returns stdout split into lines. Skips cleanly without
    a Lua interpreter on `PATH`."""
    exe = _lua_executable()
    if exe is None:
        pytest.skip(f"no Lua interpreter on PATH (tried: {', '.join(_EXEC_TOOLS)})")

    lines = [_MODULE_CONSTANTS_PREAMBLE]
    lines.extend(_extract_lua_function(name) for name in func_names)
    lines.append(body)
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
    return result.stdout.splitlines()


class TestParseArgList:
    def test_valid_list_sorted_and_deduped(self) -> None:
        out = _run_lua_lines(
            ["parse_arg_list"],
            "local a = parse_arg_list('{\"args\":[773, 3, 773, 1]}')\n"
            'print(table.concat(a, ","))',
        )
        assert out == ["1,3,773"]

    def test_empty_list_is_empty_set(self) -> None:
        out = _run_lua_lines(
            ["parse_arg_list"],
            "local a = parse_arg_list('{\"args\":[]}')\nprint(#a)",
        )
        assert out == ["0"]

    def test_64_accepted_65_rejected(self) -> None:
        sixty_four = ",".join(str(n) for n in range(64))
        sixty_five = ",".join(str(n) for n in range(65))
        out = _run_lua_lines(
            ["parse_arg_list"],
            f"local a = parse_arg_list('{{\"args\":[{sixty_four}]}}')\n"
            f"local b = parse_arg_list('{{\"args\":[{sixty_five}]}}')\n"
            "print(a ~= nil)\nprint(b == nil)",
        )
        assert out == ["true", "true"]

    @pytest.mark.parametrize(
        "args_text",
        ["4096", "-1", "1.5", "1e3", "12345", "1,,2"],
    )
    def test_bad_token_rejects_whole_op(self, args_text: str) -> None:
        out = _run_lua_lines(
            ["parse_arg_list"],
            f"local a = parse_arg_list('{{\"args\":[{args_text}]}}')\nprint(a == nil)",
        )
        assert out == ["true"]

    def test_mutation_truncate_to_64_instead_of_reject(self) -> None:
        """Written to fail if `parse_arg_list` silently truncated to 64
        instead of rejecting the whole op -- the 65-arg case above would
        then pass a 64-length table rather than `nil`."""
        sixty_five = ",".join(str(n) for n in range(65))
        out = _run_lua_lines(
            ["parse_arg_list"],
            f"local a = parse_arg_list('{{\"args\":[{sixty_five}]}}')\nprint(a == nil)",
        )
        assert out == ["true"]


class TestExtractJsonIdField:
    def test_valid_id(self) -> None:
        out = _run_lua_lines(
            ["extract_json_id_field"],
            'print(extract_json_id_field(\'{"watch_id":"abc_123"}\', "watch_id"))',
        )
        assert out == ["abc_123"]

    def test_missing_field_is_nil(self) -> None:
        out = _run_lua_lines(
            ["extract_json_id_field"],
            "print(extract_json_id_field('{}', \"watch_id\") == nil)",
        )
        assert out == ["true"]

    def test_17_char_id_rejected(self) -> None:
        too_long = "a" * 17
        out = _run_lua_lines(
            ["extract_json_id_field"],
            f'print(extract_json_id_field(\'{{"watch_id":"{too_long}"}}\', '
            '"watch_id") == nil)',
        )
        assert out == ["true"]


class TestWatchedArgsChanged:
    def test_small_move_not_a_change(self) -> None:
        out = _run_lua_lines(
            ["watched_args_changed"],
            "local last = {[886] = 1.000}\n"
            "local values = {[886] = 1.005}\n"
            "print(watched_args_changed(last, values, 0.01))",
        )
        assert out == ["false"]

    def test_larger_move_is_a_change(self) -> None:
        out = _run_lua_lines(
            ["watched_args_changed"],
            "local last = {[886] = 1.000}\n"
            "local values = {[886] = 1.02}\n"
            "print(watched_args_changed(last, values, 0.01))",
        )
        assert out == ["true"]

    def test_added_key_is_a_change(self) -> None:
        out = _run_lua_lines(
            ["watched_args_changed"],
            "local last = {}\n"
            "local values = {[886] = 1.0}\n"
            "print(watched_args_changed(last, values, 0.01))",
        )
        assert out == ["true"]

    def test_removed_key_is_a_change(self) -> None:
        out = _run_lua_lines(
            ["watched_args_changed"],
            "local last = {[886] = 1.0}\n"
            "local values = {}\n"
            "print(watched_args_changed(last, values, 0.01))",
        )
        assert out == ["true"]

    def test_mutation_compare_values_only_for_keys_present_in_both(self) -> None:
        """Written to fail under the named mutation: comparing only keys
        present in both tables would miss the removed-key case above."""
        out = _run_lua_lines(
            ["watched_args_changed"],
            "local last = {[886] = 1.0, [898] = 0.0}\n"
            "local values = {[886] = 1.0}\n"
            "print(watched_args_changed(last, values, 0.01))",
        )
        assert out == ["true"]


class TestEncodeWatchedArgsLine:
    def test_json_parseable_nil_omitted_keys_strings(self) -> None:
        out = _run_lua_lines(
            ["encode_watched_args_line"],
            "local args = {886, 898}\n"
            "local values = {[886] = 1.0}\n"
            'io.write(encode_watched_args_line(12.5, "abc123", args, values))',
        )
        line = out[0]
        parsed = json.loads(line)
        assert parsed["watch_id"] == "abc123"
        assert parsed["watched"] == {"886": 1.0}
        assert set(parsed["watched"].keys()) == {"886"}

    def test_mutation_emit_nil_as_zero(self) -> None:
        """Written to fail under the named mutation: emitting a failed
        read as 0.000 rather than omitting it would make 898 present."""
        out = _run_lua_lines(
            ["encode_watched_args_line"],
            "local args = {886, 898}\n"
            "local values = {[886] = 1.0}\n"
            'io.write(encode_watched_args_line(12.5, "abc123", args, values))',
        )
        parsed = json.loads(out[0])
        assert "898" not in parsed["watched"]


class TestBuildReadReplyLine:
    def test_json_parseable_uses_read_id_and_values_keys(self) -> None:
        out = _run_lua_lines(
            ["build_read_reply_line"],
            "local args = {773, 761}\n"
            "local values = {[773] = 1.0}\n"
            'io.write(build_read_reply_line(5.0, "readreq01", args, values))',
        )
        parsed = json.loads(out[0])
        assert parsed["read_id"] == "readreq01"
        assert parsed["values"] == {"773": 1.0}
        assert "761" not in parsed["values"]


class TestAdmitRead:
    def test_under_cap_admitted(self) -> None:
        out = _run_lua_lines(
            ["admit_read"], "print(admit_read(0))\nprint(admit_read(3))"
        )
        assert out == ["true", "true"]

    def test_at_cap_not_admitted(self) -> None:
        out = _run_lua_lines(["admit_read"], "print(admit_read(4))")
        assert out == ["false"]

    def test_mutation_no_cap(self) -> None:
        """Written to fail under the named mutation: a version with no
        cap would admit an arbitrarily large count."""
        out = _run_lua_lines(["admit_read"], "print(admit_read(1000))")
        assert out == ["false"]
