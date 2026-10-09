# BL-8 — Memory layer interfaces

- [ ] **BL-8 — Memory layer interfaces.** #status/open Not started, deliberately last (user decision, 2026-09-10:
  "the shape of what's worth remembering is only knowable after BL-2..BL-7 have run for real").
  Standing awareness note while BL-2..BL-7 touch in-mission memory shapes (`Contact`/`ContactStore`,
  BL-4's `AttentionArea` registry): keep BL-8's eventual mission-end export/persistence boundary in
  mind, not as a design constraint yet, just don't shape something in a way that obviously fights it.

  **A concrete consumer now waits on this, added 2026-09-29: the "safe from" callout.**
  `plans/dcs-driven-los/plan.md` defers it at user direction, and the reason names exactly what
  BL-8 would have to hold. *"Danger"* is a claim about something Petrovich can see; *"safe from"* is
  a claim about an **absence** — it asserts a unit is no longer able to shoot you, which needs to
  know where that unit is *now*, not where it was last observed. Once LOS comes from DCS for units
  the naked-eye channel is currently observing, a contact outside that coverage has no honest basis
  for a clearance without remembered believed positions. So BL-8 is no longer only "what is worth
  remembering after a sortie" — it now has one named in-mission consumer whose feature is switched
  off until it exists (`belief/speech.py`'s `engaged=False` branch).

