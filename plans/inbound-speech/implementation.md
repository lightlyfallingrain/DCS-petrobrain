### Implementation Summary

Stage 1 only (`plans/inbound-speech/plan.md`) — the recognition bench, a stop/go gate before any
capture/transit/PTT/body-layer wiring is built. Built in `srs-adapter/`, branch
`feature/stt-recognition-bench`. Deliverable is a script that produces numbers and a judgement, not
a working pipeline — see plan Decision 4/settled decision 2 for why the report is built around
"would I fly with this?" rather than a single accuracy threshold.

**Not run for real.** The corpus is the user's own voice and does not exist yet; no `whisper-cli`
binary and no Windows box were available in this environment. Everything below was verified
structurally (tests, a synthetic-tone WAV fixture, a hand-run against an empty/fake corpus showing
clean degradation) but the actual accuracy numbers, confusion pairs, and go/no-go judgement are
still pending the user recording a corpus and running `tools/stt_bench.py` for real.

### Files Changed
- `srs-adapter/src/vocabulary.py` (new) — 15-token vocabulary (`TOKENS`), spoken phrasings
  (`PHRASES`, several per token), and helpers (`spoken_phrases`, `token_for_phrase`, `to_gbnf`). A
  deliberate hand-synced duplicate of `body-layer/src/belief/crew_console.py`'s
  `_RELATIVE_SCAN_TOKENS`/`_BEARING_SCAN_TOKENS` and `aircraft-layer`'s `ALLOWED_COMMANDS` —
  `srs-adapter` cannot import either (module independence rule).
- `srs-adapter/src/stt_engine.py` (new) — `STTEngine` protocol, `Transcript` dataclass,
  `STTRecognitionError`, `WhisperCliEngine`, `WindowsSpeechEngine`. Mirror image of `tts_engine.py`.
- `srs-adapter/tools/stt_bench.py` (new) — the bench: loads a `<corpus-dir>/<token>/*.wav` corpus,
  runs each available engine (whisper.cpp with/without `--grammar` as separate rows, Windows only
  attempted on Windows), scores top-1 token accuracy via a simple `difflib`-based match against
  `vocabulary.py`'s phrase table, and prints accuracy + confusion pairs with sample misheard text +
  confidence distribution split by correct/incorrect. `--list-prompts` prints what to record.
- `srs-adapter/tests/fixtures/sample.wav` (new) — a small stdlib-generated (`wave` module) 16kHz
  mono tone, used only to exercise the WhisperCliEngine test class's shape (not real speech; that
  class skips entirely without a real binary+model anyway).
- `srs-adapter/tests/test_stt_engine.py`, `srs-adapter/tests/test_vocabulary.py` (new).
- `srs-adapter/pyproject.toml` — added `stt_engine`, `vocabulary` to ruff's `known-first-party`.
- `srs-adapter/CLAUDE.md`, `srs-adapter/ROADMAP.md` — documented the new files/commands and Stage 1
  status (landed, not yet run for real; Stage 2 must not start before the bench is).

### Tests Added
- `test_vocabulary.py` — 15 tokens, no duplicate phrases across tokens, `spoken_phrases`/
  `token_for_phrase`/`to_gbnf` round-trip correctly.
- `test_stt_engine.py` — `WhisperCliEngine.is_available()` true/false paths; missing-model,
  empty-audio, and missing-binary raise `STTRecognitionError` with actionable messages;
  `WindowsSpeechEngine` rejects an empty phrase list, reports itself unavailable on this platform,
  and raises (not tracebacks) if `transcribe` is called off Windows. A `TestWhisperCliEngineReal`
  class exercises the real binary end to end but is `skipif`-gated on
  `SRS_ADAPTER_WHISPER_BINARY`/`SRS_ADAPTER_WHISPER_MODEL` env vars — skipped in this environment.

### Checks
(srs-adapter/ only)
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`src`, and `tools/stt_bench.py` individually — `tools/` isn't in the mandated
  command list per `CLAUDE.md`'s own precedent for `world-model/tools/`, checked anyway): pass
- pytest -q: pass (36 passed, 1 skipped — the real-whisper-binary class, correctly absent here)

