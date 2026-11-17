"""`rules.sandbox.RuleSandbox` -- the sandbox must hold (`plans/
speech-rules/plan.md` Stage 1b item 3): no `io`/`os`/`require`/`debug`/
`load`/`string.dump`, a per-file environment, and an instruction-count
cap that actually aborts a runaway loop and a memory cap that actually
fires."""

from __future__ import annotations

import pytest

from rules.sandbox import (
    RuleBudgetExceeded,
    RuleCompileError,
    RuleRuntimeError,
    RuleSandbox,
)


def test_base_env_denies_the_whole_denylist() -> None:
    sandbox = RuleSandbox()
    env = sandbox.base_env()
    chunk = sandbox.compile(
        "return io, os, require, package, debug, load, loadfile, dofile, "
        "collectgarbage, python, string.dump",
        "probe.lua",
        env,
    )
    with sandbox.run_with_budget(100_000):
        result = chunk()
    assert result == (None,) * 11


def test_two_files_do_not_share_globals() -> None:
    sandbox = RuleSandbox()
    env_a = sandbox.base_env()
    env_b = sandbox.base_env()
    chunk_a = sandbox.compile("x = 111", "file_a.lua", env_a)
    with sandbox.run_with_budget(10_000):
        chunk_a()
    chunk_b = sandbox.compile("return x", "file_b.lua", env_b)
    with sandbox.run_with_budget(10_000):
        assert chunk_b() is None


def test_pruning_the_string_table_in_one_env_does_not_leak_to_another() -> None:
    """The research spike's own table-aliasing gotcha, pinned as a
    regression test: `base_env()`'s `string` copy must never be the
    shared library table itself."""
    sandbox = RuleSandbox()
    env_a = sandbox.base_env()
    env_b = sandbox.base_env()
    assert env_a["string"] is not env_b["string"]


def test_runaway_loop_is_aborted_by_the_instruction_budget() -> None:
    sandbox = RuleSandbox()
    env = sandbox.base_env()
    chunk = sandbox.compile(
        "local i = 0 while true do i = i + 1 end", "runaway.lua", env
    )
    with pytest.raises(RuleBudgetExceeded), sandbox.run_with_budget(5_000):
        chunk()


def test_a_finite_loop_within_budget_completes() -> None:
    sandbox = RuleSandbox()
    env = sandbox.base_env()
    chunk = sandbox.compile(
        "local s = 0 for i = 1, 100 do s = s + i end return s", "finite.lua", env
    )
    with sandbox.run_with_budget(1_000_000):
        assert chunk() == 5050


def test_memory_cap_is_enforced() -> None:
    sandbox = RuleSandbox(max_memory=1024 * 1024)
    env = sandbox.base_env()
    chunk = sandbox.compile(
        'local t = {} for i = 1, 2000000 do t[i] = string.rep("x", 100) end return #t',
        "hog.lua",
        env,
    )
    with pytest.raises(RuleRuntimeError), sandbox.run_with_budget(50_000_000):
        chunk()


def test_syntax_error_raises_rule_compile_error() -> None:
    sandbox = RuleSandbox()
    env = sandbox.base_env()
    with pytest.raises(RuleCompileError):
        sandbox.compile("this is not lua (((", "bad.lua", env)


def test_table_from_builds_a_genuine_lua_table() -> None:
    sandbox = RuleSandbox()
    env = sandbox.base_env()
    env["probe"] = sandbox.table_from({"ok": True, "reason": None})
    chunk = sandbox.compile("return probe.ok, probe.reason", "probe2.lua", env)
    with sandbox.run_with_budget(10_000):
        assert chunk() == (True, None)
