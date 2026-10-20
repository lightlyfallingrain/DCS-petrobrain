### Review Summary

Reviewed `feature/voice-latency-instrumentation` at tip `97e780608fbe60293f22d9bb328d0239ef78c32f`
(one commit, 33 files: audio-adapter, aircraft-layer, body-layer) against
`plans/voice-latency-instrumentation/{plan,implementation,security-plan-review}.md` and
`docs/acceptance/2026-10-20-sortie-feedback.md` (F1, F8, "F8 — explored", "F8 — plan decisions").

**The core deliverable works.** I built a synthetic round trip through the real code paths
(`CaptureLoop` → `TranscribeClient` → a real `TTSAdapterServer` (fake STT/TTS/sink, same posture
as the existing test suite) → `GET /transcripts/poll` → body-layer's `CrewConsole.handle_transcript`
→ `_print` → `AudioAdapterClient.push_speech` → the same real server's `/speak`) and fed the four
resulting logs into `tools/join_voice_latency.py`. Output:

```
=== c8b9c56061da ===
  capture    outcome='sent' clip_duration_s=1.2 post_duration_s=0.0265 t_ptt_release_wall=...
  transcribe outcome='ok' transcribe_duration_s=0.0101 match_duration_s=0.0019
  transcript heard='radio check' disposition='act' acted_token='radio_check' now_sim=0.0
  spoken     text='Loud and clear.' push_duration_s=0.0215 t_sim=0.0
  speak      outcome='ok' synth_duration_s=0.0102 deliver_duration_s=0.0101
```

Complete, correctly pipeline-ordered, every duration attributed to the right stage, no
cross-machine `t_wall` subtraction anywhere. I also confirmed the "never reached" flagging and the
unattributed-row count by dropping stages and adding an id-less row — both work as documented.

**One real defect, confirmed by running it, not by reading it**: `mark_target`'s deferred *write*
(not just its readback) is silently discarded if `CrewConsole.refused` becomes `True`, or a mission
restart happens, before the channel clears. See Required Fix 1 — this is squarely the question I
was asked to resolve ("could a mark the pilot asked for be lost"), and the answer is yes, demonstrated.

Everything else checked out: the `watch_nearest*` scope extension is justified (shares
`_handle_follow`'s exact renderers), the security plan review's `correlation_id` validation/cap is
present and tested on both audio-adapter and aircraft-layer, all three subprojects' format/lint/
type/test commands pass, no debug code or stray TODOs, all new files committed, invariant-check
clean.

### Required Fixes

- **A pilot-commanded `mark_target` write can be silently lost, not just its spoken
  acknowledgment.** `_handle_mark_target` (crew_console.py ~2476) defers the *call* to
  `mark_target_fn(contact_id, render_now_sim)` itself via `_speak_or_defer` when the channel is
  modeled busy — correct per Decision 2 ("current information, not old"), since the mark's position
  is read at the moment it is actually written. But `drain_pending_positional_replies` (crew_console.py
  ~1500) treats every pending entry identically regardless of whether its `render` closure is a pure
  readback or has a durable side effect: `if self.refused: self._pending_positional_replies = []`
  drops the entry outright, and `reset_for_new_mission` (via `__init__`'s default, `_pending_
  positional_replies` is not in the "survives" list) drops it on a mission (re)start too. For
  `select_target`/`follow`/`watch_nearest`/`step`/`report`, dropping a pending entry only loses a
  spoken echo of an action that already happened unconditionally — exactly the stated, correct
  reasoning in that method's own docstring. For `mark_target`, the pending entry **is** the action:
  dropping it means the mission-memory write the pilot asked for never happens, with no error, no
  log line, nothing in `--mission-memory` or any other sink — the pilot has no way to know it failed.

  **Confirmed by running it** (not inferred): I selected a target, set the channel busy, issued
  `mark_target` (deferred, not yet written — confirmed), then set `console.refused = True` and
  drained. The pending entry's `render` closure was never called; `mark_target_fn` was never
  invoked. No test in this diff exercises `mark_target`'s Stage 6 path at all — not the ordinary
  defer-then-drain case, and not this one. (`grep -n "mark_target" body-layer/tests/
  test_crew_console.py` before this review returns nothing.)

  This is a genuine correctness regression introduced by this diff (pre-Stage-6, `_handle_mark_target`
  always wrote synchronously at command time) and sits squarely against this project's "code owns
  truth" posture and mission memory's own "worth-remembering ledger" framing
  (`body-layer/CLAUDE.md`'s module map).

  **Recommended fix** (pick one, or propose another — this is a design call, not purely mechanical):
  1. Distinguish write-bearing pending entries from pure-readback ones in `drain_pending_positional_
     replies`'s refusal/reset handling — execute the write (guarding against `enrichment`/`theatre`
     being invalid, the same defensive re-check `_handle_report`'s closure already does) even while
     refused or across a mission boundary, and only suppress the *spoken* acknowledgment; or
  2. At minimum, log a `WARNING` naming the contact id and correlation id when a pending mark write
     is dropped, so a debrief/triage pass can see it happened, rather than it vanishing with zero
     trace anywhere.
  Either way, add the missing test coverage: the ordinary `mark_target` defer-then-drain path (it
  has none today), and the refusal/mission-restart drop case once the behavior is decided.

### Optional Refinements

- `aircraft-layer/tests/test_collector_server_accept_errors.py`'s two tests fail in this sandbox
  too, as the implementer reported — but the exact symptom I reproduced (`assert not
  thread.is_alive()`, a close()/join(5s) race, 3/3 runs) differs from what implementation.md
  describes (an `OSError: [Errno 98] Address already in use` from a fixed-port bind). Both are
  consistent with "environmental, unrelated to this diff" — `git diff HEAD^ HEAD` against both that
  test file and `collector/server.py` is empty, and a bare bind-test script here actually succeeded
  (unlike the implementer's own repro). Worth a one-line correction in DoD's notes that the specific
  failure mode is sandbox-dependent, not the fixed one described — not blocking, since the
  "unrelated to this feature" conclusion holds either way and both runs exclude it via `--deselect`.
- `body-layer/src/belief/audio_client.py`'s `get_transcripts()` docstring still lists the old
  seven-field `TranscriptEvent` shape (`{"transcript", "confidence", "token", "match_ratio",
  "verb_anchored", "ambiguous", "t_wall"}`), missing `slots` (pre-dates this plan) and the new
  `correlation_id`. Functionally harmless — the client returns raw dicts unmodified, so the real
  field actually passes through fine — but a stale comment on code this diff didn't touch directly
  (only `push_speech` was edited in this file). Worth a one-line fix while someone is next in this
  file.

### Verdict

NEEDS REVISION — one required fix (the `mark_target` silent-write-loss case above). Everything
else in the plan is implemented as scoped, the instrumentation itself does what it's supposed to
(verified by exercising it, not just reading it), and all three subprojects' checks are green.

### Review Confidence

Full read of `crew_console.py`'s Stage 6 changes, `server.py`/`capture_loop.py`/`audio_sender.py`'s
instrumentation, and `join_voice_latency.py`; exercised the end-to-end round trip and the
`mark_target` defect directly rather than inferring from the diff; ran all three subprojects'
format/lint/type/test commands myself and compared against the implementer's reported numbers (all
matched); ran `/invariant-check`'s mechanical greps (all clean); mutation-tested one of the ten
restored `test_crew_console.py` tests and the aircraft-layer correlation-id negative-log test to
confirm both are load-bearing, not decorative. Not independently re-read line-by-line:
`audio-adapter/src/local_playback.py`'s no-op parameter threading (low-risk, dev-only path per its
own docstring) and the `CLAUDE.md` doc additions (read for accuracy of claims, not proofread for
prose).

---

## Re-review — Required Fix 1 commit `4ac44e29`

Re-reviewed `4ac44e29d1feb997bc29b7b2cf32d2f44b0c70f6` (parent `4d5ecbdc`, this review's own prior
commit), which addresses Required Fix 1 above. Checked out detached (the branch tip is held in
another worktree); tree was clean before and after.

**The fix removes the special case rather than picking either of the two recommended options.**
`_handle_mark_target` now calls `self.mark_target_fn(contact_id, now_sim)` unconditionally at
command time — before `_speak_or_defer` is ever reached — and only the resulting (position-free)
readback string is deferred; the deferred closure replays the already-computed text rather than
re-deriving anything. This matches every other Stage 6 handler's shape exactly
(`select_target`/`step`/`follow`/`watch_nearest`*/`report`*: resolve-and-act unconditionally, defer
only the *speaking*), so `mark_target` is no longer the one command whose pending entry *is* the
action. Confirmed by reading all six handlers directly (`_handle_watch_nearest` ~2029,
`_handle_follow` ~2200, `_handle_select_target` ~2361, `_handle_mark_target` ~2455, `_handle_step`
~2542, `_handle_report` ~3072): every one performs its side effect (if any) before calling
`_speak_or_defer`; `_handle_report` has no side effect to make unconditional, by its own docstring's
correct reasoning ("a pure read... there is nothing *to* make unconditional").

**Verified the "drop echo, never action" property holds for every Stage 6 command, not just
`mark_target`.** `drain_pending_positional_replies` (refusal) and `reset_for_new_mission`
(`_pending_positional_replies` absent from the `__init__` "survives" list, confirmed by reading that
method) both only ever discard entries in `_pending_positional_replies`, and every entry in that
list is now, for every handler, a closure over an already-executed side effect plus text to speak —
there is no handler left whose closure performs the write itself. `_PendingPositionalReply`'s own
class docstring already stated "writing a mission-memory mark" as one of the immediate,
unconditional side effects — correctly unchanged, since this fix makes the code match that
docstring rather than the other way round.

**Mutation check, done myself, not re-trusted from `implementation.md`'s claim:** restored the old
deferred-call code (`mark_target_fn = self.mark_target_fn` captured before the early-returns, the
call moved inside `_render`), ran `tests/test_crew_console_mission_memory.py` — all three new tests
failed for the stated reason (`calls == []` instead of `[("CONTACT_7", 3.0)]`, i.e. the write never
ran because it was waiting on the deferred closure that refusal/reset drops before it fires).
Restored the fix; `sha256sum src/belief/crew_console.py` matched pre-mutation exactly; `git status
--porcelain` clean throughout.

**Checks, run myself in this worktree** (`.venv` resolved from the main checkout's
`body-layer/.venv/bin/`, cwd inside this worktree's `body-layer/`):
- `ruff format --check src tests`: pass, 156 files already formatted
- `ruff check src tests`: pass
- `cd body-layer && mypy src`: pass, 68 source files
- `pytest tests -q`: 2267 passed, 4 xfailed on a clean run; two separate reruns each hit exactly one
  of the flagged pre-existing flakes (`test_connection_reporter_announces_the_first_connection`,
  `test_connection_reporter_says_disconnected_once_then_connected_once`,
  `test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`), each passing in
  isolation on immediate retry — consistent with the known timing flakes named in this task, not a
  regression from this commit (`git diff HEAD^ HEAD` touches none of `logger.py`'s connection-
  reporter or mission-start-reset code paths).

**Optional refinement** (`audio_client.py` docstring): confirmed against
`audio-adapter/src/transcript_queue.py`'s actual `TranscriptEvent.to_dict` — nine fields exactly as
the new docstring states (`transcript`, `confidence`, `token`, `match_ratio`, `verb_anchored`,
`ambiguous`, `t_wall`, `slots`, `correlation_id`). Accurate. (Note, not blocking: `audio-adapter/
CLAUDE.md`'s own "Commands" section still quotes the old seven-field shape in its `GET
/transcripts/poll` description — pre-existing staleness this commit's diff doesn't touch, since only
`body-layer/src/belief/audio_client.py` was in scope for the optional refinement.)

No new required fixes. No scope drift — the diff is exactly the four files `implementation.md`
describes, all previously-staged/committed.

### Verdict

APPROVE

### Review Confidence

Full read of the fix, all six Stage 6 handlers (to verify the pattern generalizes, not just that
`mark_target` individually looks right), `drain_pending_positional_replies`, `reset_for_new_
mission`, and `_PendingPositionalReply`'s docstring. Mutation-tested the fix myself rather than
trusting `implementation.md`'s account of its own mutation check. Ran all four body-layer checks
myself in this worktree.
