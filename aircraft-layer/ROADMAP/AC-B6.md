# AC-B6 — Report when audio playback has actually stopped

- [ ] **AC-B6 — Publish a "playback stopped" signal from the collector, so the layers above stop
  predicting when Petrovich has finished speaking.** #status/open The collector-side half of
  `[[AA-B5]]`, from user direction 2026-10-14: *"It'd also be good to have a feedback channel to
  body/brain of when speaking (=audio playback) has stopped."*

  Playback is this layer's: `POST /audio/play` hands a WAV to a single `winsound` worker thread,
  routine lines queue FIFO, and an urgent line clears the queue and interrupts whatever is playing.
  **So the collector is the only process that knows when sound actually stopped** — and it currently
  tells nobody.

  Everything above it guesses instead. `belief/callouts.py` computes
  `estimate_speech_duration_s(text)` from `SPEECH_RATE_WPS = 2.5`, documented in its own comment as
  *"Uncalibrated — needs a live sortie"*, and every occupancy decision in the crew layer keys on the
  result: callout scheduling, the `BL-14` attack-run guidance gate, `silence`, and the urgent
  interrupt. One real signal retires that estimate.

  **The interrupt case is the one that makes this more than tidiness.** When an urgent line clears
  the queue, the lines it discarded were already counted as "will be spoken" upstream, and the
  interrupted line stops mid-word — so the predicted end time is wrong in both directions at once,
  and nothing upstream can know it. That is unobservable today.

  Open, and not scoped: whether the signal is a push (to a body-layer endpoint, like the existing
  UDP feeds) or a pollable field on the collector's state (cheaper, consistent with
  `/world_objects/latest` and friends, at the cost of up to one poll interval of latency — which may
  matter here precisely because the consumer is a gap of about a second). Whether it carries *which*
  line finished, which the interrupt case argues for. And whether it reports interruptions
  distinguishably from clean completions.

  Related: `[[AA-B5]]` (the gap itself and the body/brain-facing channel), `[[AC-B3]]` (the export
  throttle split — same "one rate for everything" shape, different feed).
