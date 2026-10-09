# AA-1.6 — Stage 6 — live sortie acceptance

<!-- doc-provenance:start -->
**Topics:** #speech-recognition
<!-- doc-provenance:end -->

- [x] **Stage 6 — live sortie acceptance. ANSWERED 2026-09-26 (user), never flown as a
  dedicated flight.** #status/done All three questions it existed to ask were settled across the sorties that
  were actually flown, which is why no Stage 6 card was ever completed — see also
  `docs/acceptance/2026-09-18-stage6-sortie.md`, closed the same way.

  - **Synthesis latency: not laggy.** *"< 1s is not laggy."* The lag a pilot actually feels is
    upstream, in speech-to-text, and it has its own entry (press-to-readback ~3 s) — so the
    number this stage was written to judge turned out not to be the number that matters.
  - **Several callouts in one poll: fine now.** Not because the queue was judged acceptable as
    built, but because flight feedback changed it — callouts are decided at speech time rather
    than queued ahead, and repetitive ones aggregate (`plans/callout-scheduling/`). The
    behaviour this stage would have graded no longer exists.
  - **Voice: survives, but monotonous.** *"Fine for now."* The monotony is real and already
    carried by [[AA-B1]] (accent and prosody), where the finding is that
    prosody probably matters more than accent.
  - **Ducking against other sound on the box:** answered the same day, behaves well (above).

  Acceptance, not a correctness gate — stage 5 already proved the pipeline, and nothing here
  changed that.