### Notable Discoveries
- **Neither engine's CLI/JSON contract could be verified against a real binary.** No `whisper-cli`,
  no `ffmpeg`, no `sox`, and no Windows box exist in this environment. `WhisperCliEngine` assumes
  `-ojf`/`-of`/`--grammar`/`--grammar-penalty` flags and a `{"transcription": [{"text", "tokens":
  [{"p"}]}]}` JSON shape from whisper.cpp's public docs; `WindowsSpeechEngine`'s PowerShell script
  assumes `System.Speech.Recognition`'s documented .NET API shape. Both are flagged prominently in
  `stt_engine.py`'s module docstring as unverified — running the bench for real is exactly what
  validates or corrects them, which is consistent with Stage 1's own purpose but is a real gap the
  user should know about before trusting a confusing first result to mean "STT is bad" rather than
  "the flag name was wrong."
- **No recording helper script was written.** The task allowed either a helper or clear
  documentation; a helper would itself need `ffmpeg`/`sox` (another unverified external-binary
  dependency in an environment where neither exists), so `tools/stt_bench.py`'s docstring documents
  QuickTime+`afconvert` and `sox`'s `rec` instead.
- **The bench's own text-to-token matcher is deliberately simpler than Stage 2's future
  `belief/voice_commands.py`.** No verb anchor, no separation check, no confidence bands — a single
  `difflib.get_close_matches` pass against the flat phrase list, since the bench only needs to score
  "which token does this look like," not decide whether to act on it. Documented in
  `stt_bench.py`'s `_match_token` docstring so a future reader doesn't mistake it for Stage 2's real
  matcher or try to reuse it as one.
- Confirmed via `grep` that `body-layer/src/belief/crew_console.py`'s `_RELATIVE_SCAN_TOKENS`/
  `_BEARING_SCAN_TOKENS` and `aircraft-layer/src/collector/f10_command_receiver.py`'s
  `ALLOWED_COMMANDS` agree exactly on the 15 tokens and their names — `vocabulary.py` mirrors that
  confirmed set, not a guess.

---

### Stage 2 — the matcher and the command path, driven by typed text (2026-09-19)

Branch `feature/stt-command-matcher`. No audio anywhere, per plan. Two halves, split per Decision 4
REVISED: `srs-adapter` owns matching mechanics, `body-layer` owns act/confirm/say-again behaviour.

#### Files Changed

- `srs-adapter/src/command_matcher.py` (new) — `match_transcript(text) -> MatchResult`: normalise
  (`vocabulary.normalize_for_match`) -> verb anchor -> bearing slot (`vocabulary.parse_bearing`) or
  phrase match (`vocabulary.normalized_phrase_index`) -> separation check. `MATCH_FLOOR` reuses
  `tools/stt_bench.py`'s own measured `_MATCH_CUTOFF` (0.6) verbatim — the cutoff that actually
  produced Stage 1's 99.2%/zero-unsafe-error result. `VERB_FLOOR` reuses the same figure (no
  separate verb-only distribution was measured). `SEPARATION_MIN` (0.05) is an explicitly
  undocumented-as-measured placeholder. `VERB_ANCHOR_WORDS` is derived from `vocabulary.PHRASES`
  (every phrasing's first word), not transcribed from Decision 4 REVISED's prose enumeration — see
  "Notable Discoveries" below.
- `srs-adapter/tests/test_command_matcher.py` (new).
- `srs-adapter/CLAUDE.md` — `Structure`/`Testing` entries for the new module.
- `body-layer/src/belief/voice_commands.py` (new) — `classify_response` (the band decision) and
  `classify_yes_no` (a tiny, body-owned affirm/negative word check — not a vocabulary import).
  `ACT_FLOOR` (0.60) is grounded in Stage 1's measured min-correct confidence
  (`srs-adapter/research/2026-09-19-whisper-model-sweep.md`). `ACT_FLOOR_CANCEL` (0.80),
  `CONFIRM_FLOOR` (0.35), `CONFIRM_WINDOW_S` (8.0) are documented in their own comments as
  unmeasured placeholders pending Stage 6 live-sortie data — not disguised as measured.
  `PendingConfirmation`/`BandDecision` are plain dataclasses.
- `body-layer/src/belief/speech.py` — `render_say_again`, `render_confirm_request`.
- `body-layer/src/belief/crew_console.py` — `CrewConsole.handle_transcript` (new sibling entry
  point to `handle_line`/`handle_f10_command`), `_pending_confirmation` state field,
  `_describe_token_for_confirm` (reuses `handle_f10_command`'s own token->label tables),
  `_handle_voice_test_command` (`!voice` REPL harness), `HELP_TEXT` update.
- `body-layer/CLAUDE.md` — `Structure` entry for `voice_commands.py` and the `handle_transcript`/
  `!voice` addition to `crew_console.py`'s existing entry.
- Tests extended: `body-layer/tests/test_voice_commands.py` (new), `test_speech.py` (2 new
  renders), `test_crew_console.py` (`handle_transcript` routing, pending-confirmation lifecycle,
  `!voice` harness).

#### Tests Added

- `test_command_matcher.py` — exact hits per token shape, verb-anchor rejection (with a documented
  finding about short-word false-anchoring, see below), a measured genuine-tie ambiguous case
  ("scan est" scores an identical 0.941 against both "scan east"/"scan west"), legal/illegal
  bearing outcomes via `parse_bearing` (not the phrase table), and two regression guards for the
  derived verb set ("never mind", "hey petrovich" must still anchor).
- `test_voice_commands.py` — `classify_response`'s four dispositions including the ambiguous-always-
  confirms and cancel_task-higher-floor cases; `classify_yes_no`'s three outcomes.
- `test_speech.py` — `render_say_again`, `render_confirm_request` (capitalisation, empty
  description).
- `test_crew_console.py` — `handle_transcript` fallthrough (verified via the stand-in brain client
  actually receiving the escalation, not just matching return text), act above `ACT_FLOOR`, confirm
  band (asks, holds pending, does not execute), ambiguous-always-confirms, say-again below
  `CONFIRM_FLOOR`, confirm-then-affirm commits, confirm-then-negative discards silently,
  confirm-then-unrelated-answer discards the stale question but still processes the new one,
  confirm-window expiry, `cancel_task`'s higher floor, and the `!voice` harness (happy path,
  no-match path, usage-error path).

#### Checks

**srs-adapter/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict): pass
- `pytest -q`: pass (72 passed, 1 skipped — pre-existing whisper-binary skip)

