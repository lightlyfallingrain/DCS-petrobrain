### Implementation Summary

Added a `silence` command to body-layer's `CrewConsole` command dispatcher: "make Petrovich not
talk until my next command" (user direction, 2026-10-04). No architect/plan.md preceded this --
the user's own message settled the two load-bearing decisions (absolute silence including urgent
callouts; one spoken acknowledgement) and this file records the remaining design points, as
requested.

### Design points settled

- **"Any subsequent command ends silence" is read narrowly: a real command, not any speech.**
  Silence is cleared in exactly two places, both representing an *actually dispatched* command,
  never a question still in flight:
  - `handle_command`'s top, for every token (F10 menu, a voice `"act"` disposition, or a
    committed confirm-band `"affirm"`) -- except the `silence` token's own call, which is checked
    *before* that reset so a repeated `silence` can see it was already in effect.
  - `_handle_utterance`'s `"handled"` branch, for a typed/voice free-text sentence
    `belief.utterance.parse_utterance` actually resolves to an intent (`watch <id>`, etc.).

  **Deliberately not cleared** for: an unresolved utterance (`"escalated"` disposition -- stray
  speech recognised as nothing, which is the radio-traffic use case the command exists for) or a
  voice `"confirm"`/`"say_again"` disposition that has not yet committed to a token (the question
  itself would be suppressed like any other line while silenced, so there is nothing yet to call
  "a command" from the pilot).

- **`silence` while already silenced is a no-op, not a toggle** (`_handle_silence`): checked and
  dispatched before the general clear, so a second `silence` sees `self.silenced` still `True` and
  returns immediately, speaking nothing a second time. A toggle would make a repeated press
  ambiguous exactly when the pilot has lost track of state -- the one situation `silence` exists
  to help with.

- **Mechanism: `self.silenced: bool` gates exactly one thing, in exactly one place** --
  `CrewConsole._print`'s push to `speech_client` (`AudioAdapterClient.push_speech`), for both the
  routine and the `bypass_gate=True` urgent branch. Chose a single boolean + a single gate in the
  one existing choke point every spoken line already passes through, rather than draining/skipping
  queues at several call sites. `output` (printed/crew-text) and `overlay_client` are **not**
  gated -- the use case named is audio specifically ("radio traffic", "friendly airbase"), so the
  text/overlay surfaces keep working; only the TTS sink goes quiet. `speech_log_sink` and the
  `CalloutScheduler`'s own `note_reply`/`note_urgent` occupancy bookkeeping are also **not**
  gated -- they record what Petrovich *decided* to say, independent of whether it was voiced,
  which is what makes "suppressed, not deferred" true: `drain_events` keeps calling
  `scheduler.tick` every poll regardless of `silenced`, so belief events are chosen, rendered, and
  consumed (or lost, per the scheduler's existing posture for anything it does not get to) at the
  normal pace throughout silence. Nothing is held back to be dumped the instant silence ends.

- **Absolute silence, including urgent callouts**, is enforced by the same single gate -- an
  injected `UrgentCall` reaches `_print` with `bypass_gate=True` exactly like any other line, and
  the `speech_client` push is skipped identically. No special-case code was needed; this is a
  direct consequence of gating the one choke point rather than gating per-caller.

- **The acknowledgement is spoken, not suppressed, by construction of call order.**
  `_handle_silence` calls `self._print([ack], now_sim)` *before* setting `self.silenced = True`.
  At the moment the ack is pushed, `self.silenced` is still `False`, so the gate above does not
  apply to it. This is the deliberate inverse of the removed `stop_talking` acknowledgement
  (`speech.render_stop_acknowledged`, deleted 2026-09-20): that one was a real paradox -- the ack
  had to go out over the very channel it was interrupting. `silence`'s ack has no such paradox,
  since the mute is not yet in effect when it is spoken.

- **Acknowledgement word: `"Quiet."`** (`belief.speech.render_silence_ack`) -- one word, echoing
  the pilot's own phrasing from the use case ("I can tell him to be quiet"), in the same
  radio-brevity register as `render_cancel_readback`'s `"Copy, stopping."` and
  `render_say_again`'s `"Say again?"`.

- **`silence` does not call `speech_client.stop()`.** It answers a different question from
  `stop_talking` ("say nothing from here on" vs. "stop talking right now") and the two are
  independent: silencing does not imply something is currently playing that needs interrupting,
  and ending silence does not resume anything it never stopped. A pilot who wants both commands
  says both. Covered by `test_silence_does_not_call_speech_client_stop`.

- **Confidence floor: added `"silence"` to `voice_commands.CANCEL_TOKENS`** (the elevated
  `ACT_FLOOR_CANCEL` floor), per the task's own hint -- a misfire here is arguably worse than a
  misfired `cancel_task`, since it means Petrovich going quiet near something the player never
  asked to stop hearing about. The set's name is now slightly narrower than its membership (not
  every token in it literally cancels a task); documented in place rather than renamed, since
  renaming it would touch every existing reference for a cosmetic gain.

