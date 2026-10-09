# AC-B3 — Split the export throttle

- [ ] **AC-B3 — Split the export throttle** #status/open so `LoGetWorldObjects`/HelperAI can poll slower than self-data.
  `Export.lua`'s `EXPORT_INTERVAL_S = 0.2` (5 Hz) is one shared throttle gating all three feeds
  together. Ground units don't need 5 Hz; self-data (and any future threat-reaction signal) may
  want to stay fast. Fix: two independent interval constants. Not urgent — no measured FPS cost yet
  to react to (see next item). BL-2's contact-decay timescales (30s/120s) are ~2 orders of
  magnitude slower than either 5 Hz or a candidate 2 Hz, so this is a pure export-cost/latency
  tradeoff, not a belief-quality one. Raised 2026-09-09.
