---
name: voice-stage5-oclock-scan
description: Stage 5 (voice-command-completeness) implementation choices worth knowing before touching ScanPlan/AttentionArea again
metadata:
  type: project
---

Implemented Stage 5 of `plans/voice-command-completeness/plan.md`: `scan_clock_1..12` tokens plus
the fix for compass scans never steering `NakedEyePerceptionSource`'s gaze.

- **`ScanPlan.commanded_legs` is additive, not a replacement for `commanded_sector`.** The plan's
  Decision 5 said "let `ScanPlan` carry legs directly" without specifying whether to retire the
  existing `RelativeSector`-typed field. Chose additive: `commanded_sector` (ahead/left/right/full)
  is untouched, `commanded_legs: tuple[int, ...] | None` is a new, mutually-exclusive sibling field
  for a bare o'clock hour or a converted absolute sector. This kept every existing `ScanPlan(...)`
  construction site and test (`test_optic_policy.py`, `test_detection_trace.py`,
  `test_emission_pipeline.py`, `test_gaze.py`, `test_logger.py`) unchanged — they all use keyword
  args, so a new defaulted field was purely additive.

- **`legs_within_wedge`'s sweep order does NOT match `_SECTOR_LEGS`'s order for an equivalent
  wedge.** `legs_within_wedge(-60.0, 30.0) == (9, 10, 11)` (ascending signed offset), while
  `_SECTOR_LEGS["left"] == (11, 10, 9)` (near-center-first). Same three hours, different order.
  They serve different callers (converted absolute scan vs. a named commanded sector) and were
  never required to agree on order, only membership — do not assume they interchange.

- **`_active_gaze` needed a `heading_true_deg` parameter** to convert an absolute
  `AttentionArea.sector` into relative legs every poll. Defaulted to `0.0` rather than making every
  test call site pass a real heading — safe because every existing direct caller only constructs
  `relative_sector`-based (heading-independent) tasks.

- **Binocular search band (`logger._search_sweep`) deliberately NOT extended** to the new
  `commanded_legs` cases (bare o'clock hour, converted compass scan) — still gated on
  `commanded_sector is None`. No obvious correct half-width for a single 30°-wide o'clock leg;
  left for a later stage if the user wants it. Documented in both the docstring and ROADMAP.

See [[decouple-fixtures-from-tuned-defaults]] and [[respect-instructed-caps-over-recomputed-margins]]
for related patterns in this project's gaze/scan machinery.
