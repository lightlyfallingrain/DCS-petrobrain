---
name: async-speech-interrupt-timeout
description: BL-B106's async-speech fix left SpeechWorker.interrupt()'s stop() call on the push_speech-sized 5.0s default timeout — measured 5.012s against a genuinely wedged server, reachable via the production stop_talking voice command and mission-restart, on the poll thread.
metadata:
  type: project
---

`[[BL-B106]]` (`plans/async-speech/plan.md`, performance review `plans/async-speech/
performance-review.md`) moved `CrewConsole._print`'s `push_speech` call off the 1 Hz crew-text
poll thread onto `belief.speech_worker.SpeechWorker`'s own background thread — verified
non-blocking (`enqueue()` is a bounded `queue.put_nowait`, confirmed with the same bare-socket
wedge technique as [[project_brain_layer_poll_thread_stall]]).

**But `SpeechWorker.interrupt()` → `client.stop()` stayed synchronous on the calling thread by
design (plan Decision 3: "an interrupt that itself waits in a queue is not an interrupt"), and
`AudioAdapterClient.stop()` shares `push_speech`'s own `timeout_s`** (`_DEFAULT_TIMEOUT_S = 5.0`,
`audio_client.py`, never overridden in `body.py`'s construction). Decision 3's own reasoning —
"costs at most one small round trip, never seconds" — was asserted, never measured. Measured this
review, same wedge shape as the precedent: **5.012s**, the full default timeout, not a small round
trip.

**Why it's reachable in production, not theoretical:** `interrupt()` is called from
`CrewConsole._handle_stop_talking` (the `stop_talking` voice command — a real, player-triggered
"panic button," "no readback... more of a debug tool than crew feature") and from
`reset_for_new_mission` (mission-(re)start, checked every poll) — both dispatched from the 1 Hz
poll thread. The only precondition is audio-adapter being up but unresponsive (Piper hung, a
stuck handler thread), the identical "wedged, not down" shape this role's 2026-09-25 note already
established as realistic for `brain_client`.

**Why it matters more than its rarity suggests:** `stop_talking`'s entire purpose is to react
immediately; stalling the poll thread for up to 5s on the one command meant to cut speech off
immediately reintroduces this plan's own target defect through its narrowest, most safety-critical
door.

**Mitigation recommended, not yet applied as of this review:** give `/stop` its own short,
dedicated timeout (e.g. ≤1.0s) distinct from `push_speech`'s synthesis-sized one. Local, reversible,
does not touch Decision 3's synchronous-interrupt design.

**Technique note, reaffirming [[project_brain_layer_poll_thread_stall]]'s own lesson:** a plan's
"never seconds" claim about a network call is a hypothesis until a bare-socket
`accept()`-then-never-respond wedge is actually run against it — "fast when down" and "fast when
healthy" do not imply "fast when wedged," and the existing test suite for this feature only
covered the enqueue (non-urgent) path, not `interrupt()`.
