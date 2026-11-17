# BL-17 Stage 1b + Stage 2 — Review

Branch `feature/speech-rules`, tip `4dc79825` (fast-forwarded from `6fb23698`, a strict
ancestor; tree was clean). Reviewed commits `e417d852` (Stage 1b), `41c8d72e` (Stage 2),
`4dc79825` (implementer memory). Stage 0 (lupa spike) and Stage 1a (bearing/heading rename)
were out of this review's scope per the orchestrator's instructions — Stage 1a is explicitly
paused and parked on `wip/bl17-stage1a-rename`; its absence here is not a finding.

### Review Summary

Full read of `plans/speech-rules/plan.md`, `implementation.md`, `body-layer/ROADMAP/BL-17.md`,
`alignment.md`, the Stage 0 research note, and every changed source file in the two stages
(`rules/sandbox.py`, `loader.py`, `engine.py`, `actions.py`, `crew_console.py`, `body.py`,
`audio_client.py` on body-layer; `rule_patterns.py`, `command_matcher.py`, `server.py`,
`vocabulary.py`, `stt_engine.py`, `__main__.py` on audio-adapter) plus every new/changed test
file. Built fresh venvs for both subprojects (`/opt/homebrew/bin/python3.14`) since none existed
in this worktree, and ran format/lint/type/test for both — all clean (details below). Ran
`/invariant-check` — all PASS except two pre-existing WARN classes (`type: ignore`, swallowed
exceptions in entrypoints), neither newly introduced by this diff beyond the one sanctioned
`# type: ignore[import-untyped]` in `sandbox.py` that the plan itself specified.

This is careful, well-scoped work. The sandbox isolation (allowlist-by-omission, fresh-copy
`string` table, instruction-budget abort via a Lua shim, binary-chunk refusal) matches the
Stage 0 research note's own findings exactly, with real probes behind every claim. The
`enabled_rule_ids`/`_ever_enabled_rule_ids` split correctly distinguishes "a rule id that was
dropped" (`NO_SUCH_COMMAND`, D4) from "a token that was never a command" (silent+logged,
unchanged). The action-file-error rollback (`_reset_one_shot_command_state`) is exercised with a
test that proves the rollback actually clears a field a fake handler set before erroring, not
just that the line is spoken. The differential test for Stage 2's port
(`test_rules_flight_actions.py`) loads the **real** shipped `flight.lua`, not a fixture, and
reproduces all five of the old handler's cases (left/right, wrap past 0/360, `NOT_READY`).

