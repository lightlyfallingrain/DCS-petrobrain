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
