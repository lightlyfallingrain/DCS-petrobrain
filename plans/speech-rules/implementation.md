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
  `int()`, degrading to `render_unable("").text` ("Unable.") on rejection — the same graceful-
  degradation posture `_make_action_wrapper` already uses. `""` is deliberately not one of D11's
  closed reason tokens (it reads as "no specific reason," not a fabricated `ACTION_FILE_ERROR_
  LINE`-style token). Named rather than a lambda so it carries its own docstring and is callable
  from a test without going through Lua.
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
