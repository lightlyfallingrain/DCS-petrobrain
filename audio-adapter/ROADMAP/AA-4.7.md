# AA-4.7 — Press-to-readback latency

- [ ] **Press-to-readback is ~3 s, and that is the next real problem.** #status/open Measured on the
  2026-09-23 sortie (user: *"time from release to feedback is about 3 s"*). A crew member answers
  in well under a second, so this is what will keep him feeling like a machine no matter how good
  the recognition is.

  **One component is certain rather than estimated: the logger polls `GET /transcripts/poll` once
  per `poll_interval_s`, default 1.0 s**, so a recognised command waits 0 to 1 s — half a second
  on average — purely to be noticed. It is the cheapest half-second in the chain to remove, and
  it costs nothing but loopback HTTP requests.

  The rest of the budget is estimated and should be **measured before anything is optimised**:
  the 0.4 s tail (deliberate), sox's stop and `--ignore-length` re-encode, the LAN hop, whisper
  itself, and `say`'s synthesis (previously measured at 0.6-0.8 s). Every hop already carries a
  wall-clock stamp, so instrumenting this is reading timestamps rather than adding machinery.

  **Two candidate fixes that need no accuracy trade:**
  - **Poll transcripts faster than the telemetry cadence.** They are different jobs on the same
    timer today.
  - **Cache synthesized readbacks.** The readback vocabulary is small and fixed (*"Scanning
    left."*, *"Copy, stop scan."*), so the same handful of WAVs are re-synthesized every flight.

  **Not a candidate: a smaller whisper model.** `small.en` was chosen on unsafe-error count, not
  accuracy — `tiny.en` produced seven confident wrong commands and `base.en` two, against
  `small.en`'s none. Trading that for latency would buy speed with the one failure the pilot
  cannot catch.
