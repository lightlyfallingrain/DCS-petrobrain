# AA-4.1 — Stage 1 — the recognition bench

<!-- doc-provenance:start -->
**Topics:** #speech-recognition
<!-- doc-provenance:end -->

- [x] **Stage 1 — the recognition bench. STOP/GO GATE: PASSED** #status/done (2026-09-19, user: *"this
  clears the gate"*). `stt_engine.py`, `vocabulary.py`, `tools/stt_bench.py`, plus
  `tools/record_corpus.py` for building the corpus.

  **99.2% top-1 on 252 clips of the user's own voice**, `ggml-small.en` with `--prompt`; the two
  remaining errors are both safe misses (no match → "say again"), not wrong commands.

  **Accent was never the limiting factor** — every gain came from tooling. 55.6% first run, but
  that was a recorder bug truncating 0.256s off every clip (sox's output buffer, discarded on
  terminate), which arrived at the bench dressed as an accent problem. 90.5% once recording was
  fixed, 98.4% with `--prompt`, 99.2% after collapsing whisper's repetition loops.

  Settled here, with full reasoning in `plans/inbound-speech/plan.md` and
  `research/2026-09-19-whisper-model-sweep.md`:
  - **`small.en`**, chosen on unsafe-error count rather than accuracy — lightest model with zero
    wrong-command errors (`tiny.en` seven, `base.en` two).
  - **`--prompt`, never `--grammar`**: a grammar cannot decline, so its failures are confident
    wrong commands (31.7%, including "watch nearest air defence" → "what do you see" at 0.82).
  - **Confidence bands are viable, but only prompted** — correct 0.82 vs both failures at 0.58
    and 0.66. This is what Stage 2's "say again" trigger should use.

  Vocabulary grew to 39 tokens during this stage: `report`/`stop`/`say again`, the wake word and
  `nevermind` for two-tier routing, and numeric bearings as a parsed slot with 5° resolution
  acting as a checksum on recognition.
