"""The one module in this codebase that imports `lupa` (`plans/
speech-rules/plan.md` Stage 1b item 2/3). Everything this module exposes
to the rest of `rules/` is a plain Python type (`str`, `int`, `bool`,
`None`, or a thin wrapper) -- no `lupa` type ever crosses this module's
boundary, so a caller never needs its own `# type: ignore[import-untyped]`.

**Sandbox isolation is by omission, not by constructor flag or runtime
mutation** -- `body-layer/research/2026-11-17-lupa-sandbox.md` found
`register_eval=False`/`register_builtins=False` do not strip Lua's own
stdlib (`io`/`os`/`debug`/`require`/`load`/`string.dump`/... are all still
present in a freshly constructed runtime's real `globals()`). Every rule
file therefore runs against a **fresh table** built by `base_env()`,
copying in only an explicit allowlist -- nothing else is reachable because
nothing else was ever assigned into that table, not because anything was
deleted from a shared one. `string`/`table` are each a **fresh copy** of
their safe members, never the shared library table reference pruned in
place (the research note's table-aliasing gotcha: `env["string"] =
g["string"]` then pruning `env["string"]["dump"]` mutates the one shared
table every runtime user sees).

The instruction-count cap (`run_with_budget`) is this project's named stop
condition for a runaway rule (R1): a Lua `debug.sethook` count hook,
armed from this **trusted** module before any restricted `_ENV` is built
(the hook attaches to the Lua state itself, not to any environment table,
so it still fires for sandboxed chunks that have no `debug` global of
their own -- confirmed in the research spike). `debug.sethook` rejects a
bare Python callable (`LuaError: function expected, got POBJECT` -- Lua's
C implementation requires a genuine `lua_isfunction()`), so the hook is a
one-line Lua shim wrapping the Python callback, not the callback itself."""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from lupa import lua54  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

#: Base safe allowlist every rule file's `_ENV` gets, regardless of which
#: action namespaces/API functions a caller layers on top (`engine.py`
#: does that). Deliberately excludes `io`/`os`/`debug`/`require`/
#: `package`/`load`/`loadfile`/`dofile`/`loadstring`/`collectgarbage`/
#: `coroutine` -- D7/Stage 1b item 3's denylist -- by never copying them
#: in, not by deleting them from anywhere.
_SAFE_GLOBAL_NAMES: tuple[str, ...] = (
    "print",
    "pairs",
    "ipairs",
    "tostring",
    "tonumber",
    "type",
    "select",
)

#: `string` library members with no filesystem/bytecode reach -- excludes
#: `dump` (bytecode extraction) deliberately. `table`/`math` carry no
#: member of that shape, so they are shared by direct reference rather
#: than copied (nothing on either library can read/write outside the Lua
#: state itself).
_SAFE_STRING_MEMBERS: tuple[str, ...] = (
    "byte",
    "char",
    "find",
    "format",
    "gmatch",
    "gsub",
    "len",
    "lower",
    "match",
    "rep",
    "reverse",
    "sub",
    "upper",
)


class RuleCompileError(Exception):
    """A rule file failed to `load()` -- a Lua syntax error, almost always.
    `message` is the raw `LuaError` text, already carrying `[string
    "<chunk_name>"]:<line>:` as its leading substring (the chunk name
    passed to `load()` is exactly what reappears there -- confirmed in the
    research spike; `LuaError` has no separate `.filename`/`.lineno`
    attributes to read instead)."""


class RuleRuntimeError(Exception):
    """A loaded rule file's top-level code, or a rule handler, raised a
    Lua error while running (not while compiling). Same message shape as
    `RuleCompileError`."""


class RuleBudgetExceeded(Exception):
    """The instruction-count cap (`run_with_budget`) fired -- a loop (or a
    chain of handler calls) that did not finish within its own budget.
    Distinct from `RuleRuntimeError` so a caller can log/report it as a
    runaway rule specifically, not an ordinary Lua error."""


class _InstructionBudgetExceeded(RuntimeError):
    """Raised from inside the `debug.sethook` callback, on the Lua call
    stack -- caught and re-raised as `RuleBudgetExceeded` once control is
    back in Python, so nothing outside this module ever sees a bare
    `RuntimeError` from a budget trip and mistakes it for an ordinary bug."""


def _deny_all_attributes(obj: object, attr_name: str, is_setting: bool) -> None:
    """`attribute_filter` -- denies every Python-object attribute access
    from Lua. Second line of defence only: it governs genuine attribute
    (`__getattr__`/`__setattr__`) access on a Python object proxy, **not**
    the separate item-access proxying lupa gives Python mappings (a raw
    `dict` returned to Lua is still dotted-indexable despite this filter,
    confirmed empirically) -- so the real guarantee is `engine.py`/
    `actions.py` never returning anything to Lua except primitives and
    genuine Lua tables built via `RuleSandbox.table_from`, never a raw
    Python object. This filter catches the case where that discipline is
    broken by accident (a stray Python instance, not a `dict`)."""
    raise AttributeError(f"access to {attr_name!r} denied by sandbox policy")


