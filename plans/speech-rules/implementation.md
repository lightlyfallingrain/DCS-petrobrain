### Implementation Summary

Stage 0 only (`plans/speech-rules/plan.md`, "Stage 0 — lupa spike"): verified every sandboxing
mechanism the plan's engine design (Stage 1b) will depend on, by running real probes against a
fresh `body-layer/.venv` built with Python 3.14.10 (homebrew `/opt/homebrew/bin/python3.14`,
macOS arm64) — not read off lupa's documentation. Full findings, every probe script, and its
pasted output: `body-layer/research/2026-11-17-lupa-sandbox.md`. No engine code was written —
that is explicitly Stage 1b's scope, per the plan.

**Stop condition check:** the instruction-count abort (`debug.sethook`, once the Python callback
is wrapped in a trivial Lua shim — see below) works and was verified to actually interrupt an
infinite loop cleanly. The stop condition was not triggered; Stage 1b may proceed.

### Files Changed
- `body-layer/pyproject.toml` — added `lupa==2.8` to `dependencies`, pinned to the exact version
  probed (a `cp314-macosx_11_0_arm64` wheel exists for it). Comment names the research note and
  U7 (user approval).
- `body-layer/research/2026-11-17-lupa-sandbox.md` — new. One section per plan bullet, each with
  the probe that was actually run and its pasted output, plus a "Probe scripts" appendix with the
  runnable source for every probe (so a later reader can re-run them against a newer lupa without
  re-deriving the setup).

### Tests Added
None — Stage 0 is a spike with no engine code; nothing in `src`/`tests` changed, so the fast test
suite ran only its smoke/collect-all step (no targeted tests apply) and mypy/ruff checked the
same 84/208 files as before, unchanged.

### Checks
(body-layer/ only — the one subproject touched)
- ruff format --check: pass (208 files already formatted)
- ruff check: pass
- `cd body-layer && .venv/bin/mypy src`: pass (84 source files, no issues)
- `.claude/scripts/fast-tests.sh body-layer`: pass (smoke/collect-all only; no targeted tests —
  no `src`/`tests` file changed)

### Notable Discoveries

Five things the plan's Stage 0 bullets asked to confirm turned up gotchas not mentioned in the
plan text — each is written up in full in the research note, summarized here:

1. **`register_eval=False`/`register_builtins=False` do not strip Lua's own stdlib.** They gate
   only the `python.eval()`/`python.builtins.*` bridge Lua-side. `io`/`os`/`debug`/`require`/
   `load`/`string.dump`/… are all still present in a freshly constructed runtime's `globals()`.
   Stage 1b's sandbox must isolate by **never granting** these names into a file's own `_ENV`
   table (an allowlist, built fresh), not by relying on these constructor flags or by mutating
   the runtime's real globals.
2. **`debug.sethook` rejects a bare Python callable** (`LuaError: bad argument #1 to
   'debug.sethook' (function expected, got POBJECT)`) because Lua's C implementation requires
   `lua_isfunction()`, and lupa wraps Python callables as userdata-with-`__call`, not a genuine
   Lua function value. Fix: wrap the Python callback in a one-line Lua shim
   (`function(py_fn) return function(...) return py_fn(...) end end`) before passing it to
   `sethook`. This is required, not optional, for Stage 1b's instruction cap to work at all.
3. **Lua table assignment copies a reference, not contents.** `env["string"] = g["string"]`
   followed by pruning a member on `env["string"]` (e.g. `string.dump`) mutates the single shared
   `string` library table for every runtime user, trusted code included. A sandbox pruning any
   library table must build a fresh copy with only the safe members copied in, never prune the
   shared table in place.
4. **`LuaError`'s file/line are embedded in the message string, not separate attributes.**
   `getattr(exc, "lua_error", None)` is `None`; there is no `.filename`/`.lineno`. Whatever
   Stage 1b's `RuleLoadError`/dispatch-time error logging surfaces will need to carry or
   string-match the `[string "<name>"]:<line>:` prefix, not read structured fields off the
   exception.
5. **No type stubs ship with lupa** (confirmed: no `py.typed`, no `.pyi` files in the installed
   package; `mypy --strict` reports `import-untyped` and suggests `types-lupa`). Per the plan's
   own stated fallback, Stage 1b should confine `# type: ignore[import-untyped]` to
   `sandbox.py` rather than add `types-lupa` as an unapproved second dependency — that choice is
   Stage 1b's to make if it wants to revisit it, not this spike's to decide.

**One scoping choice worth flagging explicitly rather than silently:** the plan's "Affected
modules" section lists `body-layer/CLAUDE.md`'s "Tech stack" update (dropping "stdlib only") as
one of body-layer's affected files for stages 0–3 collectively, but Stage 0's own numbered steps
only ask to install lupa and record findings. I left `CLAUDE.md` unchanged here and did not add
an import of `lupa` anywhere in `src/` — both belong with Stage 1b's `sandbox.py`, which is the
first code that actually imports it. Noted so the Stage 1b implementer knows that doc edit is
still outstanding, not already done.

**Interpreter note:** the worktree had no venvs (gitignored). Built `body-layer/.venv` fresh from
`/opt/homebrew/bin/python3.14` (3.14.10) — the plan's own text anticipated "Python 3.14 on the
Mac" — plus `ruff`, `mypy`, `pytest`, `pytest-xdist` (no pinned versions exist anywhere in the
repo for these dev tools, so current-latest was installed: ruff 0.17.5, mypy 2.4.1, pytest 9.2.0).
