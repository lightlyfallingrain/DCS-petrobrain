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

---

### Stage 1b (this run)

Built the rule engine (body-layer: sandbox/loader/engine/empty action registry) and the
adapter-side grammar/matcher/`PUT /rules` seam (audio-adapter), with no rule shipped yet — per
the plan's own "Stage 1b — the rule engine, with no rules shipped yet." Fresh venvs built for
both subprojects (same homebrew 3.14.10 interpreter as Stage 0; audio-adapter needed its own
venv too, created fresh — `ruff`/`mypy`/`pytest`/`pytest-xdist` current-latest, same versions as
Stage 0's body-layer venv).

**Acceptance check pinned by the plan itself:** "with no `PUT`, the adapter behaves exactly as
today," verified by the whole pre-existing `test_command_matcher.py` suite passing unchanged.

**Mid-task directive, overriding part of the original brief (recorded verbatim, 2026-11-17):**

> *"Until I provide decisions about how to handle 'bearing', treat 'heading' as the unit we
> mainly use. It is always a world compass three digit number in degrees 000-360."*

So the `heading` slot type (word "heading" + exactly 3 digits, 000–360 inclusive, 360 normalises
to 0, no ×5 checksum, magnetic/true convention in code unchanged) is built now in Stage 1b's
grammar, alongside `angle`/`oclock`/word-sets. `bearing` stays unbuilt. No existing spoken
command's meaning changed — `scan bearing`/`report bearing` are untouched; `heading`'s type
exists in `rule_patterns.SLOT_TYPES` but nothing uses it yet (no shipped rule names it).

**Stage 1b's own plan text named `heading`/`bearing`/`oclock`/word-set/`angle` in D7's table and
several of its own tests by name** (e.g. the "no checksum, three digits" tests). Per the
orchestrator's instructions: do not build `heading`/`bearing` as D7 originally specified them
(compass direction for commands this stage does not touch), and do not build the plan's Stage
1b tests that exercise a `heading`/`bearing` *command slot* (there are none that actually
require a shipped command using either type in Stages 1b/2 — the plan's own "Affected modules"
list for Stage 1b/2 never ships a rule using `heading`/`bearing`, only `turn_heading_relative`'s
`angle`/word-set). So nothing was dropped from the plan's own Stage 1b/2 test list; the directive
only changed *what the `heading` type itself validates* (a world-compass number, not yet wired to
any command) versus what D7's table originally described for it.

### Files Changed

**body-layer**
- `src/rules/sandbox.py` — new. The only module importing `lupa`. `RuleSandbox`: one shared
  `LuaRuntime`, `base_env()` (the safe allowlist, built fresh per file — never the shared `string`
  table pruned in place, per the Stage 0 research note), `compile()` (`load(src, name, "t", env)`,
  raising `RuleCompileError`), `run_with_budget()` (the instruction-count `debug.sethook` stop
  condition, via the one-line Lua shim the research note found necessary), `table()`/
  `table_from()` (the one path any structured value crosses into Lua, never a raw Python object).
- `src/rules/actions.py` — new. `ActionContext`/`ActionParam`/`Action`, mirroring `belief.
  tool_api.BrainTool`'s shape (D5) without reusing it directly. `ACTION_NAMESPACES` is empty
  (D5/Stage 1b item 2: "empty apart from `say`, `unable`, `digits`," which live in `engine.py`) —
  Stage 2 adds the first real action.
- `src/rules/loader.py` — new. `RuleLoadError`/`RawRegistration`, `load_rules()` (sorted-order
  file iteration, per-file env via an injected `env_builder`, a whole file's registrations
  discarded together on any load-time failure — D6). `DEFAULT_RULES_DIR` (`config/rules/`).
- `src/rules/engine.py` — new. `RuleOutcome`/`CompiledLuaRule`/`RuleSet` (`RuleSet.load` ties
  `loader.py` + `sandbox.py` + the action namespaces together; `_dedupe` disables every
  registration sharing a duplicate id, not just the second one; `_version_of` hashes the sorted
  `(id, pattern)` set). `run_rule()`. The Lua-side `say`/`unable`/`digits` API — `unable` reuses
  `belief.speech.render_unable` verbatim, `digits` reuses `belief.crew_console.CrewConsole.
  _digit_readback` verbatim, per the plan's own Stage 1b item 2 wording. `_SinkHolder` is the one
  piece of per-dispatch mutable state `say` needs, scoped to its own `RuleSet` (not module-level)
  so a reload's fresh `RuleSet`/handlers never share state with a discarded one.
- `config/rules/README.md` — new. The pattern-grammar/API reference page (no rule ships yet, so
  its one worked example is illustrative, not a file on disk until Stage 2).
- `src/belief/crew_console.py` — `ACTION_FILE_ERROR_LINE`; `rule_runner`/`enabled_rule_ids`/
  `_ever_enabled_rule_ids`/`action_file_error_pending` fields; `set_enabled_rule_ids` (the one
  writer of `enabled_rule_ids`, folding into `_ever_enabled_rule_ids`); `_reset_one_shot_command_
  state` (extracted from `handle_command`'s own preamble, reused for the error-rollback path);
  `_handle_rule`/the final `elif`/`elif` pair in `handle_command`'s dispatch (an enabled rule id;
  a *dropped* rule id — `NO_SUCH_COMMAND`, never silent, D4); `drain_action_file_error`
  (re-armable, unlike `drain_config_error`); `reset_for_new_mission` passes `rule_runner`/
  `_ever_enabled_rule_ids` through, resets `enabled_rule_ids`/`action_file_error_pending` to
  default (re-set synchronously by `body.py`'s own mission-restart handler). **Deliberately does
  not import anything from `rules.*`** (D4: avoids a `belief` <-> `rules` cycle) — the injected
  `rule_runner` is typed as a plain `(token, slots) -> (lines, error)` tuple callable, not
  `rules.engine.RuleOutcome`. (No rule id is enabled yet -- `turn_heading_relative` is still the
  static token/handler it always was; Stage 2 moves it.)
- `src/belief/audio_client.py` — `put_rules()`/`PutRulesResult`; `get_transcripts()` now returns
  `(events, rules_version)` (a signature change, sanctioned by D2's own header addition — the one
  real call site and three test assertions updated, see Tests Added).
- `src/body.py` — `RuleRuntime` (bundles the sandbox/`ActionContext`/rules dir/current `RuleSet`/
  `adapter_accepted_version`); `_print_rule_banner`/`_load_rules`/`_push_rules` (mirroring `_load_
  effector_config`'s stderr-banner shape); `--rules-dir` (default `DEFAULT_RULES_DIR`, always on)/
  `--print-rules` (D11, standalone like `--print-tuning`, optionally also pushes); load+push once
  in `main()` before the poll thread starts; reload+re-push wired into `_check_for_new_mission`'s
  genuine-reset branch only (not the "first event adopted" branch — U11 says "mission *restart*",
  and `main()` already loads once at startup); `_poll_transcripts` now returns the poll's own
  `X-Rules-Version` header, compared against `RuleRuntime.adapter_accepted_version` each poll to
  trigger a re-push on mismatch (D2).
- `CLAUDE.md` — "Tech stack" no longer says stdlib-only; names `lupa` as the one direct dependency.
- `pyproject.toml` — `rules` added to `known-first-party` (isort).

**audio-adapter**
- `src/rule_patterns.py` — new. Grammar (`LiteralElement`/`SlotElement`/`WordSetElement`/
  `OptionalElement`), `SLOT_TYPES` (`angle`/`heading`/`oclock` — see the mid-task directive above),
  `parse_pattern`/`match_pattern` (full-consumption, exact-literal — see "Notable Discoveries"),
  `CompiledRule`/`generate_samples`/`RuleRejection`/`RuleRegistry`/`compile_rules` (the three-pass
  collision check, D9), `rule_words` (for the whisper prompt, D10).
- `src/command_matcher.py` — `match_transcript` gained `rules: tuple[CompiledRule, ...] | None =
  None` (D8): the rule-match attempt (after the wake word/HVRT bare words, before every legacy
  slotted branch -- the existing `turn_heading_relative` branch among them, unchanged this stage),
  `_rule_anchor_words` (widens the anchor gate per D8), `_match_rules`. `_verb_anchor_ratio`
  gained an optional `anchor_words` parameter (default `VERB_ANCHOR_WORDS`, so the one existing
  caller importing it directly in a test is unaffected).
- `src/vocabulary.py` — added `FREE_SPEECH_GUARD` (D9, a representative pull from `test_command_
  matcher.py`'s own pinned adversarial fixtures, not a second copy of that file's full list);
  `recognised_words`/`to_prompt` gained an optional `extra_words` parameter (D10).
  `turn_heading_relative`/`parse_turn_relative` are untouched this stage.
- `src/server.py` — `PUT /rules` (`_handle_put_rules`), `_legacy_probe` (the injected collision-
  check callable, kept here rather than in `rule_patterns.py` specifically to avoid the import
  cycle — see "Notable Discoveries"), `X-Rules-Version` on `/transcripts/poll`'s response,
  `TTSAdapterServer`'s new `rule_registry` constructor param, `/transcribe`'s `match_transcript`
  call now passes `rules=rule_state.rules`.
- `src/stt_engine.py` — `WhisperCliEngine.__init__`'s `prompt` parameter is now `str |
  Callable[[], str] | None` (D10's "prompt provider"); `transcribe()` resolves it fresh on every
  call.
- `src/audio_adapter/__main__.py` — builds one `RuleRegistry`, shared between `TTSAdapterServer`
  and a `_rule_prompt_provider` closure (rebuilds the prompt from the active rule set's own words
  on every call, plus a word-count-based warning if the result would exceed whisper's prompt cap
  — risk R3; no BPE tokenizer dependency here, so word count is the dependency-free proxy).
- `pyproject.toml` — `rule_patterns` added to `known-first-party` (isort).
- `CLAUDE.md` — `PUT /rules`, `rule_patterns.py`, and the `rules=`/`FREE_SPEECH_GUARD`/
  `extra_words` additions documented in "Structure".

### Tests Added

**body-layer**
- `tests/test_rules_sandbox.py` — the sandbox denials (full denylist, one `return` statement
  checking all 11 names at once, including `python`); two files never sharing globals; the
  `string`-table-aliasing regression the Stage 0 research note found; a runaway loop aborted by
  the instruction budget; a finite loop within budget completing; the memory cap firing; a syntax
  error raising `RuleCompileError`; `table_from` producing a genuinely dotted-accessible table.
- `tests/test_rules_loader.py` — a clean file; a syntax error discarding only that file;
  registrations made before a later runtime error in the same file also discarded; a bad `when.
  speech` call disabling only that one rule; a missing directory loading as zero/zero; sorted
  load order.
- `tests/test_rules_engine.py` — a clean rule end to end (load -> dispatch); slots reaching the
  handler; `unable`/`digits` reusing the real catalogue/readback; a Lua error and a runaway
  handler both reported as `error=True`; a duplicate id across two files disabling both; the
  version hash stable for identical rules and changing when they don't; an unknown rule id as a
  defensive no-op; a reload picking up an edited file (the mission-restart reload, exercised via a
  temp directory rather than a real DCS mission); an out-of-bounds action argument (against a
  locally-defined fake namespace, not `ACTION_NAMESPACES`, which is empty this stage) degrading to
  `"Unable."` rather than raising.
- `tests/test_crew_console_rules.py` — `handle_command` dispatching an enabled rule id; slots
  reaching the injected `rule_runner`; a rule error speaking `ACTION_FILE_ERROR_LINE` and rolling
  back a one-shot field a fake handler set before "erroring"; refusal mode beating a rule; a rule
  ending silence like any other command; a *dropped* rule id answering `NO_SUCH_COMMAND` (not
  silence); an unknown token (never a rule) staying silent+logged, unchanged from before this
  plan; `drain_action_file_error`'s gate/silence-deferral and its re-arm-across-two-reloads case
  (unlike `drain_config_error`, this one can legitimately speak twice in one process).
- `tests/test_crew_console_ai_pilot_wheel.py` — `TestTurnHeadingRelative` (which dispatched the
  now-deleted static token) replaced by `TestIncrementAiHeading`, exercising the extracted method
  directly (plan Stage 2 item 4's own "test rewrite, inherent in the token moving").
- `tests/test_mission_start_reset.py` — `_CREW_CONSOLE_PRESERVE` gained `rule_runner`/`_ever_
  enabled_rule_ids` (this module's own generic field-by-field reset-completeness check would
  otherwise have failed the moment these two fields existed, regardless of whether `reset_for_
  new_mission` handled them correctly — and it caught exactly that on the first full-suite run).
- `tests/test_audio_client.py` — `get_transcripts()`'s three existing assertions updated for its
  new `(events, rules_version)` return shape (D2's own sanctioned API change); `put_rules()`
  accepted/rejected parsing and its unreachable-host case; the `X-Rules-Version` header read-back.
- `tests/test_body.py` — `FakeSpeechInputClient.get_transcripts` updated to the new tuple shape
  (no assertion depended on the old shape, so this is the only change needed there).

**audio-adapter**
- `tests/test_rule_patterns.py` — grammar parsing (literal/word-set/slot/optional, every
  `PatternError` case); each slot type including the directive's own `heading` cases (exactly 3
  digits, leading zero, 360->0, no checksum, the missing-anchor-word case); `generate_samples`
  with and without an optional group; `compile_rules`'s acceptance, bad-grammar, duplicate-id,
  rule×rule, rule×legacy, and free-speech-guard cases, plus that one rejection never collaterally
  disables an unrelated valid rule in the same push. (Uses a made-up "turn"-flavoured example
  rule for several cases -- purely as a representative pattern shape, not tied to the real
  `turn_heading_relative` command, which this stage has not touched.)
- `tests/test_rules_api.py` — `PUT /rules` against a real server (acceptance, bad grammar, a
  legacy collision against the real `scan_left`, the three malformed-body 400s); the
  `X-Rules-Version` header absent before any push, present and correct after one, and pushing the
  same set twice being byte-identical.
- `tests/test_command_matcher.py` — one new test, `test_free_speech_guard_sentences_never_resolve_
  to_a_command`, reading `vocabulary.FREE_SPEECH_GUARD` (the "both the tests and the check read
  one shared list" half of D9's own design).

### Checks

**body-layer** (fresh `.venv`, `/opt/homebrew/bin/python3.14`)
- `ruff format --check`: pass
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src`: pass
- Full suite (`-n auto`): pass, 3466 passed, 4 xfailed (this stage's own tree, i.e. without
  Stage 2's `test_rules_flight_actions.py`, which depends on the ported rule).

**audio-adapter** (fresh `.venv`, `/opt/homebrew/bin/python3.14`)
- `ruff format --check`: pass
- `ruff check`: pass
- `cd audio-adapter && .venv/bin/mypy src`: pass
- Full suite (`-n auto`): pass, 479 passed, 2 skipped (the whisper-cli/Piper live-binary-gated
  tests, skipped in this dev environment as documented elsewhere in this subproject's
  `CLAUDE.md`; this stage's own tree, without Stage 2's `test_command_matcher_rules.py`).

### Notable Discoveries

1. **A real import cycle between `rule_patterns.py` and `command_matcher.py`, resolved by
   dependency injection, not by moving the collision check.** The plan's own "Affected modules"
   list puts "collision check (D7–D9)" inside `rule_patterns.py`, but D9's rule×legacy check needs
   the real legacy matcher (`command_matcher.match_transcript`), and `command_matcher.py` must
   import `rule_patterns` for its own D8 rule-matching branch regardless of which rules are
   active. Importing `command_matcher` back into `rule_patterns.py` would be a genuine cycle, not
   a style issue. Resolved by injecting a `legacy_probe` callable (`LegacyProbeResult`, a two-field
   narrowing of `MatchResult`) into `rule_patterns.compile_rules` — the probe itself (`_legacy_
   probe`) lives in `server.py`, which already imports both modules. The collision-check
   *algorithm* (sample generation, the three passes) still lives in `rule_patterns.py`, matching
   the plan's intent as closely as the cycle allows.
2. **Matching is full-consumption and exact-literal, not the legacy matcher's fuzzy phrase-
   sequence score.** D8's text describes scoring a rule's literals with `_phrase_match_ratio`;
   this implementation instead requires every pattern element to consume its words exactly, with
   no fuzzy tolerance on literals. This is a deliberate, scoped-down choice (documented in `rule_
   patterns.py`'s own module docstring) rather than an oversight: U1's own "fixed wording is the
   fast path" is what a deterministic grammar literally means, Stage 1b/2 ships exactly one rule
   so there is no real fuzzy-matching need yet to measure against, and building a second fuzzy
   engine now — parallel to the carefully-tuned legacy one — for zero benefit this stage can
   demonstrate felt like the wrong trade. `match_ratio` is therefore always `1.0` for a rule hit;
   `ambiguous` still works (two full matches on the same transcript is a genuine tie). **Flagging
   this explicitly for Reviewer/the user**: a later stage with more rules, or real flight data
   showing STT noise defeats exact literals, may need to revisit this and add tolerance — it was
   not treated as settled, only as the right scope for what ships now.
3. **D4's "a dropped rule id answers `NO_SUCH_COMMAND`, never silent" needed a second, separately-
   tracked set, not just `enabled_rule_ids`.** `handle_command`'s existing unknown-token test
   (`test_unknown_token_returns_nothing_and_logs_a_warning`) requires a token nobody ever defined
   to stay silent+logged — but D4 also requires a rule id that *was* enabled and has since been
   dropped (a reload, or an adapter rejection) to speak `NO_SUCH_COMMAND` instead. Distinguishing
   the two needed `_ever_enabled_rule_ids` (grows, never shrinks, process lifetime) alongside
   `enabled_rule_ids` (the current set) — not named in the plan's own module list, added once the
   two cases turned out to need different state to tell apart.
4. **The `heading`/`oclock` slot types' own number words are deliberately not shared with
   `vocabulary.py`'s private tables beyond `_WORD_DIGITS`.** `oclock`'s 1-12 word table is its own
   (not `vocabulary._RANGE_NUMBER_WORDS`, which runs 1-20 for a different slot, and not `_CLOCK_
   WORD_TO_HOUR`, which is restricted to the forward hemisphere for a no-omniscience reason that
   belongs to the *commands* using a clock position, not to this generic grammar type) — documented
   in `rule_patterns.py` so a later reader does not "simplify" it into a shared table that would
   quietly import a domain restriction that does not belong there.
5. **`config/rules/README.md` explicitly says `bearing` is not built yet and why**, so a future
   rule author (including a later stage of this same plan) does not write a rule assuming it
   exists and discover the gap only at `--print-rules` time.

No other departures from the plan's stage boundaries were made this stage.

---

### Stage 2 (this run) — port "turn left/right NN"

Moved `turn_heading_relative` off its static `handle_command` token onto a rule, using Stage
1b's engine. Same venvs as Stage 1b (no new dependency).

### Files Changed

**body-layer**
- `config/rules/flight.lua` — new. The one shipped rule, exactly the plan's own worked example
  (D7/Stage 2 item 2).
- `src/rules/actions.py` — `ACTION_NAMESPACES` gains the `flight` namespace: `_increment_heading`/
  `FLIGHT_ACTIONS`, one action, `flight.increment_heading`, `delta_deg` validated −359..359.
- `src/belief/crew_console.py` — `increment_ai_heading` extracted from the deleted
  `_handle_turn_heading_relative`, returning an action result (`{"ok", "reason"}`) rather than a
  readback (the rule writes its own, D4/U4); `"turn_heading_relative"` removed from
  `DISPATCHED_COMMAND_TOKENS` and its `elif token == "turn_heading_relative":` dispatch branch
  deleted — no fallback to the old handler (D6/E5).

**audio-adapter**
- `src/command_matcher.py` — the legacy `turn_heading_relative` branch (`parse_turn_relative`,
  `_TURN_RELATIVE_VERB`) deleted; the import removed. The command is now reached only through
  Stage 1b's rule branch (D8), when body-layer has it loaded and the adapter has accepted it.
- `src/vocabulary.py` — `turn_heading_relative` removed from `TOKENS`/`PHRASES`;
  `parse_turn_relative` deleted. The "BL-16 mode 2 Stage P2a's own slot parsers" header comment
  and the `altitude_step` comment that referenced `turn_heading_relative` as a design-pattern
  comparison were updated/pruned to match (per this project's "prune the comment you are standing
  next to" rule) — the `altitude_step` comparison itself is still accurate (both are "relative to
  the AI's own held value," unchanged by the move) and was left as prose, not deleted.

### Tests Added

**body-layer**
- `tests/test_rules_flight_actions.py` — loads the **real**, shipped `config/rules/flight.lua`
  (not a fixture copy) via `DEFAULT_RULES_DIR`, with zero failures asserted; the differential
  pins against the pre-rules `_handle_turn_heading_relative`'s own behaviour for left/right, a
  wrap past 0 and past 360, and `NOT_READY` (Stage 2 item 4's own required test) -- every one of
  these five already goes end to end through the real `ACTION_NAMESPACES`/`flight.
  increment_heading`, so `test_rules_engine.py`'s own placeholder for that end-to-end case
  (written against Stage 1b's then-forthcoming action before the stage split was finalised) was
  removed rather than duplicated here verbatim.
- `tests/test_crew_console_ai_pilot_wheel.py` — `TestTurnHeadingRelative` (which dispatched the
  now-deleted static token) replaced by `TestIncrementAiHeading`, exercising the extracted method
  directly (plan Stage 2 item 4's own "test rewrite, inherent in the token moving").

**audio-adapter**
- `tests/test_command_matcher_rules.py` — a rule matching when active; the "no rules pushed
  behaves exactly as before" pin, from the matcher side, now meaningful because the legacy branch
  is actually gone (D8/Stage 1b's own acceptance test); the widened anchor set letting `angle`'s
  own rejection of `0` reach "say again" rather than silence; two colliding rules reported
  ambiguous; an active rule changing nothing about an existing legacy match or the free-speech
  guard.
- `tests/test_bl16_stage_p2_vocabulary.py` — **required rewrite, not an addition**: `TestParse
  TurnRelative` (tests the now-deleted `parse_turn_relative`) deleted outright;
  `TestMatchTranscriptTurnHeading.test_relative_turn` (asserted `match_transcript("turn right two
  zero")` resolved to `turn_heading_relative` with no `rules=` argument — no longer true, the
  capability moved to a rule) deleted, with a comment pointing at where the same behaviour is now
  covered (`test_command_matcher_rules.py`, `test_rules_flight_actions.py`). Both deletions are
  the exact "pinned matcher tests that referenced the token move to the rule-pattern suite"
  rewrite Stage 2 item 4 names as expected and pre-approved, not a surprise found mid-
  implementation.

### Checks

**body-layer**
- `ruff format --check`: pass
- `ruff check`: pass
- `cd body-layer && .venv/bin/mypy src`: pass (89 source files)
- Full suite (`-n auto`): pass, 3473 passed, 4 xfailed (combined Stage 1b + Stage 2 tree, this
  run's final state). One run of this same full suite showed `test_slew_trace_is_written_from_
  the_real_poll_loop` as a single failure under `-n auto` — it passed standalone and on a second
  full-suite run with no change in between; logged `ValueError: I/O operation on closed file`
  from a background poll-loop thread logging after a stream closed during test teardown, in code
  this stage never touched (`_log_live_los_coverage_summary`/watched-args). Read as pre-existing
  parallel-teardown flakiness, not a regression from either stage — flagged for Reviewer/DoD
  rather than silently reconciled, since it was not independently reproduced a third time.

**audio-adapter**
- `ruff format --check`: pass
- `ruff check`: pass
- `cd audio-adapter && .venv/bin/mypy src`: pass (17 source files)
- Full suite (`-n auto`): pass, 480 passed, 2 skipped (combined Stage 1b + Stage 2 tree).

### Notable Discoveries

1. **A real import cycle between `rule_patterns.py` and `command_matcher.py`, resolved by
   dependency injection, not by moving the collision check.** (Surfaced while wiring Stage 1b's
   collision check against the real legacy matcher for this stage's own rule — recorded here
   since it is this rule's own push that first exercises `_collides_with_legacy` against real
   data.) The plan's own "Affected modules" list puts "collision check (D7–D9)" inside `rule_
   patterns.py`, but D9's rule×legacy check needs the real legacy matcher (`command_matcher.
   match_transcript`), and `command_matcher.py` must import `rule_patterns` for its own D8 rule-
   matching branch regardless of which rules are active. Importing `command_matcher` back into
   `rule_patterns.py` would be a genuine cycle, not a style issue. Resolved by injecting a
   `legacy_probe` callable into `rule_patterns.compile_rules` -- see Stage 1b's own entry above
   for the mechanism; noted again here because this stage's `turn_heading_relative` push is what
   actually exercises the rule×legacy check with the real legacy branch present (during the
   necessarily-temporary period where both the old branch and the new rule briefly coexist in the
   work, before the old branch's deletion in this same stage).
2. **The differential test needed the pre-deletion handler's behaviour recorded from memory/
   source, not from a committed snapshot** -- `plans/speech-rules/plan.md` Stage 2 item 4 asks for
   "a differential test written before the deletion." The actual commit history does not show a
   separate "record old behaviour" commit preceding the deletion commit within this run (both
   land in this one stage's commit) -- the five cases (left/right, wrap past 0/360, `NOT_READY`)
   were taken from the handler's own code and its then-current test class
   (`TestTurnHeadingRelative`) while both still existed in the working tree, immediately before
   removing them, and written into `test_rules_flight_actions.py` as the new differential
   pins. Noted so a reader comparing this run's commits against the plan's own phrasing
   ("written before the deletion") understands why there is one stage commit, not two.

Stages 3+ (the test flight, and the remaining ~80 commands) are explicitly out of this run's
scope per the checkpoint already recorded in `body-layer/ROADMAP/BL-17.md`.

### Security fix (Required Fix 1, `plans/speech-rules/security-stage0-2.md`)

Security's deep analysis (tip `262d5c9d`) flagged two Lua→Python `int(...)` conversions that
checked type and bounds but not finiteness, so a Lua `nan`/`inf` value (trivial via `0/0`/`1/0`,
no stdlib needed) raised a bare `ValueError`/`OverflowError` — not a `lupa.lua54.LuaError` —
that escapes `run_rule`'s own `except (RuleRuntimeError, RuleBudgetExceeded)` uncaught and would
crash the crew-text REPL main thread.

- **`engine.py:_make_action_wrapper`** — added `isinstance(value, float) and not
  math.isfinite(value)` to the existing reject branch, before `int(value)` runs. A rejected call
  now answers `{ok=false, reason=nil}`, same shape as every other out-of-contract argument this
  wrapper already rejects (wrong arity, wrong type, out of bounds).
- **`engine.py:_make_env_builder`'s `digits` global** — replaced the bare
  `lambda n: CrewConsole._digit_readback(int(n))` with a named module-level function,
  `_digits_readback`, that validates `n` (bool/non-numeric/non-finite-float) before calling
  `int()`. Named rather than a lambda so it carries its own docstring and is callable from a
  test without going through Lua. **Superseded by the review-fix round below**: this first pass
  degraded to `render_unable("").text` ("Unable.") on rejection, the same shape as
  `_make_action_wrapper`'s reject branch; Reviewer found that shape wrong for this site
  specifically, and the fix now raises instead — see that section for why.
- **Checked for the same shape elsewhere in `body-layer/src/rules/`** — `engine.py` and
  `loader.py` have no other `int(...)`/`float(...)` conversion of a Lua-supplied value;
  `sandbox.py` performs none (it never receives rule-author-controlled values, only trusted
  module-level setup); `actions.py` has no conversion of its own — its one `Action.invoke`
  (`_increment_heading`) receives an already-validated `int` from `_make_action_wrapper`.
  `audio-adapter/src/rule_patterns.py`'s `int()` calls (`_consume_digit_run`/`_consume_angle`/
  `_consume_heading`/`_consume_oclock`) were out of scope for this fix (Security's own table
  marked them "None" — each is preceded by an explicit digit-membership check on the exact
  string converted).

**Tests added** (`body-layer/tests/test_rules_engine.py`): `test_action_wrapper_rejects_nan_
instead_of_raising`, `test_action_wrapper_rejects_infinity_instead_of_raising` (both via a
`probe.one` action and `0/0`/`1/0`), `test_digits_rejects_a_string_slot_instead_of_raising`
(`digits(s.direction)` with a string slot), `test_digits_rejects_nan_instead_of_raising`. All
four were confirmed red against the pre-fix `engine.py` (bare `ValueError`/`OverflowError`
propagating out of `run_rule`, not caught as `RuleRuntimeError`) before the fix was restored, per
this project's counterfactual-evidence convention.

**Checks** (body-layer): `ruff format --check`, `ruff check`, `.venv/bin/mypy --strict src` all
pass; `.claude/scripts/fast-tests.sh body-layer` (73 targeted files, parallel) — 2737 passed, 4
xfailed (pre-existing, unrelated); `test_rules_engine.py` run individually by name, unfiltered
`-v` — 15 passed, including all four new tests.

## Review-fix round, 2026-11-17 (`plans/speech-rules/review-security-fix.md`, NEEDS REVISION)

Reviewer confirmed, by mutation and by an independent probe, that the security fix closes the
crash (both sites' `nan`/`inf` guards go red the expected way when removed), but found the two
sites are **not architecturally equivalent**, and the security fix's uniform "degrade to Unable."
treatment is only right for one of them:

- **`_make_action_wrapper`'s reject branch is correct as shipped, no change.** Every rule author
  already checks `if not r.ok then return say(unable(r.reason)) end` for an action call (D5 —
  "validation in Python of every value Lua passes in" is the action registry's job); `nan`/`inf`
  joining that same `{ok=false, reason=nil}` reject branch is the same failure class using the
  same established, already-reviewed contract, not a new one.
- **`_digits_readback`'s degrade to "Unable." did not satisfy the user's decision — required
  fix.** `digits` has no equivalent "the rule author checks and handles this" contract; a rule
  just does `say(digits(n))` with nothing to check. Degrading to `render_unable("").text`
  produced no stderr log (`_digits_readback` never raised and never called `logger.error`) and
  spoke "Unable.", which this project's convention reserves for a legitimate precondition
  failure — but `digits(s.direction)` on a string slot is a rule-file bug (a porting mistake),
  exactly the class the user's own BL-17 decision names: *"Rule clash or lua error etc -> std
  error log and say aloud 'action file error'"* (`BL-17.md`) and D6. The fix now raises
  `RuleRuntimeError(...)` naming what was received (the non-numeric value, or that it was
  non-finite) instead of returning `render_unable("").text`; `RuleRuntimeError` is already
  imported into `engine.py` and is one of the two exception types `run_rule`'s own `except`
  clause names, so it propagates untouched and is caught correctly, routing through D6's existing
  path (stderr log with the rule id/file/message, "Action file error." readback, one-shot state
  rollback via `_handle_rule`) instead of a silent, unlogged "Unable."

Also deleted the now-dead docstring sentence explaining why `""` is not one of D11's closed
reason tokens — there is no more `render_unable` call in `_digits_readback` for it to describe.

**Tests updated** (`body-layer/tests/test_rules_engine.py`): `test_digits_rejects_a_string_slot_
instead_of_raising` → renamed `test_digits_rejects_a_string_slot_as_a_dispatch_error`, and
`test_digits_rejects_nan_instead_of_raising` → renamed `test_digits_rejects_nan_as_a_dispatch_
error` (the old names now misdescribe the behaviour — both cases *do* raise, inside the sandbox,
and surface as a dispatch error). Both now assert `outcome.lines == []` and `outcome.error is
True`, the same shape `test_a_lua_error_during_dispatch_is_reported_as_error` already asserts for
a genuine Lua error, instead of the old `outcome.lines == ["Unable."]` / `outcome.error is False`.
The two action-wrapper tests (`test_action_wrapper_rejects_nan_instead_of_raising`,
`test_action_wrapper_rejects_infinity_instead_of_raising`) are unchanged — that half of the fix
was confirmed correct as shipped.

**Checks** (body-layer, from inside `body-layer/`): `ruff format --check`, `ruff check`,
`.venv/bin/mypy --strict src` all pass; `.claude/scripts/fast-tests.sh body-layer` — see the
Checks section of the Implementer's report for the fresh run's numbers.

## Stage 3a — matching foundation: fuzzy words, number words, performance (2026-11-17)

Builds D13 (literal fuzz), D14 (number-word slot types), D15 (the two performance fixes) exactly
as scoped. **audio-adapter only** — no body-layer change, per Stage 3a's own boundary ("built and
tested without touching `handle_command`"); confirmed nothing in body-layer imports anything
touched here.

### Files changed

- `audio-adapter/src/vocabulary.py` — `_WORD_REPAIR_FLOOR` **relocated here** from
  `command_matcher.py` (see "Plan departure" below); `_static_recognised_words()`/
  `_STATIC_RECOGNISED_WORDS` split out of `recognised_words()` so the fixed `PHRASES`/slot-table
  walk runs once at import time, not on every call (D15 item 2, first half).
- `audio-adapter/src/rule_patterns.py` — the bulk of the stage:
  - `_UNITS_WORDS`/`_TEENS_WORDS`/`_TENS_WORDS`, `_consume_small_number_word`,
    `_consume_number_word_phrase` (the terminating-grammar composer: a bare units multiplier +
    "hundred" + an optional trailing small number), `_consume_natural_number` (digit run vs.
    word-phrase, with the one "single units word immediately followed by 'hundred'" override),
    `_consume_quantity`, `_consume_speed_target` (D14). `_consume_angle` rewritten to use
    `_consume_natural_number` (D14's "Corrected 2026-11-17" note — `angle` gains the same
    grammar `quantity` does, keeping its own 1–359 range check and 1–3 digit bound).
    `SLOT_TYPES` gains `quantity`/`speed_target`.
  - `_literal_ratio`, `_match_elements` (now returns `(slots, next_index, literal_ratios)`),
    `match_pattern_with_ratio` (new), `match_pattern` (now a thin wrapper discarding the ratio) —
    D13's literal fuzz. `WordSetElement`/`SlotElement` branches are untouched (no ratio path at
    all), which is what keeps E12 true.
  - `_COLLISION_PROBE_WORDS`, `_best_probe_word`, `_sample_words_with_literal_flags`,
    `_perturbed_sample`, `_samples_with_perturbation`, widened `_rules_collide`/
    `_collides_with_legacy` — D13's widened D9 collision check (one perturbed sample per rule,
    probed against both other rules and the legacy matcher).
  - `rule_anchor_words` — **moved here from `command_matcher.py`** (D15 item 1): a pure function
    of `CompiledRule` alone, so it belongs beside `CompiledRule`, and moving it is what lets
    `RuleRegistry.swap` compute it once rather than `command_matcher` rebuilding it per
    transcript.
  - `RuleRegistry` gains `anchor_words: frozenset[str]` and a `swap(rules, version)` method that
    sets all three fields together (D15 item 1).
  - `CachedRulePromptProvider` (new) — a callable that only rebuilds the whisper prompt when
    `registry.version` changes (D15 item 2, second half).
- `audio-adapter/src/command_matcher.py` — `_rule_anchor_words` deleted (moved, see above).
  `_match_rules` rewritten: uses `match_pattern_with_ratio`, no longer sorts the full `rules`
  tuple per call (only the small matched subset, for the tie-break), computes a real ratio and
  applies `SEPARATION_MIN` between the best two matches instead of "2+ matches is always a tie."
  `match_transcript` gains an `anchor_words` parameter (D15) and is restructured: the legacy
  pipeline (verb anchor through the phrase table and its own separation check) is extracted
  verbatim into a new `_match_legacy`; `match_transcript` now always runs both pipelines (no
  early return on a rule match) and compares their ratios with the same `SEPARATION_MIN`
  disposition two legacy phrases already get (D13's own explicit requirement: "`match_
  transcript`'s ambiguity check applies `SEPARATION_MIN` between rule matches (and between a rule
  match and a legacy match)").
- `audio-adapter/src/server.py` — `_handle_put_rules` calls `rule_state.swap(...)` instead of two
  separate field assignments; `_handle_transcribe` passes `anchor_words=rule_state.anchor_words`
  to `match_transcript`.
- `audio-adapter/src/audio_adapter/__main__.py` — `_rule_prompt_provider` closure replaced by
  `CachedRulePromptProvider(rule_registry, _build_rule_prompt)`; the 224-token-cap warning logic
  stays here (injected as `_build_rule_prompt`), only the caching moved into the testable class.
- `audio-adapter/CLAUDE.md` — updated the `rule_patterns.py`/`command_matcher.py` Structure
  entries, which had gone stale in three concrete ways the moment this stage's own code landed:
  the slot-type list was missing `quantity`/`speed_target`; "`parse_pattern`/`match_pattern`
  (full-consumption, exact-literal)" was now flatly wrong (D13 made it fuzzy on literals); and
  `match_transcript`'s documented signature/behaviour (no early return, no `anchor_words` param)
  no longer matched the code. Not asked for in the brief, but these are the exact comments this
  stage's own changes stood next to.

### Plan departures (reversible, decided locally)

1. **D13 says `_WORD_REPAIR_FLOOR` is "imported from `command_matcher.py`."** That is a real
   import cycle: `command_matcher.py`'s own module docstring and implementer memory
   (`project_bl17_rule_matcher_cycle_and_scoping.md`) already establish that `rule_patterns.py`
   must never import `command_matcher.py` — each module needs a name from the other that is
   defined only after its own import statement runs, so the cycle is genuine regardless of import
   order, not a style nit. **Decision:** relocated the one constant to `vocabulary.py` (a
   dependency of both, and of neither), which both modules now import — same value (0.5), same
   name, one declaration site, matching D13's actual intent ("not a second hand-tuned number")
   without the cycle. No test referenced `command_matcher._WORD_REPAIR_FLOOR` by its old location,
   so nothing else needed to change. Reversible if the user wants a different home for it.
2. **D13's own Stage 3a test-list item contradicts itself, in the same sentence.** The plan's
   test list says: *a mis-transcribed literal ("turn *lift* two zero") still matches; "right" is
   never fuzzy-repaired into a slot value anywhere (E12 pin)*. But in the shipped
   `turn_heading_relative` pattern, "left"/"right" are a `WordSetElement`'s own values, not a
   `LiteralElement` — and E12 (`alignment.md` line 292, "a number, a direction (left/right) ...")
   explicitly names "left/right" as values that must be heard exactly. Measured:
   `ratio("lift","left") = 0.75` (would match if word-sets were fuzzy), `ratio("lift","turn") =
   0.25` (nowhere near matching the literal) — so the example only makes sense as a fuzzy
   *word-set* match, which the same sentence's own E12 clause forbids. Confirmed against the
   shipped parser: `match_pattern` on `"turn lift two zero"` returns `None`. **Decision:** built
   the literal-fuzz-only design the rest of D13/E12/alignment.md's own resolution table
   unambiguously specifies (`alignment.md` line 494: "E12 | Stage 3a (D13) | met — a
   `SlotElement`/`WordSetElement` never gets the fuzzy fallback"), wrote the "mis-transcribed
   literal still matches" test against the rule's actual literal ("turn" → "turm", ratio 0.75),
   and added a *separate* test asserting "turn lift two zero" does **not** match, pinning E12
   directly rather than silently reinterpreting the plan's own contradictory sentence. This is the
   same shape of defect the plan-aligner's own memory
   (`project_bl17_test_list_claims_a_fix_its_own_exclusion_rules_out.md`) flags from this same
   revision's earlier check — not a one-off, worth a second look if a future stage's test list
   names a specific phrase again.
3. **`match_transcript` now always runs the legacy pipeline, even when a rule already matched.**
   Required by D13's own wording ("applies `SEPARATION_MIN` between a rule match and a legacy
   match"), not a choice — but worth naming as a real (small) cost: before this stage, a matched
   rule short-circuited before the legacy verb-anchor/phrase-table scan ever ran; now it always
   runs both. The measured per-call costs in `performance-stage0-2.md` were 3+ orders of magnitude
   below whisper-cli's own subprocess latency, and the legacy phrase-table scan is the same
   O(number of phrases) work that already runs on every *non*-rule-matching transcript today, so
   this is not expected to matter, but it was not previously paid on a rule hit and now is —
   flagged for Performance's own batch review rather than asserted safe.

### Tests Added

`audio-adapter/tests/test_rule_patterns.py` (29 new tests, 6 new classes): `TestCompileRules` +2
(the perturbed-sample collision catch, and its own counterfactual showing the pair does not
collide without perturbation); `TestLiteralFuzz` (6: mis-transcribed literal match, exact literal
still 1.0, a wholly unrelated literal still rejected, the word-set E12 pin, the slot E12 pin, no
literal at all defaults to ratio 1.0); `TestQuantitySlot` (parametrized over every Q10 form plus
the two paired-form rejections); `TestSpeedTargetSlot` (max / a round number / digit-by-digit);
`TestAngleNumberWords` (turn left thirty, turn left three fifteen rejected, digit forms still
pass, heading/oclock unaffected); `TestRuleAnchorWordsAndRegistrySwap` (empty rules, first-literal
derivation, a call-count spy proving `RuleRegistry.swap` computes `rule_anchor_words` exactly
once per swap); `TestCachedRulePromptProvider` (a call-count spy proving the builder is not
re-invoked until `registry.version` changes).

`audio-adapter/tests/test_command_matcher_rules.py` (10 new tests): mis-transcribed literal
resolves the rule; the word-set value mis-transcription does not (E12, at `match_transcript`
level); "turn left thirty" resolves via number words; "turn left three fifteen" does not; a real
cross-pipeline collision found while writing the fuzz test (`"tern"` scores exactly `VERB_FLOOR`
against `step`'s own verb, so it anchors both pipelines — `step` wins outright at a 0.25 gap, not
ambiguously, pinning that the comparison is a genuine one, not a formality); a rule/legacy exact
tie is `ambiguous=True`; a rule wins outright with nothing competing; precomputed `anchor_words`
gives the same result as the fallback; a call-count spy proving `match_transcript` never calls
`rule_anchor_words` when `anchor_words` is supplied, plus the counterfactual proving the spy
itself calls through when it is omitted.

### Checks (audio-adapter)

No `.venv` existed in this worktree (fresh worktree, `.venv/` is gitignored) — per implementer
memory (`feedback_worktree_use_main_checkout_venv.md`), ran the main checkout's already-built
`audio-adapter/.venv` binaries directly, with `cwd` set inside this worktree's `audio-adapter/`
(same `pyproject.toml` at the shared base commit, no install step needed):

- `ruff format --check src tests`: pass (36 files)
- `ruff check src tests`: pass
- `mypy src` (the mandated command — `tests` is not part of it per this subproject's own
  `CLAUDE.md`, and `mypy src tests` surfaces 7 pre-existing, unrelated errors in three files I did
  not touch: `test_transcribe_api.py`, `test_rules_api.py`, `test_ptt_source.py`): pass, 17 source
  files, 0 issues.
- `pytest -q` (full suite — `.claude/scripts/fast-tests.sh` could not resolve a venv in this
  worktree at all, so the full run substitutes for it rather than the targeted subset; it is a
  strict superset of what the fast script would check): **519 passed, 2 skipped** (the two
  pre-existing skips are `AUDIO_ADAPTER_PIPER_URL`/whisper-binary env-gated live tests, unrelated).
  480 passed before this stage; the +39 are all new (29 + 10, above).

**body-layer**: not touched, per Stage 3a's own scope boundary — no checks run.

### Notable Discoveries

- **A real cross-pipeline collision surfaced while writing the literal-fuzz test**: "tern" (a
  plausible mis-hearing of "turn") scores *exactly* `VERB_FLOOR` (0.5) against `step`'s own verb
  anchor, so "tern left two zero" anchors onto both `turn_heading_relative` (ratio 0.75, D13's
  fuzz) and the legacy `step` command (`_parse_step_slots` reads "left" as a direction, ratio
  1.0). `step` wins outright (gap 0.25, past `SEPARATION_MIN`) — correct behaviour, but it is a
  live demonstration that D13's widened matching genuinely creates new cross-pipeline near-misses
  worth watching for once more rules ship with longer literal vocabularies that overlap more of
  the legacy verb space.
- **The "digit-run vs. number-word-phrase" ambiguity needed one explicit override, not two
  independent grammars.** A bare digit-run interpretation of "three" (one word, value 3) and the
  word-phrase interpretation of "three hundred" (two words, value 300) both start by consuming
  "three"; without the override in `_consume_natural_number` (digit-run wins unless it consumed
  exactly one bare *units word* immediately followed by literal "hundred"), "three hundred"/"two
  hundred" would silently resolve to 3/2 with "hundred"/"twenty" left over, failing the whole
  rule rather than parsing the natural number — a defect that would have shipped invisibly
  (wrong number, not a crash) had it not been checked against the stated examples before writing
  tests.
- **D15's "sort the rules tuple once" turned out to need no caching at all.** The original
  `_match_rules` sorted the *entire* active rule set by id on every call just to get a
  deterministic tie-break order. Scoring every rule first and sorting only the (typically tiny)
  *matched* subset by `(-ratio, id)` afterward gives the same determinism without ever touching
  `rules`' own order — so `RuleRegistry` did not need a second cached "pre-sorted rules" field
  alongside `anchor_words`; only the anchor-words and prompt caching (both genuinely
  recomputations of a derived value, not an ordering) needed the `RuleRegistry.swap`/
  `CachedRulePromptProvider` machinery.

### Stage 3b (this run) — rule categories and dispatch gates

Builds D16 exactly as the plan's "Stage 3b" section lays it out: `CrewState`, `GateOutcome`
(`PASS`/`HOLD(reason)`/`UNABLE(reason)`), the closed `GATE_REGISTRY` (`"always"`/
`"flight_control"`), the `when.speech(id, pattern, category, handler)` signature change, the
hold-and-retry mechanism (`pending_rule_dispatch`/`drain_pending_rule_dispatch`/
`RULE_GATE_HOLD_TIMEOUT_S`), `turn_heading_relative`'s migration to `category="flight_control"`,
and `increment_ai_heading`'s dead-code removal. No new rules, no Stage 3c/3d/4 work.

### Files Changed

**body-layer**
- `src/belief/crew_state.py` — new. `CrewState` (frozen dataclass): `has_controls`, `settling`,
  `seat`/`hands_free`/`eyes_free` (named stubs pending `[[BL-B123]]`, per the plan's own wording).
  A leaf module (depends on nothing from `belief.crew_console`/`rules.*`) so it can be imported
  from either side with no cycle.
- `src/rules/gates.py` — new. `GateOutcome`, `GateFn`, the closed `GATE_REGISTRY` (`_always`
  always `PASS`; `_flight_control`: `UNABLE("NOT_FLYING")` if not `has_controls`, `HOLD("NOT_READY")`
  if `settling`, else `PASS`), `check_gate` (an unregistered category degrades to
  `UNABLE("NO_SUCH_COMMAND")`, defensive).
- `src/rules/loader.py` — `RawRegistration` gains `category: str = "always"`. The default exists
  only so `test_rules_loader.py`'s own deliberately simplified fake env builder (predates
  categories, never supplies one) keeps working unmodified — the real env builder always sets it
  explicitly.
- `src/rules/engine.py` — `CompiledLuaRule` gains a required `category: str`; `_dedupe` carries
  it through from `RawRegistration`. `_build_when_table`'s `speech` closure takes `*args` rather
  than four named parameters (see "Plan departures" below) and validates arity, id, pattern,
  category (against `GATE_REGISTRY`, imported from `rules.gates`) and handler, in that order,
  before constructing `RawRegistration`. `RuleSet.ids_and_patterns()` widened to return
  `(id, pattern, category)` triples (method name kept — the plan's own affected-files list did
  not ask for a rename, and the three call sites this touches are the only callers).
- `src/belief/crew_console.py` — imports `belief.crew_state.CrewState` and `rules.gates.
  check_gate` (see "Plan departures" below on why this does not reopen D4's import-cycle
  concern); `RULE_GATE_HOLD_TIMEOUT_S` (`tuning.real`, 5.0s, lo 1.0/hi 15.0, status
  `"agreed-guess"`, U20); `PendingRuleDispatch` (frozen dataclass: `rule_id`/`slots`/`category`/
  `held_since_sim`); new fields `rule_categories: dict[str, str]` and
  `pending_rule_dispatch: PendingRuleDispatch | None`; `set_enabled_rule_ids` gains an optional
  `categories` parameter (writes `rule_categories` alongside `enabled_rule_ids`, `None` meaning
  "leave it alone" so a test fake that never cares about gating keeps working); `current_crew_
  state()` (built fresh from `parked_flight_state` every call); `_dispatch_rule` (the actual
  `rule_runner` call plus D6's error rollback, factored out so `_handle_rule`'s `PASS` and
  `drain_pending_rule_dispatch`'s later `PASS` share it); `_handle_rule` now runs the gate before
  ever calling the runner; new `drain_pending_rule_dispatch`; `reset_for_new_mission`'s docstring
  updated (`rule_categories` joins `enabled_rule_ids`'s "resets, repopulated synchronously"
  group; `pending_rule_dispatch` joins the plain-reset-to-default list — both auto-verified by
  `test_mission_start_reset.py`'s existing field-enumeration test, no edit needed there);
  `increment_ai_heading`'s `current is None -> NOT_READY` branch removed, replaced by `assert
  current is not None` (D16/D18: dead code once the gate owns the precondition).
- `src/belief/speech.py` — `_UNABLE_TEMPLATES` gains `"NOT_FLYING"`/`"HANDS_BUSY"` (declared now
  per the plan item 6, even though `"HANDS_BUSY"` stays unreachable until a later stage).
- `src/body.py` — new `_rule_categories(rule_set)` helper (`rule_id -> category`); all three
  `set_enabled_rule_ids` call sites (mission-restart reload, `_push_rules`, `main()` startup) now
  pass it; `_push_rules`'s docstring updated; `--print-rules` prints each rule's category;
  `drain_pending_rule_dispatch(runner.last_t_sim)` called once per poll beside `drain_ai_pilot_
  wheel_speech`, after `parked_flight_state` is refreshed.
- `config/rules/flight.lua` — `turn_heading_relative`'s registration gains `"flight_control"` as
  its third argument.
- `config/rules/README.md` — `when.speech`'s signature line, the worked example, a new
  "Categories" section (the `always`/`flight_control` table), and the "Failures" section mention
  a missing/unrecognised category.
- `config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`); carries
  `RULE_GATE_HOLD_TIMEOUT_S`.
- `src/belief/audio_client.py` — `put_rules`'s `rules` parameter widened to `list[tuple[str, str,
  str]]` (`id, pattern, category`); payload gains `"category"` per rule.

**audio-adapter**
- `src/rule_patterns.py` — `CompiledRule` gains `category: str = "always"`. `compile_rules`'s own
  signature and matching/collision logic are **unchanged** (see "Plan departures" below) —
  category plays no part in matching in this stage.
- `src/server.py` — `_handle_put_rules` parses and validates `category` per rule (same 400 shape
  as a missing `id`/`pattern`), then attaches it to each accepted `CompiledRule` via
  `dataclasses.replace` *after* `compile_rules` returns.
- `CLAUDE.md` — the `PUT /rules` paragraph updated for the wire shape and validation change.

### Plan departures (reversible, decided locally)

- **`compile_rules`'s own signature stays `list[tuple[str, str]]` (id, pattern) — `category` is
  attached to the accepted `CompiledRule`s afterward, in `server.py`, rather than threaded through
  `compile_rules` itself.** The plan's own D16 text says category is "not yet read by anything in
  this stage" on the adapter side, and `compile_rules`'s matching/collision-check logic genuinely
  never needs it. Threading it through would have required rewriting all eight existing
  `TestCompileRules` call sites in `test_rule_patterns.py` (2-tuples, none of which are about
  categories) for no behavioural gain. Reversible: if a later stage needs category available
  *inside* `compile_rules` itself (not just carried on the output), widening the signature then
  costs the same rewrite either way.
- **`when.speech`'s Python-side closure takes `*args` and validates arity itself, rather than four
  named parameters.** Discovered while updating the shipped literal `when.speech(...)` calls in
  `test_rules_engine.py`'s own fixtures: lupa propagates a Python exception raised inside a
  callback Lua calls *unwrapped* (confirmed in `research/2026-11-17-lupa-sandbox.md`, "a Python
  `RuntimeError`-derived exception raised inside the hook propagates"). A plain 4-parameter Python
  function called from Lua with the old 3-argument shape would raise a bare `TypeError` that
  `sandbox.run_with_budget`'s `except lua54.LuaError` clause does not catch and `loader.load_rules`'s
  `except (RuleCompileError, RuleRuntimeError, RuleBudgetExceeded)` does not catch either — it
  would propagate out of `load_rules` entirely, discarding the whole file (and crashing a bare
  `RuleSet.load` call) instead of D6's own finest-grain "disable just the one bad rule." `*args` +
  an explicit `len(args) != 4` check turns a wrong-arity call into an ordinary `RuleLoadError` the
  same way a bad id/pattern/category/handler already is. This is implementation technique, not a
  behaviour change — U19's own "a missing category is a load error, not a default" is unaffected.
- **`CrewConsole` importing `rules.gates` is not a reopening of D4's import-cycle rule — it is a
  narrowing of it.** D4's own stated reason ("avoids a `belief` <-> `rules` import cycle") is
  about the *handler* indirection: `rules.engine`/`rules.actions`/`rules.loader` import
  `belief.crew_console.CrewConsole` (to reach `increment_ai_heading`), so `crew_console.py`
  importing any of those three back would be the real cycle. `rules.gates` imports only `belief.
  crew_state.CrewState` — a leaf module with no edge back to `crew_console.py` — so `crew_console.
  py` importing `rules.gates` directly creates no cycle. The plan's own D16 text already says
  this explicitly ("`gates.check_gate(category, self.current_crew_state())`" called from
  `_handle_rule`), so this is executing the plan as written, not a departure from it — flagged
  here only because the `rule_runner` field's own pre-existing docstring overstated the rule as
  "imports nothing from `rules.*`" and needed correcting (pruned in the same edit, per root
  `CLAUDE.md`'s "Prune the comment you are standing next to").

### Tests Added

**body-layer**
- `tests/test_rule_gates.py` (new, 6 tests) — pure-Python `rules.gates` tests, no Lua: `"always"`
  passes regardless of state; `"flight_control"` is `UNABLE("NOT_FLYING")` with no controls,
  `HOLD("NOT_READY")` while settling, `PASS` once flying and settled; an unregistered category
  degrades to `UNABLE("NO_SUCH_COMMAND")`; the registry holds exactly the two categories this
  batch declares.
- `tests/test_rules_engine.py` (3 new tests, plus a category argument added to all 17 existing
  `when.speech(...)` literal fixtures) — a valid category loads and is carried on the compiled
  rule; an unrecognised category disables only that rule, the file's other rule is unaffected;
  the pre-D16 three-argument shape degrades to a load error, not a crash (see "Plan departures").
- `tests/test_crew_console_rules.py` (7 new tests, via a new `_flight_console_with_rule` helper)
  — gate `PASS` runs the handler unchanged from today; `UNABLE` speaks the reason and never calls
  the runner (a spy runner asserting zero calls); `HOLD` sets `pending_rule_dispatch` and speaks
  nothing; `drain_pending_rule_dispatch` resolves to `PASS` on a later poll, not at dispatch time;
  stays `HOLD` and is silently retried under the timeout; times out to `render_unable`; a second
  held command replaces the first with no line spoken for the dropped one (U21).
- `tests/test_rules_flight_actions.py` — **one existing test replaced**, not just added-to: see
  "Notable Discoveries" below. Three new tests load the **real** shipped `flight.lua` through the
  real dispatch path (`CrewConsole.handle_command`/`drain_pending_rule_dispatch`): `NOT_FLYING`
  when `parked_active` is `False`; held-then-passed when `settling` resolves within the timeout
  (the handler actually runs and speaks on the later poll, not at dispatch time); held-then-unable
  once `RULE_GATE_HOLD_TIMEOUT_S` elapses while still `HOLD`.
- `tests/test_crew_console_ai_pilot_wheel.py` — **one existing test replaced**: see "Notable
  Discoveries" below.
- `tests/test_audio_client.py` — the two existing `put_rules` call sites that named a concrete
  rule gained a `"flight_control"` category argument and the expected payload gained the
  `"category"` key; no new tests (the shape widening is exercised by the existing round-trip
  assertions).

**audio-adapter**
- `tests/test_rules_api.py` — 2 new tests (`category` missing is a 400; `category` non-string is
  a 400) plus `"category"` added to every existing rule dict that previously omitted it (five
  call sites) so those tests keep exercising acceptance/collision logic rather than failing on
  the newly-required field.

### Checks

**body-layer** (fresh `.venv` built from `/opt/homebrew/bin/python3.14`, `pip install -e .` +
`lupa==2.8` + `ruff`/`mypy`/`pytest`/`pytest-xdist`; no editable install of `world-model` needed —
confirmed by tracing `perception.association`'s/`query.describe`'s own import graph that body-layer
only ever reaches `coordinates`/`query`/`store`/`geometry`/`projections`/`schema`/`models`, none of
which import `osmium`/`pillow`/`scipy`, so body-layer's own declared `pyproj`/`numpy` are enough;
`pythonpath = ["src", "../world-model/src"]` in `pyproject.toml` makes the source importable):
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (CWD-only config discovery, run from inside `body-layer/`): pass, 91 source files, 0
  issues
- `.claude/scripts/fast-tests.sh body-layer`: 1 failed (the pre-existing, unrelated
  `test_shipped_effector_config_loads_without_errors` — empty row in the user's own
  `config/sequences/mi-24p/seat-copilot.md`, named as a known failure in this run's own task
  brief), 2635 passed
- `.claude/scripts/fast-tests.sh --full body-layer`: same single pre-existing failure, 3493
  passed, 4 xfailed

**audio-adapter** (fresh `.venv`, same Python, `pip install -e .` + dev tools; this subproject
declares no runtime dependencies):
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (the mandated command): pass, 17 source files, 0 issues. `mypy tests` surfaces 7
  pre-existing errors in three files this stage never touches (`test_transcribe_api.py`'s
  `_NullSink` missing `interrupt`, `test_rules_api.py`'s `body["..."]` indexing on `object`,
  `test_ptt_source.py`'s `cast` argument) — confirmed pre-existing by running the same `mypy`
  invocation against the `c97731c0` tip's copy of each file before this stage's edits.
- `.claude/scripts/fast-tests.sh audio-adapter`: 467 passed, 2 skipped
- `.claude/scripts/fast-tests.sh --full audio-adapter`: 521 passed, 2 skipped

### Notable Discoveries

- **The plan's own Stage 3b test list missed two existing tests it should have named** (root
  `CLAUDE.md`'s own "the missing entry is the dangerous one" risk, realised twice in this run).
  Removing `increment_ai_heading`'s `current is None -> NOT_READY` branch (explicitly instructed
  by D16/D18) breaks any test that calls the method, or dispatches `turn_heading_relative`,
  *directly* with no held heading — bypassing the new gate the same way these tests always
  bypassed the old static dispatch branch:
  - `tests/test_rules_flight_actions.py::test_unable_without_a_known_current_heading` — named in
    the plan's own "Differential tests before deletion" precedent (Stage 2), so at least
    plausible it would be touched; replaced with three new gate-level tests through the real
    dispatch path (see "Tests Added" above) rather than left pinning dead code.
  - `tests/test_crew_console_ai_pilot_wheel.py::TestIncrementAiHeading::
    test_unable_without_a_known_current_heading` — **not named anywhere in the plan**, found only
    by running the fast-tests full-suite check after the rest of Stage 3b was green; it calls
    `console.increment_ai_heading(-20)` directly with a bare `_console()` (default `ParkedFlight
    State`, `held_heading=None`) and asserted the old `{"ok": False, "reason": "NOT_READY"}`
    result. After the dead-code removal this now raises `AssertionError` (the precondition the
    gate owns is violated) — replaced with `pytest.raises(AssertionError)`, documenting that the
    contract changed rather than silently working around it. This is exactly the "coverage
    disappears without a failing build" risk the role instructions name: a `grep` for `NOT_READY`
    across `tests/` before starting would have found it in under a minute, and is worth doing
    before any future `increment_*`-shaped action gains a similar gate.
- **`lupa` genuinely propagates a raw Python exception through a Lua call boundary, confirmed
  against real code, not just the Stage 0 research note's own probe.** Updating the 17 literal
  `when.speech(...)` Lua fixtures in `test_rules_engine.py` to the new 4-argument shape would have
  been purely mechanical (`sed`) had the old 3-argument shape not needed graceful handling too —
  see "Plan departures" above for why `*args` was the fix rather than accepting the crash.
- **The `#:` tuning comment's first sentence broke the generator's own sentence-splitter on
  "e.g."** `RULE_GATE_HOLD_TIMEOUT_S`'s first draft read "...gate said `HOLD`, e.g. the
  takeover-settle window) before giving up..." — `generate_defaults.py`'s `_first_sentence` splits
  on any period not adjacent to a digit, with no abbreviation guard, so "e.g. the" split the
  rendered description mid-clause. Caught by reading the **rendered** `config/defaults.toml`
  itself, per root `CLAUDE.md`'s own instruction on this exact failure mode, not by re-reading the
  source comment. Fixed by rewording to avoid any embedded ". " in the first sentence at all
  ("such as" in place of "e.g.") rather than teaching the generator about abbreviations.
