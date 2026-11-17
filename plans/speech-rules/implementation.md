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

---

## Stage 3a review fix (2026-11-17)

Addresses the one Required Fix from `plans/speech-rules/review-stage3a.md`: D14's composed
number-word grammar (`angle`/`quantity`/`speed_target` accepting "twenty"..."ninety",
"thirteen"..."nineteen", "hundred") taught the *matcher* these words but never reached whisper's
prompt bias via `rule_words()`/`vocabulary.to_prompt()`.

**The review's suggested shape was built, then reverted on user direction mid-task.** First pass
added a `vocabulary_words: tuple[str, ...]` field to `SlotType`, populated for `angle`/`quantity`/
`speed_target` with the teens/tens words plus `"hundred"` (and `"max"` for `speed_target`), folded
into `rule_words()`/`_words_in()` — exactly the review's own suggested mechanism. The user
overrode this before it was committed, verbatim:

> *"Writes all number formats as text vocabulary is very impractical. There's a ton of
> permutations. Nope. Numbers STT as numeric, please."*

So that field and its population were removed again; `rule_patterns.py`'s `SlotType`/`SLOT_TYPES`/
`_words_in`/`rule_words` are back to their pre-fix shape, byte-for-byte, apart from `rule_words`'s
own docstring (below).

**Why "no prompt change" is the right fix, not a dodge:**

1. **Whisper already writes recognised numbers as digit numerals, independent of the prompt's own
   wording.** `research/2026-09-19-whisper-contract-and-grammar-probe.md` measured this directly:
   "three o'clock" decodes to `"3 o'clock"` on both benched models, even though the prompt's own
   static vocabulary carries the *spelled* digit words ("zero".."nine", via `_DIGIT_NAMES`) for
   exactly this reason already. If spelling a word into the prompt does not push the transcript
   toward that spelling for single digits, there is no mechanism by which spelling "thirty" into
   the prompt would push the transcript toward text "thirty" instead of numeral "30" either — the
   normalisation is a property of whisper's own output formatting, not of what the prompt contains.
2. **The numeral-token path this needs already exists and is already tested, independent of D14.**
   `_consume_digit_run` treats any `word.isdigit()` token (a whole already-collapsed numeral like
   "45", not just single digit words) as a digit run and concatenates its characters —
   `TestAngleSlot.test_whole_number` (`tests/test_rule_patterns.py`, predates this stage) pins
   exactly this for `"turn right 45"`. So whatever numeral text whisper actually produces for a
   spoken "thirty" ("30") is already parsed correctly by the pre-D14 grammar, with zero prompt
   bias required.
3. **D14's spelled-word grammar therefore stays what it always was underneath: a fallback**, for
   the rarer case whisper emits the spelled word instead of the numeral. No change needed there
   either — ordinary English number words are exceedingly common in general training data, unlike
   this project's actual out-of-distribution vocabulary (callsigns, "Petrovich", weapon names),
   which is what the prompt bias mechanism exists to help with in the first place.

**Decision, going forward:** D14's number-word grammar is unbiased by design, not by oversight —
documented in `rule_words()`'s own docstring rather than only here, since that is the function a
future reader will land on when wondering why these words are absent from the prompt.

### Files Changed

- `audio-adapter/src/rule_patterns.py` — `rule_words()`'s docstring corrected: the old claim ("a
  slot's own value words... are already covered by `vocabulary.py`'s own digit/time words") was
  true before D14 and stopped being true the moment `angle`/`quantity`/`speed_target` gained
  composed number words with no `vocabulary.py` equivalent (the review's own finding) — now states
  the actual, deliberate reason these words stay out of the prompt (points 1-3 above, condensed,
  with the research note and the pinning test named). No other production code changed; `SlotType`/
  `SLOT_TYPES`/`_words_in`/`rule_words()`'s behaviour is identical to pre-fix Stage 3a.

### Tests Added

- `audio-adapter/tests/test_rule_patterns.py`, `TestRuleWordsNeverCarriesComposedNumberWords` (1
  parametrized test, 3 cases: `<n:quantity>`, `<degrees:angle>`, `speed <target:speed_target>`) —
  a regression pin for the decision above: `rule_words()` on a rule using any of these three slot
  types must never add a teens/tens word or `"hundred"` to the prompt bias. The expected word set
  is derived from `rule_patterns._TEENS_WORDS`/`_TENS_WORDS` directly (plus `"hundred"`), not a
  hand-copied list, so it cannot silently drift from the grammar's own tables if either grows. This
  is the test the original review asked for, reshaped to pin the opposite outcome from its
  suggested mechanism, per the override above.

### Checks (audio-adapter)

Fresh `.venv` built from `/opt/homebrew/bin/python3.14` (none existed in this worktree):

- `ruff format --check src tests`: pass (1 file — the new test — needed `ruff format`, then clean)
- `ruff check src tests`: pass
- `cd audio-adapter && .venv/bin/mypy src`: pass, 17 source files, 0 issues
- `.claude/scripts/fast-tests.sh audio-adapter`: pass, 468 passed, 2 skipped (smoke + 15 targeted
  files, parallel)
- `pytest -q` (full suite, run once to confirm the exact pre/post delta): 522 passed, 2 skipped —
  519 passed before this fix (per the review's own run), +3 the new parametrized test's cases.

---

## Stage 3a review fix, round 2 — E12 revised: directive words become fuzzy (2026-11-17)

A second, independent user decision landed in the same task, widening E12 further: a
`WordSetElement` (a closed-set directive — "left"/"right", a scan direction) is no longer an
exact-only value. It is now fuzzy like a `LiteralElement`, scored as part of the same
command phrase; only a genuinely open-ended value (a number, a landmark name) stays exact. Three
messages, in the order they arrived, because each corrected the one before it:

1. **The core decision**, verbatim:

   > *""Turn left 30" I would read it like "Turn" is base command, "Left" is sub part of command,
   > "30" is value. ... I'd want fuzzy matching for "turn left" and "scan ahead". Even more so
   > because the command base word and its directives form a short sentence that makes it easier
   > to match against something that was kinda almost heard properly."*

   So: `WordSetElement` fuzzes like a literal; the base word and its directives score together as
   one phrase; numeric/slot values stay exact; a heard word within `SEPARATION_MIN` of two
   alternatives must not be silently picked (E3 — "say again"); "left"/"right" must never swap.

2. **Clarifying where the line actually is**, verbatim:

   > *"Values would be numeric values, unit class/type, landmark name etc. — things that can be
   > truly arbitrary instead of like one of five options."*

   Read at the time as: closed-set (`WordSetElement`) is fuzzy, open-ended (`SlotElement` — a
   number, a unit class, a landmark) is exact, and that split should be a property of the
   *element type*, not a per-rule choice.

3. **Self-correction, one message later**, verbatim:

   > *"the user decided unit class words (armor, truck, air defence, AAA, tank, …) are a closed
   > set → fuzzy with the near-tie guard, not an exact 'value'."*

   A unit class turned out to belong on the *fuzzy* side after all — it is a short, closed list,
   the same shape as a direction, not an arbitrary value. **This is why the fix does not hard-wire
   "fuzzy ⇔ `WordSetElement`, exact ⇔ `SlotElement`" as a rule enforced in code.** It is true today
   only because every shipped `SlotType` (`angle`/`quantity`/`heading`/`oclock`/`speed_target`)
   happens to be open-ended — the real distinction is closed-set-vs-open-ended, and a future unit-
   class slot type would need the same fuzzy-plus-near-tie mechanism `WordSetElement` now has,
   wired into its own `consume`, not an automatic exemption for being a `SlotElement`. No such slot
   type ships this stage (no rule needs one yet) — `rule_patterns.py`'s own module docstring and
   the `SlotElement` branch's comment in `_match_elements` both say this explicitly, specifically
   so a later implementer does not read the current code's accident as the rule.

### Mechanism

- **`_resolve_word_set(heard, options)`** (new, `rule_patterns.py`) — the `WordSetElement`
  counterpart to `_literal_ratio`: scores `heard` against every alternative (`_char_ratio`, a
  small helper factored out of `_literal_ratio` so both share one comparison), picks the
  best-scoring one, rejects outright (returns `None`) if nothing clears `_WORD_REPAIR_FLOOR` (same
  floor a literal uses), and reports `near_tie=True` when a *different* alternative's own ratio
  lands within `SEPARATION_MIN` of the winner's.
- **`_match_elements`** — the `WordSetElement` branch now calls `_resolve_word_set` instead of
  `words[i] not in element.words`; resolves to the *canonical* alternative (not the raw heard
  word), appends its ratio into the same `word_ratios` list a `LiteralElement` feeds, and ORs
  `near_tie` into a new `ambiguous` return value (also threaded through `OptionalElement`'s
  recursive sub-match). `match_pattern_with_ratio` now returns a 3-tuple
  `(slots, ratio, ambiguous)`; `match_pattern` discards both, unchanged for its callers (the
  collision checks, which only need "did it match").
- **Why the existing averaging already *is* "the phrase as a whole," with no `_phrase_match_ratio`
  port needed**: the user's own phrasing invoked that function's "idea." `_phrase_match_ratio`
  exists because the legacy matcher searches an unconstrained sentence against a phrase table and
  needs `SequenceMatcher`'s alignment (insert/delete opcodes) to handle length mismatches. This
  grammar never has that problem — full-consumption matching already walks every element
  positionally, so every fuzzy position here is a length-1 "equal-length replace" block by
  construction. `_phrase_match_ratio`'s three-step algorithm, specialised to that case (no
  inserts/deletes, every block length 1), reduces exactly to "credit each position's own ratio if
  it clears the floor, divide by the count" — which is precisely `match_pattern_with_ratio`'s
  existing mean. So folding `WordSetElement` ratios into the same `word_ratios` list the literal
  fuzz already averages *is* the phrase-level score, not an approximation of it.
- **`_match_rules`** (`command_matcher.py`) — unpacks the new 3-tuple; the winning match's own
  `word_set_ambiguous` seeds `ambiguous` (previously always `False` until the cross-rule near-tie
  check), so a single rule with no competitor can now come back ambiguous purely from its own
  directive resolution. The cross-rule/cross-pipeline near-tie check is unchanged and still ORs in.
- **`SEPARATION_MIN` relocated `command_matcher.py` → `vocabulary.py`**, same move and the same
  reason `_WORD_REPAIR_FLOOR` made in Stage 3a's first pass: `rule_patterns.py` needs it now (for
  the near-tie guard) and must never import `command_matcher.py` (the established cycle).
  `command_matcher.py` imports it back from `vocabulary`, so `command_matcher.SEPARATION_MIN`
  still resolves unchanged for the one existing test (`test_command_matcher.py`) that reads it
  that way.
- **Collision probe widened to word-set positions** (`_sample_words_with_fuzzable_flags`, renamed
  from `_sample_words_with_literal_flags`; `_perturbed_sample`) — a mis-heard directive word is now
  part of the fuzzable surface a collision can hide in, the same reasoning D13 already applied to
  literals. `_COLLISION_PROBE_WORDS` already happened to carry near-misses for both "left"
  ("lift") and "right" ("light"/"write"/"night") before this change — convenient, not planned for
  it, noted in the list's own comment. Re-ran the full collision-check test suite
  (`TestCompileRules` and friends) to confirm nothing already shipped regressed: it did not — the
  shipped `turn_heading_relative` rule's own perturbed sample is unchanged, because its first
  fuzzable position ("turn", a literal) already had a usable probe word, so the widening only
  takes effect for a rule whose first fuzzable position has none, which no shipped rule triggers.

