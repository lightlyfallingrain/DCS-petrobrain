# AC-7 — Hardening — bounded audio queue and a guarded collector `accept()`

- [x] **Hardening: bounded audio queue + guarded collector `accept()` -- done 2026-09-26, merged `a63a86f`** #status/done
  (`feature/aircraft-layer-hardening`, no plan.md -- scoped directly from the two 2026-09-26
  whole-subproject reviews, `aircraft-layer/research/2026-09-26-security-review.md` and
  `-performance-review.md`). `AudioPlaybackSender`'s queue is now bounded at 64 (mirroring
  `F10CommandQueue`), dropping the oldest queued `.wav` on overflow rather than blocking the HTTP
  thread. `CollectorServer.serve_forever`'s `accept()` is guarded so a dead ingestion thread stops
  being invisible, logging loudly and retrying after a backoff instead of dying silently.
  Went through two rounds: the first `accept()` guard classified shutdown by re-reading
  `self._socket`, which raced `close()`'s own two-statement teardown and produced a false
  "unexpected failure" ERROR on 161/~230 real shutdowns -- the reviewer measured this, not just
  read it. Fixed with an explicit `self._shutting_down` flag set before the socket is actually
  closed, so the flag-write happens-before the racy syscall. Both fixes are latent hardening with
  no observed live trigger; no acceptance card, per DoD judgment (neither changes anything
  perceivable in the cockpit). **Does not change what's next** -- these were pre-existing
  RECOMMENDED findings, not new information; the export-throttle split and the
  `LoGetWorldObjects` FPS measurement below remain correctly deferred pending an actual
  measurement, which this work did not take.
