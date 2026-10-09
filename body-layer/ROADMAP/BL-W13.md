# BL-W13 — `silence` command

- [x] **`silence` command — ACCEPTED 2026-10-09.** User, reviewing the status page:
  *"silence command / one word, absolute quiet -> accepted"*. Two of the three questions this
  entry listed are therefore answered by acceptance rather than by measurement — one word of
  acknowledgement is the right amount, and absolute silence is wanted. The third is **not**
  closed by it and is worth keeping in view: whether absolute silence is still wanted once a
  threat appears while muted. That case may simply not have occurred yet.

  Original entry, kept for the record:

  - [ ] **`silence` command — DoD PASSED on fixtures/console only, 2026-10-04, unflown.**
  `feature/silence-command`, tip `de6c530`. Deferred, not waived — the plan never scoped live
  acceptance out, and whether it works for the pilot is exactly the kind of thing fixtures
  cannot settle (unbenched recogniser accuracy on the three phrasings, whether one word of
  acknowledgement is the right amount, whether absolute silence is still wanted once a threat
  actually appears while muted). Card: `docs/acceptance/2026-10-04-silence-command.md` (and its
  artifact). What the flight has to settle and static review cannot: which of `"silence"`/
  `"be quiet"`/`"shut up"` the recogniser actually hears; whether `"Quiet."` then nothing at all
  — including danger calls — feels right in practice; whether any command correctly ends it
  (including the `"stop"` quirk noted in review: `stop_talking` also ends silence, since it is a
  command too). Clear this entry only once a real sortie exercises it, and say which one — it may
  share a sortie with the group-cohesion and confirm-band entries above, since all three are
  cleared by ordinary flying with commands and contacts present.


**Status-section record, kept for the record (written before the acceptance above):**

- [x] **`silence` command — DoD PASSED on fixtures/console, live acceptance outstanding (added
  to the live-acceptance debt list above).** `feature/silence-command`, tip `de6c530`. No
  architect/plan.md — the user's own message settled the two load-bearing decisions directly
  ("make Petrovich not talk until my next command"; chose absolute silence including urgent
  threat callouts, and one spoken acknowledgement, `"Quiet."`, before the mute). A single
  `self.silenced: bool` gates the one existing `speech_client.push_speech` choke point in
  `CrewConsole._print`, applying identically to routine and urgent (`bypass_gate=True`) lines;
  text/overlay surfaces and the scheduler's own occupancy bookkeeping are untouched, so nothing
  is deferred and dumped when silence ends. Cleared only by an actually-dispatched command
  (token-level or a resolved free-text intent), never by stray unresolved speech — the
  radio-traffic use case the command exists for. `silence` also added to
  `voice_commands.CANCEL_TOKENS` for its elevated confidence floor. Reviewer: full read, no
  required fixes. Security: deep analysis, APPROVED (ack-before-mute and no-stuck-on both hold
  by construction; no new dependency, no new ingress path). No performance pass — one `bool`
  check at a call site that already does synchronous HTTP to the TTS engine, not a hot path by
  any measure; recorded here rather than treated as a skipped gate. Checks: body-layer 1398
  passed/4 xfailed, audio-adapter 219 passed/1 skipped, `ruff`/`mypy --strict` clean in both.
  **Audio-adapter half**: `silence`/`"be quiet"`/`"shut up"` wired into
  `vocabulary.VOICE_ONLY_TOKENS`/`PHRASES`. Bare `"quiet"` was dropped from the candidate set —
  measured, not guessed — at a 0.889 `difflib` ratio from the ordinary word `"quite"`, enough to
  false-anchor `"quite a nice day for flying today"` as a command (see NOTES.md). **Not wired:
  no DCS F10 radio-menu button** — that enumeration lives in aircraft-layer's Hook script;
  `handle_command` already dispatches the token generically, so only a Hook-side menu entry
  (or audio-adapter's vocabulary, now done) is needed to reach it. Voice is the only route today.
  **Milestone completion question**: does not change what's next or invalidate a downstream
  assumption — a self-contained dispatcher addition on an existing choke point. DoD report:
  `plans/silence-command/dod-check.md`.

