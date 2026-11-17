---
name: project_lupa_sandbox_quirks_bl17_stage0
description: lupa (Lua-in-Python) sandboxing gotchas found during BL-17 Stage 0/3b -- debug.sethook rejects bare Python callables, register_eval/register_builtins don't strip Lua stdlib, table assignment aliases not copies, LuaError has no structured file/line fields, no type stubs ship, any Python global exposed to Lua propagates a raw Python TypeError on a wrong-arity call unwrapped
metadata:
  type: project
---

BL-17 (`plans/speech-rules/plan.md`) Stage 0 spiked `lupa==2.8` for a sandboxed rule engine.
Full writeup with runnable probes: `body-layer/research/2026-11-17-lupa-sandbox.md`. Five quirks
worth knowing before touching `src/rules/sandbox.py` (Stage 1b) or any later lupa code in this
repo:

1. **`LuaRuntime(register_eval=False, register_builtins=False)` does not strip Lua's own
   stdlib.** These two flags only gate the `python.eval()`/`python.builtins.*` bridge table.
   `io`/`os`/`debug`/`require`/`package`/`load`/`string.dump`/… are all still present in a
   freshly constructed runtime's `globals()`. Sandbox isolation has to come from an allowlist
   `_ENV` table built fresh per file (via `load(src, name, "t", env)`) that simply never grants
   these names — not from these constructor flags, and not from mutating the runtime's real
   globals (other code sharing that runtime would see the mutation).
2. **`debug.sethook(python_callable, ...)` fails**: `LuaError: bad argument #1 to
   'debug.sethook' (function expected, got POBJECT)`. Lua's C implementation requires
   `lua_isfunction()`; lupa wraps a Python callable as userdata-with-`__call`, which fails that
   check. Fix: wrap it in a one-line Lua shim first —
   `rt.eval("function(py_fn) return function(...) return py_fn(...) end end")(python_callable)`
   — and pass *that* to `sethook`. Once wrapped, a Python exception raised inside the hook
   propagates cleanly out of `rt.execute(...)`; this is the mechanism for an instruction-count
   abort (a count hook: `sethook(lua_hook, "", N)` fires every N VM instructions).
3. **Lua table assignment aliases, it does not copy.** `env["string"] = g["string"]` then
   `env["string"]["dump"] = None` mutates the single shared `string` library table for every
   runtime user, not just `env`. To prune a library table per sandbox environment, build a fresh
   table and copy only the safe members in; never prune a table reused elsewhere.
4. **`LuaError`'s file/line live only in the message string** (`[string "<name>"]:<line>: ...`),
   not as separate attributes — `getattr(exc, "lua_error", None)` is `None`, there is no
   `.filename`/`.lineno`. Anything that wants to log or match file/line needs the chunk `name`
   passed to `load(...)` (which is exactly what appears inside `[string "..."]`) and either a
   string match or just logging the whole message.
5. **No type stubs ship with lupa** (no `py.typed`, no `.pyi`). `mypy --strict` reports
   `import-untyped` and suggests the third-party `types-lupa` package — which is a second,
   unapproved dependency; the plan's own fallback (confine `# type: ignore[import-untyped]` to
   the one module that imports lupa) is what Stage 0 used.

6. **Any Python function exposed as a Lua global propagates a raw Python exception through the
   call boundary unwrapped — not just the `debug.sethook` callback from point 2.** Confirmed on
   Stage 3b: `engine.py`'s `when.speech` registration function was widened from 3 named Python
   parameters to 4 (`id, pattern, category, handler`); a stale Lua call site still using the old
   3-argument shape raised a bare Python `TypeError: speech() missing 1 required positional
   argument`, and that `TypeError` propagated straight out of `sandbox.run_with_budget`'s own
   `except lua54.LuaError` clause (it only catches genuine Lua-raised errors, not a Python-side
   argument-count mismatch) and out of `loader.load_rules`'s `except (RuleCompileError,
   RuleRuntimeError, RuleBudgetExceeded)` too — discarding the whole file with an uncaught
   exception instead of D6's intended "disable just the one bad rule." Fix: any Python function
   registered as a Lua global that validates its own call shape (arity, types) should take
   `*args`/`**kwargs` and check explicitly, converting a bad call into the project's own error
   type (here, appending a `RuleLoadError` and returning) rather than trusting Python's own
   `TypeError` to degrade gracefully through a Lua call.

Also confirmed empirically (not just from docs): a single shared `LuaRuntime` safely serializes
concurrent calls from multiple threads (lupa's own global per-runtime lock) — verified with a
race-prone non-atomic increment across 8 threads × 2000 calls, zero lost increments. `load(src,
name, "t", env)` refuses precompiled bytecode cleanly (`attempt to load a binary chunk (mode is
't')`); extracting bytecode via `string.dump` to test that needs a *separate*
`LuaRuntime(encoding=None)` (its output isn't valid UTF-8) and bytes-keyed globals lookups
(`g[b"load"]`, not `g["load"]`) once `encoding=None` is set.