I checked the ledger (`accepted-items-ledger.sh plans/speech-rules`) by hand rather than only
reading its mechanical flags. Every `U<n>` it reports as "never named in implementation.md"
traces to one of: (a) Stage 1a's explicit pause (U2, U3, U9 — out of scope per instructions),
(b) a later stage the plan's own stage table already names (U5→Stage 7, U6→later-stages table,
U14–U16→Stage 8, U17→Stage 10 — none of these were supposed to be built in Stage 1b/2), or (c)
genuinely built in this diff but not cited by its `U<n>` literal in `implementation.md`'s prose
(U8's sequencing, U10's duplicate-both-disabled, U12's AI-overlay target, U13's fixed phrase,
U18's in-repo rule-file location — all confirmed built by reading the code above). No decision
that this run's own scope (Stage 1b/2) was supposed to deliver is missing or silently dropped.

### Required Fixes

1. **`plans/speech-rules/plan.md`'s D8 text no longer describes what was built, and will
   mislead a future reader who trusts the plan as the recorded design.** D8 says rule literals
   are "scored with the existing word-sequence scorer `_phrase_match_ratio`... The existing
   floors are reused." What actually shipped (`rule_patterns.py`'s own module docstring,
   `match_pattern`) is full-consumption, exact-literal matching with no fuzzy tolerance on a
   rule's own words — `match_ratio` is always `1.0` on a rule hit. This is a reasonable,
   well-justified scope-down (see judgement below), and it is honestly disclosed in
   `rule_patterns.py`'s docstring and `implementation.md`'s "Notable Discoveries" — but the plan
   document itself, which this project treats as the decision record, still states the
   abandoned design as if it were built. Add a short dated addendum to D8 (or a note in
   `BL-17.md`'s settled log) recording the actual scope and the reason, the same way other
   superseded decisions in this plan are marked rather than silently left stale
   (`docs/PROCESS.md`'s supersession rule). This is a documentation-only fix, not a code change.

### Judgement calls the implementer flagged

**1. Import-cycle resolution via injected `legacy_probe` (`server.py`'s `_legacy_probe`,
`rule_patterns.compile_rules`'s `legacy_probe` parameter).** Correct. `command_matcher.py` must
import `rule_patterns` for its own D8 branch; `rule_patterns.py`'s D9 collision check needs the
real legacy matcher. Importing `command_matcher` back into `rule_patterns.py` would be a genuine
cycle. Dependency injection at the one module (`server.py`) that already imports both is the
right fix, and `LegacyProbeResult` narrows the surface to exactly the two fields D9 needs rather
than leaking `MatchResult`'s full shape. No concern.

**2. Full-consumption exact-literal matching instead of D8's fuzzy scoring.** Acceptable for
Stage 3's test flight, for three concrete reasons I verified rather than took on faith:
- `strip_filler`/`normalize_for_match` already run before rule matching, so punctuation and
  filler words are gone by the time a rule's pattern sees the transcript. I ran the three
  examples from the task brief through the real matcher with the real shipped pattern:
  `"turn left 30"`, `"Turn left, 30."`, and `"turn left thirty"` all behave as expected — the
  first two both resolve to `turn_heading_relative` with `degrees=30` (comma-stripping and the
  `angle` slot's "whole numeral" form both do their job), the third correctly fails to match
  (no digit-by-digit or whole-numeral form for "thirty") and falls through to `verb_anchored=True,
  token=None` — the "say again" shape, not silence. I also tried an inserted filler word,
  `"uh turn left two zero"`, which still matches — filler stripping absorbs it.
  - This third case is not a regression: the legacy `parse_turn_relative` it replaced also only
    accepted digit-by-digit/whole-numeral via `_read_digits_after`, never a number word like
    "thirty". Exact parity on the one real risk axis (number parsing) that matters here.
- The rule's own literal words ("turn", "left"/"right") are short, common, unambiguous English
  words, and `--whisper-model`'s prompt bias already favours them (`_rule_anchor_words`/`to_prompt`
  via D10). The dimension exact-literal matching is actually weaker on — tolerance for a
  *mis-transcribed* literal word itself (not a filler insertion, not digit format) — has no
  test exercising it and is a real, if narrow, gap versus the fuzzy legacy path for this one
  word pair.
- This is explicitly a scope decision for *this* stage (one rule, two short literals), not a
  settled architecture for every future rule. Flight-control commands are next (per the
  checkpoint's stated re-plan order); scan/report/watch commands have longer, more varied
  literal phrasing where exact-literal matching's weaker tolerance will matter more. I'd treat
  revisiting this (adding literal fuzzy tolerance, or measuring whether it is actually needed
  from the Stage 3 flight's own `--speech-log`) as a near-term backlog item for the Stage
  4+ re-plan, not a blocker now — but it should be an explicit line item in that re-plan, not
  rediscovered the way "attack"/"tanks" was. (Optional, not required — see below.)

**3. The extra grows-only `_ever_enabled_rule_ids` set.** Correct and necessary, not a
workaround. `enabled_rule_ids` alone cannot distinguish "a rule id that was once valid and has
since been dropped" (D4: must answer `NO_SUCH_COMMAND`) from "a token that was never a command at
all" (must stay silent, the pre-existing, still-tested case). The mirrored shape to
`_ever_enabled_rule_ids`'s own docstring is consistent with how `config_error_pending`/process-
lifetime fields already work in this file, and `test_mission_start_reset.py`'s generic
reset-completeness check (which the implementation.md notes caught this on first run) is exactly
the mechanism that should catch a future field added without updating the preserve-set.

**4. The flaky `test_slew_trace_is_written_from_the_real_poll_loop`.** I ran the full body-layer
suite twice (once via `fast-tests.sh --full`, in addition to the targeted fast run) and it did
not reproduce either time (3472 passed, 0 flakes both runs — close to the implementer's own
3473/4 count, the one-off difference not traced and not concerning). Nothing in this diff plausibly
causes it: the reported failure is a background poll-loop thread logging through a closed stream
during test teardown, in `_log_live_los_coverage_summary`/watched-args code this stage never
touches, and BL-17's own new background state (the rule engine, `RuleRuntime`) runs synchronously
on the poll thread, not a new thread. Read as pre-existing `pytest-xdist` parallel-teardown
flakiness, correctly flagged rather than silently reconciled by the implementer, and not a
blocker.

### Checklist verification

- **Invariants**: `/invariant-check` — all PASS (no omniscience leak, module independence, no
  `sys.path` smuggling, `BINOCULAR_RANGE_MULTIPLIER` absent, no stray `print()` in belief/
  perception core, no bare `except`); WARN items (type suppressions, swallowed exceptions) are
  pre-existing classes, and the one new `type: ignore[import-untyped]` (`sandbox.py:38`) is
  exactly the confined, plan-specified exception.
- **Player-facing correctness**: `increment_ai_heading`'s math and `NOT_READY` case are proven
  identical to the deleted handler (differential test). No omniscience leak — actions never touch
  `Percept`/ground truth; rules only call `flight.increment_heading`, which reads
  `parked_flight_state.held_heading`, already a belief-side field. Callouts/cockpit actions:
  unchanged readback wording, same `AiPilotGoalRequest` shape consumed the same way by `body.py`'s
  existing poll-loop application. Co-moving state: `RuleSet.version`/`enabled_rule_ids`/
  `adapter_accepted_version` are threaded together correctly at every construction site I could
  find (`main()`, `_check_for_new_mission`, `_push_rules`) — there is exactly one real call site
  for `_check_for_new_mission` in `body.py` (grepped), so the new `rule_runtime`/`audio_client`
  parameters cannot have been missed at a second site.
- **Type hints / `mypy --strict`**: clean on both subprojects (89 body-layer files, 17
  audio-adapter files), confirmed by running it myself from inside each subproject.
- **Provenance/confidence for mixed DCS+GIS features**: not applicable — this feature touches no
  GIS-derived data.
- **DCS-internals claims without `research/` backing**: none made; the one DCS-adjacent claim
  (lupa sandbox behaviour) has a dated, probe-backed research note (Stage 0) that this diff's
  code matches exactly.
- **Coordinate transforms / coordinate math confinement**: not applicable.
- **Read-only DCS extraction**: not applicable — no DCS install access in this diff.
- **`world-model/data/` staging**: not applicable.
- **Tuning mechanism for behaviour-affecting constants**: correctly *not* used. The plan's own
  "Existing constants checked" section pre-identified the three new constants
  (`RULE_LOAD_INSTRUCTION_BUDGET`, `RULE_DISPATCH_INSTRUCTION_BUDGET`, `_MAX_SAY_LEN`) as safety
  bounds, not behaviour, and I agree: they only matter when something has already gone wrong
  (a runaway loop, a pathological `say` call), never shaping what Petrovich does in the normal
  case, the same carve-out root `CLAUDE.md`'s tuning section states for buffer sizes and internal
  epsilons. No `defaults.toml` change was needed or made; grepped to confirm no `tuning.*` call
  was added anywhere under `rules/`.
- **Spoken vocabulary vs. STT prompt agreement**: `test_vocabulary.py`'s prompt-coverage test
  passed in both the targeted and full runs. `turn_heading_relative` is correctly removed from
  `PHRASES`/`TOKENS`/`recognised_words()`'s inputs (it's a rule now); its words instead reach the
  prompt via `rule_words()`/`_rule_prompt_provider`'s `extra_words` path (D10), verified by reading
  `__main__.py`'s wiring. One open, already-flagged gap for a *future* stage: a slot type's own
  fixed anchor word (e.g. `heading`'s literal "heading") is not picked up by `rule_words()`
  because it lives inside the slot type's `consume`, not the grammar string — `rule_patterns.py`'s
  own docstring flags this for whichever future rule first uses `heading`. Not a problem today
  since no shipped rule uses it yet; worth remembering when Stage 10 arrives.
- **Comment pruning**: spot-checked the `turn_heading_relative` removal in
  `vocabulary.py`/`crew_console.py`/`command_matcher.py`. Durable lines (dated quotes, measured
  figures) were preserved; one comment comparing `altitude_step` to `turn_heading_relative`'s
  design pattern was correctly kept as prose rather than deleted, since the comparison is still
  accurate after the move (implementation.md's own account of this matches what I found in the
  diff).
- **Accepted-items ledger**: run and read by hand — see Review Summary above. No decision this
  run's scope owed was missing.
- **New mechanism's own call site, not the file list**: grepped `_check_for_new_mission(` (one
  real call site in `body.py`, confirming the mission-restart reload/re-push wiring reaches the
  only place it needs to), `rule_runner`/`enabled_rule_ids` (set from exactly one place each,
  `set_enabled_rule_ids`), and `match_transcript(` call sites in `server.py` (the one real
  `/transcribe` path passes `rules=rule_state.rules`).
- **Scope fit**: matches Stage 1b/2's stated scope exactly, no more (no Stage 3 flight-card
  execution claimed, no Stage 4+ rules shipped) and no less (every Stage 1b/2 line item in the
  plan's "Affected modules"/stage description is present).
- **Module responsibility**: `sandbox.py` is the sole `lupa` importer (grepped — confirmed);
  `rules/` imports `belief.*` (one direction, as D4 requires) and `belief.crew_console` imports
  nothing from `rules.*` (confirmed by reading the file — `rule_runner` is a plain tuple-callable
  type, not `rules.engine.RuleOutcome`). Actions mirror `BrainTool`'s shape without reusing it
  directly, matching D5's stated, named departure.
- **Tests**: meaningful throughout, not decorative — spot-checked `test_rules_sandbox.py`,
  `test_rules_engine.py`, `test_crew_console_rules.py`, `test_rule_patterns.py`,
  `test_command_matcher_rules.py`, `test_rules_api.py`, `test_rules_flight_actions.py` in full.
  Every denial/rollback/collision case asserts the actual behaviour (e.g. the rollback test sets
  a one-shot field *inside* the fake erroring handler and asserts it was cleared, not just that
  the error line was spoken).
- **Unnecessary abstraction/duplication**: none found. `ActionParam`/`Action` deliberately mirror
  `BrainTool`'s shape without importing it (named departure, D5); `unable`/`digits` reuse
  `render_unable`/`_digit_readback` verbatim rather than re-implementing them.
- **Performance/correctness regression risk**: the one shared `lupa.LuaRuntime` is accessed from
  both the REPL thread and the poll thread (R4) — Stage 0's own research note verified the global
  per-runtime lock serializes this correctly (16,000 concurrent calls, zero lost increments), and
  the instruction-budget cap bounds how long either thread can hold it. No new unbounded loop or
  per-poll allocation found.
- **New files staged**: confirmed — working tree is clean (`git status --porcelain` empty) before
  and after my own checks; nothing new added by my review needed staging beyond this report.
- **Checks per touched subproject**: `ruff format --check`, `ruff check`, `mypy --strict` (run
  from inside each subproject), and `.claude/scripts/fast-tests.sh <subproject>` all pass for
  both `body-layer` and `audio-adapter`. I also ran `--full` for both as an extra confidence check
  given the flagged flaky test (see judgement call 4) — both full suites passed clean (body-layer:
  3472 passed, 4 xfailed in ~148s; audio-adapter: 480 passed, 2 skipped in ~5.5s).
- **Debug code / stray TODOs**: none found (`/invariant-check`'s TODO/FIXME/HACK/XXX check PASS).

### Optional Refinements

- Add a `coroutine` case to `test_rules_sandbox.py`'s denylist test, for parity with the denylist
  this module's own docstring documents (`io`/`os`/`debug`/.../`coroutine`). The allowlist-by-
  omission design already excludes it correctly (confirmed by reading `base_env()` — it is never
  copied in), so this is pure test-documentation completeness, not a real gap; lupa escape-vector
  review against a hostile author is already correctly deferred to `BL-B95` for the
  multi-author/stranger-scripts threat model.
- Consider one adversarial-STT test case in `test_command_matcher_rules.py` or
  `test_rules_flight_actions.py` exercising a mis-transcribed (not just filler-inserted) literal
  word against the shipped `turn_heading_relative` pattern, to have a concrete measurement on file
  before Stage 4+ rules (with longer literal phrasing) make the exact-literal-matching tradeoff
  matter more.
- `server.py`'s `_handle_put_rules` sets `rule_state.rules` and `rule_state.version` as two
  sequential, non-atomic assignments. `ThreadingHTTPServer` could in principle serve a
  `/transcripts/poll` request between them and see new rules with the old version header for one
  request — harmless (D2's re-push is idempotent, and `.rules` itself is still swapped with one
  assignment as D8 requires), but a `RuleRegistry.apply(version, rules)` setter would close even
  this theoretical window. Not required.

### Verdict

**APPROVED WITH MINOR FIXES** — one required fix, and it is a documentation-only correction to
`plans/speech-rules/plan.md`'s D8 text (no code change). Every other checklist item passes; the
implementation is careful, the sandbox isolation is real and probe-verified, the test coverage is
meaningful, and the plan/decision ledger traces cleanly for this run's actual scope.

### Review Confidence

Full read. Every changed source file in both subprojects was read in full; every new test file
was read in full or spot-checked with representative classes read in full
(`test_rules_sandbox.py`, `test_rules_engine.py`, `test_crew_console_rules.py`,
`test_rule_patterns.py`'s `TestParsePattern`/`TestAngleSlot`, `test_command_matcher_rules.py`,
`test_rules_api.py`, `test_rules_flight_actions.py` — all read in full; `test_rules_loader.py`
was spot-checked against its docstring and the loader source rather than read line-by-line, low
risk since its five stated cases map directly onto `loader.py`'s own short, already-read
functions). Checks run directly (not delegated): both subprojects' `.venv`s built fresh, `ruff
format --check`/`ruff check`/`mypy --strict` run from inside each subproject, `fast-tests.sh` and
`fast-tests.sh --full` both run for both subprojects. The exact-literal matching judgement call
was verified by running the real matcher against the task brief's own three example transcripts,
not only by reading the code.
