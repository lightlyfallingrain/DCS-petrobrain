# X-T3 — Player bubble: unit detection bounded to 10 km

- [x] **Unit detection computations are bounded to a 10 km radius around ownship. DONE, merged
  2026-10-02.** #status/done DoD PASSED (no live acceptance owed — a waiver, not deferred debt: this feature
  has no in-cockpit observable until the 9K113 sight's 20 km cone makes `PLAYER_BUBBLE_RADIUS_M`
  diverge from `NAKED_EYE_RANGE_CAP_M`). Full writeup and status now lives in
  `body-layer/ROADMAP.md`'s own entry, per this file's own rule against duplicating milestone
  narrative. `plans/player-bubble/` has the plan/review/security/performance/DoD trail.