class RuleSandbox:
    """Owns the one `lupa.lua54.LuaRuntime` every rule file/dispatch runs
    against. A single shared runtime is safe across threads (lupa's own
    global per-runtime lock, verified in the research spike with 16,000
    concurrent calls and zero lost increments) -- R4's answer: the lock
    serializes correctness, the instruction cap bounds how long any one
    caller can hold it."""

    def __init__(self, max_memory: int = 64 * 1024 * 1024) -> None:
        self._rt = lua54.LuaRuntime(
            register_eval=False,
            register_builtins=False,
            unpack_returned_tuples=True,
            max_memory=max_memory,
            attribute_filter=_deny_all_attributes,
        )
        g = self._rt.globals()
        self._load = g["load"]  # captured before any restricted env exists
        self._debug_sethook = g["debug"]["sethook"]
        # A one-line Lua shim wrapping the Python hook callback -- `debug.
        # sethook` rejects a bare Python callable (research spike §3:
        # `LuaError: function expected, got POBJECT`, since lupa wraps a
        # Python callable as userdata-with-`__call`, not a genuine Lua
        # `function` value).
        self._wrap_hook = self._rt.eval(
            "function(py_fn) return function(...) return py_fn(...) end end"
        )
        self._safe_string = self._make_safe_string_table()

    def _make_safe_string_table(self) -> Any:
        g = self._rt.globals()
        src = g["string"]
        safe = self._rt.table()
        for key in _SAFE_STRING_MEMBERS:
            safe[key] = src[key]
        return safe

    def base_env(self) -> Any:
        """A fresh, restricted `_ENV` table -- the allowlist above plus a
        shared (not per-call-rebuilt) safe `string` copy, `table`/`math`
        by direct reference. `engine.py` layers the rule API (`when`/
        `say`/`unable`/`digits`) and the action-namespace tables on top of
        whatever this returns, once per rule *file* (so two files never
        see each other's globals -- the per-file isolation the research
        spike confirmed via `load(src, name, "t", env)`)."""
        g = self._rt.globals()
        env = self._rt.table()
        for name in _SAFE_GLOBAL_NAMES:
            env[name] = g[name]
        env["string"] = self._safe_string
        env["table"] = g["table"]
        env["math"] = g["math"]
        return env

    def table(self) -> Any:
        """A fresh, empty Lua table -- exposed so `engine.py` can build
        the `when`/action-namespace tables without importing `lupa`
        itself."""
        return self._rt.table()

    def table_from(self, data: Mapping[str, object]) -> Any:
        """A genuine Lua table built from a flat Python mapping (string
        keys, primitive values) -- the only way this codebase hands a
        structured value to Lua (module docstring: never a raw Python
        object)."""
        return self._rt.table_from(dict(data))

    def compile(self, source: str, chunk_name: str, env: Any) -> Any:
        """`load(source, chunk_name, "t", env)` -- `"t"` refuses a
        precompiled binary chunk outright (confirmed in the research
        spike), which matters here because `source` is read from a file
        on disk this process does not control the origin of once `BL-B95`
        widens past the user's own rules. Returns the loaded chunk
        function. Raises `RuleCompileError` on a syntax error."""
        result = self._load(source, chunk_name, "t", env)
        # `load()` returns a bare chunk function on success (one value) or
        # `(None, err)` on failure (lupa does not wrap a lone return value
        # in a tuple, so branch on arity -- same convention the research
        # spike's own probe used).
        if isinstance(result, tuple):
            _chunk, err = result
            raise RuleCompileError(str(err))
        return result

    @contextmanager
    def run_with_budget(self, instruction_budget: int) -> Iterator[None]:
        """Arms the instruction-count hook for the duration of the `with`
        block, then disarms it unconditionally. Any Lua call made inside
        the block (compiling+running a file's top-level code, or calling a
        rule handler) is bounded by `instruction_budget` VM instructions.

        Raises `RuleBudgetExceeded` if the budget is exceeded, or
        `RuleRuntimeError` for any other Lua error raised inside the
        block (a genuine bug in the rule file, not a runaway loop)."""
        remaining = {"n": instruction_budget}

        def _count_hook(*_args: object) -> None:
            remaining["n"] -= 1
            if remaining["n"] <= 0:
                raise _InstructionBudgetExceeded("instruction budget exceeded")

        lua_hook = self._wrap_hook(_count_hook)
        self._debug_sethook(lua_hook, "", 1000)
        try:
            yield
        except _InstructionBudgetExceeded as exc:
            raise RuleBudgetExceeded(str(exc)) from exc
        except lua54.LuaError as exc:
            raise RuleRuntimeError(str(exc)) from exc
        finally:
            self._debug_sethook(None)
