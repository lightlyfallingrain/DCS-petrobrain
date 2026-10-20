---
name: reply-lane-never-defers-against-busy-until-sim
description: CrewConsole's reply lane (select_target etc.) charges scheduler.busy_until_sim after speaking but never checks it before — unlike the push lane's "decide at speech time" fix, which only re-renders because it defers. OutgoingSpeech.template exists but is discarded before _print. Cross-machine timing design principle for this voice chain.
metadata:
  type: project
---

**Found while planning `voice-latency-instrumentation` (2026-10-20), for F8's "stale select_target
readback, several seconds late, after a U-turn."**

**The reply lane (`CrewConsole._handle_select_target` and siblings) renders position text
synchronously at command-handling time and never defers.** `_print` only *charges*
`scheduler.busy_until_sim` afterward via `note_reply` (extend via `max`, never preempt) — it never
*checks* `busy_until_sim` before speaking. Contrast the push lane
(`belief/callouts.py`, "the decision moves to speech time"): `CalloutScheduler.tick` chooses and
renders **at most one** candidate per call, the instant it is chosen, specifically so nothing is
ever rendered ahead of being spoken. The reply lane has no equivalent — a reply queued (in
sim-time terms) behind another already-modeled utterance still renders using `now_sim` at command
time, not at the later tick when the channel is actually believed clear. This is a real, fixable
gap, reusing the same `busy_until_sim` field, not a new scheduler.

**This only explains *modeled* staleness** (reply stacked behind another sim-time-modeled
utterance). It does **not** explain staleness from raw STT/TTS/network pipeline latency while the
channel was modeled clear — body-layer has no sim-time representation of that latency at all, and
there is no playback-completion feedback signal from audio-adapter/aircraft-layer back to
body-layer to close it (one was explicitly rejected for the push lane itself, for
replay-determinism and `--speech-audio`-off reasons that would reapply here). Don't assume fixing
the modeled case resolves a reported "stale readback" complaint — check which case actually
occurred (needs per-stage timing logs; that's what `voice-latency-instrumentation` built).

**`OutgoingSpeech.template` (`belief/speech.py`) already carries exactly the "template" tag a
later ask for richer logging will want — and it is already discarded.** Both `CalloutScheduler.
tick` and every `_handle_*` reply method return plain `list[str]`, not `OutgoingSpeech`, before
reaching `_print`/the speech log. Threading `.template` all the way through would touch that
return-type convention across roughly twenty handler methods plus `tick` itself — a real refactor,
not a logging tweak. If this is wanted later, scope it as its own pass; don't let a logging-plan
quietly turn into that refactor.

**Cross-machine timing design principle, for any future instrumentation across this chain**: this
project's committed topology (2026-10-20, §F1) runs audio-adapter+brain on the Mac and
body-layer+collector on Windows, so most hops cross a machine boundary and absolute wall-clock
subtraction across two logs is not trustworthy. The fix that avoids needing cross-machine clock
sync: wrap every HTTP call with `time.monotonic()` immediately before/after **on the calling
process's own clock** — that yields a trustworthy round-trip duration (covering network + whatever
the far side did) regardless of skew, chained across however many hops. The one gap this can't
close is dwell time in a queue the producer and consumer don't share a call/response for (here:
audio-adapter's `TranscriptQueue` sitting between enqueue and body-layer's next poll) — bound it by
the known poll interval instead of faking a precise number.
