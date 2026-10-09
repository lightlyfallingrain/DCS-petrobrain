# AC-B4 — Measure `LoGetWorldObjects` FPS cost live

- [ ] **AC-B4 — Measure `LoGetWorldObjects` FPS cost live** #status/open before tuning its poll rate. No confirmed,
  quantified per-call cost exists at realistic unit counts (~50–200) — only qualitative
  forum/Tacview-wiki folklore. Fly with world-objects export on/off at 5/2/1 Hz and diff
  FPS/frame-time. Also worth checking whether "being fired at" is even served by this poll rate at
  all (nothing currently reads it for threat/launch detection) — the urgent-callout-latency case
  may want its own dedicated signal later (e.g. RWR export) instead. Raised 2026-09-09, kept
  separate from the throttle-split item above since this is measurement that should land first.
