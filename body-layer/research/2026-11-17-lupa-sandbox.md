# 2026-11-17 — lupa sandbox spike (BL-17 Stage 0)

Verifies the seven bullets `plans/speech-rules/plan.md` Stage 0 lists, before Stage 1b's engine
depends on any of them. Environment: `body-layer/.venv` built fresh for this spike with
`/opt/homebrew/bin/python3.14` (3.14.10, macOS arm64/`macosx-27.0-arm64`), `lupa==2.8` installed
from the published wheel. Every probe below was actually run against that interpreter; outputs
are pasted verbatim, not transcribed from memory.

## 1. Wheel availability for body-layer's Python version

```sh
$ .venv/bin/pip download lupa==2.8 --no-deps -d /tmp/lupa_check
Downloading lupa-2.8-cp314-cp314-macosx_11_0_arm64.whl (1.2 MB)
```

**A `cp314` macOS arm64 wheel exists for lupa 2.8.** No fallback to an older lupa version was
needed. `lupa.lua54.LuaRuntime().lua_version == (5, 4)` — the 5.4 build is what the rest of this
note (and the plan's Lua-side examples) exercise; `lupa.lua54` is also what ships the Lua version
the plan's grammar/engine design assumes.

**Verdict: available. Pin `lupa==2.8`.**

## 2. `LuaRuntime(register_eval=False, register_builtins=False, unpack_returned_tuples=True, max_memory=...)`

```python
rt = lua54.LuaRuntime(register_eval=False, register_builtins=False,
                       unpack_returned_tuples=True, max_memory=64 * 1024 * 1024)
```

Constructs without error. Probed behaviour of each flag:

- `unpack_returned_tuples=True`: a Python callable returning `(1, 2, 3)` unpacks into three Lua
  return values (`local a, b, c = py_multi()` gives `a=1, b=2, c=3`), confirmed by
  `rt.execute("local a, b, c = py_multi(); return a, b, c")` → `(1, 2, 3)`.
- `max_memory=64MiB`: a loop that keeps allocating (`string.rep("x", 100)` into a growing table)
  raised `lupa.lua54.LuaMemoryError` before completing — the cap is enforced, not advisory.
- **`register_eval=False` and `register_builtins=False` do *not* strip Lua's own standard
  library** (`io`, `os`, `debug`, `require`, `package`, `load`, `string`, `print`, … are all
  still present in a freshly constructed runtime's `globals()`). Per `LuaRuntime`'s own
  docstring: these two flags gate only `python.eval()` and `python.builtins.*` — the `python`
  bridge table Lua-side, not Lua's base libraries. A probe listing every name the plan's D7/Stage
  1b-item-3 denylist cares about (`io`, `os`, `require`, `package`, `debug`, `load`, `loadfile`,
  `dofile`, `loadstring`, `collectgarbage`, `python`, plus `string.dump`) found every one of them
  present=`True` except `loadstring` (absent in Lua 5.4; dropped in favour of `load`, so denying
  it defensively costs nothing and is still correct to keep in the sandbox's denylist). **The
  sandbox cannot rely on these constructor flags for isolation — it must build a restricted
  per-file `_ENV` table that never grants these names in the first place** (see §4).

**Verdict: all four options work as advertised, with the one caveat above (load-bearing for how
`sandbox.py` is written: the denylist is enforced by omission from a file's environment table,
not by mutating the runtime's real globals or trusting the constructor flags).**

## 3. Instruction-count abort (the plan's stop condition)

`debug.sethook(hook, mask, count)` with `mask=""` and a count fires the hook every `count` VM
instructions, independent of calls/lines/returns — this is the mechanism.

**Gotcha found, not in the plan:** `debug.sethook` rejects a bare Python callable passed
directly from Python:

```
lupa.lua54.LuaError: bad argument #1 to 'debug.sethook' (function expected, got POBJECT)
```

Lua's C implementation requires `lua_isfunction()` to be true; lupa wraps a Python callable as a
userdata-with-`__call`, which is not a genuine Lua `function` value, so the native debug library
rejects it. Fix: a one-line Lua shim — itself a real Lua function — that calls the Python
callable from inside Lua:

```python
make_hook = rt.eval("function(py_fn) return function(...) return py_fn(...) end end")
lua_hook = make_hook(count_hook)
g["debug"]["sethook"](lua_hook, "", 1000)
```

With that shim, a Python `RuntimeError`-derived exception raised inside the hook propagates
cleanly out of `rt.execute(...)` back to the calling Python frame — no VM corruption, no hang:

```
instruction budget enforced via debug.sethook: instruction budget exceeded
finite loop after clearing hook: 5050
loop within budget completed: 500500 remaining budget: 999998
```

(`while true do i = i + 1 end` — a genuine infinite loop — was aborted; clearing the hook let an
ordinary finite loop complete; re-arming with a fresh budget let a loop safely inside that budget
complete normally and left budget to spare.) `debug.sethook` is called from the **trusted**
top-level code, before a file's restricted `_ENV` is built — the hook attaches to the Lua state
itself, not to any environment table, so it fires for sandboxed chunks too even though their own
`_ENV` never grants them `debug` (confirmed: the count hook fired while `count_hook` was armed
from Python, with the executed Lua code having no `debug` global available to it at all, since
`debug` is consulted only by the Python-side arming call, not looked up inside the executed
chunk).

**Verdict: available, and it works. This is the plan's named stop condition — it is satisfied,
so Stage 1b may proceed.**

## 4. Per-file environments via `load(src, name, "t", env)`, and refusal of binary chunks

Captured the real `load` function from `globals()` **before** building any restricted
environment (the loader needs this one reference kept out of every file's own `_ENV`). Built two
separate environment tables, each copying in only an explicit safe-names allowlist
(`print`/`pairs`/`ipairs`/`tostring`/`tonumber`/`type`/`select`/`string`/`table`/`math`) — nothing
else is reachable because nothing else was ever assigned into the table, not because anything was
deleted from it.

```
file_a sandboxed-global checks (all should be True): (True, True, True, True, True, True, True, True, True, True)
file_b sees file_a's global x_a (should be None -- separate envs): None
env_a['x_a'] after running file_a (should be 111): 111
env_b['x_a'] (should be None): None
```

`file_a.lua` set a bare global `x_a = 111` and checked `io`/`os`/`debug`/`python`/`load`/
`require`/`collectgarbage`/`dofile`/`loadfile`/`string.dump` were all `nil` inside its own
`_ENV` — all ten came back `nil` (`True` for "is nil"). `file_b.lua`, loaded against a
**different** fresh env, could not see `file_a`'s `x_a` — confirming per-file isolation, not a
shared sandbox namespace.

**Gotcha found, not in the plan:** Lua table assignment copies a *reference*, not contents.
`env["string"] = g["string"]` followed by `env["string"]["dump"] = None` does not give that one
environment a pruned `string` table — it mutates the single shared `string` library table every
runtime user sees, including trusted code. To strip `string.dump` (or any library member) per
environment without this leak, the sandbox must build a **fresh copy** of any library table it
needs to prune (copy the specific safe members across into a new table), never prune the shared
table in place. `sandbox.py` must do this once per allowed library, not per file, if files share
one template env, or per file if they do not.

**Binary-chunk refusal (`load(..., "t", ...)`):**

```
bytecode length: 81 type: <class 'bytes'>
loading precompiled bytecode with mode='t' -> None err: attempt to load a binary chunk (mode is 't')
loading precompiled bytecode with mode='bt' -> chunk is None? False err: None
  and calling it gives: 42
```

A chunk compiled normally, dumped to Lua 5.4 bytecode via `string.dump`, and fed back through
`load(bytecode, name, "t", env)` is refused outright with `attempt to load a binary chunk (mode
is 't')`. The identical bytecode loads and runs fine under the default `"bt"` mode — proving the
refusal above is specifically `"t"`'s doing, not some unrelated failure. **One more gotcha**:
`string.dump`'s output is arbitrary bytes, not valid UTF-8, so a default `encoding="utf-8"`
runtime raises `UnicodeDecodeError` trying to hand it back to Python as `str`; extracting it at
all needs a second, throwaway `LuaRuntime(encoding=None)` — and with `encoding=None`, lupa also
stops auto-encoding Python `str` keys to Lua strings, so `g["load"]` silently returns `None` and
`g[b"load"]` is required instead. Noted here because it is exactly the kind of silent-`None`
footgun that would otherwise show up as a confusing bug in `sandbox.py`, not in this spike.

**Verdict: `load(src, name, "t", env)` gives true per-file isolation and refuses binary chunks,
both confirmed by running code, not by reading the manual.**

## 5. `LuaError` carries file and line

```
chunk = g["load"]("""
local function boom()
  error("something broke")
end
boom()
""", "rules/flight.lua", "t")
chunk()
# raises lupa.lua54.LuaError:
# [string "rules/flight.lua"]:3: something broke
# stack traceback:
# 	[string "rules/flight.lua"]:5: in main chunk
# 	[string "rules/flight.lua"]:3: in local 'boom'
# 	[C]: in function 'error'
```

A load-time syntax error does the same: `load("this is not lua(((", "bad.lua", "t")` returns
`(None, '[string "bad.lua"]:1: syntax error near \'is\'')`.

**The file name and line are embedded in `LuaError`'s message string (and its `.args[0]`), not
exposed as separate structured attributes** (`exc.lua_error`, `.filename`, `.lineno` do not
exist — probed directly, `getattr(exc, "lua_error", None)` is `None`). Whatever file/line
`sandbox.py`/`engine.py` surface in a `RuleLoadError` or the dispatch-time "Action file error."
log line will need a string match (`[string "<name>"]:<line>:`) or simply log/propagate the whole
message, not a structured field lookup. The chunk name passed to `load(...)` is exactly what
appears in `[string "..."]`, so passing the real relative file path there (as the plan's loader
already intends) is what makes the message useful without any further parsing.

**Verdict: yes, file and line are carried — as the leading substring of the message, not as
separate fields.**

## 6. Type stubs

```
$ find .venv/lib/python3.14/site-packages/lupa -maxdepth 1 -type f
lupa/__init__.py
lupa/lua51.cpython-314-darwin.so
lupa/lua52.cpython-314-darwin.so
lupa/lua53.cpython-314-darwin.so
lupa/lua54.cpython-314-darwin.so
lupa/lua55.cpython-314-darwin.so
lupa/version.py
$ find .venv/lib/python3.14/site-packages/lupa -iname "py.typed"
(nothing)
```

No `py.typed` marker and no `.pyi` files ship inside the `lupa` package itself (the Lua-version
modules are compiled `.so` extensions with no stub companions). Confirmed the practical
consequence directly:

```
$ .venv/bin/mypy --strict mypy_check.py   # `import lupa.lua54 as lua54; rt: lua54.LuaRuntime = lua54.LuaRuntime()`
error: Library stubs not installed for "lupa.lua54"  [import-untyped]
note: Hint: "python3 -m pip install types-lupa"
error: Library stubs not installed for "lupa"  [import-untyped]
```

mypy itself suggests `types-lupa` (a third-party stub package exists on PyPI, latest
`2.8.0.20260827`, matching this lupa version) — but that is a **second** new dependency the user
was not asked about, so this spike did not install it. Per the plan's own fallback ("without
them, confine `# type: ignore[import-untyped]` to `sandbox.py` and expose a typed wrapper"),
Stage 1b should take the `# type: ignore[import-untyped]` route, confined to the one module that
imports `lupa`, rather than silently adding `types-lupa` as an unapproved second dependency.
Whether `types-lupa` is worth asking for later is a Stage 1b question, not this spike's to
settle.

**Verdict: no stubs ship with lupa itself. Use `# type: ignore[import-untyped]` confined to
`sandbox.py`, per the plan's own fallback — do not add `types-lupa` without asking.**

## 7. Thread safety across the REPL thread and the poll thread (R4)

lupa's own packaged description states: *"Each `LuaRuntime` is protected by a global lock that
prevents concurrent access to it."* Verified empirically rather than trusting the claim: one
shared `LuaRuntime`, 8 threads, each calling a Lua closure that does a non-atomic
read-increment-write on a shared Lua table field 2000 times (16,000 calls total — a race would
lose increments if calls were not serialized):

```
expected=16000 actual=16000 elapsed=0.035s errors=0
RESULT: no lost increments -- consistent with calls being serialized by a lock
```

No lost increments and no exceptions across 16,000 concurrent calls. This is consistent with
lupa's documented per-runtime global lock actually serializing access — concurrent callers from
different threads block rather than race or corrupt state. **Implication for Stage 1b/R4**: one
shared `LuaRuntime` reachable from both the REPL thread and the poll thread (`handle_command` →
`run_rule`) is safe as far as "does not corrupt the Lua state" goes; it does **not** mean a
runaway rule on one thread cannot stall the other thread's dispatch while the lock is held —
that is what the instruction-count cap (§3) is for, and the two mechanisms are complementary, not
substitutes for each other.

**Verdict: safe. A single shared `LuaRuntime` serializes concurrent access correctly; the
instruction cap is still needed to bound how long any one caller can hold that lock.**

## Stop condition

The instruction-count cap (§3) works. **No stop was triggered.** Stage 1b may proceed on the
assumptions above.

## Dependency added

`lupa==2.8` added to `body-layer/pyproject.toml`'s `dependencies`, pinned to the exact version
probed here (a cp314 macOS arm64 wheel for this interpreter). `body-layer/CLAUDE.md`'s "Tech
stack" section (which currently says "Stdlib only for body-layer's own code") is left for Stage
1b to update, together with `src/rules/sandbox.py` — Stage 0's scope is the spike and the
dependency pin only, per the plan's own stage boundary ("No engine code — that is Stage 1b").

## Probe scripts

Every output above was produced by running the probe scripts below (kept here verbatim rather
than only described, so a later reader can re-run them against a newer lupa without re-deriving
the setup) against `body-layer/.venv/bin/python -I` (isolated mode, so nothing from the scripts'
own directory or site customizations leaked in).

### Probe: constructor options, register_builtins semantics

```python
import lupa.lua54 as lua54

rt = lua54.LuaRuntime(register_eval=False, register_builtins=False,
                       unpack_returned_tuples=True, max_memory=64 * 1024 * 1024)

def py_multi():
    return (1, 2, 3)

g = rt.globals()
g.py_multi = py_multi
print(rt.execute("local a, b, c = py_multi(); return a, b, c"))

try:
    rt.execute("""
        local t = {}
        for i = 1, 20000000 do t[i] = string.rep("x", 100) end
        return #t
    """)
except Exception as exc:
    print("memory cap enforced:", type(exc).__name__, exc)
```

### Probe: what a vanilla runtime grants by default

```python
import lupa.lua54 as lua54

rt = lua54.LuaRuntime(register_eval=False, register_builtins=False)
g = rt.globals()
for name in ["io", "os", "require", "package", "debug", "load", "loadfile", "dofile",
             "loadstring", "collectgarbage", "python", "print", "string", "table",
             "math", "_G", "coroutine"]:
    v = g[name]
    print(name, "present=", v is not None)
print("string.dump present:", g["string"]["dump"] is not None)
```

### Probe: instruction-count abort via `debug.sethook`

```python
import lupa.lua54 as lua54

class InstructionBudgetExceeded(Exception):
    pass

rt = lua54.LuaRuntime(register_eval=False, register_builtins=False)
g = rt.globals()
budget = {"remaining": 0}

def count_hook(lua_runtime, *args):
    budget["remaining"] -= 1
    if budget["remaining"] <= 0:
        raise InstructionBudgetExceeded("instruction budget exceeded")

# debug.sethook rejects a bare Python callable (LuaError: function expected, got POBJECT) --
# wrap it in a genuine Lua function first.
make_hook = rt.eval("function(py_fn) return function(...) return py_fn(...) end end")
lua_hook = make_hook(count_hook)
g["debug"]["sethook"](lua_hook, "", 1000)

budget["remaining"] = 5000
try:
    rt.execute("local i = 0 while true do i = i + 1 end")
except InstructionBudgetExceeded as exc:
    print("enforced:", exc)

g["debug"]["sethook"](None)
budget["remaining"] = 10**9
print(rt.execute("local s = 0 for i = 1, 100 do s = s + i end return s"))

budget["remaining"] = 10**6
g["debug"]["sethook"](lua_hook, "", 1000)
print(rt.execute("local s = 0 for i = 1, 1000 do s = s + i end return s"), budget["remaining"])
```

### Probe: per-file `_ENV` isolation and binary-chunk refusal

```python
import lupa.lua54 as lua54

rt = lua54.LuaRuntime(register_eval=False, register_builtins=False, unpack_returned_tuples=True)
g = rt.globals()
lua_load = g["load"]  # captured BEFORE any restricted env exists

safe_names = ["print", "pairs", "ipairs", "tostring", "tonumber", "type", "select", "string",
              "table", "math"]

def make_safe_string_table():
    # NOTE: env["string"] = g["string"] aliases the SAME table; pruning it in place would
    # mutate the shared library for everyone. Build a fresh table with only safe members.
    src_tbl = g["string"]
    safe = rt.table()
    for key in ("byte", "char", "find", "format", "gmatch", "gsub", "len", "lower",
                "match", "rep", "reverse", "sub", "upper"):
        safe[key] = src_tbl[key]
    return safe

def make_env():
    env = rt.table()
    for name in safe_names:
        env[name] = g[name]
    env["string"] = make_safe_string_table()
    return env

def compile_chunk(src, name, mode, env=None):
    # load() returns a bare chunk function on success (ONE value) or (None, err) on failure
    # (a tuple) -- lupa does not wrap a lone return value in a tuple, so branch on arity.
    args = (src, name, mode) if env is None else (src, name, mode, env)
    result = lua_load(*args)
    return result if isinstance(result, tuple) else (result, None)

env_a, env_b = make_env(), make_env()
src_a = """
x_a = 111
return (io == nil), (os == nil), (debug == nil), (python == nil), (load == nil),
       (require == nil), (collectgarbage == nil), (dofile == nil), (loadfile == nil),
       (string.dump == nil)
"""
chunk_a, _ = compile_chunk(src_a, "file_a.lua", "t", env_a)
print(chunk_a())
chunk_b, _ = compile_chunk("return x_a", "file_b.lua", "t", env_b)
print(chunk_b())  # None -- file_b cannot see file_a's global

# Binary chunk refusal -- extracting bytecode needs a SEPARATE encoding=None runtime, since
# string.dump's output is not valid UTF-8, and encoding=None also requires bytes keys.
rt_bytes = lua54.LuaRuntime(encoding=None, register_eval=False, register_builtins=False)
g_bytes = rt_bytes.globals()
dump_chunk_bytes = g_bytes[b"load"](b"return 42", b"to_dump", b"bt")
bytecode = g_bytes[b"string"][b"dump"](dump_chunk_bytes)

refused, err = compile_chunk(bytecode, "evil_binary", "t", make_env())
print(refused, err)  # None, "attempt to load a binary chunk (mode is 't')"
accepted, _ = compile_chunk(bytecode, "evil_binary_bt", "bt", make_env())
print(accepted())  # 42 -- same bytecode loads fine under the default "bt" mode
```

### Probe: `LuaError` file/line

```python
import lupa.lua54 as lua54

rt = lua54.LuaRuntime(register_eval=False, register_builtins=False)
g = rt.globals()
chunk = g["load"]("""
local function boom()
  error("something broke")
end
boom()
""", "rules/flight.lua", "t")
try:
    chunk()
except lua54.LuaError as exc:
    print(str(exc))
```

### Probe: thread safety of one shared `LuaRuntime`

```python
import threading
import lupa.lua54 as lua54

rt = lua54.LuaRuntime(register_eval=False, register_builtins=False)
rt.execute("counter = {n = 0}")
increment = rt.eval("function() counter.n = counter.n + 1 end")

N_THREADS, N_PER_THREAD = 8, 2000
errors = []

def worker():
    try:
        for _ in range(N_PER_THREAD):
            increment()
    except BaseException as exc:
        errors.append(exc)

threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(rt.eval("counter.n"), "expected", N_THREADS * N_PER_THREAD, "errors", len(errors))
```
