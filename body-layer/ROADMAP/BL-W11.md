# BL-W11 — F10 command vocabulary

- [x] **F10 command vocabulary — CLOSED 2026-09-21 as tested and good enough** #status/done (user direction).
  The 15-token set and relative-sector re-projection, merged 2026-09-16
  (`plans/f10-command-vocabulary/`). First sortie flown 2026-09-16/17, closed after further flying.

  **Confirmed live:** the menu tree is navigable, scans register real tasks, and `Cancel Task`
  genuinely cancels — which it never could before this milestone. Two defects were found and fixed
  (merge `74f0fff`, `fix/scan-naked-eye-not-9k113`): Scan was driving the 9K113 sight instead of
  this project's own naked-eye perception, and `Cancel Task` spoke a raw task id.

  **Some items close unexercised, deliberately — worth saying why that is reasonable rather than a
  shortcut.** The F10 menu is an explicitly temporary surface, with voice as the primary interface
  (user, 2026-09-16: *"It's alright if F10 menu goes stale, we'll remove it at some point"*).
  Proving relative-vs-bearing rotation through a 0/360 wraparound on a path scheduled for deletion
  is effort spent on a deliverable nobody will keep. If that behaviour matters again it will matter
  for voice, which needs its own sortie regardless.

  **Not closed — re-homed, because these outlive the menu:**
  - `F10_SCAN_RADIUS_M` (3000 m) and `DEFAULT_SCAN_DEADLINE_S` are still **uncalibrated
    placeholders**. They are properties of *scanning*, not of the F10 surface, so they belong with
    the cones work and the existing `todo/todo.md` entry — and they stay hard to judge until a scan
    actually steers perception.
  - The scan → naked-eye-perception wiring (`todo/todo.md`, "Scan commands should drive naked-eye
    perception") is a perception item that merely happened to surface through the menu.

  Full original acceptance plan, kept for the record:
  `plans/f10-command-vocabulary/dod-check.md`.

