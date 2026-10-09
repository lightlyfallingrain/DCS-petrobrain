# BL-9 — Debug visualization

- [x] **BL-9 — Debug visualization. DONE, merged 2026-09-20** #status/done (`1553eb9`, branch
  `feature/bl9-detection-trace`). `--detection-trace` flag, `DetectionTraceWriter` (a read-only join
  between `LoGetWorldObjects` ground truth and belief state), and a post-flight reducer.
  **Merged immediately after cones slice 1 (`ce9baea`) so one sortie serves both** — that slice's
  deferred detection-range question and BL-9's own acceptance.

  **The merge itself found two defects neither branch's tests could see**, which is worth recording
  because both were invisible by construction: each branch was correct alone. The trace computed its
  `range_threshold_m` with `BINOCULAR_RANGE_MULTIPLIER` hardcoded, so once the naked eye became the
  default optic every trace row would have reported a threshold 4x larger than the gate applied —
  the instrument misreporting precisely the quantity it exists to measure. And the new field-of-view
  gate returned without recording, which would have started dropping trace entries as soon as slice
  2 made a non-default optic selectable. Full detail in the merge commit.

  Original entry, kept for its reasoning (user, 2026-09-20: do it after inbound-speech Stage 3). Belief-vs-DCS-truth debug view. Its own entry already allowed for this — "arguably worth
  pulling earlier if BL-2/BL-3 turn out hard to reason about textually" — and the reason it moved is
  stronger than legibility: it multiplies what a single sortie is worth.

  Detection-range calibration has never been flown, and the loop above means the next sortie has to
  serve calibration, the outstanding acceptance debts, and BL-8's "run for real" gate at once.
  Without this, calibration data is a pilot's recollection of roughly when a callout happened. With
  it, it is what Petrovich believed next to what was actually there. Same flight, very different
  evidence.

