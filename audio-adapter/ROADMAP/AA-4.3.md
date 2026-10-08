# AA-4.3 — Stage 3 — recognition as a service, and body-layer's inbound wiring

<!-- doc-provenance:start -->
**Topics:** #speech-recognition
<!-- doc-provenance:end -->

- [x] **Stage 3 — recognition as a service, and body-layer's inbound wiring.** #status/done Merged
  2026-09-20. `POST /transcribe` and `GET /transcripts/poll` on the existing server, a bounded
  transcript queue, `AudioAdapterClient.get_transcripts()`, and `--speech-input` on the logger.
  The seam carries **seven fields**, all required: `token=None` alone cannot distinguish "not a
  command" from "verb-anchored but unresolved" from "ambiguous", and those demand three different
  responses.

  **Acceptance was performed, not described:** real corpus WAVs POSTed to a running adapter, real
  whisper recognition, real band routing — no Windows, no DCS. One honest limit found and
  recorded: `logger.py`'s `--crew-text` poll loop never reaches `_poll_transcripts` until real
  telemetry arrives (`ConsolePerceptionRunner.run_once` short-circuits on `None`), so the full CLI
  path cannot demonstrate that claim even though its components do. Pre-existing, not introduced
  here.

  Two changes rode along, both reviewed:

  - **`stop` speaks nothing** (Decision 5 REVISED). It previously said "Copy.", which was not a
    stylistic slip but architecturally forced — there was no interrupt-only call anywhere, so the
    only way to reach the queue-clear was to push new urgent audio. Building that path
    (`POST /audio/stop`, `AudioSink.interrupt()`) took the audio side of a stop to **~6 ms**,
    which also answers the latency question the reviewer had flagged for Stage 6: the delay is
    recognition and dispatch, not the audio mechanism. A concurrency race in the
    interrupted-versus-failed flag was found in review and fixed by tracking processes by
    identity.
  - **Confidence and match ratio are gated independently** (Decision 4 REVISED AGAIN).
    `ACT_FLOOR = 0.60` was measured against the *confidence* distribution and applied to
    `confidence × match_ratio` — a product whose range is systematically lower than either
    factor. Four real clips run end to end put two in the confirm band, both barely under their
    floor. The fix points the constant at the quantity it was measured on, and gives the brain
    layer its **second route in**: speech heard clearly that matches no command is free speech,
    not a failure.
