# BL-W4 — Terrain callout, Stages 3-4-5

- [~] **`feature/terrain-callout-stages-345` — DoD mechanical checks PASSED 2026-10-05, not yet
  merged, unflown.** #status/in-progress `world-model/query/divides.py`'s query-time divide counter plus the Stage 5
  wiring that lets a terrain qualifier ("next valley"/"beyond the ridge") **displace** the generic
  "near X" fragment on a contact report. Reviewer (round 2), Security deep analysis and
  Performance (APPROVED — MONITOR) all signed off; see `plans/terrain-feature-probing/`. **Rides
  the already-pending `fix/contact-report-flood`/`fix/redundant-group-disclosure` sortie
  (card https://claude.ai/artifact/VJZnmdF3aqxhVGZea3iKN4) rather than needing its own flight** —
  all three change what the pilot hears about the same contact stream, in the same cockpit. What
  only a real flight settles: whether the qualifier fires where the pilot would say it and stays
  silent where they wouldn't (the real-store check at Baalbek reads 1 divide across the flank at
  8 km, 0 along the valley floor to 16-20 km); whether it ever displaces something more useful
  than itself (the risk direction, since it now wins over the road fragment); and whether the four
  shipped-to-be-flown constants (300 m qualifier ceiling, 2x dominance factor, 400 m divide-merge
  distance, >=2-divides-means-silence) need retuning. See `docs/acceptance/
  2026-10-05-terrain-callout-sortie.md`.

