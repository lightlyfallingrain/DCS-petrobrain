# AC-B3 — Split the export throttle

- [ ] **AC-B3 — Split the export throttle** #status/open so `LoGetWorldObjects`/HelperAI can poll slower than self-data.
  `Export.lua`'s `EXPORT_INTERVAL_S = 0.2` (5 Hz) is one shared throttle gating all three feeds
  together. Ground units don't need 5 Hz; self-data (and any future threat-reaction signal) may
  want to stay fast. Fix: two independent interval constants. Not urgent — no measured FPS cost yet
  to react to (see next item). BL-2's contact-decay timescales (30s/120s) are ~2 orders of
  magnitude slower than either 5 Hz or a candidate 2 Hz, so this is a pure export-cost/latency
  tradeoff, not a belief-quality one. Raised 2026-09-09.

  **Correction, filed from the `plans/attack-run/plan.md` (`BL-14`) amendment pass, 2026-10-14
  (§21 of `docs/acceptance/2026-10-14-attack-run-guidance-direction.md`, itself reshaped by a
  second round of direction the same day).** The "not a belief-quality one" clause above no longer
  holds universally: attack-run guidance re-rotates a carried relative offset against *current*
  ownship attitude every poll (`plan.md` Decision 16), and future 9K113 missile guidance needs the
  same freshness, so there is now a real case where attitude freshness **is** a quality driver.

  **But this item is not the prerequisite for that case — the dependency runs the other way.**
  Aircraft-layer already exports everything at 5 Hz (`EXPORT_INTERVAL_S = 0.2`,
  `aircraft-layer/dcs-export/Export.lua:143`); this item is about *slowing bulk world-object*
  export for FPS cost reasons, which it has not yet needed to do. The quality-freshness case above
  is served by a **selective body-layer-side fast lane** — polling only ownship telemetry and the
  currently-selected target faster than the normal perception tick, filed separately as `BL-B63`
  — and that fast lane gets its 5 Hz target data **today, from the export rate this item would
  slow down, with no change here at all.**

  **This item becomes a prerequisite for `BL-B63` only if and when it lands and slows bulk
  world-object export below 5 Hz for FPS reasons.** At that point the selected target would need
  its own fast publication carved back out on the export side, and this item's own fix (two
  independent interval constants) is exactly the shape that would need to preserve. Until then,
  `BL-B63`'s fast lane depends on nothing here. `BL-14` itself needs neither: its own staleness
  budget already closes with re-rotation alone at the existing 1 Hz body-layer rate (the register
  and the dynamics co-vary — see `plan.md` Decision 16's amendment note).
