### Review Summary

Reviewed `fix/confirm-band-affirmatives` (tip `c33739e`, one commit on `main` @ `8e9282b`) — HEAD
matched the expected tip exactly, reviewed directly in the checkout, no worktree/archive needed.

Touches `body-layer/src/belief/voice_commands.py` (word sets, `CONFIRM_WINDOW_S`, new
`CONFIRM_LATE_ANSWER_GRACE_S`), `body-layer/src/belief/crew_console.py` (new
`_confirmation_expired_sim` field and its two check sites in `handle_transcript`), tests, and
`todo/todo.md`. All commands pass: `ruff format --check` clean, `ruff check` clean, `mypy --strict`
clean (52 files), `pytest` 1307 passed / 4 xfailed.

The lifecycle of `_confirmation_expired_sim` was traced by hand and confirmed correct for the paths
the plan targeted: it is set only on expiry, cleared unconditionally whenever a pending
confirmation is answered in time (whichever of the three places creates that pending confirmation —
the voice band, `_handle_brain_confirm`, or `_handle_brain_ask`), and cleared when a fresh question
is asked. The two brain-reply paths don't explicitly clear it themselves, but this is harmless: any
new `_pending_confirmation` is caught by `handle_transcript`'s top block on the next call, which
clears both fields together before the late-answer branch is ever reached — so there's no window
where a genuine answer to a *new* question gets intercepted by a stale expiry from an *old* one.

One required fix, confirmed by direct reproduction, not by reading alone.

### Required Fixes

- **The late-answer grace branch can swallow an unrelated, fresh utterance, not just a late
  answer — reproduced, not merely suspected.** `classify_yes_no` matches on the transcript's
  *first word only* (`voice_commands.py:216-220`), and the widened `_AFFIRM_WORDS` now includes
  ordinary sentence-openers people actually use on the radio: `ok`, `okay`, `correct`, `yeah`,
  `yep` (plus `confirm`/`confirmed`, which is also plausible as an opener). The new
  `CONFIRM_LATE_ANSWER_GRACE_S` window (20 s) means that for up to 20 seconds after *any* confirm
  question expires — answered or not — the next utterance is checked against this set before it
  ever reaches command classification.

  Reproduced directly: after a confirm question is asked and left to expire, a transcript 5 s
  later reading `"okay watch that truck at three o'clock"` — an ordinary tactical report that has
  nothing to do with the expired question — returns `["Say again?"]` and drops the report
  entirely, rather than reaching `_handle_utterance`/escalation as it would have before this
  change (and as it still does outside the grace window).

  This is exactly the class of regression the fix was trying to avoid introducing elsewhere: it
  trades a bug that fired on *every* cancel for a narrower one that fires whenever a pilot happens
  to open a fresh sentence with a common word within 20 s of a lapsed confirm — which, for exactly
  the kind of clipped tactical speech this project models, is not a rare phrasing.

  It also invalidates a safety claim stated twice in this same commit. `voice_commands.py`'s
  `_AFFIRM_WORDS` docstring says the set "is consulted only inside an open confirm window, so
  widening it cannot collide with any command" — true for literal command-token collisions (there
  is no command token spelled `ok`/`yeah`/etc., confirmed by grep against
  `audio-adapter/src/vocabulary.py`), but the grace window this same commit adds in
  `crew_console.py` now also consults this set for up to 20 s with **no confirm window open at
  all**, which is the exact condition the docstring says doesn't happen. `todo/todo.md`'s entry
  makes the identical claim and needs the same correction.

  Fix suggestion: gate the late-answer branch on more than "first word is in the set" — e.g.
  require the transcript to be short (a real late answer to a yes/no question is one or two
  words; `"okay watch that truck at three o'clock"` is not), or require the *whole* normalised
  transcript to be a member of the word sets rather than just its first token, in that branch
  specifically. Add a test for the swallow case (a multi-word utterance opening with an affirm/
  negative word, arriving within the grace window) alongside the existing expiry/grace tests.

### Optional Refinements

- `_confirmation_expired_sim` is never reset to `None` once its grace window has fully elapsed
  without a yes/no answer or a fresh question — it just sits at a stale timestamp forever, since
  every later `since_expiry` computation is `> CONFIRM_LATE_ANSWER_GRACE_S` and the branch never
  fires. Functionally inert (the guard makes it dead weight, not a bug), but worth a one-line
  reset for hygiene/debuggability — a `repr=False` field holding a meaningless multi-flight-old
  timestamp is a minor trap for anyone reading state via a debugger later. (Optional.)
- The `CONFIRM_WINDOW_S`/`CONFIRM_LATE_ANSWER_GRACE_S` reasoning is honestly caveated ("still not
  measured end to end") and the cited numbers check out against real sources: Whisper `small.en`
  p90 1.46 s / max 1.68 s matches `audio-adapter/research/2026-09-19-whisper-model-sweep.md:10`,
  and the TTS "<1s is not laggy" framing matches `audio-adapter/ROADMAP.md:73`. No fix needed here
  — flagging only that this held up under verification, unlike some past latency claims in this
  project.
- The test-file change (`test_handle_transcript_confirm_expires_after_window` changed rather than
  extended) was the right call: the scenario's assertion legitimately changed (expiry now falls
  inside the new grace window, so "Say again?" is the correct new behavior for that exact input),
  and the commit added a *new* test
  (`test_handle_transcript_late_answer_beyond_the_grace_falls_through`) that covers what the old
  test used to guard — silence/no-command-fired once genuinely past the grace. Nothing lost.

### Verdict

NEEDS REVISION — one required fix (the free-speech-swallow window), everything else sound.

### Review Confidence

Full read of both changed source files and the relevant test diffs; lifecycle of the new state
field traced by hand across all three code paths that touch `_pending_confirmation`
(voice band, `_handle_brain_confirm`, `_handle_brain_ask`); the required-fix finding was verified
by direct reproduction (a standalone script exercising `CrewConsole.handle_transcript`), not
inferred from reading; the two cited external latency numbers were checked against their source
research docs rather than trusted from the docstring's citation alone.
