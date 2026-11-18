# Review — `refactor/rule-action-unable-throw`

Reviewed at `09218679` (branch tip; base `main` `f06c53fb`). Decision under review: BL-17's "A
failed action throws 'unable'" (user, 2026-11-18, `body-layer/ROADMAP/BL-17.md`).

Diff: `body-layer/ROADMAP/BL-17.md`, `body-layer/config/rules/README.md`,
`body-layer/config/rules/flight.lua`, `body-layer/src/rules/actions.py`,
`body-layer/src/rules/engine.py`, `body-layer/tests/test_rules_effector_action.py`,
`body-layer/tests/test_rules_engine.py`, `body-layer/tools/check_rules.py`.

### What was checked

- **`RuleUnable` propagation through lupa.** Confirmed from code (`_make_action_wrapper`'s
  `wrapper` raises `RuleUnable` after `action.invoke` answers `ok=false`; `run_rule`'s
  `except RuleUnable` catches it around `rule.handler(lua_slots)` inside
  `sandbox.run_with_budget`) and from tests — `test_a_failed_action_ends_the_handler_and_says_
  unable`, `test_a_failed_action_with_no_reason_says_plain_unable`,
  `test_a_rule_cannot_catch_a_failed_action` in `test_rules_engine.py` all run the real
  sandbox (no lupa mocking), and all pass. The engine docstring's claim that lupa propagates a
  Python exception raised inside a Lua-called callback unwrapped is consistent with Stage 0's
  §3 probe (`research/2026-11-17-lupa-sandbox.md`, the `debug.sethook` hook case) and is now
  additionally demonstrated for the action-wrapper case specifically, by these three passing
  tests through the real `RuleSandbox`/`lupa.lua54.LuaRuntime`.
- **Lines already said stay spoken; nothing is rolled back for an `unable`.** Verified by
  reading `_SinkHolder.say` (appends, never cleared mid-dispatch) and by running
  `test_a_failed_action_ends_the_handler_and_says_unable` (`lines=["Arming.",
  "Unable, not ready."]`).
- **A bad call (arity/type/range/nan/inf) is now "Action file error," not a closed "unable"
  reason.** `reject()` raises `RuleRuntimeError` directly; the engine-level tests renamed and
  re-asserted this (`test_an_out_of_bounds_argument_is_a_rule_error`,
  `test_a_wrong_argument_type_is_a_rule_error`, `test_a_wrong_argument_count_is_a_rule_error`,
  `test_nan_argument_is_a_rule_error_not_a_bare_exception`,
  `test_infinite_argument_is_a_rule_error_not_a_bare_exception`) all pass.
- **`ActionContext.on_rejected_call` is fully gone.** Grepped `body-layer/`, `plans/speech-rules/`,
  `docs/` — the only remaining hit is the ROADMAP entry's own past-tense mention that it was
  removed. `tools/check_rules.py` now catches `RuleUnable` and ignores it (an action failing is
  a normal dry-run outcome, not a reported finding); every other exception is still reported.
