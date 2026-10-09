# BL-B28 — `report right` is not recognised

- [ ] **BL-B28 — `report right` is not recognised while `report left` is.** #status/open Same sortie, 40 seconds
  apart: `"report left."` (0.83) reached `confirm`, `"report right."` (0.85) got `say_again`.

  **DIAGNOSED 2026-10-06, and it is not an asymmetry — it is a silent wrong-direction match.
  Scheduled as [[BL-13]] Stage 1.** Measured directly against `command_matcher.match_transcript` and
  independently re-run by the main loop:

  | transcript | result |
  |---|---|
  | `"report left"` | `token='report_bearing_e'`, ratio **0.75**, `ambiguous=True` — **reports EAST** |
  | `"report right"` | `token=None` |
  | `"scan left"` / `"scan right"` | `scan_left` / `scan_right`, 1.0 each |

  So the `confirm` the pilot heard 40 s before the `say_again` was Petrovich offering to report **a
  compass direction he was never asked about**. *"report left"* fuzzy-matched *"report east"*.
  **The left side was the dangerous one**, which is the opposite of how this entry read — a
  `say_again` is a failure the pilot can hear and correct; a confirm prompt for the wrong direction
  is one he might accept.

  **Root cause: there is no own-ship-relative frame on the report side at all.** `PHRASES` has
  `scan_left`/`scan_right`, while the report family has only cardinals, clock hours and
  `report_bearing_deg`. So the fix is not a phrase-table entry: left/right are a *where* value in
  decision 12's grammar, and this falls out of [[BL-13]] Stage 1 rather than needing its own change.
  Full analysis: `plans/crew-query-path/plan.md`.
  **An asymmetry between left and right in one session is a phrase-table defect, not a recognition
  accident** — the confidences are near-identical and the second is *higher*. Look directly at
  `audio-adapter/src/vocabulary.py`'s `PHRASES` and body-layer's own token handling for a missing
  right-hand form, rather than treating it as a matcher-tuning question.

  Cheap, and worth doing alongside the `describe` synonym (`plans/sortie-2026-10-05-refinements/`
  item 2) since both touch the same table.
