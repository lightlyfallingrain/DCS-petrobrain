---
name: inbound-speech-stage3-approved
description: Stage 3 (recognition-as-a-service, stop_talking dispatch) reviewed APPROVED — sequencing trace and interrupt-mechanism reasoning worth reusing.
metadata:
  type: project
---

Reviewed `plans/inbound-speech/plan.md` Stage 3 (branch `feature/stt-recognition-service`,
`986af12^..9291906`) — audio-adapter's `POST /transcribe`/`GET /transcripts/poll`, body-layer's
`_poll_transcripts`/`--speech-input`, and `stop_talking` dispatch. APPROVED, no required fixes.

**`stop_talking` speaking "Copy." is architecturally forced, not a stylistic choice.**
`CrewConsole._print` only threads `bypass_gate` through to `push_speech(..., urgent=True)` when
there's at least one line to push (`for line in lines:` skips entirely on `[]`) — there is no
interrupt-only call anywhere in this codebase. `AudioPlaybackSender.play_audio` (aircraft-layer)
writes the new WAV, then (if urgent) synchronously clears the queue + stops playback, *then*
enqueues — so no audio overlap, but the interrupt itself only fires after the full round trip
(recognition -> dispatch -> TTS synthesis -> HTTP to aircraft-layer) completes, which is a real
latency cost inherited from the existing push_speech(urgent=True) mechanism, not introduced by
this stage. Worth checking for at Stage 6 live-sortie latency acceptance, not a defect now.

**Telemetry-gate claim verified genuine via git diff, not trusted from the disclosure.** The `if
runner.last_t_sim is not None:` gate around `drain_events`/`_poll_f10_commands` predates this
branch; Stage 3 added two lines inside it. Real consequence: the actual CLI entrypoint
(`run-crew-text.sh`) can't demonstrate Stage 3's own "no Windows, no DCS" acceptance claim without
a live aircraft-layer feeding telemetry — implementer's disclosed workaround (drove the real
components directly via a throwaway script) is honest and sufficient, but the gap isn't tracked
anywhere durable (ROADMAP/todo) — flagged as optional, not required.

**`run-crew-text.sh`'s committed state silently drops `--overlay` / adds `--speech-audio` vs. the
last clean commit** (`git show b533fca:body-layer/run-crew-text.sh` vs. current) —
implementation.md's "Files Changed" only mentioned the `--srs-adapter-url` fix and `--speech-input`
addition, not this. Worth checking a run script's actual prior committed state with `git show`,
not just the doc's own account of what changed, when a doc says a file was "already
modified/uncommitted at task start."

See [[project_group_contact_model_stage4b_approved]]-style pattern: tracing an actor's exact
call sequence (temp-file-write -> interrupt -> enqueue) in a *sibling* subproject
(aircraft-layer) was necessary to answer a behavioral question that only the implementer's other
codebase could resolve — cross-subproject tracing paid off again.
