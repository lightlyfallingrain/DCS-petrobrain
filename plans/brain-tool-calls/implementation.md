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

## Stage 2 (the tool loop, query tools only, template answers)

### Implementation Summary

Stage 2 of `plans/brain-tool-calls/plan.md`: the tool loop, D5's seven query tools, D7's template
answer forms, and `ToolLoopDecider`. Touches two subprojects.

### Files Changed

**body-layer**
- `src/belief/tool_api.py` — D2's calling convention and D5's tool surface: `ParamSpec` (kinds
  `str`/`int`/`bool`/`enum`/`contact_ref`/`place_ref`/`memory_ref`, plus `allow_ownship` for
  `recall_memory`'s `near`), `BrainTool`, `ToolObservation` (`summary`, `handles`,
  `candidate_texts`), `ToolContext` (mutable `place_positions` cache, populated by `find_place`'s
  own adapter and read by `recall_memory`'s — the one place one tool call's result feeds another's
  input without a coordinate ever reaching the wire). `BRAIN_TOOLS` — seven hand-written adapters
  over `tools.find_contact`/`get_contacts`/`describe_contact`/`get_contact_history_with_memory`/
  `find_place`/`describe_our_position`/`mission_memory_tools.recall_memory`, each capped at
  `BRAIN_TOOL_LIST_CAP` (5) with an "and N more" tail. `BrainTool.name` equals the wrapped
  `TOOL_SET` entry's own name (`get_contacts`, not D5's illustrative "list_contacts" prose — see
  Notable Discoveries). `RECALL_MEMORY_NEAR_RADIUS_M` is the one new tunable (`tuning.real`, 5000.0,
  500–50000).
- `src/belief/brain_reply.py` — `_evidence_passes` factored out of `_validate_pick` (identical
  behaviour, now shared); `validate_tool_call` (D3: name/unknown-args/per-`ParamSpec` checks,
  offered-ref membership, the repeated-`(tool, args)` rejection); `validate_turn_final` dispatching
  `answer`/`command`/`ask`/`unable`; `_validate_turn_answer` (D7's four forms, the ambiguity-evidence
  degrade reusing `_evidence_passes`); `_validate_turn_command` (Stage 3 hook, see Notable
  Discoveries); `VALID_TURN_UNABLE_REASONS` (`NO_ANSWER`/`NO_PLACE`/`CANNOT_ANSWER`/
  `FIXED_COMMAND_ONLY`/`NO_BRAIN` — `NO_BRAIN` included because `ToolLoopDecider` itself emits it on
  an Ollama failure, not only client-side).
- `src/belief/crew_console.py` — `ToolStep` (the real shape Stage 1's placeholder `BrainTurn.steps`
  invited); `BrainTurn.candidate_sets`' type widened to `(handle, text)` pairs (same invitation).
  `_start_brain_turn`/new `_post_tool_continuation` build the mode-`"addressed"` payload with
  `BRAIN_TOOL_SPECS`. `drain_brain` caps tool execution at one per poll across its reply batch.
  `_handle_brain_reply` branches: `tool_call` keeps the turn alive (`_handle_brain_tool_call`);
  `answer`/`command`/`ask`/`unable` pop it and dispatch to the new `_handle_brain_turn_final`
  (with the same staleness check the old `pick`/`confirm` path already had); `pick`/`confirm` keep
  their original BR-1 path, now dead in practice (every addressed turn is tool-loop mode) but not
  removed. `_render_turn_ask` D4-revalidates a candidate set against the current store before
  asking (0 survivors → lost him, 1 → reported directly, ≥2 → the question) — a gap in my own first
  pass, caught by rewriting the Stage 1 tests below. New `run_brain_tool`/`lookup_memory_entry_fn`
  injected-closure fields, same shape as `mark_here_fn`.
- `src/belief/escalation.py` — `BrainReplyKind` widened (`tool_call`/`answer`/`command` added);
  `BrainReply` gains `tool`/`args`/`form`/`refs`/`target`/`slots`; `EscalationPayload` gains
  `mode`/`round`/`steps`/`tools`/`commands`; `handle_player_utterance` gains matching keyword-only
  parameters, every existing call site unaffected by the new defaults.
- `src/belief/brain_client.py` — `_payload_to_dict`/`_reply_from_dict` widened for the five new
  fields each way.
- `src/belief/speech.py` — `render_nothing_seen`, `render_our_position_answer`,
  `render_contact_answer` (adds the freshness phrase via new `_freshness_phrase`),
  `render_memory_entry` (reuses `relative_geometry` against *current* ownship, never the entry's
  own written position).
