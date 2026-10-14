# AA-B5 — The inter-utterance gap belongs in the audio path, and playback should report when it stops

- [ ] **AA-B5 — Enforce a 1 s pause after every spoken line in the audio path (urgent lines exempt),
  and give body/brain a feedback channel for when playback has actually stopped.** #status/open User
  direction, 2026-10-14, arriving as the answer to where `BL-14`'s requested post-readback delay
  belongs:

  > *"The 1s audio gap could live in the audio path. It's failry natural for humans to pause shortly
  > between utterances, that makes the transition to next topic clear. Simple solution, after every
  > spoken audio, add 1s delay before anything new is accepted. Expection: urgent -tagged items.
  > It'd also be good to have a feedback channel to body/brain of when speaking (=audio playback) has
  > stopped."*

  ## Two parts, and the second is the architecturally interesting one

  **1. The gap.** A pause after every utterance, enforced where the audio actually plays rather than
  where the text is decided. His reasoning is about speech, not scheduling — a short pause is how a
  person marks the transition to a new topic. Urgent-tagged lines are exempt, consistent with the
  existing interrupt behaviour (an urgent line already clears the queue and interrupts playback).

  **Partly built already, in the wrong layer.** `belief/callouts.py` has
  `INTER_UTTERANCE_GAP_S = 0.75`, applied by `CalloutScheduler.note_reply` when it extends
  `busy_until_sim`. So a gap exists and `BL-14`'s guidance already waits on it — the delta to the
  requested 1 s is 0.25 s, not a missing mechanism. **But it lives in body-layer and is applied to an
  *estimate*** (`estimate_speech_duration_s`, whose `SPEECH_RATE_WPS = 2.5` is documented
  "Uncalibrated — needs a live sortie"). Moving the gap to the audio path makes it a property of
  speaking rather than of scheduling, which is what he asked for.

  **2. The feedback channel, which replaces a guess with a fact.** Body-layer currently *predicts*
  when Petrovich will stop talking from a word-count estimate. A signal from the audio path saying
  playback has **actually** ended removes that estimate from the loop entirely. That matters beyond
  tidiness: every occupancy decision downstream — callout scheduling, the attack-run guidance gate,
  `silence`, the urgent interrupt — is currently keyed on a number nobody has measured in flight.
  One real signal retires it.

  **It is a two-subproject change.** Playback happens on the Windows box, in the aircraft-layer
  collector's `winsound` worker (`POST /audio/play`), so the "stopped" event originates there and
  audio-adapter relays it. See `[[AC-B6]]`.

  ## What to decide when it is planned

  - **Whether the gap is enforced by refusing new audio or by delaying it.** "Before anything new is
    accepted" reads as a refusal at the boundary; a delay queues instead. The difference shows up
    only when something arrives inside the gap, which is exactly the case the gap exists for.
  - **Whether body-layer's `INTER_UTTERANCE_GAP_S` is then removed or kept as a fallback.** Keeping
    both means two gaps compose and Petrovich pauses twice as long; removing it means body-layer's
    occupancy model depends on a channel that may not be connected. Deciding this is the whole of the
    migration risk.
  - **Latency cost.** Press-to-readback is already measured at ~3 s and is the thing that reads as
    machine-like. A gap after an utterance does not add to that, but a gap enforced by *refusal*
    could delay a reply to a pilot command landing just after a callout.

  ## Done when

  A spoken line is followed by a real 1 s pause, urgent lines still interrupt, body-layer learns that
  playback stopped from the audio path rather than from a word count, and the two gap constants do not
  compose by accident.

  Related: `[[AC-B6]]` (the collector-side playback-stopped signal), `[[AA-B4]]` (verb anchoring, the
  other vocabulary item from the same day), `body-layer/ROADMAP/BL-14.md` (the attack run, whose
  post-readback delay prompted this and which waits on body-layer's gap until this lands),
  `docs/acceptance/2026-10-14-attack-run-guidance-direction.md` §23.
