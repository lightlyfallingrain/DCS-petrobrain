# BL-W23 — Cones slice 2B — gaze as a filter

- [x] **Cones slice 2B — gaze as a filter. DONE, merged 2026-09-21.** #status/done `perception/gaze.py`;
  `check_visibility` evaluates a gaze first in the gate chain; `Optic.peripheral` and the bypass
  rule; **F10 scan commands finally steer naked-eye perception** rather than only registering an
  attention area.

  **Behaviour-preserving by construction** — nothing observable changed by default, which is the
  point. Achieving that required deviating from the plan: it specified `FULL_GAZE` (±90°) as the
  default and called it a no-op, but `cockpit_mask.py`'s measured envelope reaches ±130°, so that
  would have silently narrowed detection through the 90–130° band. The default is `None`
  (plan corrected in `e520e8b`).

  **Live-acceptance debt, deferred not waived:** a commanded scan is testable today but reads
  properly only against free-scan gaze, so it clears on 2C's sortie.

  **Standing exposure until the capture channel exists:** `Optic.peripheral` is wired with no
  triggers — nothing generates a peripheral stimulus, because there is no behaviour-change channel.
  From 2C onward, nothing outside the focus cone captures attention.