### Explicitly out of scope (flagged, not built)

- **`brain_reply.OFFERED_CONFIRM_VOCABULARY` was not extended.** This is brain-layer's own
  classify-prompt token mirror (cross-subproject, with its own synced test in
  `brain-layer/tests/test_prompts.py`) and the task scoped this work to body-layer. Consequence:
  if the brain ever emits `CONFIRM silence`, `validate_brain_reply` degrades it to `ASK` (the
  documented fail-safe direction for that constant, never a misdispatch) rather than confirming
  the word. Harmless today since nothing upstream emits it, but worth remembering when `silence`
  gets a brain-side vocabulary entry.
- **No DCS F10 radio-menu button.** That enumeration lives in aircraft-layer's Hook script, a
  separate subproject. Body-layer's `handle_command` already dispatches the `"silence"` token
  generically, so no further body-layer change is needed once either the F10 menu or
  `audio-adapter`'s phrase vocabulary actually produces that token. Reachable today only via the
  `!voice silence <ratio> <confidence> 1 0` typed test harness.
- **No real phrase added to `audio-adapter/src/vocabulary.py`.** Same cross-subproject boundary;
  flagged for the same reason as the F10 item above.

### Files Changed

- `src/belief/voice_commands.py` -- added `"silence"` to `CANCEL_TOKENS` (elevated confidence
  floor), with a docstring note on why the set's name undersells its new membership.
- `src/belief/speech.py` -- added `render_silence_ack()`, returning `"Quiet."`.
- `src/belief/crew_console.py`:
  - New `silenced: bool` field on `CrewConsole` (default `False`), gating `_print`'s
    `speech_client` push only.
  - New `_handle_silence(now_sim)` method.
  - New `NO_RETURN_VALUE_COMMAND_TOKENS` constant (`{"stop_talking", "silence"}`), factored out so
    `handle_command` and the regression test share one definition of "this token deliberately
    returns `[]`" instead of two independently-maintained lists.
  - `"silence"` added to `DISPATCHED_COMMAND_TOKENS`.
  - `handle_command`: checks `token == "silence"` before the general `self.silenced = False` reset
    (so `_handle_silence` can see prior state); every other token clears `self.silenced`.
  - `_handle_utterance`: clears `self.silenced` in the `"handled"` branch (a recognised free-text
    command also ends silence).
  - `_print`: `speech_client` push now gated on `not self.silenced`; docstring updated to explain
    what is and is not gated and why.
  - Module docstring and `HELP_TEXT` considered for a `silence` entry; `HELP_TEXT` was **not**
    changed -- it documents the typed console's natural-language grammar
    (`belief.utterance.parse_utterance`), which has no `silence` intent and never will (`silence`
    is a token-level command, reachable only via F10/voice/confirm, the same category as
    `stop_talking`/the scan/report/cancel family, none of which `HELP_TEXT` lists either).
- `docs/STRUCTURE.md` -- a paragraph on `silence` alongside the existing `stop_talking` entry in
  `crew_console.py`'s module-map section.
- `tests/test_crew_console.py` -- ten new tests (see below) plus one existing-test update:
  `test_dispatched_command_tokens_all_return_something` now checks membership in
  `NO_RETURN_VALUE_COMMAND_TOKENS` instead of a literal `token == "stop_talking"` comparison, since
  `silence` joined that same no-return-value category. This is a direct, mechanical consequence of
  the token-set change, not a behavioural rewrite.
- `plans/silence-command/implementation.md` -- this file.

### Tests Added

