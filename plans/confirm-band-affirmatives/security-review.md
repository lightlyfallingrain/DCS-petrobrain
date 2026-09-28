## Security Deep Analysis: confirm-band-affirmatives

Branch `fix/confirm-band-affirmatives` @ `867cbfe`, against `main` @ `8e9282b`.
Verified: worktree/checkout HEAD matched the expected tip sha before any review began.

### Dependency Status

No dependency change. `git diff main...HEAD --stat` touches only
`body-layer/src/belief/{crew_console,voice_commands}.py` and their tests plus one
cross-subproject documentation test in `audio-adapter/tests/test_command_matcher.py`. No
`pyproject.toml`/`requirements` file changed.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `voice_commands.py` `_AFFIRM_WORDS`/`_NEGATIVE_WORDS` (widened to 11+5 words) + `CONFIRM_WINDOW_S` 8.0→15.0 + new `CONFIRM_LATE_ANSWER_GRACE_S` 20.0 | Widened vocabulary and longer exposure window on the path that commits/discards a pending command, including the raised-floor destructive tokens (`cancel_task`/`cancel_scan`/`cancel_watch`) | **Reachable, not exploitable** — see risk note below. Input is the pilot's own PTT-gated speech (single-player, single-user, LAN-only); there is no channel for a third party to inject a transcript. The wider vocabulary only matters *inside* an open confirm window the pilot's own prior utterance opened, and the window is bounded (15s + 20s grace, both finite and code-owned, not attacker-controlled). This is a behavioural/UX risk (an incidental "okay" during that window could commit or discard a pending destructive confirm), not a security vulnerability — present to user, see below | None required to pass this gate; user decision offered below |
| `classify_yes_no` normalisation: `char.isalnum() or char == " "` over the raw transcript, unbounded length | Untrusted-input handling (Whisper transcript) | **False positive as a security issue.** `str.isalnum()` accepts non-ASCII alnum (accented letters, other scripts) as well as ASCII, so the filtering is more permissive than the docstring's "minimal local normalisation" implies — but the only consumers of the filtered string are membership tests against small ASCII frozensets (`_AFFIRM_WORDS`, `_NEGATIVE_WORDS`, `_ANSWER_FILLER_WORDS`) and a plain `.split()`/`len()`. A transcript of any length or script degrades gracefully to `"other"`; no crash, no quadratic blowup, no injection (the classified result is a 3-way literal, never echoed). Rule 1 (`any(... for word in words)`) is the only unbounded-length check; it is O(n) in transcript length either way, and transcript length here is bounded by realistic PTT speech, not adversarial input | None |
| `crew_console.py` new field `_confirmation_expired_sim: float | None` | New per-console state, potential leak/unbounded growth | **Not exploitable.** It is a single scalar field, not a collection — cannot grow. It is set on window expiry, cleared on a fresh confirm request, on a successful in-window answer, and on a late answer consumed inside the grace window. If a late answer never arrives, the stale value simply stops mattering once `since_expiry > CONFIRM_LATE_ANSWER_GRACE_S` (the `<=` bound in the `if` guards this) — dead state, not a growing one. A backward jump in `now_sim` is guarded by the explicit `0.0 <=` lower bound, so a sim-clock discontinuity can only suppress the late-answer branch, never wrongly fire it | None |
| `crew_console.py:1799` `except Exception:  # noqa: BLE001` (`_log_transcript`) | Error suppression | **Pre-existing, not touched by this diff** (confirmed against `git diff main...HEAD` — this line is outside the changed hunks). Not this feature's finding | None (note only) |
| `classify_yes_no(transcript, matched_command)` — rule ordering (bare-answer-word check before `matched_command`, then `matched_command` before the length-capped first-word fallback) | Logic correctness on the confirm/command boundary | Reviewed against the stated failure modes ("disregard" resolving to `cancel_nevermind` at ratio 1.00, "roger wilco"/"negative hold off" anchoring a verb from word 1 alone). The three-rule order matches the documented reasoning and is covered by tests added in this diff (`test_handle_transcript_grace_window_does_not_swallow_a_real_utterance`, `test_handle_transcript_confirm_commits_on_the_questions_own_word`, `test_handle_transcript_late_answer_beyond_the_grace_falls_through`) plus the cross-subproject coupling test in `audio-adapter`. No bypass found: a real command token (`matched_command=True`) can never be silently swallowed as a late answer, and a late answer can never commit a command (pending state is discarded before the late-answer branch runs) | None |

### Risk Communication

**Finding:** Widening the confirm-band affirm/negative vocabulary (4→11 affirm words, 3→5 negative
words) and extending the answerable window (8s→15s, plus a new 20s late-answer grace) increases the
window and the vocabulary during which an utterance unrelated to answering the pending question
could be read as committing or discarding it — including the three destructive tokens
(`cancel_task`/`cancel_scan`/`cancel_watch`) that route through this same confirm band precisely
because they destroy standing state.
**Location:** `body-layer/src/belief/voice_commands.py` (`_AFFIRM_WORDS`, `_NEGATIVE_WORDS`,
`CONFIRM_WINDOW_S`, `CONFIRM_LATE_ANSWER_GRACE_S`).
**Probability:** low — input is PTT-gated (the pilot must deliberately key up to speak at all,
per the project's compute/voice model), single-player with no other party who could speak into this
channel, and every word in the widened sets is a plausible direct answer to the question's own
phrasing ("<X>, confirm?" — "confirm"/"correct"/"okay" are natural echoes, not incidental noise).
**Impact:** medium — if it does happen, the effect is exactly "cancel everything" firing (or a
wanted cancel being discarded) on a word the pilot did not intend as an answer; recoverable
(tasks can be re-issued) but momentarily wrong.
**Recommended action:** accept as-is. This is the tradeoff the fix exists to make — the previous
narrow window was reviewer- and sortie-demonstrated to make the band *unanswerable* in real flying
conditions, which is a worse failure (a destructive confirm the pilot can never actually answer is
not safer, just silently broken). The four review rounds already exercised the specific failure
modes (verb-anchor collisions, sentence-swallowing, escalation mis-wording) that would make this
worse than intended, and none remain open per the `review.md` history and the tests added here.

Options:
  (A) Ignore — document acceptance of this risk (recommended; it is the designed tradeoff)
  (B) Add to todo.md — revisit window/vocabulary sizing once BL-10/SRS free speech changes who can be
      speaking into this channel
  (C) Fix now — narrow the window or vocabulary before merge
  (D) Stop — do not proceed until resolved

### Verdict

APPROVED
