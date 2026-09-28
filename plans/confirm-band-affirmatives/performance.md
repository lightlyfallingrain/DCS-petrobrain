### Performance Review

Branch `fix/confirm-band-affirmatives` @ `867cbfe` (verified: `git rev-parse HEAD` matched the
expected tip; main checkout was already on this branch, no worktree/archive needed).

### Findings

#### `classify_yes_no` rule rewrite (`body-layer/src/belief/voice_commands.py`)
- **Location:** `classify_yes_no`, called from `CrewConsole.handle_transcript`
  (`body-layer/src/belief/crew_console.py`).
- **Risk:** none credible. `handle_transcript` is invoked once per drained item in
  `_poll_transcripts` (`body-layer/src/logger.py:1213`), which itself only iterates
  `audio_client.get_transcripts()` — a handful of recognised-speech events per sortie, not a
  per-poll (5 Hz) call. An empty poll adds zero work: the `for item in transcripts` loop body
  never runs. The rewritten function is three ordered rules over an already-short word list
  (transcripts are a few words; `_MAX_ANSWER_WORDS` only *caps* length, nothing iterates past it)
  plus two `any()` passes and a list comprehension over the same short list — all O(words in one
  utterance), not O(anything that grows with sortie length or contact count.
- **Action:** MONITOR (no mitigation needed; recorded so a future change to the caller —
  e.g. widening the branch to something list-based — gets checked against this baseline).

#### Widened `_AFFIRM_WORDS`/`_NEGATIVE_WORDS`/`_ANSWER_FILLER_WORDS`
- **Location:** module-level `frozenset`s in `voice_commands.py`.
- **Risk:** none. These are fixed-size, module-level constants (12 / 5 / 4 words respectively),
  built once at import, not per call. Widening them by a handful of words does not change the
  cost shape of `classify_yes_no` (membership test in a `frozenset` is O(1) regardless of set
  size).
- **Action:** MONITOR.

#### New `_confirmation_expired_sim: float | None` field + `CONFIRM_LATE_ANSWER_GRACE_S` branch
- **Location:** `CrewConsole` dataclass field and the new late-answer branch in
  `handle_transcript` (`crew_console.py`).
- **Risk:** none. This is a single scalar field on an already-existing per-console object, not a
  collection — it cannot grow or leak across a long sortie; it is overwritten (or cleared back to
  `None`) on every question expiry, every fresh confirm question, and every late-answer match.
  The new branch only executes work (one more `classify_yes_no` call and a comparison) when
  `_pending_confirmation is None and _confirmation_expired_sim is not None` — i.e. only in the
  narrow post-expiry grace window after a confirm question was actually asked, never on the
  common path where no confirm-band question is in flight. No allocation, no I/O, nothing
  blocking.
- **Action:** MONITOR.

#### Widened `CONFIRM_WINDOW_S` (8.0 -> 15.0) and new `CONFIRM_LATE_ANSWER_GRACE_S` (20.0)
- **Risk:** none from a cost perspective. Both only change how long a single scalar timestamp
  comparison stays "true" — they do not change what is stored (still one `float | None` field)
  or how often anything is computed. Longer windows mean the pending/expired state is held
  slightly longer in wall-clock terms, which has no bearing on per-poll or per-call cost.
- **Action:** MONITOR.

### Verdict
APPROVED

This entire change lives on the transcript-dispatch path (a handful of recognised-speech events
per sortie), not the 5 Hz poll loop — `_poll_transcripts` only calls into it per drained
transcript item, and an empty poll costs nothing extra. Every new piece of state is a fixed-size
constant or a single scalar field, none of it grows, retained, or allocates per call in a way
that accumulates over a sortie. No mitigation warranted.
