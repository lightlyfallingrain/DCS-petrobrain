## Security Deep Analysis: speech-rules (BL-17 Stages 0, 1b, 2)

Branch `feature/speech-rules`, tip `1f5fa7ae8d5a67c1cd1dfb22d0ae482fe3e81409` — matched the
expected tip given in the dispatch. The branch is checked out in another worktree
(`/Users/sg/Code/DCS-petrobrain-speech-rules`), so it was verified against an isolated snapshot
(`git archive 1f5fa7ae | tar -x`) rather than checked out directly in this worktree, per the
dispatch's own fallback instruction. All findings below are against that snapshot's tree, which is
byte-identical to the branch tip.

Reviewed: `body-layer/src/rules/{sandbox,engine,loader,actions}.py`, `audio-adapter/src/{server,
rule_patterns,command_matcher,vocabulary,stt_engine}.py`, `audio-adapter/src/audio_adapter/
__main__.py`, `body-layer/config/rules/flight.lua`, the full test suites for all of the above,
`body-layer/research/2026-11-17-lupa-sandbox.md`, and `plans/speech-rules/{plan,implementation,
review-stage1b-2}.md`.

### Dependency Status

`lupa==2.8` is the one new dependency (body-layer's `pyproject.toml`), pinned exact.

- **Licence**: MIT ("MIT style" per package metadata, verified with `pip show`/`importlib.
  metadata` against a freshly built venv) — no GPL conflict with this project's CC BY-NC-SA 4.0,
  and matches the user's own approval (U7, `BL-17.md`: *"`lupa` (MIT) approved as a new
  dependency"*). lupa statically links Lua 5.4's own C sources, also MIT.
- **CVE-2026-34444** (GHSA-69v7-xpr6-6gjm, "Lupa Sandbox escape and RCE due to incomplete
  `attribute_filter` enforcement in `getattr`/`setattr`") — affects lupa `<= 2.6`; this project is
  on 2.8, past the fix. More importantly, the advisory's own mechanism requires Lua code to reach
  Python's `getattr`/`setattr` builtins via `register_builtins=True` (confirmed by fetching the
  advisory directly: *"the product is affected if it does not also disallow access to the Python
  builtins via the `register_builtins=False` option"*) — `sandbox.py`'s `RuleSandbox.__init__`
  already passes `register_builtins=False` explicitly, independent of the version pin. Not
  exploitable here on either ground. No other advisory found for lupa 2.8.
- No other new dependency in this batch.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `body-layer/src/rules/engine.py:192` (`_make_action_wrapper`) | `int(value)` on a Lua-supplied `float`/`int`, checked for type and bounds but not finiteness | **Confirmed defect.** `value` can be a Lua float `nan`/`inf` (trivial via `/`, no stdlib needed — e.g. a future rule's `delta / count` with `count` that can be zero). `isinstance(value, (int, float))` passes a `nan`/`inf` float; `int(value)` then raises a bare `ValueError`/`OverflowError` — **not** `lupa.lua54.LuaError**. Empirically verified (standalone probe against `lupa==2.8`, mirroring this function's exact shape): a Python exception raised inside a Lua-called Python callback propagates out of the top-level Lua call *as itself*, not wrapped. See "Exploitability" below. | **Required fix 1** |
| `body-layer/src/rules/engine.py:257` (`_make_env_builder`'s `digits` lambda) | `"digits": lambda n: CrewConsole._digit_readback(int(n))` — zero validation of any kind before `int(n)` | **Confirmed defect, more directly reachable than the row above.** `digits` is a bare Lua global every rule handler can call with anything: a slot value that is a `str` (every `WordSetElement` slot — e.g. `s.direction`, `"left"`/`"right"` in the shipped grammar — is a Lua string), `nil`, a table, or a `nan`/`inf` float all reach `int(n)` unguarded. `int("left")` → `ValueError`; `int(None)` → `TypeError`; `int(nan)` → `ValueError`. None is `lua54.LuaError`. A rule author writing `say(digits(s.direction))` by an ordinary mistake (not malice) hits this with no sandbox arithmetic trick needed at all. | **Required fix 1** (same fix family) |
| `body-layer/src/rules/sandbox.py` (whole module) | `register_eval=False`, `register_builtins=False`, `attribute_filter`, per-file `_ENV` via allowlist-by-omission, `load(..., "t", env)` | Reviewed against the research spike's own probes and `test_rules_sandbox.py`'s full denylist/isolation/instruction-budget/memory-cap tests, re-read line by line. **Sound.** `string`/`table`/`math` aliasing is correct (fresh copy for `string`, direct reference for `table`/`math`, neither of which has a filesystem/bytecode-reach member); the per-call `debug.sethook` shim is armed/disarmed correctly (`finally`); `attribute_filter` is explicitly documented as second-line-of-defence only, with the real guarantee (never return a raw Python object to Lua) resting on `engine.py`/`actions.py` discipline, which the diff honours everywhere checked. | None |
| `body-layer/src/rules/loader.py` / `engine.py` (`RuleSet.load`/`run_rule`) | `except (RuleCompileError, RuleRuntimeError, RuleBudgetExceeded)` / `except (RuleRuntimeError, RuleBudgetExceeded)` | These catch exactly what `sandbox.py` is documented to raise for a genuine Lua error or budget trip — correct for that contract. The gap is upstream of these `except` clauses (the two rows above), not in them: a raw `ValueError`/`OverflowError`/`TypeError` from inside a Lua-called Python callback is never a `RuleRuntimeError` to begin with, so no amount of widening these tuples would catch it — the fix has to be at the point of conversion, not the point of catching. | Covered by Required fix 1 |
| `body-layer/src/belief/crew_console.py:3069-3074` (`_handle_rule`) | `lines, error = self.rule_runner(token, slots)`, no `try`/`except` around the call | By design, relying on `run_rule` to turn every dispatch-time failure into `(lines=[], error=True)` rather than raising (D6's own contract). Required fix 1 is what makes that actually true for every input shape, not just the ones `test_rules_engine.py`/`test_rules_flight_actions.py` already exercise. | Covered by Required fix 1 |
| `audio-adapter/src/server.py` (`_handle_put_rules`, `_read_body`, `_validate_correlation_id`) | New `PUT /rules` endpoint | Field-by-field JSON validation (version, each rule's id/pattern, all strings non-empty), `Content-Length` guarded against non-numeric/negative (existing `_read_body` fix, pre-existing), loopback-only default host, 404 for any other path. Same posture as the pre-existing `/speak`/`/transcribe` handlers — no new unauthenticated capability beyond what those already have, and nothing here executes anything. No body-size or rule-count cap, but that is pre-existing posture on every endpoint in this file, not a regression this feature introduced — see **Suggestions** below. | None blocking |
| `audio-adapter/src/stt_engine.py` (dynamic `--prompt`) | Whisper `--prompt` rebuilt per-call from active rule *literal* words (`rule_words`, never slot values) | `subprocess.run(command, ...)` with `command` a list and no `shell=True` — no command injection regardless of word content. This is ASR decoder bias text, consumed by whisper.cpp, never read by an LLM with tool access — rules exist specifically to bypass the brain/LLM path (plan D1: "fixed wording is the fast path"), so this introduces no new LLM-prompt-injection surface. | None |
| `audio-adapter/src/rule_patterns.py` (`_consume_digit_run`/`_consume_angle`/`_consume_heading`/`_consume_oclock`) | `int(digit_str)`/`int(word)` | Every call is preceded by an explicit `isdigit()`/digit-table membership check on the exact string being converted — cannot raise. Checked specifically because this is the same "`int()` at a wire boundary" pattern; this one is clean. | None |

### Exploitability of Required fix 1 (detail)

- **Not reachable today.** The one shipped rule (`config/rules/flight.lua`'s `turn_heading_relative`) only ever passes `delta`, an integer in `[-359, 359]` derived from the `angle` slot type (bounded `1..359` by `rule_patterns._consume_angle`) and negated — never non-finite, never non-numeric. It never calls `digits`. No currently-reachable voice command triggers either finding.
- **Becomes reachable the moment a future rule's own Lua arithmetic can produce `nan`/`inf`** (division is enough, no stdlib) **or passes a non-integer slot to `digits`** (any `WordSetElement` slot, by construction, is a string) — both are ordinary mistakes a rule author makes while porting the next command, not an attack. `[[BL-17]]`'s own roadmap schedules exactly that (Stages 4-10, "the remaining commands, ported in scheduled stages"), and `sandbox.py`'s own docstring already anticipates the action surface widening (`[[BL-B95]]`).
- **Consequence, traced two ways** (confirmed by reading the call chain in `body.py`, not assumed):
  - **Crew-text REPL thread** (`_run_crew_text_repl`, `body.py:5440-5503`, run on the **main thread**, unconditionally since `BL-B96` — this is the normal foreground input surface, not a test-only path): `for line in sys.stdin: ... crew_console.handle_line(...)` has no broad exception handler (only `except KeyboardInterrupt`). An uncaught `ValueError`/`OverflowError`/`TypeError` from a rule dispatch propagates straight out of this loop, out of `main()`'s own `try/finally` (which only stops the poll thread and closes the speech worker on the way out), and **crashes the whole body-layer process.**
  - **Poll thread** (`_run_crew_text_poll_loop`, `body.py:4468-5427`): every per-tick operation, including voice-command dispatch, runs inside one `try: ... except Exception as exc: ... logger.exception("crew-text poll cycle failed; continuing")` (`body.py:5416`). This catches the raw exception and the process survives, but two things are lost silently: (1) `_handle_rule`'s documented D6 contract — "every Lua error during dispatch rolls back one-shot state and speaks `ACTION_FILE_ERROR_LINE`" — never runs, so the pilot gets **no response at all** for that command, the exact "recognised, did nothing, indistinguishable from unheard" failure mode `[[BL-17]]`'s own design exists to avoid for Lua errors generically; (2) whatever this poll tick's own processing does *after* the point of dispatch (inside the same `try` block — e.g. point-request/optic-state transitions later in the same tick) never runs for that tick either, since the exception aborts the whole tick, not just the command. These are correctness consequences downstream of this security finding, not an independent Reviewer-domain issue — see note below.
- **Empirically confirmed propagation mechanics** (not inferred from documentation): a standalone probe against the real `lupa==2.8` package, mirroring `_make_action_wrapper`'s exact shape (a Python callable bound as a Lua global, called from a Lua chunk with `0/0` and `1/0` as arguments), shows the raised `ValueError`/`OverflowError` reaches the Python caller as itself — `isinstance(exc, lua54.LuaError)` is `False` in both cases. This is why `sandbox.run_with_budget`'s `except lua54.LuaError` and `engine.run_rule`'s `except (RuleRuntimeError, RuleBudgetExceeded)` do not and cannot catch it as written.

### Required Fixes

1. **Guard every Lua→Python `int(...)` conversion of a rule-supplied value against non-finite and non-numeric input before conversion, at both sites that currently lack it:**
   - `body-layer/src/rules/engine.py`, `_make_action_wrapper` (~line 185-199): after the existing `isinstance(value, bool) or not isinstance(value, (int, float))` check, add `isinstance(value, float) and not math.isfinite(value)` to the same reject branch (return `sandbox.table_from({"ok": False, "reason": None})`), before `int(value)` runs.
   - `body-layer/src/rules/engine.py`, the `digits` lambda in `_make_env_builder` (~line 257): replace the bare `lambda n: CrewConsole._digit_readback(int(n))` with a small function that validates `n` the same way (`bool`/non-`(int,float)`/non-finite-`float` all degrade to the existing `render_unable(None).text` "Unable." fallback, the same graceful-degradation posture `_make_action_wrapper` already uses) rather than calling `int()` unguarded. Add the mirror-image test to `test_rules_engine.py` (a rule calling `digits` with a string slot, and with a computed `nan`) alongside the existing `test_digits_reuses_the_digit_readback`.
   - Rationale for blocking rather than filing as backlog: this is the same recurring defect class flagged project-wide (`.claude/agent-memory/security/project_nan_infinity_int_conversion_at_lan_boundary.md`, and `[[BL-B104]]`/`[[BL-B120]]` on two earlier boundaries) and it sits in a function whose whole job is to be the validation boundary for *every* rule-callable action, present and future — cheap to close now, while only one rule and one action exist, rather than once several of `[[BL-17]]`'s later porting stages depend on it already holding.

### Suggestions (non-blocking, filed)

- **`[[BL-B125]]`** — the rule engine's instruction-count budget constants (`RULE_LOAD_INSTRUCTION_BUDGET`/`RULE_DISPATCH_INSTRUCTION_BUDGET`) are counted in `debug.sethook` hook firings (every 1000 real VM instructions), so the actual instruction count before `RuleBudgetExceeded` fires is ~1000× the named value — up to ~2×10⁸ real instructions for one dispatch, held under the sandbox's single shared `LuaRuntime` lock the whole time. Mechanism works and is tested; this is about the constants' real scale vs. what they read as.
- **`[[BL-B126]]`** — `PUT /rules` (and the pre-existing `/speak`/`/transcribe`) have no cap on request body size or, for `/rules`, list length, ahead of an O(n²) collision check. Not a regression from this feature (same posture every endpoint in this file already has) and not reachable under the default loopback-only `--host`; would matter only if `--host` is ever widened to the LAN as a matter of course.

### Passed to Reviewer

None — no player-experience/correctness issue was found outside what Required Fix 1 itself causes (addressed above as a security finding, not filed separately).

### Verdict

**CHANGES REQUIRED** — Required Fix 1 only. Everything else reviewed (sandbox isolation, the
dependency, the HTTP surface, the whisper-prompt path) is clean or already appropriately captured
as a non-blocking backlog item.
