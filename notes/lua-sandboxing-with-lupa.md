# Lua Sandboxing with lupa

- **`register_eval=False`/`register_builtins=False` gate only the `python.eval()`/
  `python.builtins.*` bridge, not Lua's own standard library.** A freshly constructed
  `lupa.lua54.LuaRuntime(register_eval=False, register_builtins=False)` still has `io`/`os`/
  `debug`/`require`/`load`/`string.dump`/… present in its globals — these constructor flags do
  not strip them. A real sandbox must isolate by building an allowlist `_ENV` table per file and
  **never granting** the dangerous names into it, not by relying on the constructor flags or by
  mutating the runtime's real `globals()` in place (`body-layer/src/rules/sandbox.py`,
  `research/2026-11-17-lupa-sandbox.md`, `[[BL-17]]`).

- **A bare Python callable cannot be passed to `debug.sethook`** — `LuaError: bad argument #1
  to 'debug.sethook' (function expected, got POBJECT)`, because lupa wraps a Python callable as
  userdata-with-`__call`, and Lua's C implementation of `sethook` requires `lua_isfunction()`,
  which that is not. Fix: wrap it in a one-line Lua shim first —
  `function(py_fn) return function(...) return py_fn(...) end end` — and pass the *shim's*
  return value to `sethook`. Needed for any instruction-count/time-budget abort mechanism built
  on `debug.sethook`, not just this project's.

- **Lua table "copy" (`env["x"] = g["x"]`) copies a reference, not contents.** Pruning a member
  off the copy (e.g. deleting `string.dump` to narrow a sandboxed `string` library) mutates the
  single shared table for every runtime user, trusted code included. Build a fresh table with
  only the safe members copied in; never prune a shared library table in place.

- **`debug.sethook(hook, mask, count)`'s `count` fires every `count` *VM instructions*, not
  every hook call** — an instruction-count budget armed with `count=1000` and decremented by 1
  per firing actually bounds ~1000× the named budget in real VM instructions. Easy to misread the
  constant as "the real instruction cap" when it is really "the cap divided by the hook-firing
  interval" (`[[BL-B125]]`, filed as a non-blocking follow-up once this was found in review).

- **`LuaError`'s file/line live in the message string, not a structured attribute** — there is no
  `.filename`/`.lineno`; the `[string "<name>"]:<line>:` prefix has to be carried or string-matched
  by whatever surfaces the error, not read off the exception object.

- **A bare Python exception raised inside a Python callable invoked *from* Lua propagates to the
  caller as itself, not wrapped as `lupa.lua54.LuaError`** — confirmed empirically against the real
  package, not assumed from documentation. Every `except lua54.LuaError` / `except
  (SomeDomainError, ...)` written to catch "a Lua-side failure" will not catch a raw
  `ValueError`/`TypeError`/`OverflowError` that an *unguarded* Python-side conversion (e.g. `int()`
  on a value Lua handed over) raises — the guard has to sit at the point of conversion, inside the
  Python callable itself, not at the point where Lua errors are caught. This bit a real security
  finding in `[[BL-17]]` (`nan`/`inf` reaching `int()`), and the two call sites were not
  architecturally equivalent: one had an existing "caller checks and handles rejection" contract,
  the other did not, so the right failure mode (degrade vs. raise-and-let-the-existing-error-path-
  catch-it) differed per site even though the unguarded-conversion shape was identical.

- **No type stubs ship with lupa** (no `py.typed`, no `.pyi` files) — `mypy --strict` reports
  `import-untyped`. Confine the resulting `# type: ignore[import-untyped]` to the one module that
  imports lupa directly, and expose a typed wrapper to everything else, rather than letting the
  suppression spread.

- **`LuaRuntime` holds one global per-runtime lock for the entire top-level call, including any
  Python callback invoked from inside it** — measured empirically (8 threads, 16,000 concurrent
  calls, zero lost increments, consistent with full serialization), not assumed. If thread A is
  paused mid-dispatch inside a Python action-wrapper callback (even a plain, pure-Python
  `threading.Event.wait()`), thread B's own call into the *same* `RuleSandbox`/`LuaRuntime`
  blocks until A's whole dispatch returns — two dispatches sharing one sandbox never actually
  overlap inside Lua execution, only in the narrow plain-Python window between one dispatch's
  `rule_runner()` return and whatever runs right after it. A test that needs genuine,
  deterministic two-thread overlap through the rule-dispatch path must give each thread its own
  `RuleSandbox`/`LuaRuntime` (each has its own lock) and its own loaded `RuleSet`, with both
  `ActionContext`s pointed at the same shared state under test — a single `rule_runner` closure
  then dispatches to whichever sandbox matches the incoming rule id (`[[BL-17]]` Stage 3d
  re-review Required Fix 4, `test_rules_effector_action.py::
  test_rollback_leaves_a_concurrent_dispatchs_own_queued_write_alone`).