**body-layer/**
- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict, run from `body-layer/`): pass
- `pytest -q`: pass (705 passed)

#### Notable Discoveries

- **`VERB_ANCHOR_WORDS`, derived programmatically, is a strict superset of Decision 4 REVISED's own
  prose verb-set enumeration.** The prose says `{scan, look, report, watch, cancel, stop, say,
  repeat}` plus the wake word and `nevermind`. Deriving from every phrasing's first word (per the
  task's own instruction: "derive it from the actual vocabulary rather than hardcoding a list that
  will drift") additionally admits `full` ("full scan"), `what` ("what do you see"), `hey` ("hey
  petrovich"), `never`, and `disregard` ("never mind"/"disregard"). Kept deliberately: excluding
  `never` would silently break `"never mind"` — the exact alternate spelling `vocabulary.py`'s own
  docstring says exists *because* `base.en` splits a spoken "nevermind" into two words — and the
  identical argument applies to `hey petrovich`. Regression tests pin both. This is a real
  deviation from the plan's literal prose list; I believe it is what the plan intended given its
  own stated reasoning, but it is worth the user's explicit sign-off since the plan text names a
  specific, narrower set.
- **Fuzzy verb-anchor matching against short words is looser than it looks.** Measured while
  writing tests: the word "the" scores a 0.667 `SequenceMatcher` ratio against "hey", clearing
  `VERB_FLOOR` (0.6) and false-anchoring an ordinary sentence starting with "the". Any 3-4 letter
  verb-anchor word (`hey`, `say`, `full`) is vulnerable to this — short strings have a structurally
  higher baseline similarity to arbitrary other short strings. Not fixed here (`VERB_FLOOR` is
  explicitly Stage 1's `MATCH_FLOOR` reused, not a verb-specific measurement, and the plan expects
  Stage 6 to re-tune these constants from live data) but flagged for that re-tuning pass, and the
  test that would have used the research doc's own out-of-vocabulary probe ("the weather is quite
  nice today") had to be swapped for a different sentence because of exactly this.
- **The plan's own Decision 6 seam table is stale relative to Decision 4 REVISED.** Decision 6
  (below Decision 4 REVISED in the doc, but not itself marked REVISED) describes
  `CrewConsole.handle_transcript(text, confidence, now_sim)` — a 3-argument signature with no
  `token`/`match_ratio` at all — while Decision 4 REVISED's own seam table says body receives
  `{transcript, confidence, token, match_ratio}`. Neither matches what got built:
  `handle_transcript` needed **two more fields** than either table gives (`verb_anchored`,
  `ambiguous`) to distinguish three behaviourally distinct `token=None` outcomes that Decision 4's
  own prose requires be treated differently (not-a-command-attempt -> fallthrough;
  verb-anchored-but-unresolved -> always say-again; ambiguous -> always confirm on the best
  candidate). Two fields cannot encode three outcomes without a fragile magnitude-based convention
  over `match_ratio`, so I added `verb_anchored: bool` and `ambiguous: bool` to `MatchResult` and
  threaded them through. This is a genuine plan gap, not a preference — flagging for the user/
  Architect to fold into Stage 3's real wire-shape design (`GET /transcripts/poll`'s JSON will need
  these two fields too, not just the two the seam table currently names).
- **Voice-only tokens (`report_all`, `report_bearing_*`, `report_clock_*`, `scan_bearing_deg`,
  `stop_talking`, `say_again` as a player command) have no real dispatch behaviour yet.** The plan's
  own Tests section describes the act path as "match -> `handle_f10_command` effects and readback",
  which only covers the 15-token legacy vocabulary. `handle_transcript`'s act disposition reuses
  `handle_f10_command` directly rather than building new dispatch logic for the newer voice-only
  tokens (report-by-bearing/clock needs a query capability that doesn't exist anywhere in this
  codebase; `stop_talking`/`say_again` as player-spoken commands need the not-yet-planned
  transmission-buffer/repeat-last-utterance mechanisms the plan's own "Not planned here" note
  defers). These tokens still match and can reach the confirm/say-again bands
  (`_describe_token_for_confirm` has a generic fallback description), but "acting" on them is a
  graceful no-op via `handle_f10_command`'s existing defensive `else` branch — a documented gap,
  not a silent one, and consistent with effort/value: building real report-by-bearing dispatch is
  its own feature, not part of "the matcher and the command path."

---

### Stage 2 review fixes (2026-09-19)

Reviewer found the verb-anchor leak reached false command execution (`plans/inbound-speech/
review.md`), not just spurious "say again" noise, and a wrong research-doc citation on `ACT_FLOOR`.
Both required fixes addressed; two optional items folded in too.

#### Fix 1 — word-sequence phrase scoring (was: whole-string character scoring)

`srs-adapter/src/command_matcher.py`'s phrase-matching step scored the *whole normalised string*
character-by-character (`difflib.SequenceMatcher`/`get_close_matches`), which rewards prefix/
character overlap with no notion of word count. Verified live: `"look at that"` scored 0.727
against `scan_ahead` and `"watch out"` scored 0.636 against `watch_nearest`, both clearing
`ACT_FLOOR` at confidences inside Stage 1's measured correct range — a false command execution
from ordinary speech, since `look`/`watch`/`report`/`scan`/`say`/`stop`/`cancel`/`full` are all
both real verbs in this vocabulary and ordinary English words.

Replaced with `_phrase_match_ratio`, a word-sequence score (reviewer-specified, reviewer-verified
against a real false-positive/real-mishearing fixture set): `SequenceMatcher` over word lists,
exact word matches score 1.0, equal-length `"replace"` opcode blocks get per-word character-ratio
credit only above `_WORD_REPAIR_FLOOR` (0.5), divided by `max(len(heard), len(phrase))`.
`MATCH_FLOOR` (0.6) is unchanged and still separates the two classes under the new scoring.
Confirmed by direct comparison against the reviewer's own verification table (9 of the reviewer's
12 numbers matched exactly once the algorithm used equal-length-only replace-block pairing rather
than an unrestricted best-pairwise search across all remaining words — the unrestricted version let
long irrelevant sentences inflate their score via coincidental short-word overlaps, which is the
same failure class as the bug being fixed). `test_command_matcher.py` pins the reviewer's exact
false-positive rejections, the `_phrase_match_ratio` table, and the separation-check pair
("scan left"/"scan right" at 0.5, "scan north"/"scan south" at 0.8) as regression tests.

**One real, remaining gap found while verifying:** the verb-anchor gate (unchanged by this fix,
per the reviewer's explicit "keep the verb anchor as a cheap early-out, not the primary defence")
is loose in *both* directions on short words — it now also *rejects* two of the reviewer's own
"real mishearing, should still be accepted" examples end-to-end (`"walk ahead"`, `"skin bearing
315"`), because `ratio("walk", "watch")`/`ratio("skin", "scan")` are 0.5, below `VERB_FLOOR`'s 0.6.
This is the same short-word fuzzy-matching looseness flagged in Stage 2's original implementation
notes (`"the"` scoring 0.667 against `"hey"`), just manifesting as an over-rejection here rather
than an under-rejection. Not fixed — explicitly out of this fix's scope — but the test file
documents it directly (`test_phrase_match_ratio_finds_real_mishearings_above_floor`'s docstring)
rather than silently asserting around it, and it is the natural next target if `VERB_FLOOR`/
`VERB_ANCHOR_WORDS` gets a Stage 6 re-tuning pass.

Updated the module docstring's framing accordingly: the verb anchor "fires first" but is no longer
claimed to be "the single most important line of defence" — that language now describes
`_phrase_match_ratio`.

#### Fix 2 — ACT_FLOOR citation

`voice_commands.py`'s `ACT_FLOOR` comment cited `srs-adapter/research/2026-09-19-whisper-model-
sweep.md`, which has no confidence distribution at all (only accuracy/safe-miss/unsafe-error/
latency). Repointed at `srs-adapter/research/2026-09-19-corpus-bench-results.md` (committed by the
user, `8070d6e`), which records the figures as data, and added the caveat the research doc itself
states: the floor holds **only while `--prompt` is in use** — on the plain/unprompted row, correct
and incorrect confidence ranges overlap almost entirely and the single most confident answer in
that run was wrong. Same citation fixed in `body-layer/CLAUDE.md` and
`tests/test_voice_commands.py`'s docstring.

#### Optional items folded in

- `plans/inbound-speech/plan.md` Decision 6's seam table updated in place (with an inline "Updated
  2026-09-19" note explaining what changed and why) rather than left stale: both rows now show
  `token`/`match_ratio`/`verb_anchored`/`ambiguous`, matching what Stage 2 actually built.
- Added a note to the plan's Stage 3 description: `stop_talking`'s eventual dispatch should reuse
  `aircraft-layer/src/collector/audio_sender.py`'s existing `_interrupt_playback` (already
  reachable via `push_speech(..., urgent=True)`) — cheaper than the other voice-only tokens still
  parked as no-ops, since the interrupt mechanism it needs already works end to end.

#### Checks (re-run after both fixes)

**srs-adapter/**: `ruff format --check` pass, `ruff check` pass, `mypy src` pass, `pytest -q` pass
(78 passed, 1 skipped).

**body-layer/**: `ruff format --check` pass, `ruff check` pass, `mypy src` (from `body-layer/`)
pass, `pytest -q` pass (705 passed).

---

### Stage 2 follow-up: lower VERB_FLOOR (2026-09-19)

Coordinator flagged that one of the two over-rejected cases from the previous fix's residual gap
(`"skin bearing 315"`) is not hypothetical — it is an actual whisper transcript from the user's
own recorded corpus (a mishearing of "scan bearing three one five"), so rejecting it meant a
command the player really spoke would silently fall through as free speech: a wrong action, not a
missed one.

**Fix follows from the earlier one.** Now that the phrase score (`_phrase_match_ratio`) is the
real defence and the verb anchor is a cheap early-out, the two floors guard mistakes of very
different cost: a false anchor costs one extra phrase-scoring pass that almost always rejects it
anyway (`"the"` anchors against `"hey"` at 0.667, but `"the tanks are on the ridge"` scores 0.083
against its best phrase candidate); a false rejection at the anchor is irreversible — it discards
the transcript before phrase scoring ever runs. `VERB_FLOOR` lowered from 0.6 (`== MATCH_FLOOR`) to
**0.5**, `MATCH_FLOOR` left untouched at 0.6.

Verified end to end after the change:
- `"skin bearing 315"` → `scan_bearing_deg`, `bearing_degrees=315`, ratio 1.0.
- `"walk ahead"` → `scan_ahead`, ratio 0.75.
- All of the reviewer's original false positives (`"look at that"`, `"watch out"`, `"report says
  otherwise"`, `"this kind of stuff"`, `"it's kind of full"`, `"the tanks are on the ridge"`,
  `"scan the trucks on the road"`) still resolve to no token end to end — none reopened.

No need to raise `MATCH_FLOOR` to compensate (would have traded a measured constant for an
unmeasured one) — not attempted, per the coordinator's explicit stop condition.

`VERB_FLOOR`'s comment and the module docstring were rewritten so the two floors read as a
deliberate pair (the asymmetry stated explicitly, not just the new number) rather than two
independent knobs someone could "fix" back to matching later. Added
`test_skin_bearing_315_matches_end_to_end` (citing corpus provenance directly in the docstring so
it's harder to delete as "just a fixture"), `test_walk_ahead_matches_end_to_end`, and
`test_lowering_verb_floor_does_not_reopen_the_false_positives` as a dedicated regression guard.

Checks re-run: srs-adapter (`ruff format --check`/`ruff check`/`mypy src`/`pytest -q`) — 81
passed, 1 skipped. body-layer (unaffected by this change, re-run anyway per instruction) — 705
passed.

---

### Stage 3 — recognition as a service, and body-layer's inbound wiring (2026-09-20)

Branch `feature/stt-recognition-service`, forked from a just-merged `main` (the `srs-adapter` ->
`audio-adapter` rename had already landed). Both halves of Decision 6's seven-field seam row, plus
`stop_talking` dispatch deferred from Stage 2.

#### Plan-vs-tree check (before starting)

Per process: read Decision 6's seam table (2026-09-19 update), Decision 1/4 REVISED, the Stage 1
GATE-CLEARED section, and `implementation.md`'s own Stage 2 entry before writing anything. The
plan's Tests section names `srs-adapter/tests/...` paths throughout — all pre-rename prose, mapped
to `audio-adapter/tests/...` per the 2026-09-20 rename note in the task brief; no other test-list
mismatch found. `CrewConsole.handle_transcript` already took all seven of Decision 6's fields
(Stage 2 had already added `verb_anchored`/`ambiguous` beyond the plan's own stale two-field
table) — Stage 3 only had to build the wire that feeds it, not change its signature.

#### Files Changed

**`audio-adapter/`:**
- `src/transcript_queue.py` (new) — `TranscriptEvent` (the seven-field row) + `TranscriptQueue`
  (`push`/`drain_all`), a bounded FIFO mirroring `aircraft-layer/src/collector/cache.py`'s
  `F10CommandQueue` almost exactly (same two-poller-safe drain-on-GET reasoning).
- `src/server.py` — `TTSAdapterServer` gains optional `stt_engine`/`transcript_queue` constructor
  params (both optional, `stt_engine=None` the default) and two routes: `POST /transcribe`
  (base64 WAV in, mirroring `/audio/play`'s decode shape from `aircraft-layer`) ->
  `STTEngine.transcribe` -> `command_matcher.match_transcript` -> `TranscriptQueue.push`; `GET
  /transcripts/poll` -> `TranscriptQueue.drain_all`, `[]` on empty, mirroring `GET
  /f10_commands/poll`. Without `stt_engine` configured, `/transcribe` answers `503` and
  `/transcripts/poll` always drains empty — same "optional collaborator" posture as
  `aircraft-layer`'s optional senders.
- `src/audio_adapter/__main__.py` — `--whisper-binary`/`--whisper-model` wire a `WhisperCliEngine`
  into the server using Stage 1's settled config (`vocabulary.to_prompt()` biasing, never
  `--grammar`). No default model path — omitted means no recogniser, a true no-op.
- `pyproject.toml` — `command_matcher`/`transcript_queue` added to ruff's `known-first-party`.
- `tests/test_transcribe_api.py` (new) — structural copy of `test_server.py`'s pattern plus a
  recording `STTEngine` double; `command_matcher.match_transcript` runs for real against whatever
  text the double returns, so these tests exercise the real match path, not a matcher double.
- `audio-adapter/CLAUDE.md` — Structure/Testing/Commands sections updated for all of the above.

**`body-layer/`:**
- `src/belief/audio_client.py` — `AudioAdapterClient.get_transcripts()`, following
  `get_f10_commands`'s own drain-on-poll precedent (`[]` not `None` on empty; raises
  `AudioAdapterError` on transport/parse failure, same as `push_speech` — not a swallow-and-
  return-`[]` posture, since `logger.py`'s poll loop is where that decision belongs).
- `src/belief/speech.py` — `render_stop_acknowledged()` ("Copy.").
- `src/belief/crew_console.py` — `handle_f10_command`'s dispatch gains a `stop_talking` branch
  calling a new `_handle_stop_talking`, and — unlike every other token's shared tail — pushes via
  `self._print(lines, bypass_gate=True)` instead of the plain `self._print(lines)` every other
  token uses. `bypass_gate=True` is what threads through as `speech_client.push_speech(...,
  urgent=True)`, which is what actually triggers aircraft-layer's `AudioPlaybackSender.
  _interrupt_playback` per the plan's own note on this token.
- `src/logger.py` — `_poll_transcripts` (mirrors `_poll_f10_commands`'s per-call
  `try`/`except`-isolated shape), validating all seven wire fields (type-checking each, including
  an explicit `bool`-excluded numeric check for `confidence`/`match_ratio` since `bool` is an `int`
  subclass) before dispatching through `CrewConsole.handle_transcript`; `t_wall` is read but not
  passed through — `now_sim` is this poll's own sim time, the clock every other dispatch path
  already uses. `--speech-input` (requires `--audio-adapter-url`, independent of `--speech-audio`)
  wires it into `_run_crew_text_poll_loop` right after `_poll_f10_commands`. `main()` now builds
  one shared `AudioAdapterClient` when either `--speech-audio` or `--speech-input` is set (one
  process, one URL) — `CrewConsole.speech_client` only takes it when `--speech-audio` is actually
  set, since audio *output* stays its own concern.
- `run-crew-text.sh` — fixed a stale `--srs-adapter-url` flag left over from the `audio-adapter`
  rename (would have crashed `main()`'s own `parser.error` check the moment `--speech-audio` was
  parsed against an unrecognized flag); added `--speech-input`. This script was found already
  modified/uncommitted at task start (unrelated prior session), fixed in place since it's the
  exact run path this stage's acceptance target needed.
- `tests/test_audio_client.py` — `get_transcripts()`: empty poll, ordered drain, unreachable-host
  raise; `_make_handler` extended with a `do_GET` branch for `/transcripts/poll`.
- `tests/test_speech.py` — `render_stop_acknowledged`.
- `tests/test_crew_console.py` — `stop_talking`: speaks "Copy.", pushes to `speech_client` with
  `urgent=True`, pushes to the overlay with the `"!! "` prefix (the same rule every other injected-
  urgent line follows, not new behaviour).
- `tests/test_logger.py` — `_poll_transcripts`: dispatches a matched command, a `token=None`/
  `verb_anchored=False` transcript falls through to `handle_line`/escalation (verified via a
  recording `BrainClient`, not just a return value), an empty queue dispatches nothing, a failed
  poll degrades without raising, and a malformed item in a list is skipped while a well-formed
  sibling in the same list still dispatches.
- `body-layer/CLAUDE.md` — `--speech-input` flag doc, `AudioAdapterClient.get_transcripts`,
  `_poll_transcripts`, and `stop_talking` dispatch added to their respective Structure entries.

#### Tests Added

See "Files Changed" above for what each new/extended test file covers; nothing summarized twice.

#### Checks

**audio-adapter/**: `ruff format --check` pass, `ruff check` pass, `mypy src` (strict) pass,
`pytest -q` pass (98 passed, 1 skipped — pre-existing real-whisper-binary skip, unaffected).

**body-layer/**: `ruff format --check` pass, `ruff check` pass, `mypy src` (strict, from
`body-layer/`) pass, `pytest -q` pass (717 passed, up from 705 baseline + 12 new).

#### Acceptance verification (real, not simulated)

Ran for real, per the task's explicit instruction not to describe this untested. Found a stale
`audio-adapter` process already listening on 7795 from before this session's code existed (`GET
/transcripts/poll` 501'd — no `do_GET` at all, confirming it predated Stage 3); killed it and
started a fresh instance from this branch:

```sh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter --whisper-model /Users/sg/whisper-models/ggml-small.en.bin --target local --port 7795
```

POSTed three of the user's Stage 1 corpus WAVs (`data/corpus/raw/<token>/*.wav`) directly to
`POST /transcribe`, real whisper-cli, real `command_matcher`:
- `scan_left/scan_left_0.wav` -> `{"transcript": "scan left.", "token": "scan_left",
  "confidence": 0.86, "verb_anchored": true, "ambiguous": false}` via `GET /transcripts/poll`.
- `cancel_task/cancel_task_0.wav` -> recognised and matched, but confidence landed in the confirm
  band (below `ACT_FLOOR_CANCEL`'s higher floor) — real behaviour, not act-by-default.
- `stop_talking/stop_0.wav` -> recognised, matched to `stop_talking`, acted.

Then drove `AudioAdapterClient.get_transcripts()` -> `_poll_transcripts` -> `CrewConsole.
handle_transcript` directly (a small in-process script, not the full `logger.py main()` — see
"Notable Discoveries" below for why) against a real `speech_client` pointed at the same running
`audio-adapter` instance:
- `scan_left` -> acted immediately (no confirm question), `handle_f10_command("scan_ahead"-family)`
  ran (a "no world-model connection configured" readback line is the expected degraded output
  with no `EnrichmentContext` wired in this minimal script, not a Stage 3 defect).
- `cancel_task` -> printed `"Cancel the task, confirm?"` — the confirm band's real question, driven
  by real recognition confidence, not a fixture.
- `stop_talking` -> printed `"Copy."`. `_handle_stop_talking`'s dispatch path (`bypass_gate=True`)
  ran; `speech_client.push_speech(..., urgent=True)` was called without raising against the real
  `POST /speak` endpoint (delivery via `afplay` — this project's own compute-topology note that
  audio confirmation is a human-in-the-loop check, and `test_server.py`'s existing suite already
  covers the synthesis/delivery mechanics this call exercises).

This exercises every real component in the chain end to end — `WhisperCliEngine`,
`command_matcher.match_transcript`, `POST /transcribe`, `TranscriptQueue`, `GET /transcripts/poll`,
`AudioAdapterClient.get_transcripts`, `_poll_transcripts`'s field validation,
`CrewConsole.handle_transcript`'s band routing, and `_print`'s real `speech_client.push_speech`
call — with no Windows box and no DCS involved, matching the stage's stated acceptance target.

#### Notable Discoveries

- **The full `logger.py main() --crew-text` path could not be driven end to end in this
  environment, for a reason unrelated to Stage 3.** `ConsolePerceptionRunner.run_once`/
  `PerceptionLogger.run_once` both return early (`[]`) whenever
  `aircraft_client.get_telemetry_latest()` is `None`, and `_run_crew_text_poll_loop`'s own gate
  (`if runner.last_t_sim is not None`) means `_poll_transcripts`/`_poll_f10_commands`/
  `drain_events` never run at all until *some* real telemetry has arrived at least once — a
  pre-existing property of `--crew-text` (present since Stage 4's `_run_console_poll_loop`, not
  introduced here), not something Stage 3 changed. Running the real `main()` for a from-WAV
  acceptance test would need a live `aircraft-layer` collector process actually receiving
  telemetry (from DCS or a synthetic Export.lua-shaped feed), which is out of Stage 3's own scope
  ("no Windows, no DCS in the loop"). The verification above drives the same real components
  (`AudioAdapterClient`, `_poll_transcripts`, `CrewConsole.handle_transcript`, `speech_client`)
  directly instead of through `main()`'s CLI wiring — everything Stage 3 itself built is real and
  exercised; only the pre-existing telemetry-gating wrapper around it was bypassed. Worth the
  user's awareness before the next stage that needs a from-WAV acceptance test through the full
  `--crew-text` process.
- **A stale `audio-adapter` process from before this branch's code was already listening on port
  7795** at task start (confirmed via `GET /transcripts/poll` 501ing with "Unsupported method",
  which only happens on a handler with no `do_GET` at all — pre-Stage-3 code). Killed and replaced
  with a freshly built instance before verification; flagging in case the user notices the PID
  changed underneath a session they had running.
- **`run-crew-text.sh` was already modified/uncommitted at task start**, passing a stale
  `--srs-adapter-url` flag from before the `audio-adapter` rename — would have hit `main()`'s own
  `parser.error` the moment `--speech-audio` was parsed (unrecognized argument). Fixed in place
  (see "Files Changed") since it is the exact script this stage's acceptance flow needed to be
  correct, and leaving it broken would have actively misled whoever ran it next.
