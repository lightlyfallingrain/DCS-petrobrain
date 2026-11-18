## Security Deep Analysis: refactor/rule-action-unable-throw

Mode 2, single-change batch. Branch fast-forwarded cleanly onto `main` (`f06c53fb` was a strict
ancestor, tree clean): HEAD now `09218679`, "Rule actions throw unable; rules no longer check r.ok".

### Dependency Status

No dependency change. `lupa` stays pinned at the version `research/2026-11-17-lupa-sandbox.md`
verified; nothing added or bumped.

### What changed

`_make_action_wrapper` (`src/rules/engine.py`) now raises `RuleUnable(reason)` on `ok=false`
instead of handing the rule a `{ok=false, reason=...}` table, and raises `RuleRuntimeError` for a
bad call (arity/type/range/nan/inf) instead of answering a closed-looking reason. `run_rule`
catches both, plus `RuleBudgetExceeded` and a catch-all `Exception`. `ActionContext.
on_rejected_call` is removed; `tools/check_rules.py` now catches `RuleUnable` as an expected
outcome and anything else as a reported bug. `config/rules/flight.lua` loses all 17
`if not r.ok then say(unable(r.reason)) return end` blocks.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `src/rules/engine.py:262-264` (`_make_action_wrapper`) | Raises `RuleUnable`/`RuleRuntimeError` — a bare Python exception — out of a lupa callback | Matches `research/2026-11-17-lupa-sandbox.md` finding #6 (unwrapped propagation) exactly, and is the documented, intended mechanism, not an accident. Empirically confirmed this session to also propagate correctly through a **nested** Lua helper-function frame (`local function helper() return probe.one(3) end`), one level beyond anything the Stage 0 research or the shipped `flight.lua` exercises — none of the shipped rule files currently wrap an action call in a local function, but the mechanism holds if one later does. | None — false positive risk, closed by direct empirical test (see below) |
| `src/rules/sandbox.py:48-56` (`_SAFE_GLOBAL_NAMES`) | No `pcall`/`xpcall`/`error`/`debug` exposed to rule `_ENV` | A rule cannot catch, inspect, or obtain the `RuleUnable`/`RuleRuntimeError` exception object — there is nothing in the sandbox that would let it. `test_a_rule_cannot_catch_a_failed_action` covers the dict-free-call case (`pcall` itself is `nil`, so the probe call fails as "attempt to call a nil value", correctly reported as a dispatch error, not a caught value). | None |
| `src/rules/engine.py:263` (`reason = result.get("reason")`) | `RuleUnable.reason` comes from the **action's own Python `invoke` result**, never from a rule-supplied string argument | Every shipped action (`rules/actions.py`'s `FLIGHT_ACTIONS`/`EFFECTOR_ACTIONS`) returns a fixed, code-chosen reason string (`"NOT_READY"`, `"UNKNOWN_EFFECTOR"`, etc. via `CrewConsole` methods) — none interpolates a Lua-supplied value into `reason`. A rule cannot forge an arbitrary `reason` today. | None — note as a boundary to recheck if a future action ever builds `reason` from caller input |
| `src/belief/speech.py:532-541` (`render_unable`) | `_UNABLE_TEMPLATES.get(reason, "Unable.")` — closed dict lookup, not string interpolation | Even if `reason` *were* forged to something outside the closed set (it currently cannot be, per the row above), the spoken output degrades to the plain `"Unable."` default — the forged string is never echoed into speech. No injection path into TTS output via this mechanism. | None |
| `src/rules/engine.py:446` (`logger.info("rule %r (%s) unable: %s", rule_id, rule.file, exc.reason)`) | Logs `rule_id`, `rule.file`, `exc.reason` with `%` formatting (not f-string into the message) | `rule_id`/`rule.file` come from the locally-authored `*.lua` config file (not network input — this is a single-user, LAN-only project and rule files are the user's own config, same trust tier as any other local config file); `exc.reason` is a closed, code-chosen string per the row above. No log/format injection risk; even if it were a long or odd string, `logging`'s `%s` formatting is safe. | None |
| `src/rules/sandbox.py:207-234` (`run_with_budget`) | `finally: self._debug_sethook(None)` unconditionally disarms the instruction-count hook | `RuleUnable`/`RuleRuntimeError` escaping the `with` block (neither matches the `except _InstructionBudgetExceeded`/`except lua54.LuaError` clauses, since both are unwrapped Python exceptions, not `LuaError`) still runs the `finally` — Python's `try/finally` semantics guarantee this regardless of which exception type propagates through. Empirically verified this session: 5 consecutive `RuleUnable`-raising dispatches on the same `RuleSandbox`, followed by a clean dispatch of an unrelated rule, left the hook/sandbox state uncorrupted (no stale budget, no leaked arm state). | None |
| `src/rules/engine.py:404-466` (`run_rule`) | Exception hierarchy: `RuleUnable` → ordinary outcome; `(RuleRuntimeError, RuleBudgetExceeded)` → `error=True`; bare `except Exception` → `error=True` with a logged `type(exc).__name__` | Nothing escapes `run_rule` uncaught (confirmed by the existing `test_a_lua_error_during_dispatch_is_reported_as_error`/`test_a_runaway_handler_is_aborted_and_reported_as_error` plus the new `RuleUnable`-path tests, and by running the full suite). The catch-all is deliberately broad (D6 posture, documented in the function's own docstring) specifically because lupa's unwrapped-exception propagation means *any* Python exception raised inside *any* future action/callable could otherwise reach here as something other than the three named types — this refactor does not narrow that posture, it adds `RuleUnable` ahead of it. | None |
| `src/rules/actions.py` (nan/inf guard, `security-stage0-2.md` Required Fix 1) | `math.isfinite` check before `int()` in `_make_action_wrapper`, and in `_digits_readback` | Still present and still tested (`test_nan_argument_is_a_rule_error_not_a_bare_exception`, `test_infinite_argument_is_a_rule_error_not_a_bare_exception`, `test_digits_rejects_nan_as_a_dispatch_error`) — this refactor changed *what* a rejection raises (`RuleRuntimeError` directly instead of via a `reject()`-table), not whether the guard exists. Confirmed by reading the diff and rerunning these tests. | None |

### Questions answered directly

- **Can a rule observe, catch, forge, or abuse `RuleUnable`/`RuleRuntimeError`?** No. No `pcall`/
  `xpcall`/`error`/`debug` in the sandbox `_ENV` (`sandbox.py`'s `_SAFE_GLOBAL_NAMES`), so there is
  no Lua-side mechanism to catch anything, and `reason` is never built from rule-supplied text
  today (every action returns a fixed, code-chosen reason string).
- **Does `RuleUnable` escaping while the instruction-count hook is armed leave the sandbox in a
  bad state for the next dispatch?** No — `run_with_budget`'s `finally` always disarms the hook,
  Python exception-propagation semantics guarantee this independent of exception type, and this
  was verified empirically against the real `RuleSandbox`/lupa runtime, not just read off the code.
- **Does anything now escape `run_rule` uncaught and crash the poll loop?** No — verified by
  reading the full exception hierarchy, by the existing and new test coverage, and by running the
  complete body-layer test suite (3527 passed, 29 deselected, 4 xfailed) plus `mypy --strict`
  (clean) and `ruff format`/`check` (clean).
- **Is the log line safe? Can `reason` carry rule-controlled text?** `reason` is code-chosen today,
  not rule-controlled, and even if a future action changed that, `logger.info`'s `%s` formatting
  and `render_unable`'s closed-dict lookup both degrade safely rather than echoing arbitrary text
  into speech or the log format string.

### Scope note

This is a LAN-only, single-user project; `config/rules/*.lua` is the user's own local
configuration, authored on the same machine — not untrusted network input. The analysis above
still treats the sandbox boundary as a real boundary (per the project's own "rule files are
trusted enough to run, never trusted enough to hand a value straight to a method that assumes its
caller already checked it" posture, `rules/actions.py`'s module docstring) because that boundary
is what a future, less-trusted rule source (or a typo/bug in a hand-written rule) would cross, and
because the whole point of this refactor is making the *one-place* exception handling the thing
that holds it, rather than 17 duplicated per-handler checks.

### Verdict

APPROVED

No required fixes. All four questions in the brief are answered negatively (no observe/catch/
forge path, no corrupted sandbox state, nothing escapes `run_rule`, no unsafe log/speech
interpolation), each backed by either existing tests, new empirical probes run this session
against the real `lupa` runtime, or a direct trace through the code. The nan/inf guard from
`security-stage0-2.md` Required Fix 1 is intact and still covered by its own tests. Full
`body-layer` test suite, `mypy --strict`, and `ruff format`/`check` all pass clean on this
exact commit.
