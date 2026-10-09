# BL-W16 — Overlay clock/range summary

- [x] **Overlay clock/range summary (small feature riding on BL-3 + BL-2.5; done, merged 2026-09-10,
  `4ef08bd`).** #status/done `feature/overlay-clock-range-summary`. Appends a clock-position/range fragment
  (`"11 o'clock, 3.0 km."`) to `Contact` summaries via `tools.py`'s `_contact_summary`, rendered
  whenever `relative_now` is present regardless of visibility. No `console.py` change needed —
  `format_event_for_overlay` already reads `summary` verbatim, so overlay and console both picked it
  up automatically. One Reviewer-required fix: a double-punctuation defect from appending onto a
  string already ending in `.`. No live acceptance needed — judged a pure formatting change over an
  already-verified field. Full history: `plans/overlay-clock-range-summary/`.

