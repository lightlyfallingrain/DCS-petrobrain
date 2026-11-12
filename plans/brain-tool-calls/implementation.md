# BR-2 brain tool calls — implementation log

## Stage 0 (probe)

### Implementation Summary

Stage 0 of `plans/brain-tool-calls/plan.md` (BR-2): the tool-call-form measurement probe,
fixture, research stub and tests. Agent sandboxes have no route to Ollama and did not attempt
one — the deliverable is the tooling the user runs on the Mac, plus a stub research note with the
exact command lines to fill it in.

### Files Changed

- `brain-layer/src/ollama_client.py` — added `OllamaUsage`, `ToolCall`, `ChatResult` dataclasses;
  `chat()` (native `/api/chat` with `tools`, for Stage 0's "native" form) and
  `generate_with_usage()` (same request as `generate()`, also returning `prompt_eval_count`/
  `eval_count`). Both share request/response handling via a new `_post_json` helper.
  `generate()` itself is unchanged in behaviour (now a thin wrapper over
  `generate_with_usage()`), so `decider.OllamaDecider` is untouched. **`chat()` reproduces
  `generate()`'s own unbounded `response.read()` — `[[BR-B3]]`, still open — rather than fixing
  it here**; flagged below rather than silently carried.
- `brain-layer/tools/stage0_tool_call_probe.py` (new) — the CLI. Loads `stage0_cases.json`,
  builds a byte-stable system prompt per form (R3), drives each case through up to
  `--max-rounds` tool-call rounds (default 4, standing in for the not-yet-built body-side
  `BRAIN_MAX_TOOL_ROUNDS`) plus one final round, answering every tool call from the case's own
  canned observation, and records per round: latency, prompt/eval tokens, well-formedness, step
  match, and final-reply correctness. Prints a per-case verdict line and a markdown summary
  table (correct/total, mean/max round latency, max prompt tokens, cases needing >2 rounds) per
  `(form, num_ctx)`; `--out` writes the full per-round JSON.
- `brain-layer/tools/stage0_cases.json` (new) — 15 cases, one per utterance in the plan's
  "Acceptance set (A1 categories)" section (the two place-report bullets and the two
  `FIXED_COMMAND_ONLY` bullets are each two separate cases), the shared 7 query-tool specs,
  `BRAIN_COMMANDS`-shaped allowlist, header fixtures (clock/range/landmark text only, no x/z per
  D2), canned observations, and expected step sequence + final reply. Includes both
  `FIXED_COMMAND_ONLY` cases and the one `CANNOT_ANSWER` case the task asked for explicitly.
- `brain-layer/research/2026-11-12-tool-call-form.md` (new) — stub: question, method, the exact
  `PYTHONPATH=src .venv/bin/python tools/stage0_tool_call_probe.py ...` command lines (joint and
  per-`num_ctx`), empty results tables, and a conclusions section with the four questions it
  needs to answer, marked "to be filled in from the run."
- `brain-layer/tests/test_ollama_client.py` — extended the fake Ollama server to also answer
  `/api/chat` and to carry configurable `prompt_eval_count`/`eval_count`; added tests for
  `chat()` (tool-call parsing, no-tool-call content, malformed `tool_calls`, missing `content`,
  unreachable server) and `generate_with_usage()` (counts returned, counts default to 0 when
  absent, and a regression test that `generate()`'s own two-argument-in/text-out contract is
  unchanged by the refactor).
- `brain-layer/tests/test_stage0_tool_call_probe.py` (new) — loads the probe module via
  `importlib` (mirroring `body-layer/tests/test_generate_effector_registry.py`'s pattern for a
  `tools/` script not on `pythonpath`). Covers the grammar parser (`CALL`, all four `FINAL ...`
  shapes, malformed text, case-insensitivity), native `tool_calls` extraction (single call,
  multiple calls → not well-formed, content-only final, malformed content), the case loader
  (a small inline fixture, plus a test that loads the actual shipped `stage0_cases.json` and
  checks its tool/case counts and that both `FIXED_COMMAND_ONLY` cases and the one
  `CANNOT_ANSWER` case are present), `find_observation`'s by-tool-name matching, and the round
  loop itself driven by scripted fake clients (`_FakeGrammarClient`/`_FakeNativeClient`) for:
  call-then-final, a malformed reply ending the turn, exceeding the round cap, the native form's
  call-then-final path, and a transport error being recorded rather than raised out of the loop.

### Tests Added

See the `test_ollama_client.py` and `test_stage0_tool_call_probe.py` bullets above — 25 new test
functions in total (11 in `test_ollama_client.py`, 14 in `test_stage0_tool_call_probe.py`).

### Checks

(brain-layer/ — `cd brain-layer`; no committed `.venv` existed in this worktree, so one was
created fresh with `python3.12 -m venv .venv && pip install ruff mypy pytest`, matching the
subproject's declared tool versions, not a project dependency change)

- `ruff format src tests tools`: pass (formats cleanly; see note below)
- `ruff check src tests tools`: pass — "All checks passed!"
- `mypy src tools`: **3 pre-existing errors, none from this change** — `tools/
  live_cross_process_check.py:29-31`, `import-not-found` on `belief.brain_client`/
  `belief.escalation`/`belief.utterance`. That file predates this task, is untouched by it, and
  was never covered by the subproject's own documented `mypy src` command (only `tools` passed
  on this task's wider check command reaches it). `mypy src tools` restricted to this task's own
  files (`src/ollama_client.py`, `tools/stage0_tool_call_probe.py`) is clean.
- `pytest -q`: pass — 74 passed (up from 49 before this change: 25 new).

**Note on `ruff format ... tools`**: it also reformats `tools/live_cross_process_check.py`
(pure whitespace, two `print(f"...")` calls wrapped onto their own lines) — a pre-existing file
this task did not touch otherwise. Reverted that file after each format/lint pass so this
branch's diff stays scoped to Stage 0's own deliverables; whoever next edits that file will hit
the same reformat and may want to land it as its own small commit.

### Notable Discoveries

- **The plan's acceptance-set bullet list is 15 utterances, not 13.** Re-reading "Petrovich,
  anything near Gemerek? and ...report south of Gemerek" and "arm the weapons" / "turn left" as
  the two separate utterances each bullet actually names (rather than one bullet = one case)
  gives 15, not the ~13 a first skim suggests. Both the fixture and its loader test assert 15;
  said here because a future reader recounting bullets by eye will plausibly land on 13 too.
- **`BRAIN_MAX_TOOL_ROUNDS` does not exist yet** (plan D9 is body-side, Stage 1+, not built in
  this stage) — the probe's `MAX_TOOL_ROUNDS = 4` is a local stand-in at the same default, not
  an import, so Stage 2's real tunable and this probe's cap can drift independently once the
  real one ships. Worth re-measuring Stage 0 if that default changes before BR-2 Stage 2.
- **`chat()`'s read-cap gap is the only place this task touched code BR-B3 already flags.**
  Folding BR-B2/BR-B3 into Stage 2 is U4 (accepted, "recommend yes" in the plan) — out of scope
  for Stage 0, which is why `chat()` was written to match `generate()`'s existing (uncapped)
  style rather than fixing it ahead of that stage. Noted in `ollama_client.py`'s own module
  docstring as well as here.
- **The native form's "well-formed" bar for >1 tool call is a judgement call, not something the
  plan specifies.** Ollama's `/api/chat` allows a `tool_calls` array with more than one entry;
  this probe only ever acts on the first and records the round as not well-formed when there is
  more than one, since D3's "one round, one tool" rule has no stated native equivalent. If the
  real model routinely returns multiple tool calls per round, Stage 2's design will need an
  explicit decision here, not an inherited probe default.
## Stage 1 (wake routing and the honest edges)

### Implementation Summary

Stage 1 of `plans/brain-tool-calls/plan.md` ("wake routing and the honest edges, no tools yet").
No tool loop, `BRAIN_TOOLS`, validators, or `ToolLoopDecider` were built — out of scope per the
dispatch. Touches two subprojects: `audio-adapter/` (wire field) and `body-layer/` (routing,
budget, tuning).

### Files Changed

**audio-adapter**
- `src/command_matcher.py` — `MatchResult` gains `addressed: bool = False`, set `True` on the
  wake-word branch of `match_transcript` (the same `opens_with_wake_word` check that already
  forces `verb_anchored=False`).
- `src/transcript_queue.py` — `TranscriptEvent` gains `addressed: bool = False`, carried into
  `to_dict()`.
- `src/server.py` — `_handle_transcribe` threads `match.addressed` into the constructed
  `TranscriptEvent`.
- `tests/test_command_matcher.py` — the wake-word test (`test_opening_wake_word_is_free_speech_
  for_the_brain`) now expects `addressed=True`; added `_ADDRESSED_NOT_A_COMMAND`.
- `tests/test_transcribe_api.py` — the eight-field set assertion is now nine fields; added
  `test_wake_prefixed_speech_enqueues_as_addressed`.

**body-layer**
- `src/belief/brain_client.py` — `BrainLayerClient.available()`: `False` until the background poll
  thread's first successful round, then `False` again once that round is older than
  `_AVAILABILITY_MAX_AGE_S` (3× `_POLL_RETRY_BACKOFF_S`, a plain literal — a protocol/timing
  constant, not a Petrovich choice). `_last_poll_success_wall` recorded under `_poll_lock` on every
  successful `_poll_once()`, whether or not it carried replies.
- `src/belief/escalation.py` — `BrainClient` protocol gains `available()`; both stand-ins
  (`NullBrainClient`, `DebugPrintBrainClient`) always return `False`.
- `src/belief/utterance.py` — new public `opens_with_vocative(text)`, the typed-console twin of
  `audio-adapter`'s `opens_with_wake_word`, built on the existing private `_VOCATIVE_PREFIX`.
- `src/belief/speech.py` — five new `_UNABLE_TEMPLATES` entries: `NO_BRAIN`, `NO_ANSWER`,
  `NO_PLACE`, `CANNOT_ANSWER`, `FIXED_COMMAND_ONLY` (U3 wording verbatim).
- `src/belief/crew_console.py` — the main change:
  - `STAND_BY_AFTER_S`, `BRAIN_REPLY_MAX_AGE_S` converted from bare literals to `tuning.real(...)`
    (`lo`/`hi` per D9: 0.5–10.0 and 1.0–60.0). New `BRAIN_MAX_TOOL_ROUNDS` (`tuning.whole`, 4,
    1–8) declared now though nothing calls it until Stage 2.
  - New `BrainTurn` dataclass (fields per the plan's table: `started_sim`, `transcript`, `parse`,
    `addressed`, `round`, `steps`, `offered`, `candidate_sets`, `stand_by_spoken`,
    `correlation_id`) replacing `_pending_escalations`/`_stand_by_spoken_for` with one
    `_brain_turns: dict[str, BrainTurn]`.
  - `_PendingPositionalReply` gains `brain_turn_id: str | None = None` (R6) — one construction
    site (`_speak_or_defer`), left at its default in Stage 1 since no brain command dispatches
    through `handle_command` yet; the field and `_drop_positional_replies_for_turns` exist so
    Stage 3 has somewhere to plug in.
  - `handle_line`/`_act_on_voice_decision`/`handle_transcript` all gained an `addressed` parameter
    threaded end to end. `handle_line`'s own `addressed=None` default computes it from
    `opens_with_vocative` for the typed-console surface; the voice surface always passes the wire's
    own value.
  - `_handle_utterance` rewritten: addressed → always `_start_brain_turn` (parse carried only as a
    hint, never acted on even when `"handled"`); unaddressed+`"handled"` → unchanged (`_act`);
    unaddressed+unresolved → new `_handle_unaddressed_miss` (U1: "which one?" on ≥2 candidates,
    else "say again", no brain call).
  - `_start_brain_turn` pops every outstanding turn first (`_pop_all_brain_turns`, D3's
    one-job-in-flight mirrored client-side), then speaks `NO_BRAIN` immediately if
    `brain_client.available()` is false, otherwise posts the escalation as before.
  - `drain_brain` gained `_expire_overdue_brain_turns` (D9 budget expiry → `NO_ANSWER` spoken once,
    turn popped, a late reply becomes untracked and silently dropped by `_handle_brain_reply`).
    `_speak_stand_by_if_due` and `_handle_brain_reply` reworked onto `BrainTurn`.
- `src/body.py` — `_poll_transcripts` reads the tenth field `addressed` (`item.get("addressed",
  False)`, additive — absent reads `False`, present-and-wrong-type skips the row like every other
  field), threads it into `handle_transcript`.
- `config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`) for the three new
  tuning keys.

### Tests Added

- `audio-adapter/tests/test_transcribe_api.py::test_wake_prefixed_speech_enqueues_as_addressed` —
  the wire field round-trips through the real `POST /transcribe` → `GET /transcripts/poll` seam.
- `body-layer/tests/test_body.py` — split the old `test_poll_transcripts_no_match_falls_through_
  to_handle_line` into `..._addressed_..._reaches_the_brain` (addressed:true in the raw dict
  escalates) and `..._unaddressed_..._never_reaches_the_brain` (absent key reads False, U1
  degrades, never escalates).
- `body-layer/tests/test_crew_console.py`:
  - `test_handle_transcript_addressed_fallthrough_reaches_the_brain` — the wire's `addressed=True`
    still reaches the brain via `handle_transcript`.
  - `test_unaddressed_ambiguous_reference_asks_which_one_without_the_brain` — U1's ≥2-candidate
    branch.
  - `test_addressed_utterance_never_acts_on_a_resolvable_parse_directly` — the plan's own worked
    case ("Petrovich, where's the Shilka?" must reach the brain, not answer itself).
  - `test_addressed_utterance_with_unavailable_brain_speaks_no_brain_immediately` /
    `test_null_brain_client_default_speaks_no_brain_for_an_addressed_utterance` — `NO_BRAIN`, both
    against an explicit `available()==False` fake and the real default stand-in.
  - `test_drain_brain_expires_an_overdue_turn_and_speaks_no_answer_once` — budget expiry, spoken
    once, a late reply discarded afterwards.
  - `test_start_brain_turn_supersedes_the_outstanding_one_silently` — D3's silent supersession
    (distinct from expiry: no `NO_ANSWER` for the superseded turn).
  - `test_reset_for_new_mission_clears_outstanding_brain_turns`.
- `body-layer/tests/test_brain_client.py` — `test_available_is_false_before_the_first_poll_
  completes`, `test_available_becomes_true_after_a_successful_round`, `test_available_stays_
  false_against_an_unreachable_server`.
- `body-layer/tests/test_escalation.py` — `test_null_brain_client_is_never_available`,
  `test_debug_print_brain_client_is_never_available`.

**Existing tests rewritten, not just extended** (plan-mandated by the `BrainTurn` fold and U1's
supersession of the old implicit second escalation route — flagged per the Implementer's own
"treat the plan's test-impact list as a hypothesis" step): roughly a dozen `test_crew_console.py`
tests that drove brain-reply mechanics (`test_drain_brain_pick_*`, `test_drain_brain_ask_*`,
`test_drain_brain_confirm_*`, `test_drain_brain_unable_*`, `test_drain_brain_discards_stale_reply`,
`test_drain_events_not_gated_by_an_in_flight_escalation`, the two `test_refused_drain_brain_*`
tests, `test_unresolvable_reference_escalates_and_speaks_nothing`) had their trigger transcripts
prefixed `"Petrovich, "` so they still exercise the BR-1 decider path Stage 1 keeps, and their
`_pending_escalations`/`_stand_by_spoken_for` references renamed to `_brain_turns`.
`test_handle_transcript_fallthrough_uses_handle_line_unchanged` and `test_handle_transcript_late_
answer_beyond_the_grace_falls_through` asserted the *old* "unaddressed no-match escalates" or
"escalates silently" behaviour the plan's U1 explicitly supersedes; both now assert the
deterministic degrade instead, with a docstring note pointing at U1. Every `BrainClient`-shaped
test double across `test_crew_console.py`/`test_body.py`/`test_escalation.py`/`test_brain_client.py`
gained an `available()` method (mostly returning `True`, so existing escalation-mechanics tests
keep exercising the post-availability-check path; `_UnavailableBrainClient` is the one new fake for
the `NO_BRAIN` path).

### Checks

**audio-adapter/**
- `ruff format src tests`: pass (no changes)
- `ruff check src tests`: pass
- `mypy src`: pass (16 source files)
- `pytest tests -q`: pass — 391 passed, 2 skipped

**body-layer/**
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (82 source files)
- `pytest tests -q`: pass — see the full-suite run recorded below once it completed.

### Notable Discoveries

- **`cancel_nevermind` has no dispatch path anywhere in the current code.** It is one of
  `audio-adapter/src/vocabulary.py`'s `ROUTING_TOKENS`, listed there for the recogniser/bench, but
  no `command_matcher.match_transcript` branch, `crew_console.py` handler, or anything else ever
  resolves it to an action. The plan's Co-moving Fields table lists a "nevermind pops all turns"
  row regardless, so `CrewConsole._pop_all_brain_turns`/`_drop_positional_replies_for_turns` were
  built as the shared primitive a future `cancel_nevermind` dispatch can call — today the only
  caller is `_start_brain_turn`'s own supersession. Flagging this rather than inventing a dispatch
  path that was not asked for.
- **`_PendingPositionalReply.brain_turn_id` has exactly one construction site** (`_speak_or_defer`)
  and is left at its default `None` throughout Stage 1 — nothing in this stage dispatches a brain
  command through `handle_command`, so nothing needs to tag a deferred readback with a turn id
  yet. Noted per the R6 risk's own "grep every construction site" instruction.
- **`BRAIN_REPLY_MAX_AGE_S` now serves two purposes under one name**: D9's turn budget (checked
  every poll in `drain_brain`, regardless of whether a reply ever arrives) and D4's original
  stale-reply discard (checked against `BrainReply.t_sim` once a reply does land). In practice the
  budget check pops a turn before a reply old enough to trip the second check could ever reach it
  — the second check now mostly guards a reply whose own timestamp happens to be old despite
  arriving inside the budget window. Both checks were kept rather than removing one, since the
  plan did not ask for either to be dropped and the behaviour each guards is still real.
- **mypy's structural `Protocol` check on `BrainClient` caught every test double missing
  `available()`** at `mypy src`... actually at runtime (`# type: ignore[arg-type]` suppresses the
  static check at these particular call sites, so the gap would have been a *runtime*
  `AttributeError` the first time `available()`/`poll_replies()` was actually called, not a mypy
  failure) — found by running the real test suite, not by mypy. Worth remembering: a `type:
  ignore[arg-type]` on a fake assigned to a `Protocol`-typed field defeats the structural check
  that would otherwise catch a missing method.
- **Tuning-comment sentence-splitter trap, third variant found**: a quoted verbatim phrase ending a
  comment's intended first sentence (`says "Unable, no answer." Too low cuts off...`) is not split
  there — the generator's quote-parity rule (meant to protect a pilot verbatim's own full stop from
  ending the sentence early) also protects this case, where the quote happens to close right where
  the sentence was meant to end, merging it with the next sentence in the rendered
  `config/defaults.toml`. Recorded as `feedback_tuning_comment_period_before_closing_quote` in
  agent memory (two related but distinct traps — digit-before-period, backtick-line-wrap — were
  already on file).
- **No `.venv` exists in a freshly created agent worktree** for either subproject (gitignored, not
  copied). Symlinked both `body-layer/.venv` and `audio-adapter/.venv` to the main checkout's own
  venvs rather than building fresh ones — already a documented pattern in this role's own memory
  (`feedback_worktree_missing_venv`/`feedback_worktree_no_venv`/`feedback_worktree_venv_borrow_
  also_applies_to_implementer`).
- **A pre-existing test-isolation hazard, not introduced here but touched by the new `available()`
  tests**: several `test_brain_client.py` tests (old and new) construct a `BrainLayerClient`
  against an unreachable address and call `poll_replies()`, which starts a daemon background
  thread that retries forever, logging a `WARNING` every `_POLL_RETRY_BACKOFF_S` for the rest of
  the whole pytest process — these threads are never joined between tests. One full-suite run
  during this task showed a single, unrelated `test_mission_start_reset.py` test's exact-list
  `caplog` assertion fail once, with a stray `"background brain reply poll failed (retrying)"`
  record from one of these leftover threads mixed in. Re-running the full suite did not reproduce
  it. This mechanism predates this change (several existing `test_brain_client.py` tests already
  point at unreachable addresses); the two new `available()` tests against an unreachable server
  add two more such threads to the same pre-existing pool rather than a new category of hazard.
  Flagging for whoever next touches test isolation in this file, not fixing here (out of Stage 1's
  scope and would touch test infrastructure well beyond this plan).
