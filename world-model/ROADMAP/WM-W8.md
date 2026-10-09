# WM-W8 — Road-junction progress logging

- [x] **Road-junction progress logging (no M-number — a follow-up to junctions-streaming-fix; done,
  merged 2026-09-13, merge `8c18a2c`, branch `feature/junctions-progress-logs`).** #status/done A real
  `syria-full` rebuild logged nothing between `[5/8] road junctions: starting` and `done`, so a
  long Stage 5 looked hung. `ingest_junctions_streaming` now logs the road and chunk totals up
  front, then `chunk i/N`, percent, junctions kept, elapsed and a rough remaining estimate at
  most every 30 s (`_PROGRESS_LOG_INTERVAL_S`). Time-based rather than every-N-chunks because
  per-chunk cost varies widely between empty and dense chunks. One remaining gap: nothing is
  logged *during* a single slow chunk. 2 new tests (340 passed, 3 skipped). Small change, no
  plan/review files — Implementer plus self-review of the diff. Next-milestone impact: none; it
  only makes the pending `syria-full` validation run observable.
