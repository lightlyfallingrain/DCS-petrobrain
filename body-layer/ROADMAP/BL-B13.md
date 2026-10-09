# BL-B13 — Own perception end-to-end, dropping DCS ambient detection

- [>] **BL-B13 — Parked: stop consuming DCS's ambient detection at all, own perception end-to-end.** #status/deferred Raised
  2026-09-09 after the PB-1.5 live probe showed DCS's ambient callout is unreadable/late/
  sight-coupled. All four open questions were answered by the user 2026-09-09 (scope channel
  stays — needed for future acquire/lock/fire gameplay, which is why the association-namespace-
  mismatch fix above mattered; suppressing DCS's own radio callout text is low-priority,
  investigate only if resumed; [[BL-2]] is barely affected since it already consumes `Observation`s
  channel-agnostically). What's left, once those deferrals are subtracted, is not architectural:
  reclassify `visibility.py`'s naked-eye filter from "fallback" to "primary mechanism" in the
  docs, and calibrate its tier/range constants against "if the player can see a unit, Petrovich
  should too." Calibration needs live sorties, so it's meant to ride along with a milestone that's
  flying anyway rather than run standalone. **Do not start without the user's instruction.**