- **Buffered effector writes on an `unable`.** This was the main thing worth not just reading.
  `run_rule`'s `except RuleUnable` branch leaves `error = False` (the `except
  (RuleRuntimeError, RuleBudgetExceeded)` branch is the only one that sets `error = True`).
  `CrewConsole._dispatch_rule`'s buffer-then-commit only discards the dispatch's write buffer
  `if error:`; otherwise it extends the buffer onto the shared `pending_effector_writes` list.
  So a write followed by a later `unable` in the same dispatch **commits**, exactly as the user
  direction in the task brief says it should (not rolled back) — confirmed by direct execution,
  not just by reading:

  ```
  rule: effector.write("observ", ...) then effector.write("no_such", ...) [unable]
  lines: ['Unable.']
  pending_effector_writes: [('observ', 'on')]   # committed, not discarded
  ```

  This is the correct behaviour and distinct from the existing, heavily-tested
  write-then-`RuleRuntimeError` case (`test_a_write_then_a_later_error_in_the_same_dispatch_is_
  rolled_back` and its two siblings in `test_rules_effector_action.py`), which still discards
  the buffer — that path is untouched by this diff and still correct.
- **`flight.lua`**: all 17 `if not r.ok then say(unable(r.reason)) return end` blocks removed;
  every remaining `local r = flight.X(...)` is still used for a readback field (`r.heading_deg`,
  `r.speed_kmh`, `r.altitude_m`, `r.barometric`, `r.is_max`) — none of these locals are now dead.
  `speak_level_off`'s helper function was inlined into `level_off`'s own `when.speech` call,
  which is a reasonable simplification once the only thing the helper did besides the one `say`
  call was the now-removed `ok` check.
- **README.md**: "Actions" section rewritten consistently with the new contract (no rule checks
  `r.ok`; a bad call is "Action file error"; nothing is undone; rules cannot catch the failure).
  The worked example at the top was updated too.
- **BL-16 mode-1 plan** (`feature/bl16-raw-axes`, `plans/flight-control/plan.md` Decision 22):
  explicitly built on this refactor ("built on `refactor/rule-action-unable-throw`, which lands
  on main before any mode-1 code" — "raises unable"/"no rule in this series contains an `r.ok`
  check"). No implementation exists yet on that branch to check for staleness; the plan text
  itself is consistent with what actually landed.
- Historical mentions of the old `if not r.ok`/`{ok=false, reason=nil}` shape remain in
  `plans/speech-rules/plan.md`, `implementation.md` and `review-security-fix.md` — these are
  dated planning/implementation/review records, not live contracts, and the project convention
  (`docs/PROCESS.md`) is that supersession is marked at the current decision record
  (`ROADMAP/BL-17.md`'s "A failed action throws 'unable'" section), not retrofitted into every
  historical document. No action needed there.
- **Checks**: `ruff format --check` reports 2 pre-existing, unrelated findings in
  `research/2026-10-05-security-audit.md` and `research/2026-11-17-lupa-sandbox.md` (ruff
  formatting embedded Python fences in Markdown) — both files are untouched by this diff and the
  finding is identical on `main`. `ruff check .` — all checks passed. `mypy src` (run from
  `body-layer/`) — success, no issues in 91 files. `pytest --collect-only` (smoke) — 3560 tests
  collected. Targeted run (`test_rules_engine.py`, `test_rules_effector_action.py`,
  `test_check_rules_tool.py`, plus `-k "rule or effector or crew_console"` across the suite) —
  all pass (40 + 646). `tools/check_rules.py --adapter-python
  .../audio-adapter/.venv/bin/python` — `ok: 1 rule file(s) checked`.
- No new behaviour-affecting constants were introduced (pure control-flow refactor: an exception
  type plus removed dead branches), so the tuning-mechanism checklist does not apply here.
- Comment pruning: the removed `#:` block documenting `on_rejected_call` and the removed
  docstring sentences describing the old `{ok=false, reason=nil}` return both describe a
  mechanism that no longer exists at all (the field itself is gone) — nothing durable (a dated
  quote, a measurement) was cut; no boundary case was dropped without a replacement test.

### Required Fixes

- **Add a test for the one interaction this review had to verify manually: a dispatch that
  calls `effector.write` successfully and then hits `RuleUnable` (not `RuleRuntimeError`) later
  in the same handler must still commit the buffered write, through the real
  `_dispatch_rule`/`handle_command` path** (not `run_rule` directly, the same reasoning
  `test_a_write_then_a_later_error_in_the_same_dispatch_is_rolled_back` gives for using that
  path). The symmetric case — a write followed by a *bug* (`RuleRuntimeError`) — already has
  three dedicated tests in `test_rules_effector_action.py`
  (`test_a_write_then_a_later_error_in_the_same_dispatch_is_rolled_back`,
  `test_concurrent_dispatches_do_not_lose_each_others_queued_writes`,
  `test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_it`); the new
  write-then-`unable` case introduced by this refactor has none. The behaviour is currently
  correct (confirmed above by direct execution), but it depends on `_dispatch_rule`'s `if
  error:` check reading `RuleUnable`'s `error=False` correctly — exactly the kind of interaction
  a later change (e.g. someone deciding "unable should also roll back" and flipping that flag)
  could silently break with nothing to catch it. A short addition to
  `test_rules_effector_action.py`, mirroring `test_a_successful_dispatchs_write_commits_to_the_
  shared_list` but with the handler's second call answering `ok=false` instead of returning
  cleanly, closes the gap.

### Optional Refinements

- `_make_action_wrapper`'s `reject()` now always raises and never returns a value, but every
  call site still writes `return reject(...)`. Harmless (the `raise` means the `return` is never
  reached), but a `NoReturn` return type on `reject` plus dropping the leading `return` at each
  call site would make that explicit rather than reading as a leftover from when `reject`
  produced a Lua table. (optional)

### Verdict

**APPROVED WITH MINOR FIXES** — the refactor is correctly built, consistently applied across
`flight.lua`, README, tests and the rule checker, and the one interaction that most needed
independent verification (buffered effector writes surviving an `unable`) checks out by direct
execution. The missing test above is cheap and closes a real, specific coverage gap rather than
a style complaint; nothing else blocks.

### Review Confidence

Full read. Every changed file was read in full against the diff; the lupa-propagation and
buffer-commit claims were verified by running the real test suite and, for the untested
interaction, by executing the real code path directly (not just by reading) before writing the
required fix above.
