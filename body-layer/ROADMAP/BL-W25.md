# BL-W25 — Aspect-aware object profiles

- [x] **Aspect-aware object profiles — DONE, merged 2026-09-21** #status/done (`3f624d9`, branch
  `feature/aspect-aware-profiles`). `ObjectTypeProfile` gains optional length/width/height;
  `apparent_extent_m` gives `max(L·|sinθ|+W·|cosθ|, height)`. **Aspect drives recognition
  (`MEDRES`/`HIRES`) only — detection keeps the aspect-invariant `size_m`**, because a BTR-60 seen
  through four instruments showed presence identical at every aspect while class and type moved
  1.33×–2.31× (`body-layer/research/2026-09-21-aspect-magnification-and-distinctiveness.md`).

  Fixes the tall-mast bug: the S-300 40B6M's presence range went from 1665 m to 8000 m against an
  observed 6700 m, on an independently sourced 24 m mast height. Only the two S-300 rows carry real
  dimensions; the other ~148 are untouched and unaffected.

  **Threshold recalibration remains deferred, now for a third reason.** Class is short for radars
  while too generous for vehicles, which no single threshold pair resolves. The missing term is
  silhouette distinctiveness, measured this session: infantry classifies at *exactly* its detection
  range at all four instruments, while a BTR-60 needs 7.75× closer. That is a model-shape change,
  not a constant.