### Files Changed

- `audio-adapter/src/vocabulary.py` — `SEPARATION_MIN` constant + comment moved in from
  `command_matcher.py` (see above).
- `audio-adapter/src/rule_patterns.py` — module docstring's E12 section rewritten to the revised
  rule and its own later correction (above); `_char_ratio` (new, factored out of `_literal_ratio`);
  `_resolve_word_set` (new); `_match_elements`/`match_pattern_with_ratio`/`match_pattern` signature
  and behaviour changes (above); `_sample_words_with_fuzzable_flags`
  (renamed+widened)/`_perturbed_sample` (widened); `_COLLISION_PROBE_WORDS`'s own comment updated
  to say it now probes word-set positions too.
- `audio-adapter/src/command_matcher.py` — `SEPARATION_MIN` import added from `vocabulary`, its
  own former declaration replaced by a pointer comment (mirroring `_WORD_REPAIR_FLOOR`'s own);
  `_match_rules` unpacks/folds the new `ambiguous` source (above).

### Tests Added/Changed

- `audio-adapter/tests/test_rule_patterns.py`, `TestLiteralFuzz`:
  - `test_word_set_value_is_never_fuzzy_repaired` → **flipped**, renamed
    `test_mis_transcribed_word_set_value_now_resolves_fuzzily`: "turn lift two zero" now resolves
    to `direction="left"`, ratio `(1.0 + 0.75) / 2`, `ambiguous=False` — the exact case the old
    test pinned as a non-match.
  - `test_mis_transcribed_literal_still_matches` — ratio assertion updated `0.75` → `0.875` (the
    word-set's own exact hit now folds into the average).
  - `test_word_set_never_silently_flips_the_wrong_way` (new) — "turn light two zero" resolves to
    `"right"`, never `"left"`, pinning that the fuzzy pick always follows the actual best-ratio
    alternative rather than defaulting to the first option.
  - `test_word_set_near_tie_is_ambiguous_not_a_guess` (new) — `_resolve_word_set` directly, against
    synthetic options (`"cap"`/`"cat"`) engineered to tie exactly against `"cab"` (measured: both
    score `2/3`) rather than hunting a real English near-rhyme for "left"/"right" (there isn't a
    clean one — the two words are different enough in spelling that no natural mishearing lands
    this close to both). Pins `near_tie=True`, deterministic first-seen-wins tie-break.
  - `test_word_set_match_folds_near_tie_into_match_ambiguous` (new) — the same near-tie through the
    full grammar (`set <choice:cap|cat>` against "set cab"), pinning that a single rule with no
    competitor can still come back `ambiguous=True` purely from its own word-set resolution.
- `audio-adapter/tests/test_command_matcher_rules.py`:
  - `test_word_set_value_mis_transcription_does_not_resolve_the_rule` → **flipped**, renamed
    `test_mis_transcribed_word_set_value_now_resolves_the_rule`: same shape as the
    `test_rule_patterns.py` flip, at the `match_transcript` level.
  - `test_mis_transcribed_literal_still_resolves_the_rule` — ratio assertion updated `0.75` →
    `0.875`, docstring explains why.
  - `test_legacy_wins_outright_over_a_weaker_rule_match` — docstring's cited ratio/gap corrected
    (`0.75`/`0.25` → `0.875`/`0.125`); the test's own assertions (`token == "step"`,
    `ambiguous is False`) were already correct and unchanged, since the gap is still well past
    `SEPARATION_MIN` either way — this was a stale-comment fix, not a behaviour change.

No test needed rewriting beyond the two flips and the two ratio-comment corrections — every other
collision/ambiguity/separation test in both files passed unchanged against the new matching logic.

### Checks (audio-adapter)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `cd audio-adapter && .venv/bin/mypy src`: pass, 17 source files, 0 issues
- `.claude/scripts/fast-tests.sh audio-adapter`: pass, 471 passed, 2 skipped (smoke + 15 targeted
  files, parallel)
- `pytest -q` (full suite): 525 passed, 2 skipped — 522 before this round, +3 net (4 new tests,
  1 fewer because the two flipped tests replace their old selves 1-for-1, not additions).

### Stage 3d (this run) — effector-write action surface

Builds D20 exactly as the plan's "Stage 3d" section lays it out: `_execute_switch_row` extracted
from `advance`'s inline per-row block, a new `EffectorRunState.ad_hoc_runs` run kind processed by
the *same* function (never a second write path), `effector_engine.request_write`, and `rules.
actions`' widened `ActionParam`/`effector.write(name, value, says)`. No sequence file migrated, no
shipped rule calls this — pure capability, proven by test. Prerequisite work first: confirmed the
Stage 3b tip (`7b956918`) was already this worktree's `HEAD` (via `fc282270`, the prior merge
chain's own tip) and strictly behind it — fast-forwarded with `git merge --ff-only 7b956918`, no
conflicts.

### Files Changed

**body-layer**
- `src/belief/effector_engine.py` — module docstring gains a paragraph on the second run kind;
  `_effective_value` generalised from taking a `_RunCursor` to a bare `snapshot`/`snapshot_sim`
  pair, so both run kinds can share it; new `_AdHocEffectorCursor` (mirrors `_RunCursor`, minus
  `row_index` — a single target has no sequence of rows), `_RowResult`/`_RowOutcome`, and
  `_execute_switch_row` (the condition check → self-check → `absolute_write` gate → write →
  bookkeeping → spoken-line block, extracted verbatim from `advance`'s own per-row loop); new
  `request_write` (mirrors `fire_trigger`'s "start if idle" shape); `advance`'s per-row loop
  rewritten to call `_execute_switch_row` instead of the inline block, and gains a second pass
  over `EffectorRunState.ad_hoc_runs` after the trigger-run loop, sharing `assumed_writes`/
  `commanded_values`/`failed_effectors`/`spoken` with it in the same call; `EffectorRunState`
  gains the `ad_hoc_runs` field.
- `src/rules/actions.py` — `ActionParam` widened with `kind: Literal["int", "str"]` and
  `optional: bool`; `Action.invoke`'s signature widened to `dict[str, object]`;
  `Action.__post_init__` added (rejects a required parameter declared after an optional one);
  `ActionContext` gains `request_effector_write: Callable[[str, str, str | None], dict[str,
  object]] | None = None`; `_increment_heading` updated for the widened `args` type; new
  `_write_effector`/`EFFECTOR_ACTIONS`; `ACTION_NAMESPACES` gains `"effector"`.
- `src/rules/engine.py` — `_make_action_wrapper` widened: a `kind="str"` parameter is type-checked
  (string) rather than bound-checked; a trailing `optional` parameter may be omitted from the Lua
  call (arity check becomes a range, `required <= len(lua_args) <= len(params)`) or passed as an
  explicit `nil`, either way landing as `None` in `invoke`'s `args`.
- `src/body.py` — new `request_write` import (aliased `request_effector_write`); `_request_
  effector_write` closure built in `main()` (validates `name`/`value` against the already-loaded
  `effector_registry_entries`, mints a fresh request id via `itertools.count()`, mutates
  `crew_runner.effector_state` in place); `rules_ctx`'s construction passes it to `ActionContext`.
- `config/rules/README.md` — `effector.write` added to the Actions table, and a note on its
  failure reason, since it is now a real part of the Lua API surface even though no shipped rule
  calls it yet.

### Tests Added

**body-layer**
- `tests/test_effector_engine.py` (8 new tests) — `request_write` enqueues an idle ad hoc run; a
  second request for the same effector while one is pending is a no-op (plan's own wording —
  dedup is by `.effector`, not `request_id`, see "Notable Discoveries" below); the ad hoc pass's
  self-check match speaks and removes the run; a real write succeeds, speaks, and removes the
  run; a write with no `says` speaks nothing; a failed write is silently retried then succeeds; an
  unknown readback on a non-absolute effector is kept and retried with a fresh read next poll
  (D20's own departure from a sequence row's "skip forever" behaviour); an ad hoc write and a
  sequence row both targeting the same effector in the same poll share D9's same-poll collision
  rule via `failed_effectors`.
- `tests/test_rules_actions.py` (new, 5 tests) — `ACTION_NAMESPACES["effector"]` is registered;
  `Action.__post_init__` rejects a required parameter after an optional one; `_write_effector`
  degrades to `{"ok": false, "reason": "UNKNOWN_EFFECTOR"}` with no `request_effector_write`
  wired (the standalone-load case); it calls the injected closure with validated args; it passes
  the closure's own reason straight through.
- `tests/test_rules_effector_action.py` (new, 5 tests) — the plan's own "small synthetic rule,
  never shipped" end-to-end test: a Lua call to `effector.write` through the real sandbox →
  the validated action → the injected closure → `request_write` → `advance` →
  `EffectorRunState.spoken` → `CrewConsole.drain_effector_speech`, asserted against
  `console.output.getvalue()`; an unknown effector and an illegal value name both never reach the
  (intentionally assertion-raising) fake engine closure; `says` is optional in the Lua call; a
  write that never gets a readback (fake client always raises) is silently retried, never
  "Action file error.".
- `tests/test_rules_engine.py` — two existing local `_invoke` helper functions' parameter type
  changed from `dict[str, int]` to `dict[str, object]` (mechanical, required by `Action.invoke`'s
  widened signature; zero behaviour change — see "Notable Discoveries").

### Checks

**body-layer** (fresh `.venv` built from `/opt/homebrew/bin/python3.14`, `pip install -e .` +
`lupa==2.8` + `ruff`/`mypy`/`pytest`/`pytest-xdist`; no venv existed yet in this worktree):
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (CWD-only config discovery, run from inside `body-layer/`): pass, 91 source files, 0
  issues
- `.claude/scripts/fast-tests.sh body-layer`: 1 failed (the pre-existing, unrelated
  `test_shipped_effector_config_loads_without_errors` — empty row in the user's own
  `config/sequences/mi-24p/seat-copilot.md`, named as a known failure in this run's own task
  brief), 2653 passed
- `.claude/scripts/fast-tests.sh --full body-layer`: same single pre-existing failure, 3511
  passed, 4 xfailed (up from Stage 3b's 3493 passed/4 xfailed by exactly the 18 tests this stage
  adds)

### Notable Discoveries

- **The plan's own test-list wording for `request_write`'s dedup rule ("a second request for the
  same effector while one is pending is a no-op") is more specific than D20's main-body
  description ("mirrors `fire_trigger`'s own 'start if idle' shape"), and the two readings
  diverge.** `fire_trigger` dedups by its own dict key (the trigger); a literal transcription of
  that shape onto `ad_hoc_runs` (keyed by request id) would dedup by `request_id` — but every real
  dispatch mints a *fresh* id (`body.py`'s `itertools.count()`), so a `request_id in state.ad_hoc_
  runs` check would almost never fire and would not implement the test list's own stated rule at
  all. Built to the test list's literal wording instead: `request_write` scans `ad_hoc_runs`'
  existing `.effector` values and no-ops if any entry already names the same effector, regardless
  of request id. Worth flagging per root `CLAUDE.md`'s "a plan's test-list example can contradict
  its own stated invariant" risk, extended here to "a test-list sentence can specify a *different*
  rule than the prose it is illustrating" — caught by writing the test from the test list's own
  words first, then checking the implementation against it, rather than the other way round.
- **`ActionParam`'s widened shape needed one more mechanical decision the plan did not spell out
  at the Lua-call-arity level**: a trailing `optional` parameter (`says`) must be acceptable both
  *omitted entirely* from the Lua call (`effector.write("x", "on")`, 2 positional args) and *passed
  explicitly as `nil`* (`effector.write("x", "on", nil)`, 3 positional args, the third `None`) —
  Lua does not pad a native-function call with trailing `nil`s the way it pads a Lua-defined
  function's own formal parameters. `_make_action_wrapper`'s arity check became a range
  (`required <= len(lua_args) <= len(params)`) and the per-parameter loop treats an explicit
  `None` on an optional parameter the same as an omitted one; parameters past `len(lua_args)` are
  filled with `None` after the loop. Covered by `test_effector_write_says_is_optional` (the
  omitted-from-the-call case); the Lua literal `nil` case was **not** actually covered until the
  Stage 3d review's optional refinement added `test_effector_write_says_explicit_nil_is_also_
  optional` — "covered implicitly" above was wrong: no test in this stage's own diff passed a
  literal third `nil` argument, and the "present" side of the arity check other tests exercise is
  a real string, not `nil`, so it proved nothing about this specific path. The behaviour itself was
  already correct (traced by hand and confirmed by the new test), only the claim that it was
  proven was not.
- **`Action.__post_init__` is new, cheap, correctness hygiene, not asked for by the plan.** With a
  tuple of `ActionParam`s and no mechanical check, a future action could declare a required
  parameter after an optional one, and the "parameters past `len(lua_args)` are optional" slicing
  assumption inside `_make_action_wrapper` would silently mis-attribute values to the wrong names
  for certain call arities. One `ValueError` at `Action` construction time (i.e. at module import,
  for every shipped action) catches this before it could ever reach a live dispatch. Reversible —
  it is a pure addition with no behaviour change for any `Action` that was already ordering its
  parameters correctly (every existing one does).
- **The REPL thread can, in principle, dispatch a rule that calls `effector.write` concurrently
  with the poll thread's own `advance_effectors` call, and both would mutate `crew_runner.
  effector_state` — a genuine data race the existing `observ_transition`/`weapon_safety_
  transition`-style one-shot fields never had**, because those are read and acted on *inside* the
  poll loop itself (never touching `runner.effector_state` from any other thread), while D20's own
  design (the plan's explicit words: the closure "calls a new `effector_engine.request_write(...)`
  ... against `body.py`'s own runner-owned `EffectorRunState`") calls for the closure to mutate
  `crew_runner.effector_state` directly, synchronously, at dispatch time — which can happen on the
  REPL thread via `handle_line` → `handle_command`. Lupa's own per-runtime lock (R4) only serialises
  the *Lua call itself*; it says nothing about a plain Python attribute read-modify-write outside
  that call. Not fixed here: no shipped rule calls `effector.write` in this stage, so the race is
  latent and unreachable in practice until Stage 5 ships the first real effector-writing rule —
  but whoever builds that stage should read this note first, since the fix (routing the ad hoc
  write request through a one-shot field the poll loop itself drains, the same shape `observ_
  transition` already uses, rather than mutating `effector_state` from the dispatch call) is a
  real design choice, not a one-line patch.
- **`crew_runner.last_t_sim` can be `None`** at the moment a rule dispatches (before the poll
  loop's first successful poll) — `_request_effector_write` degrades to the generic `{"ok":
  False, "reason": None}` in that case (the same graceful-degradation shape `unable(nil)` already
  has), rather than inventing a new closed reason for an edge no shipped rule can reach yet. Not
  covered by a test (it needs a live `ConsolePerceptionRunner` with a real poll thread to exercise
  meaningfully, which is `test_body.py`'s territory, not this stage's unit-level tests) — flagged
  here rather than silently assumed.

### Stage 3d review fixes

Applying the three Required Fixes from `plans/speech-rules/review-stage3d.md`, plus the optional
"explicit Lua `nil`" test. Scoped tight to the effector-write path, per the dispatching brief —
Stage 4 (flight-control port) is being built in parallel on `crew_console.py`'s flight handlers
and did not need touching.

**Required Fix 1 (cross-thread race on `effector_state`).** `body.py`'s `_request_effector_write`
closure no longer mutates `crew_runner.effector_state` itself. It still validates `name`/`value`
against the live registry and `crew_runner.last_t_sim is not None` synchronously (so the rule
still gets its immediate `{ok=false}`), but on success it now appends a new
`belief.crew_console.PendingEffectorWrite(request_id, effector, value, says)` to a new
`CrewConsole.pending_effector_writes: list[PendingEffectorWrite]` field instead. `body.py`'s poll
loop drains that list (swap-with-a-fresh-`[]`, not iterate-then-clear, so an append landing during
the swap is never dropped) immediately before `advance_effectors`, calling `effector_engine.
request_write` once per queued entry against `runner.effector_state` — the same place every other
cross-thread effector signal (`observ_transition`/`weapon_safety_transition`) is already applied.

A **queue**, not a single one-shot slot like `observ_transition`, because those two each carry
exactly one domain fact at a time while an ad hoc write names an arbitrary effector — two
different-effector requests dispatched in the same poll window must not collide the way they would
in a single slot. `list.append()` is GIL-atomic, so concurrent appends from the poll thread's own
voice dispatch and the REPL thread's typed dispatch cannot lose an entry; this is the same
"append from any thread, drain-and-rebuild on the poll thread, no lock" shape `_pending_
positional_replies` already uses (`crew_console.py`), not a new mechanism.

Deliberately **not** reset by `_reset_one_shot_command_state` (same reasoning as `where_is_it_
requested`): an entry queued by an earlier dispatch this poll has not yet drained must survive an
unrelated later command dispatched in between. One consequence not asked for by the review and not
built here: `_dispatch_rule`'s D6 rollback (a Lua error later in the same dispatch) does **not**
retroactively remove an `effector.write` this dispatch already queued earlier in its own handler.
This is not a regression — the pre-fix code never rolled this back either, since it mutated
`crew_runner.effector_state` directly, an object `_reset_one_shot_command_state` (a `CrewConsole`
method) cannot reach at all — but it is a real gap, now sitting on a field that could in principle
be truncated back to its pre-dispatch length on rollback. Left alone because the review did not
ask for it and no shipped rule can reach it yet; flagging it here rather than silently deciding it
is out of scope. Resets to empty for free on a mission (re)start (not in `reset_for_new_mission`'s
pass-through list) since `effector_state` itself is dropped wholesale then too (D11).

Test added: `test_effector_write_queued_from_background_thread_is_applied_on_next_poll_drain`
(`test_rules_effector_action.py`) — dispatches the rule from a real background `threading.Thread`
(standing in for the REPL thread), asserts the request is queued but no `EffectorRunState` was
ever touched by the dispatch itself, then simulates the poll loop's own drain on the test's own
thread and asserts the request only reaches `ad_hoc_runs` there. `body.py`'s own closure and poll
loop are not directly unit-tested (`main()`'s CLI wiring is untested by design, per `body-layer/
CLAUDE.md`'s module map) — this test exercises the same queue field and the same `effector_engine.
request_write` call the real wiring uses, at the boundary that is actually testable.

**Required Fix 2 (differing-value second request).** Main-loop decision, consistent with U21 and
`AiPilotWheelGoal`'s "latest wins, nothing lost" convention (`body-layer/CLAUDE.md`,
flight-control): `effector_engine.request_write` now distinguishes the two cases its dedup check
used to conflate. A second `effector.write` naming an effector that already has a pending ad hoc
run is a no-op only if it names the **same** value (the pilot repeating themselves, or a rule
re-firing — D1's own shape, unchanged); if it names a **different** value, the pending entry is
replaced outright — new `request_id`, new `value`/`says`, the old entry discarded — so Petrovich's
eventual spoken confirmation is always for the pilot's most recent instruction, never a stale
earlier one. `config/rules/README.md`'s `effector.write` row now states both halves of this rule
explicitly, so a future rule author is not surprised by either.

Test added: `test_request_write_with_a_differing_value_replaces_the_pending_request`
(`test_effector_engine.py`), beside the existing same-value no-op test.

**Required Fix 3 (`says` length cap).** D20's own plan text promised `says` is "a free-text,
length-capped string (the same cap `say()` already enforces)," but nothing enforced it. The cap
(`_MAX_SAY_LEN` = 500) moved from `rules/engine.py` to `rules/actions.py` as `MAX_SAY_LEN` — a
single declaration, not a duplicated magic number — because `rules/actions.py` cannot import from
`rules/engine.py` (the reverse import already exists, D5) but `engine.py` already imports from
`actions.py`, so this is the only non-cyclic shared home. `engine.py`'s `_SinkHolder.say` now
imports and uses the same constant it always enforced; `rules/actions.py`'s `_write_effector` now
truncates `says` to `MAX_SAY_LEN` characters (silently, matching `say()`'s own overflow behaviour)
before ever calling `ctx.request_effector_write` — so neither the closure, the engine, nor the
eventual spoken line ever sees an uncapped value.

Tests added (`test_rules_actions.py`): `test_write_effector_caps_says_at_the_same_length_say_
enforces` (an over-cap `says` is truncated to exactly `MAX_SAY_LEN` characters before reaching the
closure) and `test_write_effector_says_within_the_cap_is_untouched` (a normal-length `says` passes
through unchanged).

**Optional refinement (explicit Lua `nil`).** Added `test_effector_write_says_explicit_nil_is_
also_optional` (`test_rules_effector_action.py`) — see the corrected "Notable Discoveries" entry
above for why the earlier "covered implicitly" claim was wrong.

**Checks.** `.venv` built fresh from `/opt/homebrew/bin/python3.14` (none existed in this
worktree); `ruff format --check`, `ruff check`, `mypy --strict src` (91 source files) all clean.
`fast-tests.sh body-layer`: 2658 passed, 1 failed (`test_shipped_effector_config_loads_without_
errors` — the named pre-existing, unrelated `seat-copilot.md` empty-row failure, untouched by
this change), 4 xfailed — matches the dispatching brief's stated known failure exactly.

---

## Stage 4 — flight-control port (2026-11-17)

Builds D18 (plan's "Stage 4 — flight-control port" section): `turn_heading`, `level_flight`,
`set_speed`, `set_altitude`, `hold_altitude`, `level_off`, `altitude_step`, `speed_step`, the HVRT
bare words, and "you/i have controls," all as rules in `config/rules/flight.lua`. 19 rules ship
(`turn_heading_relative` + 18 new). Depends on Stage 3b's gate (D16); resolves that stage's own
Required Fix 1 (the `settling` generalisation) as part of this stage, per the review's own
instruction to pick one approach and record why.

### D16 Required Fix 1 — per-parameter categories, not per-handler checks

**Chose option (a): the gate's settle test became per-parameter**, not (b) keeping per-handler
checks. `rules.gates.GATE_REGISTRY` grew from two entries to six: `"always"`, `"flight_control"`
(base — has-controls only, no held value needed — the absolute-set forms and HVRT, whose own
`_ai_pilot_hvrt_ready()` mode check stays the action's own finer precondition per D16), and four
more that also hold on their own specific value: `"flight_control_heading"` (`held_heading`),
`"_speed"` (`held_speed`), `"_altitude"` (`held_altitude`), `"_any"` (passes once *any* of the
three is known — `level_flight`'s own rule). `belief.crew_state.CrewState` dropped the single
`settling: bool` field in favour of carrying `held_heading`/`held_altitude`/`held_speed` directly,
so each gate function reads whichever one its own category needs. `turn_heading_relative` migrated
from `"flight_control"` to `"flight_control_heading"` in the same stage (its own precondition
*is* `held_heading`, so this is the one rule the old single-category design happened to get right).

**Why (a) over (b):** D16's own stated design already puts the "when" (precondition) in the gate,
apart from the action, as a *generic*, reusable mechanism — keeping per-handler checks instead
would have meant reintroducing the exact second-source-of-truth problem D16 was built to remove
(the gate says `PASS`, the action re-derives the same check and could disagree). Splitting into
named categories keeps the mechanism entirely in `gates.py`, costs one new gate function per
parameter shape (four), and every extracted action's own dead `held_* is None -> NOT_READY` branch
is removed and replaced with an `assert`, mirroring `increment_ai_heading`'s own precedent exactly
(Stage 3b already set this precedent for the one rule it shipped).

### Actions — extracted CrewConsole methods, not actions.py-resident logic

Each flight handler's math moved onto a **public `CrewConsole` method** (`set_heading`,
`level_flight`, `set_speed`/`set_speed_max`, `step_speed`, `set_altitude`, `step_altitude`,
`hold_altitude`, `level_off`, `hvrt_translate`, `hvrt_hold`, `hvrt_step`), exactly mirroring
`increment_ai_heading`'s own Stage 2 shape — `rules/actions.py`'s `FLIGHT_ACTIONS` entries are thin
one-line wrappers calling these. `rules/actions.py` grew by 16 actions but **the action mechanism
itself (`Action`/`ActionParam`/`_make_action_wrapper`) is untouched** — every new action still
takes only bounded ints, per the task's own instruction to keep this file's change small while
Stage 3d (effector writes) builds on the same module elsewhere. Four of those ints are **closed
small-integer encodings of a word the Lua handler already resolved**, the same idiom `increment_
heading`'s own sign flip established: `set_altitude`'s `reference_code` (0 none / 1 radar /
2 barometric), `step_speed`'s `sign` (±1), `step_altitude`'s already-signed `delta_m`. HVRT's four
translate directions and two step directions are **zero-arg actions, one per bare word**
(`hvrt_translate_left/right/forward/back`, `hvrt_step_up/down`), each a one-line wrapper to the
*same* `hvrt_translate`/`hvrt_step` method — no int-code needed since the direction is implicit in
which rule/action is called, not a runtime value.

**The absolute `turn_heading` drops the legacy compass-point form** ("heading north"). The shipped
`heading` slot type (D7: "always a world compass three digit number") has no compass-word
alternative, and the plan's own Stage 4 text names only `heading` for this slot. A real, reported
behaviour narrowing — flagged in the handback, not silently dropped.

### Hardening `run_rule` against a bare Python exception (review-stage3b.md's optional refinement)

Several new actions' own precondition is an `assert` (mirroring `increment_ai_heading`'s), each
"correctly unreachable today" because its category's gate already guarantees it — the exact shape
the optional refinement flagged as worth hardening "the next time this area is touched." Added a
second `except Exception` clause to `run_rule` (`rules/engine.py`), degrading *any* bare exception
to D6's `ACTION_FILE_ERROR_LINE`/`error=True`, logged with the exception's own type name. Confirmed
via Stage 0's own research note that lupa propagates a Python exception raised inside a callback
unwrapped through the Lua boundary — this is the second place that finding has driven a fix
(the first was Stage 3b's `when.speech` `*args` arity shape).

### Two genuine bugs found and fixed in shared collision-check infrastructure (both zero-behaviour-change for the pilot)

Building the real matching differential tests (`audio-adapter/tests/test_flight_rules_matching.py`)
against the *real* `compile_rules`/`match_transcript` surfaced two defects neither the one rule
Stage 1b/2 shipped, nor Stage 3a/3b's own tests, had ever exercised:

1. **`speed_target`'s own tagged table (`{"kind": ..., ...}`) was silently dropped at the wire**,
   never a crash: `command_matcher._match_rules`'s own `typed_slots` filter kept only `isinstance
   (value, (int, str))`, and `body.py`'s own `/transcripts/poll` row validator rejected (`continue`
   -- the whole transcript, not just the slot) any slots dict whose values were not scalar. `set_
   speed`'s own rule is the *first* time any shipped rule has carried a union slot value through
   the real dispatch path (D7/D14's "a union arrives in Lua as a table" design predates this stage,
   but nothing had wired it end to end until now). Fixed by widening the type both filters check
   against to `int | str | dict[str, object]` (`command_matcher.SlotValue`, `MatchResult.slots`
   and `transcript_queue.TranscriptEvent.slots` both become `Mapping[str, SlotValue]`, `Mapping`
   rather than `dict` so every pre-existing `_parse_*_slots` branch's own `dict[str, int | str]`
   construction needs no change — mypy's own covariance suggestion) ~~and widening `body.py`'s own
   validator's `isinstance` check (one level of nesting, matching the tagged-table shape exactly,
   never arbitrary recursion)~~. **Correction, 2026-11-17 (security deep analysis,
   `plans/speech-rules/security-stage3-4.md` Required Fix 1): the strikethrough clause above was
   wrong.** `body.py`'s own `/transcripts/poll` row validator was never touched by this stage —
   `git diff c309092b..1e5ddd5e -- body-layer/src/body.py` showed zero lines changed in that
   block, confirmed independently by a probe feeding it the exact wire shape "speed two hundred"
   produces (`console.calls == []`, the item silently dropped). The adapter-side fix above (1) did
   land; the body-layer-side half of the same fix did not, until the Required Fix 1 pass described
   under "Security fix (stages 3-4)" below. Confirmed via `nested dict -> lupa table_from` probes that the
   nested dict crosses into Lua correctly (`s.speed_target.kind`) under the real sandbox's real
   `attribute_filter` — `sandbox.py`'s own `_deny_all_attributes` docstring already documents that
   a plain `dict` (never a custom object) is tolerated as "userdata" for exactly this reason.
2. **Every HVRT bare-word rule "collided with itself."** `rule_patterns._collides_with_legacy`
   treated *any* non-`None` legacy-probe token as a collision, including when that token is the
   rule's *own* id — which is exactly what happens for all seven HVRT rules, since `command_
   matcher._HVRT_BARE_WORD_TOKENS`'s own exact shortcut resolves a bare "left"/"hold"/etc. to that
   same token regardless of whether any rule is active at all. Fixed by requiring the legacy
   token to differ from the rule's own id before counting it as a collision — a one-line, narrowly
   scoped change with its own direct unit test (`test_rule_patterns.py`'s `test_a_legacy_probe_
   resolving_to_the_rules_own_id_is_not_a_collision`).

### Notable discovery — five real wording collisions, not forced through

Running the *real* 19-rule pattern set through the *real* collision check (after the two fixes
above) found **five genuine, measured collisions** this stage does not resolve by renaming
anything, because that is a product decision, not an Implementer's to make unilaterally:

| rule | collides with | mechanism | ratio |
|---|---|---|---|
| `set_speed` | `altitude_step` (rule x rule) | "speed two zero zero" fuzzy-resolves `altitude_step`'s own `<direction:climb\|descend>` word-set to "descend" | `ratio("speed","descend") == 0.5`, exactly `_WORD_REPAIR_FLOOR` |
| `altitude_step` | `set_speed` | same, the other direction | 0.5 |
| `level_off` | the existing `observ_off` command (rule x legacy) | word-sequence scoring against "observe off" | 0.75, comfortably above `MATCH_FLOOR` |
| `straight` | the existing `point` command, and `hvrt_translate_right` | "straight" vs "sight"/"right" | 0.77 both |
| `hvrt_translate_right` | the existing `point` command (rule x legacy, via the perturbed-sample probe) | "right"'s own near-miss probe word "light" resolves to `point` | — the *exact* collision `_HVRT_BARE_WORD_TOKENS`'s own comment already named (`ratio("right","sight")==0.8`) as the reason that exact-match shortcut exists; it protects an *exact* "right," not a mis-transcribed "light" landing outside it |

All five are real per the project's own existing mechanism (not an artifact introduced by this
stage), and all five were checked for a narrower fix before accepting them: dropping `straight`
entirely does **not** rescue `hvrt_translate_right` (its own collision is independent, via the
perturbed-sample probe); reordering `altitude_step`'s word-set does not change `_resolve_word_set`'s
own best-of-all-alternatives search. **Consequence, already handled correctly by existing
machinery, not newly built**: `body.py`'s `_push_rules` already treats an adapter-rejected rule id
exactly like a load-time failure (D6) — one stderr banner naming each id and reason, "Action file
error." spoken once, and the id excluded from `enabled_rule_ids`. Nothing new needed building for
this to degrade gracefully; it already does. The five rule ids still *load* cleanly in body-layer
(`test_shipped_rule_files_load_with_zero_failures` asserts all 19) — only the adapter's own `PUT
/rules` collision check, run separately, disables them. `test_flight_rules_matching.py`'s own
`test_the_real_shipped_pattern_set_rejects_exactly_the_known_collisions` pins this exact set rather
than asserting zero rejections, so a drift either direction is caught.

**Recommendation for whoever picks this up**: `set_speed`/`altitude_step` is the cheapest to fix
(rename one word-set alternative, e.g. a synonym for "descend" that scores further from "speed");
`level_off`/`straight`/`hvrt_translate_right` all involve an *existing* shipped command's wording
and need a product decision, not a code fix.

### U22 — not built in this stage

D19's `CalloutScheduler.note_urgent` proposal (flight readbacks cutting ahead of a queued routine
callout) is answered "build it" (U22), but Stage 4's own five numbered build steps in the plan
never mention it, and no code here wires it. Per the task's own instruction ("build it here only
if the plan places it in Stage 4"), it is left unbuilt. It belongs with whichever stage actually
reorders `CalloutScheduler`'s own queue — most likely folded into this stage's own follow-up once
U22 is explicitly scheduled, but not assumed here.

### Test deletions and moves

- `audio-adapter/tests/test_bl16_stage_p2_vocabulary.py` deleted entirely — every test in it
  exercised a parser (`parse_heading_deg`/`parse_speed_value`/`parse_speed_step_direction`/`parse_
  altitude_value`/`parse_altitude_step`) or a slotted `match_transcript` branch this stage deletes.
  Its still-live HVRT bare-word tests (a real, unchanged mechanism, `_HVRT_BARE_WORD_TOKENS`) moved
  to a new `TestHvrtBareWordShortcut` class in `test_command_matcher.py`, where that mechanism
  lives — plus one new test (`test_a_multi_word_transcript_never_takes_this_shortcut`) and the
  `hold`-vs-`hold_altitude` disambiguation test, updated to build its `hold_altitude` fixture rule
  via the real grammar rather than assuming a legacy phrase table entry.
- `body-layer/tests/test_crew_console_ai_pilot_wheel.py` lost `TestLevelFlight`/`TestTurnHeading`/
  `TestSetSpeed`/`TestSpeedStep`/`TestSetAltitude`/`TestAltitudeStep`/`TestHoldAltitude`/
  `TestLevelOff`/`TestHvrtTranslate`/`TestHvrtHold`/`TestHvrtStep`/`TestTransitionsResetEachDispatch`
  (12 classes) — every one dispatched a token this stage moved to a rule. `TestIncrementAiHeading`
  (Stage 2) and `TestDrainAiPilotWheelSpeech` (never a command token) are unaffected and stay.
  Their differential equivalents, dispatched through the real gate and the real shipped
  `flight.lua` (not a bare `handle_command` call with no gate at all), now live in `test_rules_
  flight_actions.py` — one class per command, 44 tests total in that file, each setting exactly the
  held field its own rule's category needs rather than a blanket "flying" fixture.
- `body-layer/tests/test_crew_console_rules.py`'s five Stage 3b hold-and-retry tests (`test_gate_
  hold_sets_pending_and_speaks_nothing`, both `test_drain_*` timeout tests, `test_drain_resolves_
  to_pass_...`, `test_a_second_held_command_replaces_...`) used a synthetic `"my_rule"` under
  category `"flight_control"` with `held_heading=None` to exercise the *generic* hold mechanism --
  broken by the category split, since bare `"flight_control"` no longer holds on any `held_*` value
  at all. Fixed by widening `_flight_console_with_rule`'s own helper to take an explicit `category`
  parameter, and passing `category="flight_control_heading"` at each of the five call sites that
  actually need a hold-capable category; the two pass/unable tests that only care about `has_
  controls` keep the default. This is exactly the fast-tests risk the role instructions name
  (`fast-tests.sh body-layer` caught all five locally before the full suite ran) — found by running
  the touched-file selection, not by reasoning about what Stage 3b's own tests would still assert.
- `body-layer/tests/test_rule_gates.py` rewritten for six categories instead of two (one test per
  category plus the registry-membership pin).

### Checks (both subprojects)

**body-layer** (existing `.venv`, Python 3.14.10, `lupa==2.8` already installed):
- `ruff format --check src tests`: pass (221 files)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, 91 source files, 0 issues
- `.claude/scripts/fast-tests.sh body-layer`: 1 failed (the named pre-existing `test_shipped_
  effector_config_loads_without_errors`), 2643 passed, 4 xfailed
- `.claude/scripts/fast-tests.sh --full body-layer`: same single pre-existing failure, 3501 passed,
  4 xfailed

**audio-adapter**:
- `ruff format --check src tests`: pass (36 files)
- `ruff check src tests`: pass
- `cd audio-adapter && .venv/bin/mypy src`: pass, 17 source files, 0 issues
- `.claude/scripts/fast-tests.sh --full audio-adapter`: 523 passed, 2 skipped (parallel)

### Notable discoveries, summarised

1. The five wording collisions above — the single most consequential finding of this stage.
2. The `speed_target`/nested-slot wire-type gap — a real, if latent, defect in shared
   infrastructure that no prior stage's own tests exercised, now fixed and covered.
3. The HVRT self-collision bug in `_collides_with_legacy` — same shape, now fixed and covered.
4. `heading`'s own collision-probe sample ("heading three one five") coincided with `scan_bearing_
   deg`'s hardcoded example list — moved to "heading two zero zero" (collision-check infrastructure
   only; the accepted grammar is unchanged, still any `0..359` value).
5. `rules/actions.py`'s own change is additive only (16 new actions, zero changes to `Action`/
   `ActionParam`/`_make_action_wrapper`) — should not conflict with Stage 3d's own planned widening
   of `ActionParam` and new `"effector"` namespace, built in parallel on a different branch.
6. Comment pruned: `belief/speech.py`'s `NOT_FLYING`/`HANDS_BUSY` comment block, stale the moment
   this stage shipped more than one `flight_control*` rule (it said "the one rule in this category
   until Stage 4 ports the rest" — true when written, false now).

### Stage 3d re-review Required Fix 4 (2026-11-17) — D6 rollback closed over queued effector writes

`plans/speech-rules/review-stage3d.md`'s "Re-review — 2026-11-17" section, Required Fix 4: the gap
Required Fix 1 above flagged and deliberately left open ("not asked for by the review") is now
closed — a rule that calls `effector.write` and then raises later in the *same* dispatch (Lua
error → `_dispatch_rule`'s D6 rollback → `ACTION_FILE_ERROR_LINE`) no longer leaves that write
sitting in `pending_effector_writes` to be applied on the next poll drain. D20's own carve-out
("D6 rollback does not apply here") is unchanged and still stands for the *other* case — an ad hoc
write that queues cleanly and only fails on a later poll, after the dispatch has already returned
"queued" — the code comment on `_dispatch_rule` says so explicitly.

**Mechanism: identity (a dispatch-scoped token), not a length/count snapshot.** The review's own
required shape, and the reason: `pending_effector_writes` is shared and appended to from either
thread without a lock (`list.append` is GIL-atomic — the entire premise Required Fix 1 relies on),
so a `del pending_effector_writes[before:]`-style truncate would also discard whatever the *other*
thread legitimately queued in the same window — exactly the class of bug Required Fix 1 exists to
prevent, reintroduced by the fix for a different bug. Concretely:

- `PendingEffectorWrite` (`belief/crew_console.py`) gains a fourth field, `dispatch_token: object |
  None = None` — defaulting to `None` so every existing direct-construction test is unaffected.
- `CrewConsole` gains `_dispatch_token_local: threading.local` (a new field, `repr=False,
  compare=False`) and `current_dispatch_token() -> object | None`, reading `getattr(self.
  _dispatch_token_local, "token", None)`. Thread-local, not a plain field, because the poll thread
  and the REPL thread each run their own `_dispatch_rule` call independently and must never see or
  overwrite each other's token — a plain instance attribute would have one thread's token clobber
  the other's mid-dispatch.
- `_dispatch_rule` mints a fresh `object()` at the start of every dispatch, stores it on the
  calling thread's own `_dispatch_token_local.token` for the duration of the `rule_runner` call
  (cleared in a `finally`), and — on error — filters `pending_effector_writes` by `write.
  dispatch_token is not token` rather than slicing by position.
- `body.py`'s real `_request_effector_write` closure stamps `dispatch_token=crew_console.
  current_dispatch_token()` onto every `PendingEffectorWrite` it appends, so an entry always
  carries the token of whichever dispatch queued it.

**Why a filter-and-reassign is the accepted shape here, not a further lock.** The review's required
fix explicitly asks for "filtering `pending_effector_writes` to drop exactly the entries carrying
this dispatch's token," which is what this is — a list comprehension iterating the *live* list
object (so a concurrent append landing mid-iteration is still seen and correctly kept, since
Python's list iterator rechecks the current length each step) followed by one attribute
reassignment. The remaining theoretical window — a concurrent append landing between the
comprehension's iterator exhausting and the reassignment executing — is the same few-bytecode
window Required Fix 1's own already-approved swap-to-drain (`pending_writes, crew_console.
pending_effector_writes = crew_console.pending_effector_writes, []`) already carries and was
reviewed as safe; this is not a new category of risk introduced here, and the review did not ask
for a lock.

**Lua-level concurrency note, confirmed before writing the concurrency test, not assumed.**
`research/2026-11-17-lupa-sandbox.md`'s R4 measured that a single shared `LuaRuntime` serializes
every call via its own global per-runtime lock — two threads dispatching through the *same*
`RuleSandbox` never actually overlap at the Lua-execution level, only at the plain-Python level
(the gap between one dispatch's `rule_runner()` return and its own rollback filter running, during
which another thread can acquire the now-free lock and run its own dispatch to completion). The
concurrency test below uses two independent `RuleSandbox` instances (two separate `LuaRuntime`s)
feeding the same `CrewConsole`, specifically to get real, deterministic overlap on the thing
actually under test — `CrewConsole`'s own token-based filter over the shared list — without
depending on winning a narrow, OS-scheduling-dependent race for lupa's lock.

**Tests added** (`test_rules_effector_action.py`):

- `test_a_write_then_a_later_error_in_the_same_dispatch_is_rolled_back` — the basic case (1):
  dispatched through the real `handle_command`/`_dispatch_rule` path (not `run_rule` directly,
  unlike the Required-Fix-1 test, since the gate/rollback plumbing only exists on that path).
  Asserts `pending_effector_writes` is empty and the returned line is `ACTION_FILE_ERROR_LINE`
  after a rule that queues an `effector.write` then calls `digits("not_a_number")` (raises
  `RuleRuntimeError`).
- `test_rollback_leaves_a_concurrent_dispatchs_own_queued_write_alone` — the concurrency-safety
  case (2), the one that actually exercises the reason a length-based truncate is wrong. Rule A
  (its own `RuleSandbox`) queues an `effector.write`, then blocks (via a `threading.Event` inside
  the shared `request_effector_write` closure) before reaching its own erroring `digits()` call;
  while blocked, rule B (a second, independent `RuleSandbox`, on a second real background thread)
  dispatches its own unrelated `effector.write` to completion. Asserts both entries coexist in
  `pending_effector_writes` at that point (proving the window is real), then releases rule A,
  letting it error and roll back, and asserts only rule B's entry survives.
  **Counterfactual run**: temporarily replaced the token-filter with the rejected
  "`del pending_effector_writes[before:]`" shape (a `len()` snapshot taken at dispatch start,
  truncated on error) — this test failed for the stated reason (`assert [] ==
  [('weapons', 'safe')]`, rule B's entry discarded alongside rule A's), confirming the test can
  tell the difference. Restored the real implementation afterward; `shasum -a 256` before and
  after the probe matched.

**Files changed**: `belief/crew_console.py` (`PendingEffectorWrite.dispatch_token`,
`CrewConsole._dispatch_token_local`/`current_dispatch_token`, `_dispatch_rule`'s token
mint/rollback), `tests/test_rules_effector_action.py` (import `ACTION_FILE_ERROR_LINE`, the two
tests above).

**Checks.** `.venv` already built from the prior review round; `ruff format --check`, `ruff check`,
`mypy --strict src` (91 source files) all clean. `fast-tests.sh body-layer`: 2660 passed, 1 failed
(`test_shipped_effector_config_loads_without_errors` — the same named pre-existing, unrelated
`seat-copilot.md` empty-row failure, untouched by this change), 4 xfailed. Also ran
`test_rules_effector_action.py` directly (9 tests, all pass).

**Notable discovery**: the project's own tuning-constants rule does not apply to anything added
here — no new bare numeric literal was introduced; `object()` tokens and `threading.local` carry
no magic number to tune.

### Required Fix 4 follow-up (same day) — `body.py`'s real closure was still not stamping the token

**Self-caught gap, reported rather than left silent**: the commit above built the rollback
correctly, but `body.py`'s real `_request_effector_write` closure still appended a bare
`PendingEffectorWrite(request_id=..., effector=..., value=..., says=...)` with no `dispatch_
token` — only the *test* closures passed `dispatch_token=console.current_dispatch_token()` by
hand. In production, every queued write would have carried `dispatch_token=None` (the dataclass
field's own default), so `_dispatch_rule`'s rollback filter (`write.dispatch_token is not token`)
would never find anything to remove — the fix was real and tested, but the one caller that matters
in flight never participated in it.

**Fix: make the production path unable to forget, not just remind it to remember.**
`CrewConsole` gains `queue_effector_write(request_id, effector, value, says) -> None` — the single
appender of `pending_effector_writes`, stamping `dispatch_token=self.current_dispatch_token()`
itself. `body.py`'s `_request_effector_write` closure now calls `crew_console.queue_effector_write
(request_id, name, value_name, says)` instead of importing and constructing `PendingEffectorWrite`
directly (the import is dropped from `body.py` entirely — nothing there references the dataclass
any more). Every test closure that used to construct `PendingEffectorWrite(..., dispatch_token=
console.current_dispatch_token())` by hand now calls `console.queue_effector_write(...)` the same
way, so there is exactly one way to queue a write anywhere in this codebase.

**Pinning it so it cannot regress silently, without touching `main()`'s untested CLI wiring.**
`body.py`'s real closure lives inside `main()`, which `body-layer/CLAUDE.md`'s own module map
already documents as untested by design (the runners are tested against fakes; `main()`'s wiring
is not) — restructuring it to be call-through-testable without a live aircraft-layer/world-model
setup was judged out of scope for this fix. Instead, pinned the invariant two other ways, both in
`test_rules_effector_action.py`:

- `test_queue_effector_write_stamps_the_current_dispatch_token` — calls `queue_effector_write`
  directly, once outside any dispatch (asserts the queued entry's `dispatch_token is None`) and
  once with the thread-local token field set by hand the way `_dispatch_rule` sets it (asserts the
  queued entry's `dispatch_token is` that exact object). This is the actual mechanism under test,
  independent of whether `body.py` remembers to call it correctly.
- `test_pending_effector_write_is_constructed_in_exactly_one_place_in_crew_console_py` and
  `test_body_py_never_constructs_pending_effector_write_directly` — grep-enforced fences, the same
  shape `test_mission_memory_store.py`'s own `test_entry_is_constructed_in_exactly_one_place_in_
  store_py`/`test_admission_and_marks_never_construct_entry_directly` already use in this codebase
  for an identical "one construction site, checked by caller" shape. The first asserts exactly one
  `PendingEffectorWrite(` construction exists anywhere in `crew_console.py` (inside `queue_
  effector_write`); the second reads `body.py`'s own live source file (via `body_module.__file__`,
  not a copy) and asserts neither `PendingEffectorWrite(` nor the bare name `PendingEffectorWrite`
  appears in it at all.
  **Counterfactual run**: reintroduced the exact original gap (imported `PendingEffectorWrite` and
  appended one by hand, no `dispatch_token`, inside the closure) — `test_body_py_never_constructs_
  pending_effector_write_directly` failed for the stated reason. Restored the real file afterward;
  `shasum -a 256` before and after matched.

**Files changed**:
- `belief/crew_console.py` — `queue_effector_write` method added; `PendingEffectorWrite`'s,
  `pending_effector_writes`'s, `_dispatch_token_local`'s and `current_dispatch_token`'s docstrings
  updated to name it as the one appender (comment pruned where it described the now-superseded
  "body.py's closure stamps it" shape, per root `CLAUDE.md`'s "Prune the comment you are standing
  next to" — the `_dispatch_rule` docstring itself needed no change, since "stamped with it via
  `current_dispatch_token`" is still accurate — `queue_effector_write` is what calls it now).
- `body.py` — `_request_effector_write` now calls `crew_console.queue_effector_write(...)`; the
  `PendingEffectorWrite` import is dropped (no longer referenced anywhere in this file).
- `tests/test_rules_effector_action.py` — the three existing `request_effector_write` test
  closures that built `PendingEffectorWrite` by hand now call `console.queue_effector_write(...)`
  instead (two of the three no longer need `dispatch_token=console.current_dispatch_token()`
  spelled out, since the method does it); `PendingEffectorWrite` import dropped (no longer
  constructed in this file); three tests added (above); `import body as body_module`, `import re`,
  and a module-level `_SRC` path constant added.

**Checks.** Same `.venv`. `ruff format --check`, `ruff check`, `mypy --strict src` (91 source
files) all clean. `fast-tests.sh body-layer`: 2663 passed, 1 failed (the same named pre-existing
`test_shipped_effector_config_loads_without_errors`), 4 xfailed — three more passing tests than the
prior round, matching the three added. `test_rules_effector_action.py` directly: 12 tests, all
pass.

### Required Fix 4, round 2 — buffer then commit

**Why round 1 was not enough.** The re-review's "Re-review (Fix 4)" section
(`plans/speech-rules/review-stage3d.md`) demonstrated, against the unmodified round-1 code, that
the poll loop's own unconditional per-poll drain (Required Fix 1's mechanism,
`pending_writes, crew_console.pending_effector_writes = crew_console.pending_effector_writes, []`)
could run *inside* a still-open REPL-thread dispatch's window — after that dispatch's own
`effector.write` call had already appended to the shared list, but before the same dispatch's
later error ran the token-filter rollback. The drain would remove the entry (correctly stamped
with the dispatch's token) and feed it straight into `effector_state`, where it started executing,
before the rollback ever ran to find it. The entry was gone by the time the filter looked, not
because nothing was queued, but because something else had already taken it — round 1's rollback
filtered the shared list *after* an entry was visible on it, and anything else reading that same
unlocked list first could always win that race.

**The fix: keep a dispatch's own writes off the shared list until the dispatch itself has decided
to keep them.** `CrewConsole` gains `_dispatch_write_buffer_local: threading.local` (replacing
`_dispatch_token_local`) — `None`/unset outside any dispatch, else the `list[PendingEffectorWrite]`
`_dispatch_rule` opened for *this* call on *this* thread. `queue_effector_write` checks it: if a
buffer is open, the write is appended there, invisible to anything reading the shared
`pending_effector_writes`; if not (the one path that reaches this with no open dispatch — a test
calling `run_rule` directly rather than through `handle_command`/`_dispatch_rule`), it appends
straight to the shared list exactly as before, since there is no dispatch to stage it under and
none to roll back. `_dispatch_rule` opens a fresh buffer before calling `rule_runner`, and on
return: success extends the shared list with the whole buffer in one `list.extend` call (GIL-
atomic, same no-lock posture `list.append` already relied on — confirmed by reading CPython's
`listextend`, which does not release the GIL mid-copy for a list argument); error discards the
buffer untouched. Either way the shared list only ever receives a block of writes from a dispatch
that has already finished and already succeeded, so the poll thread's drain can only ever see a
dispatch's writes in the state its own outcome already decided — there is no window where a
decision is still pending on the shared list for the drain to race.

**`dispatch_token` is gone, not just unused.** `PendingEffectorWrite` no longer carries the field
at all (removing, per the task's own direction, the identity-filter machinery round 1 needed and
round 2 does not); `current_dispatch_token()` is removed with it. `queue_effector_write` remains
the single construction site and the single appender, and `body.py`'s `_request_effector_write`
closure needed no change at all — it already only ever called `crew_console.queue_effector_write
(...)`, never constructed the dataclass itself, so the grep fences
(`test_pending_effector_write_is_constructed_in_exactly_one_place_in_crew_console_py`,
`test_body_py_never_constructs_pending_effector_write_directly`) needed no change either and both
still pass unmodified.

**Tests.** `test_rules_effector_action.py`:
- `test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_it` (new) — the
  reviewer's own probe interleaving, reproduced against the real `_dispatch_rule`/`handle_command`
  path rather than argued from the call graph: opens a dispatch, pauses it mid-handler (past its
  own `effector.write` call, before its own error), runs the poll loop's exact drain line from the
  test thread during that open window, then lets the dispatch error. Asserts the drained batch was
  empty and nothing reached a real `EffectorRunState`/`ad_hoc_runs` — the stronger claim the review
  asked for, not just "`pending_effector_writes` ends up empty," which would also hold if the entry
  had already been drained away and started executing.
- `test_a_successful_dispatchs_write_commits_to_the_shared_list` (new) — the success side: a
  dispatch with no later error must still land its write on `pending_effector_writes` once
  `_dispatch_rule` returns.
- `test_concurrent_dispatches_do_not_lose_each_others_queued_writes` (renamed from
  `test_rollback_leaves_a_concurrent_dispatchs_own_queued_write_alone`, same two-sandbox/two-thread
  plumbing reused) — asserts only rule B's committed write is visible on the shared list while rule
  A is still paused mid-dispatch (A's own write is sitting in A's own buffer, not the shared list
  at all — a different, stronger reason than round 1's "both visible, a truncate must not drop
  either"), and that B's entry survives untouched once A later errors and discards its own buffer.
- `test_queue_effector_write_buffers_inside_a_dispatch_and_appends_directly_outside_one` (replaces
  `test_queue_effector_write_stamps_the_current_dispatch_token`, which tested the now-removed
  `dispatch_token` field directly) — exercises `queue_effector_write`'s own branch: outside a
  dispatch it appends straight to the shared list; with a buffer set on the thread-local (the same
  field `_dispatch_rule` itself opens), it appends there instead, leaving the shared list
  unchanged.
- `test_a_write_then_a_later_error_in_the_same_dispatch_is_rolled_back` and
  `test_effector_write_queued_from_background_thread_is_applied_on_next_poll_drain` — unchanged
  assertions (docstrings updated to describe buffer-then-commit instead of rollback-by-identity);
  both still exercise the behaviour they always did — the first through `_dispatch_rule`, the
  second through `run_rule` directly, confirming the no-dispatch path still works.

**Counterfactual run, not taken on faith.** Reverted `queue_effector_write` to append straight to
the shared list unconditionally (the exact round-1 shape, minus the token stamp) — `shasum -a 256`
confirmed the file's content before and after the probe. Four tests failed for the stated reason:
the new probe test, the new buffer/no-buffer test, the renamed concurrency test, and (because an
unrolled-back write now actually dispatched into Lua's own error path) the basic rollback test —
each failure traced to the missing buffer, not an unrelated break. Restored the real file;
`shasum -a 256` matched the pre-probe value exactly, and the full test file (14 tests) passed again
unchanged.

**Files changed:**
- `belief/crew_console.py` — `PendingEffectorWrite.dispatch_token` field removed;
  `_dispatch_token_local` renamed `_dispatch_write_buffer_local` (holds a buffer, not a token);
  `current_dispatch_token()` removed; `queue_effector_write` now branches on whether a buffer is
  open; `_dispatch_rule` opens/commits/discards a buffer instead of minting/filtering-by a token.
  Docstrings on all four updated or replaced, not left describing the superseded mechanism (root
  `CLAUDE.md`'s "Prune the comment you are standing next to").
- `tests/test_rules_effector_action.py` — one test renamed with updated assertions/docstring
  (`test_concurrent_dispatches_do_not_lose_each_others_queued_writes`), one test replaced
  (`test_queue_effector_write_buffers_inside_a_dispatch_and_appends_directly_outside_one`), two
  tests added (`test_poll_thread_drain_during_an_open_dispatch_window_gets_nothing_from_it`,
  `test_a_successful_dispatchs_write_commits_to_the_shared_list`), one docstring updated for
  accuracy with no assertion change; `PendingEffectorWrite` added to the existing `crew_console`
  import for the new buffer test's type annotation.

**Checks.** `.venv` built fresh from `/opt/homebrew/bin/python3.14` (none existed in this
worktree); `ruff format --check`, `ruff check`, `mypy --strict src` (91 source files) all clean.
`fast-tests.sh body-layer`: 2673 passed, 1 failed (the same named pre-existing
`test_shipped_effector_config_loads_without_errors`), 4 xfailed — matches the task brief's stated
known failure exactly. `test_rules_effector_action.py` directly: 14 tests, all pass.

**Notable discovery:** none beyond what the counterfactual run above already surfaced — no new
tuning-constant-shaped literal was introduced (a buffer is a `list`, not a magic number), and no
other module references `dispatch_token`/`current_dispatch_token`/`_dispatch_token_local` (checked
with `grep -rn` over `src/` and `tests/` before removing them; the only other hit,
`tests/test_brain_reply.py::test_confirm_of_a_real_but_unoffered_dispatch_token_is_rejected`, is an
unrelated confirm-band token with no connection to this mechanism).

## Stage 4 follow-ups (2026-11-17)

Two independent follow-up tasks on `feature/speech-rules-matching`, tip `6a6ce8e7` at the start of
this work.

### 1 — Recalibrating the collision check (audio-adapter)

**What was wrong.** D9/D13's original collision check (`rule_patterns._rules_collide`/
`_collides_with_legacy`) counted *any* sample resolving to a different rule/legacy command, at or
above a floor, as a collision — a binary "did it match at all," correct back when every ratio was
`1.0` (Stage 1b/2) but never updated once D13 made a rule's own ratio something other than always
`1.0`. That is not the user's decision (`body-layer/ROADMAP/BL-17.md`, "Settled after the goal
check": *"Two rules claiming the same wording: both disabled"* — U10, `plans/speech-rules/
plan.md`) — the same wording, not merely similar wording.

**The fix.** `rule_patterns._is_genuine_collision` (new) replaces the binary check with a
comparison between the sample's own rule's ratio and the competing resolution's ratio on the same
sample:

- an **exact tie** (`own_ratio == other_ratio == 1.0`) — the clean, unperturbed sample parses with
  zero fuzziness on *both* sides, so this exact wording is claimed, every time it is spoken, by two
  different commands. This is the literal case U10 names, and it can only arise on a clean sample
  (a perturbed one never scores `1.0` against its own generating rule, by construction);
- the other side beating the sample's own rule by at least `SEPARATION_MIN` — saying the rule's own
  wording would make Petrovich confidently act on the other command instead;
- a **fuzzy near-tie** (gap under `SEPARATION_MIN`, neither side at `1.0`) is logged at `INFO` and
  is **not** a collision — this is exactly the gap `command_matcher.match_transcript`/
  `_match_rules` already turns into a confirm question at runtime (E3), a rare mis-hearing rather
  than a deterministic clash on every utterance, so there is nothing left for load time to guard
  against.

`LegacyProbeResult` gained a `match_ratio: float` field (every call site updated: `server.py`'s
`_legacy_probe`, `test_flight_rules_matching.py`'s `_real_legacy_probe`, and every direct
`LegacyProbeResult(...)` construction in `test_rule_patterns.py`) so `_collides_with_legacy` has
something to compare the rule's own ratio against.

**Measured outcome on the real 19-rule flight set, before vs. after:**

| rule | previously rejected? | now rejected? | why |
|---|---|---|---|
| `set_speed` | yes | **no — rescued** | own `1.0` (exact) vs. `altitude_step`'s `0.5` fuzzy word-set resolution, both directions — gap `0.5` |
| `altitude_step` | yes | **no — rescued** | same pair, the other direction |
| `level_off` | yes | **no — rescued** | own `1.0` vs. the existing `observe_off` legacy command's `0.75` — gap `0.25` |
| `straight` | yes | **yes — still rejected** | `straight`'s own perturbed sample ("right," its `_best_probe_word` for "straight") matches `hvrt_translate_right` at ratio `1.0` (exact), clear of `straight`'s own `0.769` self-match on that same sample by `0.231` |
| `hvrt_translate_right` | yes | **yes — still rejected** | taken down by the *same* rule x rule collision above (`compile_rules` disables both ids in a colliding pair); its own perturbed sample ("light") lands on a genuine `0.8`-vs-`0.8` near-tie against `point`'s "sight" verb, which alone is **not** a collision under the new check |

The previous writeup's framing of `straight`/`hvrt_translate_right` as "straight vs sight" (the
*clean* sample, 0.77 both directions) was the un-recalibrated check's own false positive — under
the recalibrated check the clean sample is rescued (own `1.0` beats `0.77` clearly in both
directions); the *perturbed* sample is the real, surviving cause, and it is a genuine
confident-wrong collision, not a near-tie. `_EXPECTED_REJECTED_IDS` in
`test_flight_rules_matching.py` is now `{"straight", "hvrt_translate_right"}`; its own module-level
comment and `body-layer/tests/test_rules_flight_actions.py::test_shipped_rule_files_load_with_zero_
failures`'s docstring (a cross-reference, not an assertion — body-layer's loader never runs this
check) are both updated to the new count.

**Tests added** (`audio-adapter/tests/test_rule_patterns.py`, `TestCompileRules`):
- `test_legacy_probe_resolving_with_a_fuzzy_near_tie_is_not_a_collision` — a legacy resolution
  within `SEPARATION_MIN` of the rule's own (perturbed) ratio, neither side at `1.0`, is accepted.
- `test_legacy_probe_confidently_beating_a_perturbed_sample_is_still_rejected` — the counterfactual:
  a legacy resolution beating the rule's own perturbed ratio by `>= SEPARATION_MIN` is still
  rejected, even though the clean sample never collides.
- `test_a_perturbed_sample_confidently_resolving_to_another_rule_is_rejected` — the same
  counterfactual, rule x rule: `scan_rule`'s perturbed sample ("scam two zero," its own probe word
  for "scan") matches a second rule whose literal is exactly "scam" at ratio `1.0`, clear of
  `scan_rule`'s own `0.75`.
- `test_rule_colliding_with_legacy_is_disabled` (existing, updated) now documents and exercises the
  exact-tie case explicitly (`match_ratio=1.0` on both sides).

`plans/speech-rules/plan.md`'s D9 entry gained a dated "Recalibrated 2026-11-17" paragraph citing
U10 and this measurement.

**Checks (audio-adapter, fresh `.venv` built from `/opt/homebrew/bin/python3.14`):**
- `ruff format --check src tests`: pass (36 files)
- `ruff check src tests`: pass
- `cd audio-adapter && .venv/bin/mypy src`: pass, 17 source files, 0 issues
- `.claude/scripts/fast-tests.sh --full audio-adapter`: 526 passed, 2 skipped

### 2 — U22: flight-rule readbacks may cut off an in-flight routine callout (body-layer)

D19 proposed, and U22 confirmed ("as recommended"), reusing `CalloutScheduler.note_urgent` — the
same mechanism `!inject-urgent` already exercises — for a flight-category rule's own readback
while Petrovich has controls, rather than building a second "skip the queue without killing what's
playing" mechanism. Stage 4's own five numbered build steps never mentioned this, so it was left
unbuilt there; built now as this follow-up.

**What changed** (`body-layer/src/belief/crew_console.py`):
- `handle_command`'s shared `_print` call at the bottom of the dispatch chain now takes a local
  `bypass_gate` (default `False`), set `True` only inside the `elif token in self.enabled_rule_ids:`
  branch when the matched rule's own category starts with `"flight_control"` *and*
  `current_crew_state().has_controls` is true. `"always"`-category rules (`you_have_controls`/
  `i_have_controls`) and every static (non-rule) token are unaffected.
- `drain_pending_rule_dispatch`'s own two `_print` calls (the hold-and-retry path: a `PASS` that
  flies late, an `UNABLE`/held-timeout line) get the identical scoping, computed from
  `pending.category` and a fresh `current_crew_state()` read. `rules.gates._require_controls`
  guarantees `has_controls` is true for as long as a category holds (an `UNABLE` replaces `HOLD`
  the moment controls are lost), so the held-timeout-elapsed "unable, not ready" line is urgent too
  when it was genuinely held while flying.
- `_print`'s own docstring, which claimed "an injected urgent call is the only line that ever sets
  [`bypass_gate`]," is corrected to name this second source — a claim this change would otherwise
  have made false without anyone noticing.

**Not touched, flagged for a future opportunistic pass**: `belief/speech_worker.py`'s
`SpeechWorker.enqueue` docstring and `belief/callouts.py`'s `CalloutScheduler.note_urgent`
docstring both still say "an injected urgent call" is the (implied: only) source reaching them —
now incomplete, not wrong, since neither function's own code changed. Left alone per this role's
"stay local to the block you are editing" rule rather than swept.

**Tests added** (`body-layer/tests/test_rules_flight_actions.py`, `TestFlightReadbackUrgency`, plus
a `_RecordingSpeechClient` double and an optional `speech_client` kwarg on the existing
`_dispatching_console` helper):
- `test_a_flight_rule_readback_cuts_off_the_callout_while_flying` — `turn_heading_relative` while
  parked and settled: `push_speech` sees `urgent=True`, and a pre-set far-future
  `scheduler.busy_until_sim` is reset *down* (`note_urgent`'s own behaviour), proving the cutoff.
- `test_a_static_command_readback_never_cuts_off_the_callout` — counterfactual: `radio_check` (not
  a rule at all) leaves the pre-set busy time exactly as high (`note_reply`'s `max()`).
- `test_the_always_category_have_controls_rule_never_cuts_off_the_callout` — `you_have_controls` is
  a rule id but category `"always"`, excluded by the category check, not dispatch order.
- `test_an_unable_not_flying_readback_never_cuts_off_the_callout` — a flight rule dispatched while
  `parked_active=False` answers `UNABLE`; excluded by the `has_controls` half of the scoping.
- `test_a_held_timeout_unable_readback_cuts_off_the_callout` — `drain_pending_rule_dispatch`'s own
  hold-timeout-elapsed "unable" line gets the same urgent treatment, since `has_controls` was true
  throughout the hold.

**Counterfactual run** (showing red, not just green): both "cuts off the callout" tests were
confirmed to fail against the pre-fix code (`bypass_gate` forced `False` at both of
`crew_console.py`'s new call sites) — `AssertionError: [('Unable, not ready.', False)] ==
[('Unable, not ready.', True)]` and the equivalent for the immediate-dispatch test — while the
three negative-space counterfactual tests stayed green throughout, confirming they were not
tautological. Restored by `shasum` match (`f0c8614a...` before and after) rather than by eye.

**Checks (body-layer, fresh `.venv` built from `/opt/homebrew/bin/python3.14`, `lupa==2.8`,
editable `../world-model`):**
- `ruff format --check src tests`: pass (223 files)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, 91 source files, 0 issues
- `.claude/scripts/fast-tests.sh body-layer`: 1 failed (named pre-existing
  `test_shipped_effector_config_loads_without_errors`), 2671 passed, 4 xfailed
- `.claude/scripts/fast-tests.sh --full body-layer`: same single pre-existing failure, 3524 passed,
  4 xfailed

## Performance fix (collision check)

Required Fix 1 from the performance review of this batch (`plans/speech-rules/
performance-stage3-4.md`): `audio-adapter/src/rule_patterns.py::compile_rules`'s rule x rule and
rule x legacy collision passes each called `_samples_with_perturbation(rule)` fresh on every
pair/rule they were called with, instead of once per rule, turning D13's intentional O(n^2) check
into a much worse multiplier (measured 66-107x at 100-200 rules, ~2.8-3.1s against body-layer's
5.0s `PUT /rules` client timeout at the plan's own ~100-rule target).

**What changed** (`audio-adapter/src/rule_patterns.py`):
- `compile_rules` now computes `samples_by_id: dict[str, list[str]]` once per accepted rule,
  right after the parse loop and before the rule x rule pass, and passes each rule's precomputed
  sample list into `_rules_collide`/`_collides_with_legacy` as parameters instead of letting those
  functions call `_samples_with_perturbation` themselves.
- `_rules_collide(rule_a, rule_b)` -> `_rules_collide(rule_a, samples_a, rule_b, samples_b)`.
- `_collides_with_legacy(rule, legacy_probe)` -> `_collides_with_legacy(rule, samples, legacy_probe)`.
- No change to D9's collision semantics, D13's fuzz behaviour, or `_is_genuine_collision`'s own
  three-way split — this is a pure memoization of an already-pure, already-deterministic per-rule
  computation, the same shape as `rule_anchor_words` (D15) and `CachedRulePromptProvider`.
- **"Cache per-rule legacy-probe results" (the review's optional second ask), checked and not
  applicable**: `_collides_with_legacy` is already called exactly once per accepted rule inside
  `compile_rules`'s rule x legacy pass (`for rule_id in ids: ... _collides_with_legacy(...)`) —
  there is no second call site and no pair-wise loop around it, so `legacy_probe` was never called
  more often than the genuinely-necessary once-per-rule-per-sample count. The precomputed-samples
  fix above already removes the one redundant computation this pass had (`_samples_with_
  perturbation` itself); there was nothing further to memoize without changing behaviour.

**Tests added** (`audio-adapter/tests/test_rule_patterns.py`, `TestCompileRules`):
- `test_samples_with_perturbation_computed_once_per_rule` — call-count spy on
  `rule_patterns._samples_with_perturbation`, same style as `TestRuleAnchorWordsAndRegistrySwap.
  test_swap_computes_anchor_words_exactly_once`. Four of the real shipped `flight.lua` patterns
  (collision-free, so a legacy-probe-only `calls` list is unambiguous), asserts `len(calls) == 4`
  and that every id appears exactly once.
- No accept/reject-outcome test was added beyond the existing suite — this review explicitly asks
  for an identical-outcome pin on "the real shipped flight rules plus a synthetic ~100-rule set,"
  and `test_flight_rules_matching.py::test_the_real_shipped_pattern_set_rejects_exactly_the_known_
  collisions` (unmodified, still passing) already is that pin for the real 17-rule set; a
  synthetic ~100-rule outcome pin would only be checking that padding rules with distinct literals
  never collide with each other or the real set, which is true by construction of the padding and
  adds no coverage the call-count test does not already imply (the precomputed-samples path is
  read by the identical `_is_genuine_collision` call, unchanged).

**Counterfactual run (showing red, not just green)**: the new call-count test was run against the
pre-fix `rule_patterns.py` (`git show 688d500b:audio-adapter/src/rule_patterns.py`, imported from
a separate path, same 4-rule scenario) — it called `_samples_with_perturbation` 16 times, not 4,
confirming the test is not tautological. Full before/after module diff staged normally, no
revert/restore needed on the working tree itself (the counterfactual ran against a throwaway copy
under `/tmp`, never the worktree's own file).

**Re-measured timings** (real `compile_rules`, real 17 `flight.lua` patterns +
`test_flight_rules_matching.py`'s own `_real_legacy_probe`/`FREE_SPEECH_GUARD`, padded with
distinct synthetic literal rules to each target `n`, median of 3 runs, `/opt/homebrew/bin/
python3.14`, no cProfile overhead):

| rules | this fix (after) | pre-fix (performance review's own measurement) |
|---|---|---|
| 18 | ~21 ms | 49 ms |
| 50 | ~63 ms | 791 ms |
| 100 | ~185 ms | 2.76-3.15 s |

At the plan's own U6 ~100-rule target this removes essentially all of the regression the
performance review measured — 100 rules now costs well under 4% of body-layer's 5.0s `PUT /rules`
client timeout, down from 55-63% — leaving only the genuinely-necessary O(n^2)
`match_pattern_with_ratio` pairwise cost, consistent with the review's own stated expectation.
(Absolute numbers differ somewhat from the review's own synthetic-rule mix, as expected for a
different padding scheme; the shape and magnitude of the fix are what's being confirmed, not an
exact-number match.)

**Checks (audio-adapter, fresh `.venv` built from `/opt/homebrew/bin/python3.14`, stdlib only):**
- `ruff format --check src tests`: pass (36 files)
- `ruff check src tests`: pass
- `cd audio-adapter && .venv/bin/mypy --strict src`: pass, 17 source files, 0 issues
- `.venv/bin/python -m pytest tests -q` (full suite, not just fast-tests): 526 passed, 2 skipped
- `.claude/scripts/fast-tests.sh audio-adapter`: 472 passed, 2 skipped

### Security fix (stages 3-4) — 2026-11-17

`plans/speech-rules/security-stage3-4.md` Required Fix 1: `body.py`'s own `_poll_transcripts`
slot-value filter was never actually widened for the union-slot case (see the correction inserted
above, in the "Two genuine bugs found and fixed" section) — `isinstance(value, (int, str))` alone
still silently dropped any slots dict carrying `set_speed`'s `speed_target` tagged table
(`{"kind": "max"}` / `{"kind": "number", "value": N}`), so "speed max"/"speed two hundred" over the
real audio-adapter → body-layer wire did nothing and said nothing, with no existing test crossing
that specific boundary to catch it.

Fixed in `body-layer/src/body.py`: two new module-level helpers immediately above
`_poll_transcripts`, `_is_bounded_slot_dict` (one level deep, `str` keys, `int`/`str`-not-`bool`
values, at most `_MAX_SLOT_DICT_KEYS` (4) keys — generous headroom over the 1-2 keys
`_consume_speed_target` ever actually produces, not a tight fit) and `_is_valid_slot_value` (a
scalar or a bounded dict; anything else — an unbounded/nested dict, a list, ... — rejected exactly
like a malformed scalar already was). `_poll_transcripts`'s own validation loop now calls
`_is_valid_slot_value` per slot value instead of the old bare `isinstance(value, (int, str))`
check. `_MAX_SLOT_DICT_KEYS` is a plain `Final` literal, not a `tuning.*` declaration — it bounds
an external process's own wire shape, never Petrovich's behaviour (root `CLAUDE.md`'s inclusion
test for the tuning mechanism).

**Deliberately scoped to `body.py` alone** — `crew_console.py`'s `handle_transcript`/
`handle_command`/`_handle_rule`/`_dispatch_rule` and `rules.engine.run_rule` all keep their
existing `dict[str, int | str] | None` slot type unchanged. The real `slots_raw` value entering
`_poll_transcripts` is `Any` (`AudioAdapterClient.get_transcripts() -> tuple[list[dict[str, Any]],
...]`), so assigning a dict that may itself hold a bounded nested dict to a locally-declared
`dict[str, int | str] | None` variable, and passing that straight through every downstream
signature declaring the same narrower type, type-checks under `mypy --strict` without a `cast` —
`Any` absorbs the mismatch at the one point it is introduced, same as it already did before this
fix. Widening every signature on the full dispatch path (`handle_transcript` through to
`run_rule`) was considered and rejected: `handle_command`'s own `slots` parameter is shared by
every token branch, including roughly a dozen unrelated handlers (`_handle_follow`,
`_handle_select_target`, `_handle_mark_target`, `_handle_step`, `_handle_engage`,
`_handle_where_is_it`, `_handle_point`, `_handle_slotted_report`, `_handle_greeting`, ...) that
never see a dict-valued slot in practice — widening it would have cascaded into every one of
those signatures (and transitively into the dataclass fields some of them write, e.g.
`PendingPointRequest.slots`) for zero behavioural gain, which is well past Required Fix 1's own
scope. The one place a dict value is ever actually read apart (`rules.engine.run_rule`'s
`sandbox.table_from(slots)`) already accepts it correctly at runtime regardless of the static
type given to it, confirmed by the new end-to-end test below.

**Tests added** (`body-layer/tests/test_body.py`):
- `test_poll_transcripts_threads_a_dict_valued_slot_into_handle_transcript` — the mirror of the
  pre-existing `test_poll_transcripts_threads_slots_into_handle_transcript`, for a `speed_target`
  tagged-table value: asserts the dict reaches `handle_transcript` intact rather than being
  dropped.
- `test_poll_transcripts_skips_items_with_an_oversized_slot_dict` — a 5-key dict (over
  `_MAX_SLOT_DICT_KEYS`) is rejected.
- `test_poll_transcripts_skips_items_with_a_nested_slot_dict` — a dict whose own value is itself a
  dict (two levels deep) is rejected, not recursively admitted.
- `test_poll_transcripts_drives_a_real_speed_two_hundred_wire_item_to_set_speed` — the one
  end-to-end test the security finding asked for: a real wire-shaped "speed two hundred" item
  driven through the real `_poll_transcripts` → `handle_transcript` → `handle_command` →
  `_handle_rule` → `_dispatch_rule` → `rules.engine.run_rule` → the real shipped `flight.lua`'s
  `set_speed` rule (no doubles anywhere on that path, mirroring
  `test_rules_flight_actions.py`'s own `_dispatching_console` wiring, kept local rather than
  imported across test files per that file's own stated precedent); asserts
  `console.ai_pilot_goal_transition == AiPilotGoalRequest(param="speed", speed_kmh=200.0)`.
  Updated the pre-existing `test_poll_transcripts_skips_items_with_a_malformed_slot_value`'s own
  docstring (it asserted "a slots value must be `int | str`," no longer accurate on its own).

**Counterfactual run (showing red, not just green)**: restored the pre-fix validator
(`isinstance(value, (int, str)) and not isinstance(value, bool)`, dropping the new
`_is_valid_slot_value` call) and re-ran the four new tests. The two threading tests
(`test_poll_transcripts_threads_a_dict_valued_slot_into_handle_transcript` and
`test_poll_transcripts_drives_a_real_speed_two_hundred_wire_item_to_set_speed`) failed for the
stated reason (`console.calls == []` / `console.ai_pilot_goal_transition` stayed `None`); the two
rejection tests (oversized/nested dict) stayed green throughout, confirming they are not
tautological — both the old and the new code reject those shapes, so they would only ever go red
if a future change admitted too much, not too little. Restored by `shasum` match (`f0af0ae5...`
before and after) rather than by eye.

**Checks (body-layer, same `.venv` as above):**
- `ruff format --check src tests`: pass (224 files, `test_body.py` reformatted once for the new
  tests' import ordering)
- `ruff check src tests`: pass
- `cd body-layer && .venv/bin/mypy src`: pass, 91 source files, 0 issues
- `pytest tests/test_body.py -k poll_transcripts -v`: 17 passed (13 pre-existing + 4 new), every
  one confirmed by name, not by a `-k` count alone
- `pytest tests/test_body.py -q`: 1 failed (the same pre-existing, unrelated
  `test_shipped_effector_config_loads_without_errors`), 227 passed
- `.claude/scripts/fast-tests.sh body-layer`: 1 failed (same pre-existing failure), 2681 passed,
  4 xfailed