- `src/body.py` — `_run_brain_tool_fn`/`_lookup_memory_entry_fn` closures (same "inject over live
  `runner`/`memory` state" shape as `_mark_here_fn`), wired onto `crew_console` beside the existing
  mark closures.
- `config/defaults.toml` — regenerated for `RECALL_MEMORY_NEAR_RADIUS_M`.

**brain-layer**
- `src/final_reply.py` *(new)* — the closed `FINAL ...` grammar, **moved** out of
  `tools/stage0_tool_call_probe.py` rather than duplicated (`parse_final_text`, `final_to_dict`,
  `ParsedLine`) so `ToolLoopDecider` and the probe parse the identical grammar. The probe now
  imports from here; its own `parse_grammar_line` (the grammar-form's `CALL ...` extension, probe-
  only) is the one piece that stays local.
- `src/tool_loop_prompts.py` *(new)* — `build_system_prompt`/`build_user_message`/
  `tool_to_json_schema`, adapted from the research note's own measured prompt (the `_FINAL_GRAMMAR_
  BLOCK` text, byte-stable system-prompt-per-turn shape, R3) to the real wire shapes
  (`belief.tool_api.BRAIN_TOOL_SPECS`'s `{name, params}`, not the probe's local fixture classes).
- `src/decider.py` — `ToolLoopDecider`: one `decide()` call is one round: native `tool_calls` →
  `{"kind": "tool_call", ...}` (>1 call degrades to `ask`, D3 has no native "one tool" equivalent);
  a `FINAL ...` line in `content` → `final_reply.final_to_dict`'s dict; a transport failure
  (`OllamaRequestError`) → `{"kind": "unable", "reason": "NO_BRAIN"}` (D4's own wording for "brain-
  layer up, Ollama not"); anything unparseable → `{"kind": "ask"}`, deferring to body's own D3
  validator rather than guessing at refs this decider cannot see. `TOOL_LOOP_NUM_CTX` (2048),
  `TOOL_LOOP_MAX_ROUNDS` (4), `TOOL_LOOP_NUM_PREDICT` (120) are the research note's own measured
  values, kept independent of `OllamaDecider`'s own constants even where the numbers coincide.
- `src/brain_layer/__main__.py` — `--decider tool_loop` wires `ToolLoopDecider`; `stub`/`ollama`
  unchanged (default still `stub`).
- `tools/stage0_tool_call_probe.py` — refactored to import the grammar from `final_reply` instead
  of defining it; `_final_from_parsed` removed (now `final_to_dict`).

### Tests Added

**body-layer** (`tests/test_brain_tool_loop.py`, new, 12 tests) — a scripted fake `BrainClient` plus
a scripted fake `run_brain_tool` drive exact step sequences through the real `CrewConsole`:
- `test_scripted_tool_call_then_final_answer_drives_the_whole_turn` — the plan's own worked case,
  full round-trip including the continuation payload's `round`/`steps`.
- `test_unoffered_ref_is_rejected_and_costs_a_round`, `test_unoffered_tool_call_arg_is_rejected_
  as_invalid_and_continues` — D3's offered-ref membership check, both directions (a final citing an
  unoffered ref; a tool call arguing an unoffered one).
- `test_ambiguous_answer_without_evidence_becomes_which_one`,
  `test_evidence_grounded_in_transcript_and_candidate_passes` — D3's ambiguity-evidence rule, both
  outcomes.
- `test_contact_lost_between_call_and_speech_says_lost_him` — D4 revalidation at speech time.
- `test_superseded_turn_never_speaks` — D3's silent supersession.
- `test_at_most_one_tool_execution_per_poll` — D6.
- `test_repeated_identical_tool_call_is_rejected` — the research note's design input.
- `test_round_cap_exceeded_degrades_the_turn` — D9.
- `test_serialised_tool_call_payload_carries_no_raw_coordinates`,
  `test_describe_our_position_observation_has_no_x_or_z` — D2's "no raw x/z," grep-style over the
  actual JSON and over one adapter's own observation text.

**body-layer** (`tests/test_stage2_acceptance_bench.py`, new, 31 tests, parametrised over the 15
Stage 0 cases) — "the acceptance bench runs offline on the Mac": every case's `expected.final`
replayed against the *real* `belief.brain_reply.validate_turn_final`/`belief.tool_api.
BRAIN_TOOLS_BY_NAME`, no Ollama, no brain-layer process. Finds and records two real discrepancies
between the Stage 0 fixture and the shipped Stage 2 implementation rather than hiding either behind
a passing assertion — see Notable Discoveries.

**body-layer** (`tests/test_crew_console.py`, reworked) — four Stage-1-era tests
(`test_drain_brain_ask_two_survivors_speaks_disambiguation`, `test_drain_brain_ask_zero_survivors_
yields_lost_him`, `test_drain_brain_ask_one_survivor_confirms_rather_than_acts` → renamed
`..._reports_it_directly`, `test_drain_brain_unable_speaks_the_reason`) exercised the BR-1 decider's
old `ask`/`unable` wire shape for an addressed turn — Stage 1's own docstring on these invited this:
"still go through the BR-1 decider... Stage 2 onward is the tool loop." Since every addressed turn
now posts `mode="addressed"` and only `ToolLoopDecider` ever answers one, these four were rewritten
against the new wire shape (`candidate_sets` seeded directly on the `BrainTurn`, the new `unable`
reason vocabulary) rather than left asserting dead behaviour. Per the Implementer role's own
"treat the plan's test-impact list as a hypothesis" step — this was found by running the full suite
after wiring the new dispatch, not predicted up front.

**brain-layer** (`tests/test_tool_loop_decider.py`, new, 8 tests) — `ToolLoopDecider` against the
existing fake Ollama HTTP server (`test_ollama_client._FakeOllamaServer`, reused via import rather
than duplicated): native `tool_calls` → `tool_call` dict; >1 native tool call degrades to `ask`;
`FINAL answer`/`FINAL unable` lines parsed; malformed content degrades to `ask`; an unreachable
Ollama degrades to `unable NO_BRAIN`; a continuation round's own request body carries the grown
`steps` block; the system prompt is byte-identical across two rounds (R3).

### Checks

**body-layer/**
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (82 source files)
- `pytest -q`: pass — 3250 passed, 4 xfailed (full suite, run twice; second run, after the final
  acceptance-bench edits and the four reworked Stage-1 tests, is the number quoted)

**brain-layer/**
- `ruff format src tests tools`: pass (reformats `tools/live_cross_process_check.py`, pure
  whitespace, unrelated to this task — reverted after, same as Stage 0's own note)
- `ruff check src tests tools`: pass
- `mypy src`: pass (9 source files)
- `pytest -q`: pass — 82 passed (74 existing + 8 new)

### Notable Discoveries

- **`BrainTool.name` must equal `TOOL_SET`'s own name, not D5's illustrative prose.** The dispatch
  instruction ("names test-enforced to equal `TOOL_SET` names") settles this explicitly, but D5's
  own table in the plan calls the `get_contacts` wrapper `list_contacts`. `brain-layer/tools/
  stage0_cases.json` (built before this naming decision, against D5's prose) uses `list_contacts`
  throughout — `tests/test_stage2_acceptance_bench.py`'s `_FIXTURE_TOOL_NAME_TO_REAL` documents and
  translates the one name that differs; the fixture file itself is untouched (it is brain-layer's
  own Stage 0 artifact, already measured against).
- **Stage 2's `situational_header` offers no contact refs at all — a real gap against one of the
  plan's own acceptance cases**, found by the offline bench, not designed around in advance.
  `A4_which_ones_the_bmp` ("Petrovich, which one's the BMP?") is a Stage 0 fixture case whose two
  candidates are pre-seeded in the *header*, with `expected.steps == []` — i.e. Stage 0 assumed a
  turn can start with contacts already offered (plausibly from a recent callout/report). The plan's
  own Affected Modules list names "header refs" as a Stage 2 deliverable for `escalation.py`/
  `brain_client.py`, but nothing in the Stage 2 scope bullet ("the tool loop, query tools only,
  template answers") calls for populating them, and I did not add it on my own initiative (a
  genuine design decision — what counts as "recently mentioned," how long it stays offered — not a
  one-line gap). Today this exact case degrades to `unable CANNOT_ANSWER` rather than answering
  directly; `test_stage0_fixture_discrepancies_are_recorded`-style documentation
  (`_EXPECTED_NO_HEADER_REFS_GAP`) records this as a tracked fact for whoever picks up header-ref
  population next (Stage 4's landmark work is the natural place, or a dedicated follow-up).
- **A second fixture/implementation mismatch, same bench**: `A2_anything_near_gemerek`'s
  `list_contacts` step is called with `{"filter": "near PLACE_1"}` — Stage 0 measured the model
  producing a "near a place handle" filter syntax that Stage 2's real `ParamSpec` for `get_contacts`
  (`filter` is an `enum` of `"all"`/`"visible"`/`"watched"` only) does not implement.
  `test_stage0_fixture_discrepancies_are_recorded` asserts the real validator rejects it today, so
  the gap is a checked fact rather than a silently-skipped args check.
- **A gap in my own first implementation pass, caught by rewriting the four old `ask`/`unable`
  tests**: the first version of `_render_turn_ask` rendered the turn's recorded candidate set
  without re-checking which of its contacts still exist in the store — a direct miss of D4's own
  "ids are rechecked against current belief at speech time" rule, which the *old* BR-1 `_handle_
  brain_ask` already honoured. Fixed before committing (0 survivors → lost him, 1 → reported
  directly, ≥2 → the question), and `_speak_turn_degrade`'s own round-cap path now delegates to the
  same revalidated renderer rather than carrying a second, unrevalidated copy.
- **D1's "command finals accept an optional `because` slot" choice**: `_validate_turn_command`
  structurally validates a `command` final's `target` (offered-ref check) but always degrades to
  `unable CANNOT_ANSWER`, never `FIXED_COMMAND_ONLY` — that reason means "excluded by policy" (U2),
  and a Stage 2 command final is excluded by *construction* (no `BRAIN_COMMANDS` exists yet), a
  different fact that would become indistinguishable from U2's own degrade once Stage 3 ships.
  Flagged as the dispatch instruction asked ("say which you chose and why").
- **The four design inputs from `brain-layer/research/2026-11-12-tool-call-form.md` ("Design inputs
  for Stage 2"), and where each landed**:
  1. *Reject a repeated identical call* → `belief.brain_reply.validate_tool_call`'s own
     `(tool, canonical_args)` check against `turn.steps`, costing a round via an `invalid:` and
     never executing `run_brain_tool` for the repeat (`test_repeated_identical_tool_call_is_
     rejected`).
  2. *`command` finals carry an optional `because`* → `BrainReply.because` is reused (not a second
     field) for both `answer` and `command` finals; `_validate_turn_command` reads it (currently a
     no-op, since there is no command allowlist yet to validate against) and `_validate_turn_
     answer` is where it actually matters this stage, via `_evidence_passes`.
  3. *The invalid-call observation must name the fix* → every `validate_tool_call` rejection string
     states the tool/param and the concrete reason (`"get_contacts.filter must be one of all,
     visible, watched"`, `"already called find_contact with these args, see the observation
     above"`), not a generic "invalid."
  4. *The research note's prompt is the starting point for `ToolLoopDecider`'s prompt* →
     `tool_loop_prompts.py`'s `_FINAL_GRAMMAR_BLOCK`/`_SYSTEM_PROMPT_HEAD` are that prompt's own
     text, adapted to the real wire shapes; the system prompt stays byte-stable per turn (R3,
     `test_system_prompt_is_identical_across_rounds`).
- **Mechanical note on the Stage 0 probe refactor**: `final_reply.ParsedLine` keeps `tool`/`args`
  fields that only the probe's own grammar-form `"call"` kind ever populates — `ToolLoopDecider`
  never produces that kind (native tool calls are read straight off `ollama_client.ChatResult`, not
  through this grammar), so those two fields are dead weight from `decider.py`'s point of view but
  necessary for the probe's own `parse_grammar_line` to keep working unchanged. Noted rather than
  split into two dataclasses, since the probe is a measurement tool, not production code, and a
  second near-identical dataclass would cost more clarity than it buys.
- **`brain-layer/tools/live_cross_process_check.py` reformats under a bare `ruff format tools`
  every time** — pre-existing whitespace debt, unrelated to this change, same finding Stage 0's own
  report already made. Reverted after each check run rather than landed, so this branch's diff
  stays scoped.

## Stage 3 (commands through `handle_command`)

### Implementation Summary

Stage 3 of `plans/brain-tool-calls/plan.md`: D5's `BRAIN_COMMANDS` allowlist and slot schemas,
command dispatch in `drain_brain` through the single `handle_command` dispatcher (D5/A7/E3), D3's
ambiguity-evidence rule extended to a command's `target`, D4's header refs, and the R1/R6 risks.
Touches both subprojects.

### Files Changed

**body-layer**
- `src/belief/tool_api.py` — `BrainCommand` (`name`, `takes_target`, `meaning`); `BRAIN_COMMANDS`
  (D5's initial set, verified token-by-token against the real `handle_command` dispatch table, not
  copied from the plan's illustrative prose — see Notable Discoveries); `BRAIN_COMMANDS_BY_NAME`;
  `serialize_command`/`BRAIN_COMMAND_SPECS` (the `{"token", "takes_target", "meaning"}` wire shape).
- `src/belief/brain_reply.py` — `_validate_turn_command` rewritten: unknown/excluded token →
  `FIXED_COMMAND_ONLY`; a `target` supplied to a command that `takes_target=False`, or any non-empty
  `slots`, is a malformed shape (same `_turn_degrade` path every other shape check uses); an offered
  `target` drawn from a ≥2-candidate set without passing `_evidence_passes` degrades to `ask` over
  the survivors, otherwise the reply validates unchanged. `_reply_with_reason` factored out (shared
  by the unknown-token and the (hypothetical, never reached in practice) malformed-reply paths).
- `src/belief/crew_console.py`:
  - `BrainTurn.header_refs` (new field) — D4's header-ref set, fixed once at turn start and resent
    unchanged on every continuation round (see Notable Discoveries for why).
  - `_pending_brain_turn_id` (new field, R6) — set for the duration of `_handle_brain_command`'s one
    `handle_command` call, read by `_speak_or_defer`'s one construction site so a brain-dispatched
    positional readback carries the turn id `_drop_positional_replies_for_turns` (wired since Stage
    1) already knows how to act on.
  - `_header_contact_refs` (new) — D4: every contact in `_referent_memory`'s window, newest mention
    per id, resolved to `tools.describe_contact`'s own plain-text summary (no x/z), capped at
    `BRAIN_TOOL_LIST_CAP`.
  - `_start_brain_turn`/`_post_tool_continuation` — now seed `turn.offered`/`turn.header_refs` from
    `_header_contact_refs` (never `turn.candidate_sets`, see Notable Discoveries) and pass
    `commands=BRAIN_COMMAND_SPECS`/`recent_contacts=header_refs` to `handle_player_utterance`.
  - `_handle_brain_turn_final`'s `command` branch now calls the new `_handle_brain_command` instead
    of a hard-coded degrade; `_handle_brain_command` plants a `Mention` into `_referent_memory`
    (never `_pending_mentions`, which `handle_command` resets on entry) when a `target` is present,
    builds `slots={"referent": True}` or `None`, and dispatches through `handle_command` — the exact
    phrasebook path, so readback/task/marker/cancel semantics are the phrasebook's own by
    construction (E3). Never calls `_print` itself: `handle_command`'s own tail already does, and
    `_handle_brain_turn_final` returns early for `kind == "command"` to avoid double-speaking.
  - `handle_command`'s reset-before-dispatch block **no longer resets `where_is_it_requested`/
    `where_is_it_slots`** — R1's fix, see Risks below.
- `src/belief/escalation.py` — `_situational_header`/`handle_player_utterance` gain `recent_contacts:
  tuple[tuple[str, str], ...]`, serialised into `header["recent_contacts"]` as `{"id", "summary"}`
  dicts, omitted entirely when empty.

**brain-layer**
- `src/final_reply.py` — `ParsedLine.because` (new field); `_FINAL_ANSWER_RE` gains an optional
  trailing `BECAUSE "<words>"`; `final_to_dict`'s `"final_command"` branch now **pops** `target`/
  `because` out of the raw JSON slots dict into their own `BrainReply` fields (previously `target`
  was left duplicated inside `slots` *and* exposed as its own field — a pre-existing Stage-2 wire
  shape this stage needed to fix so `slots` reliably reflects only genuinely-extra keys, which
  Stage 3's "no extra slots" validation reads).
- `src/tool_loop_prompts.py` — `_FINAL_GRAMMAR_BLOCK` gains the `FINAL command <token> <json
  object>` line (missing entirely before — Stage 2 had no commands to document) and the optional
  `BECAUSE` clause on `FINAL answer`; `_command_block` now renders `BRAIN_COMMAND_SPECS`'
  `token`/`takes_target`/`meaning` instead of a bare token list (the research note's own follow-up:
  derive the command notes rather than hand-write them); `_render_header` renders
  `header["recent_contacts"]` as offered-ref lines.
- `src/decider.py`/`server.py` — unchanged; both already read `commands`/forward `because`
  generically from the wire (confirmed by reading, not assumed — see Notable Discoveries).

### Tests Added

**body-layer** (`tests/test_brain_tool_loop.py`, 10 new tests):
- `test_brain_command_mark_target_matches_phrasebook_dispatch`,
  `test_brain_command_cancel_task_matches_phrasebook_dispatch` — the E3 differential test, a
  target-taking and a no-target command: the brain path (tool call then `command` final) and the
  phrasebook path (a direct `handle_command` call, referent pre-seeded for the target case) from
  identical belief state produce identical readback text and task/mark state.
- `test_excluded_token_gets_fixed_command_only`, `test_unknown_token_also_gets_fixed_command_only` —
  U2's excluded tokens and a genuinely unknown token both degrade to `FIXED_COMMAND_ONLY`, per D5's
  own instruction that the two are indistinguishable at this layer.
- `test_command_target_not_offered_is_rejected` — an unoffered `target`.
- `test_ambiguous_command_target_without_because_becomes_which_one`,
  `test_ambiguous_command_target_with_because_dispatches` — D3's ambiguity-evidence rule extended to
  a command's `target`, both outcomes.
- `test_r1_brain_command_signal_survives_an_unrelated_command_same_poll` — the R1 regression test;
  verified red without the fix (see Checks) before confirming green with it.
- `test_header_refs_offered_without_a_tool_call` — D4: a recently-mentioned contact is offered from
  round 0 with no tool call, and the serialised header payload carries no raw `x`/`z`.

**body-layer** (`tests/test_crew_console.py`, `TestBrainCommandsAreRealDispatchTokens`, 4 new
tests) — `BRAIN_COMMANDS`' own names against the real `DISPATCHED_COMMAND_TOKENS`/
`_CLOCK_REPORT_TOKENS`/`_BEARING_REPORT_TOKENS` tables (not the plan's illustrative "1..12"/
"north/south/east/west" prose), and U2's excluded tokens absent by construction.

**body-layer** (`tests/test_stage2_acceptance_bench.py`, reworked) — `_turn_from_case` now also
seeds `turn.offered` (never `candidate_sets`) from `case["header"]["contacts"]`; `_EXPECTED_
COMMAND_DEGRADES`/`_EXPECTED_NO_HEADER_REFS_GAP` are now empty (kept as the place a future gap of
either shape would be recorded); a new `_EXPECTED_COMMAND_NEEDS_EVIDENCE_GAP` documents one real,
remaining discrepancy (see Notable Discoveries). All 31 cases pass or land in a documented,
reasoned gap.

**brain-layer** (`tests/test_tool_loop_prompts.py`, new, 7 tests) — the command-notes block
rendered from hand-written `{"token", "takes_target", "meaning"}` fixtures (module independence:
this subproject cannot import body's `tool_api`), the fixed `FINAL command` grammar line's
presence regardless of whether any command is offered, R3 byte-stability, and `recent_contacts`
rendering in the user message.

**brain-layer** (existing tests updated) — `test_tool_loop_decider.py`'s
`test_final_answer_line_becomes_answer_dict` and `tools/stage0_tool_call_probe.py`'s
`test_run_case_once_grammar_form_call_then_final` both asserted the pre-fix wire shape (`because`
absent from an `answer` dict; `target` duplicated inside a `command`'s `slots`) — updated to the
corrected shape per the dispatch instruction's own permission to update a test the plan's behaviour
change invalidates, not left passing against a shape this stage deliberately changed.

### Checks

**body-layer/**
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (82 source files)
- `pytest -q`: pass (full suite; see exact count in the handback report — run in progress at the
  time this section was written, confirmed before the task's final report)

**brain-layer/**
- `ruff format src tests tools`: pass (reformats `tools/live_cross_process_check.py`, pure
  whitespace, unrelated to this task — reverted after, same as Stage 0/2's own note)
- `ruff check src tests tools`: pass
- `mypy src`: pass (9 source files)
- `pytest -q`: pass — 89 passed (82 existing + 7 new)

**R1 regression test verified red before green**: temporarily restored the old unconditional
`where_is_it_requested = False` / `where_is_it_slots = None` reset inside `handle_command`,
confirmed `test_r1_brain_command_signal_survives_an_unrelated_command_same_poll` fails
(`assert False is True`), then restored the real fix and confirmed it passes — per this role's own
"show the red" rule for a test whose assertion is "the signal survives" (an absence-of-a-wipe
claim).

### Notable Discoveries

- **The plan's D5 prose and the real `handle_command` dispatch table disagree on two token
  families, caught by checking rather than copying.** `report_clock_1..12` does not exist as
  written: the real `_CLOCK_REPORT_TOKENS` is the nine *forward* hours only (8,9,10,11,12,1,2,3,4 —
  no 5/6/7), the same no-omniscience exclusion `_CLOCK_SCAN_TOKENS` already applies (Petrovich
  cannot see behind the aircraft). Likewise `report_bearing_north/south/east/west` is the plan's
  four-word shorthand for the real `_BEARING_REPORT_TOKENS`, which is the full eight-point compass
  (n/ne/e/se/s/sw/w/nw). Counting what is actually in `BRAIN_COMMANDS` (30 entries total,
  `len(BRAIN_COMMANDS)`): 9 clock tokens + 8 bearing tokens + `report`/`report_all` = 19
  report-shaped tokens, plus the 4 target-taking commands (`where_is_it`/`follow`/`select_target`/
  `mark_target`), `drop_target`, `mark_here`, the 2 `watch_nearest*` tokens and the 3 `cancel_*`
  tokens = 30. Both token-family tests above assert the clock/bearing match mechanically against
  the real tables, so a future drift in either is caught, not re-copied by hand. **No allowlisted
  token was dropped** — every one of D5's named tokens exists and is included; the correction only
  widened two families to their real membership and narrowed neither.
- **`report`'s own richer phrasebook slots (`descriptor`/`clock`/`sector`/`relative`/`band`) are
  deliberately not exposed this stage.** `report` is in `BRAIN_COMMANDS` (matching D5's own listing)
  but with `takes_target=False` and no extra `ParamSpec`s — a brain-dispatched `report` is a plain
  whole-scene report today, identical to `report_all`. A place slot is explicitly Stage 4's own job;
  the other four slots are free-text/enum values a resolved `target` (via a tool call first) already
  makes redundant for every Stage 3 acceptance-set case. Kept as its own token, not folded into
  `report_all`, so Stage 4 can widen *this* command's schema without re-adding it to the allowlist.
- **Review fix (`plans/brain-tool-calls/review.md`): a header offering two or more candidates is
  now pushed into `turn.candidate_sets`, closing a real trust-boundary gap this stage's original
  design left open.** As first implemented, header-seeded candidates were offered (`turn.offered`)
  but never pushed into `candidate_sets` at all, on the theory that a header-offered "recently
  mentioned" contact deserved the same no-evidence trust a bare "it"/"that" pronoun already gets
  on the voice path (`belief.referent.resolve_referent` asks for no evidence at all). The review
  found that analogy false once the header offers **two or more** genuine candidates with equal
  trust: a bare pronoun never makes a choice among several candidates (it deterministically
  returns the single most recent mention), so there is no "which one did it pick" question to ask
  evidence of — but the header can and does offer several, and `_validate_turn_answer`/
  `_validate_turn_command` were silently skipping the evidence check entirely for any final naming
  one, trusting the model's pick on competence alone, not D10's deterministic safety net. `_start_
  brain_turn` now pushes `header_refs` into `turn.candidate_sets` when `len(header_refs) >= 2`; a
  single header contact is unaffected and keeps the pronoun-level trust. `A4_which_ones_the_bmp`'s
  fixture (`brain-layer/tools/stage0_cases.json`) gained a `"because": "BMP"` field (the pilot's
  own word from "which one's the BMP?") to carry the evidence the rule now requires, rather than
  the fix being shaped to keep the fixture passing unchanged.
- **Of the task's named acceptance-bench cases, two pass as named and one does not, for a reported
  reason, not a forced one.** `A2_referent_where_is_it` and `A4_which_ones_the_bmp` (D4's own two
  named examples) now validate as their fixture's own `command`/`answer` final, once `_turn_from_
  case` seeds `offered` from the header. (Review fix, see above: `A4`'s 2-candidate header is now
  also pushed into `candidate_sets`, so this case passes through the evidence check rather than
  around it — the fixture itself gained a `"because": "BMP"` field to carry that evidence, since
  `A2`'s header has only one candidate and needs none.) `A1_where_two_shilkas_discriminated` — one of the "A1_*"
  cases the brief named as expected to pass — genuinely does not: its fixture resolves `where_is_it`
  `target=CONTACT_2` out of a 2-candidate `find_contact` result (discriminated by the utterance's
  own "the one by the village") with **no `because` field at all**. D3's ambiguity-evidence rule,
  implemented as the plan specifies, degrades this to `ask` over the two survivors — correctly, by
  the rule's own text, but not the fixture's own direct `command`. This is the same shape as the two
  gaps Stage 2 already documented (a Stage-0-authored expectation predating a validation rule added
  afterward); recorded as `_EXPECTED_COMMAND_NEEDS_EVIDENCE_GAP` with the fixture itself left
  untouched, rather than silently exempting command targets from the evidence rule to force a match.
  The other two "A1_*" cases (`A1_where_one_shilka`, `A1_where_shilka_lost_four_minutes`, both
  single-candidate) and `A5_keep_an_eye_on_the_tank_by_the_village` (also single-candidate) pass as
  named.
- **R1, concretely, in the real loop (`body.py`):** the per-poll order is `drain_attack_run` →
  `drain_where_is_it` (consumes *last* poll's `where_is_it_requested`, if any) → `drain_events` →
  `drain_pending_positional_replies` → `drain_brain` (where a brain `command` final now dispatches)
  → `drain_speech_results` → `_poll_transcripts` (where a voice command dispatches). Because `drain_
  where_is_it` runs at the *top* of the poll and `drain_brain` runs later in the *same* poll, a
  brain command setting `where_is_it_requested=True` this poll cannot be consumed until the *next*
  poll's `drain_where_is_it` — and `_poll_transcripts`, later in *this* same poll, could dispatch an
  unrelated voice command whose `handle_command` call would otherwise wipe that flag at entry before
  it is ever read. The fix is narrower than the plan's own suggested "at most one command dispatch
  per poll": only `where_is_it` among Stage 3's allowlisted tokens uses this one-shot-signal-to-a-
  later-poll shape (every other allowlisted command's readback is fully synchronous within
  `handle_command` itself, via `_speak_or_defer` at worst, never a runner-level flag consumed on a
  later poll) — `engage`/`disengage`/`observ_on`/`observ_off`/`weapons_armed`/`weapons_safe`, the
  only other tokens that set a one-shot runner signal, are all excluded from `BRAIN_COMMANDS` by
  U2, so they cannot collide with a brain dispatch in the first place. So the fix is simply: `handle_
  command` no longer resets `where_is_it_requested`/`where_is_it_slots` at all — only `_handle_
  where_is_it` sets them and only `body.py`'s `drain_where_is_it` consumption (or a mission reset)
  clears them. A request is delayed by at most one poll if a second command lands before
  consumption; it is never silently dropped by an unrelated dispatch. No generic per-poll dispatch
  guard, no change to `body.py`, were needed.
- **R6's grep confirmed exactly one construction site** (`_speak_or_defer`, as Stage 1's own report
  already found) — `_pending_brain_turn_id` threads through that one site only.
- **`final_to_dict`'s pre-existing `target` duplication was a real (if harmless until now) Stage-2
  wire-shape defect**, found while wiring `because` through the same grammar: `slots["target"]` and
  the top-level `target` field carried the same value, so a "no extra slots" check (needed for
  Stage 3's command validation) would have seen a false extra key on every single real command
  reply. Fixed by popping both `target` and `because` out of the raw JSON object rather than only
  reading `target` with `.get`.
- **`decider.py`/`server.py` needed no changes** — both already forward `commands`/`because`
  generically from the wire payload/decider-returned dict (confirmed by reading `ToolLoopDecider.
  decide`'s `commands_raw = payload.get("commands") or []` and `server.py`'s `reply = dict(result)`,
  not assumed from the plan's Affected Modules list, which names `decider.py` for "continuation
  rounds, NO_BRAIN" — both already built in Stage 2).

## Review fix (`plans/brain-tool-calls/review.md`)

The one required fix: `_start_brain_turn` (`body-layer/src/belief/crew_console.py`) now pushes
`header_refs` into `turn.candidate_sets` when `len(header_refs) >= 2`, so `_candidate_set_for_ref`
(`body-layer/src/belief/brain_reply.py`) finds a header-seeded multi-candidate set and
`_validate_turn_answer`/`_validate_turn_command` apply the same verbatim-`because` evidence check a
tool-returned multi-candidate set already got. A single header contact is unaffected (not pushed)
and keeps the bare-pronoun no-evidence trust. See the Stage 3 "Notable Discoveries" entry above
(now rewritten) for the full reasoning the review itself gave.

Added two tests in `body-layer/tests/test_brain_tool_loop.py`
(`test_header_ref_ambiguity_without_because_becomes_which_one`,
`test_header_ref_ambiguity_with_because_dispatches`) against a new local helper, `_store_with_two_
far_apart_differently_classed_contacts` (one T-72, one BMP, so the evidence check's substring test
has real signal to discriminate on) — a two-contact header naming one with no `because` degrades to
"which one?"; with the pilot's own verbatim word ("BMP" from "which one's the BMP?") it dispatches.
Confirmed red without the fix (reverted the `_start_brain_turn` change locally, both new tests
failed — the no-`because` case wrongly spoke the answer instead of degrading), then green with it.

Updated `brain-layer/tools/stage0_cases.json`'s `A4_which_ones_the_bmp` case to carry
`"because": "BMP"` on its `expected.final`, and `body-layer/tests/test_stage2_acceptance_bench.py`'s
`_turn_from_case` to push a >=2-contact header into `candidate_sets` (mirroring the real fix) — the
bench's own comments were updated in place rather than left asserting the pre-fix design.

Added a one-line comment to the E3 differential tests
(`test_brain_command_mark_target_matches_phrasebook_dispatch`,
`test_brain_command_cancel_task_matches_phrasebook_dispatch`) noting they deliberately cover the two
dispatch shapes (`takes_target`/none), not 2 of 30 `BRAIN_COMMANDS` tokens by accident — the review's
non-blocking note.

No wire-shape change, no change outside `body-layer`'s own files plus the `brain-layer` fixture.

### Checks (review fix)

**body-layer/**
- `ruff format src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass
- `pytest -q`: pass (see handback report for the exact count)

**brain-layer/**
- `ruff check src tests tools`: pass
- `mypy src`: pass
- `pytest -q`: pass

### A4 outcome

As predicted by the review: `A4_which_ones_the_bmp` now needs `because` to validate as its own
fixture's direct `answer`. The fixture was updated to carry it (`"because": "BMP"`), rather than the
fix being shaped to avoid touching the fixture. `_EXPECTED_COMMAND_NEEDS_EVIDENCE_GAP` (the one
genuine, already-documented gap, `A1_where_two_shilkas_discriminated`) is unaffected — it is a
tool-returned candidate set, not header-seeded, and was already going through the evidence check
before this fix.

### Security fixes

**U4 (plan.md's Decisions: fold `[[BR-B2]]`/`[[BR-B3]]` into Stage 2) was accepted by the user but
never built** — Stage 0's implementation log correctly deferred it to Stage 2, but Stage 2's own
log and Files Changed list make no mention of it at all, and `review.md` did not raise it either.
The security deep analysis caught this directly: both backlog items were still open in code,
exactly as filed, with the call frequency U4's own rationale named as the reason to act now now
realised (every addressed turn calls `_post_json` up to `TOOL_LOOP_MAX_ROUNDS + 1` times). Built
now, on this branch, as the security review's two Required-equivalent (option C, "fix now")
findings:

**Fix 1 — U4 itself:**
- `brain-layer/src/server.py`'s `_handle_escalate` now reads the body through a `_read_body`
  method, ported from `audio-adapter/src/server.py`'s own guard shape (same non-numeric/negative
  `Content-Length` rejection, `400` before `rfile.read` is ever called), plus a declared-length cap
  (`MAX_ESCALATE_BODY_BYTES = 262_144`) audio-adapter's own version does not need. `[[BR-B2]]`
  marked done.
- `brain-layer/src/ollama_client.py`'s `_post_json` now reads one byte past
  `MAX_OLLAMA_RESPONSE_BYTES` (`1_048_576`) and raises `OllamaRequestError` if the response
  exceeds the cap — shared by `generate()`/`generate_with_usage()` and `chat()` alike, since both
  go through this one method. `[[BR-B3]]` marked done. Both constants are behaviour-affecting by
  this project's tuning rule and would want the tuning mechanism; `brain-layer` has no loader yet
  (body-layer-only), so both stay plain module constants with a `#:` comment saying so, per the
  Implementer role's standing instruction for this case.
- Tests: `test_escalate_non_numeric_content_length_returns_400_without_raising`,
  `test_escalate_negative_content_length_returns_400`,
  `test_escalate_oversized_content_length_returns_400`,
  `test_escalate_valid_content_length_still_succeeds` (`test_server.py`, ported helper
  `_post_raw_content_length` from `audio-adapter/tests/test_server.py`); `test_generate_raises_
  when_response_exceeds_byte_cap`, `test_chat_raises_when_response_exceeds_byte_cap`,
  `test_generate_under_cap_still_succeeds` (`test_ollama_client.py`).
- Pruned `ollama_client.py`'s module docstring paragraph claiming `chat()` "reproduces
  `generate()`'s own unbounded `response.read()`" — now false, since both share the fixed
  `_post_json` (root `CLAUDE.md`'s "prune the comment you are standing next to").

**Fix 2 — the uncaught-exception gap on the tool-dispatch path (security review's Recommended,
non-blocking finding, also taken as option C):**
- `body-layer/src/belief/crew_console.py`'s `_handle_brain_tool_call` now wraps the single
  `self.run_brain_tool(tool_name, validated, now_sim)` call in `try`/`except Exception`: on an
  exception it logs with `logger.exception` (traceback kept), pops the turn, and speaks the
  existing `unable NO_ANSWER` degrade (`render_unable("NO_ANSWER")`) — the same reason the
  round-cap path already uses, not a new one. Never re-raises into `drain_brain`/body.py's poll
  loop, which also owns perception/belief/speech.
- Corrected the function's own docstring in passing — it claimed `_handle_brain_tool_call` "never
  calls `self._print`," which was already false for the round-cap degrade (`_speak_turn_degrade`
  does call it); now states both exits that do.
- Test: `test_run_brain_tool_raising_ends_the_turn_and_logs_rather_than_propagating`
  (`test_brain_tool_loop.py`) — a `run_brain_tool` closure that raises `RuntimeError`; asserts the
  turn ends with `["Unable, no answer."]`, the exception is logged, and a second, unrelated
  utterance afterward still completes normally (the console itself stays usable, not just the
  process).

**`todo/backlog/BR-B2.md`/`BR-B3.md` named in the dispatch do not exist** — both backlog items
live at `brain-layer/ROADMAP/BR-B2.md`/`BR-B3.md` (this layer's own `ROADMAP/` backlog directory,
not `todo/backlog/`), marked `[x]`/`#status/done` there instead, each with a one-line resolution
naming this branch. `todo/backlog/todo-backlog.md`'s only mention of either (the `X-B9` entry
recording that they were *filed*) needed no change — it is a historical record of the filing
session, not a live status tracker for either item.