- `test_silence_speaks_one_word_acknowledgement_then_goes_quiet` -- the ack is pushed to
  `speech_client`, `handle_command` itself returns `[]`, `console.silenced` is `True` afterward.
- `test_silence_pushes_nothing_to_the_overlay_differently_than_speech` -- the overlay still gets
  the ack (silence gates audio only, not even for its own acknowledgement).
- `test_silence_does_not_call_speech_client_stop` -- distinguishes `silence` from `stop_talking`.
- `test_silence_suppresses_a_drained_callout_that_would_otherwise_be_spoken` -- a lifecycle event
  is still chosen/rendered by the scheduler (`len(spoken) == 1`) but never pushed to
  `speech_client`; the overlay still gets it (text/overlay keep working).
- `test_silence_suppresses_an_injected_urgent_call_too` -- the user's explicit absolute-silence
  choice, pinned directly: an `!inject-urgent` call still produces its line but reaches
  `speech_client` zero times while silenced.
- `test_silence_twice_is_a_no_op_not_a_toggle` -- two `silence` commands in a row: both return
  `[]`, `console.silenced` stays `True`, and the ack is in `speech_client.pushed` exactly once.
- `test_a_subsequent_command_ends_silence_and_is_itself_heard` -- `watch_nearest` after `silence`
  clears `self.silenced` and its own readback is heard.
- `test_silence_ends_and_the_next_drained_callout_is_heard` -- after silence ends via a command, a
  later lifecycle event is both chosen and actually pushed to `speech_client`.
- `test_unrecognised_free_text_does_not_end_silence` -- an escalated (unmatched) utterance leaves
  `console.silenced` at `True`.
- `test_recognised_free_text_command_ends_silence` -- a typed `watch <id>` the grammar resolves
  clears `console.silenced`, same as a token-level command.

### Checks (body-layer/)

- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (`--strict`): pass, 53 source files
- `pytest tests -q`: pass, 1398 passed, 4 xfailed (baseline on `main` was 1388 passed, 4 xfailed --
  the +10 is exactly the new tests; nothing regressed)

### Notable Discoveries

- **`CalloutScheduler.note_reply`'s `busy_until_sim` budget (`MIN_UTTERANCE_S` + word count /
  `SPEECH_RATE_WPS` + `INTER_UTTERANCE_GAP_S`) is deliberately unconditional in `_print`, even
  though the silence gate only skips the actual `speech_client.push_speech` call.** First draft of
  the "suppressed callout" tests placed the ingest/tick/drain only ~1 second after the `silence`
  ack and got `len(spoken) == 0` -- not a suppression bug, but the scheduler correctly treating the
  ack's own one-word utterance as still occupying the channel (`0.6 + 1/2.5 + 0.75 = 1.75s` budget)
  exactly as if it had been spoken aloud. This is in fact the mechanism that makes "suppressed, not
  deferred" true -- the pacing is identical whether or not the line was actually voiced -- but it
  means any test driving `drain_events` shortly after a `silence`-adjacent `_print` call needs to
  clear that budget first (used `t_sim`/`now_sim` offsets of 10s in the final tests, well past any
  plausible accumulated budget, rather than computing the exact figure and coupling the test to
  it).

---

## audio-adapter half (this file's second entry)

Wires the spoken phrase for `silence` into `audio-adapter`, so the token the body-layer half
already dispatches is actually reachable by voice, not only through the typed `!voice` harness.
No body-layer change -- `handle_command` dispatches the token generically.

### Design points settled

- **Token placement**: `silence` added to `vocabulary.VOICE_ONLY_TOKENS`, alongside
  `stop_talking`/`say_again` -- no F10 button today, same category as those two.
