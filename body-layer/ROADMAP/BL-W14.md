# BL-W14 — PB-1.5 — Naked-eye visual detection channel

- [x] **PB-1.5 — Naked-eye visual detection channel (done 2026-09-09, no direct BL- number —
  a perception-tier addition, not contact-memory work).** #status/done `feature/pb1.5-naked-eye-detection`. A
  second, independent perception channel (`NakedEyePerceptionSource`) reporting plausibly-visible
  ground objects from `LoGetWorldObjects`, gated by FOV + angular-size + terrain-LOS, quantised to
  ED's own callout vocabulary. A live A/B probe established DCS's ambient contact callout has no
  Lua-readable companion — the synthetic filter is not a fallback, it's the only implementation.
  Findings: `aircraft-layer/research/2026-09-09-pb15-ambient-callout-live-probe.md`. One live bug
  fixed: `LoGetWorldObjects` included the player's own aircraft as a contact
  (`association.exclude_ownship`, later replaced — see BL-2 Stage -1 below).