- **Phrase set: `("silence", "be quiet", "shut up")` -- three, not the four candidates the task
  raised.** Bare `"quiet"` was weighed and measured, then dropped. As a one-word phrase it would
  have become its own verb-anchor word (`command_matcher.VERB_ANCHOR_WORDS` is derived from each
  phrase's first word), and `"quiet"` sits a 0.889 `difflib.SequenceMatcher` ratio from the
  ordinary English word `"quite"` -- comfortably above `VERB_FLOOR` (0.5). That turned
  `match_transcript("quite a nice day for flying today")` from a clean anchor rejection into a
  false `verb_anchored=True`, breaking the existing pinned
  `test_verb_anchor_rejects_non_command_speech` regression test. This was found by actually
  running the matcher with the candidate wired in, not by eyeballing the word -- the task's own
  warning that "each phrase is a chance to misfire" held literally here. `"quiet"` survives inside
  `"be quiet"` without the risk, since only a phrase's *first* word becomes an anchor word.
- **Collision measurement method**: before choosing, every candidate was run through the real
  `command_matcher.match_transcript` (with the candidate phrases temporarily wired into
  `vocabulary.PHRASES`/`VOICE_ONLY_TOKENS` via a throwaway script, not guessed) against: the exact
  phrasings themselves (all resolve, `match_ratio=1.0`, unambiguous); the existing cancel/
  stop_talking/watch/scan families (`"cancel"`, `"cancel task"`, `"cancel scan"`, `"cancel
  watch"`, `"stop"`, `"watch nearest"`, `"scan left"`, `"follow nearest"` -- all unaffected, none
  resolve to `silence`); and adversarial sentences that merely contain one of the candidate words
  (`"be careful"`, `"shut the door"`, `"silence is golden"`, `"quiet down there"`, `"report
  quietly"`, `"stay quiet"` -- all come back `token=None`, verb-anchored at most, never a false
  `silence`). The one real finding from that sweep is the `"quiet"`/`"quite"` collision above --
  everything else came back clean on the first pass.
- **`VERB_ANCHOR_WORDS` and `normalized_phrase_index()` needed no separate wiring** -- both are
  derived from `vocabulary.PHRASES` at import time (`command_matcher.py`'s own design, predating
  this change), so adding the token to `PHRASES` was the only vocabulary-side step. No change to
  `command_matcher.py` itself.
- **Marked unbenched** in `vocabulary.py`'s own comment, following that file's established
  convention for every token added since the corpus was last recorded (`cancel_scan`/
  `cancel_watch`'s comment is the precedent cited). Flagged as worth weighing more carefully than
  most, since this is a command reached for when busy and not wanting to repeat it.

### Files Changed

- `audio-adapter/src/vocabulary.py` -- added `"silence"` to `VOICE_ONLY_TOKENS` and
  `PHRASES["silence"] = ("silence", "be quiet", "shut up")`, with a comment recording the
  `"quiet"`/`"quite"` collision finding and why it was dropped.
- `audio-adapter/tests/test_command_matcher.py` -- new `TestSilence` class (five tests: all three
  phrasings resolve unambiguously at `match_ratio=1.0`; `"stop"` still resolves to `stop_talking`,
  not stolen; the cancel family is untouched; adversarial sentences containing a candidate word do
  not falsely resolve to `silence`; the three phrasings are separable from everything else).
- `audio-adapter/tests/test_vocabulary.py` -- `test_silence_is_distinct_from_stop_talking`,
  matching the existing `test_stop_and_nevermind_are_distinct_tokens` pattern.
- `plans/silence-command/implementation.md` -- this entry.

### Checks (audio-adapter/)

- No `.venv` existed in this worktree; built one from `pyproject.toml` (stdlib-only, no
  dependencies declared) with `ruff`/`mypy`/`pytest` installed into it.
- Baseline (before this change, branch tip `493ba6a`): `pytest tests -q` -> 213 passed, 1 skipped.
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (`--strict`): pass, 15 source files
- `pytest tests -q`: pass, 219 passed, 1 skipped -- the +6 is exactly the new tests (5 methods in
  `TestSilence` plus 1 in `test_vocabulary.py`); nothing regressed, and the `"quiet"`/`"quite"`
  regression found above was fixed before this count, not papered over.

### Notable Discoveries

- **A single-word phrase addition is not safe by default, even against ordinary English rather
  than another vocabulary token.** `command_matcher.VERB_ANCHOR_WORDS`'s fuzzy floor (`VERB_FLOOR
  = 0.5`) is deliberately loose (false anchors are cheap; false rejections are not, per that
  module's own docstring), which means a short, common-looking candidate word can anchor against
  an unrelated English word nobody meant to route anywhere. The fix pattern worth remembering:
  check `difflib.SequenceMatcher(None, candidate, nearby_word).ratio()` against plausible
  near-neighbours before committing a bare one-word phrase, not just against the existing
  vocabulary table -- the existing table was clean on the first pass, and the real risk was
  outside it.
