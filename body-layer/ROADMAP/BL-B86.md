# BL-B86 — above ~3.6–4 km AGL the sight's idle search cycle goes fully idle (free/ahead scan)

- [ ] **BL-B86 — Found by the Reviewer re-review of the `9k113-narrow-search` elevation
  field-of-regard security fix (`plans/9k113-narrow-search/security-review.md` Required Fix 1,
  closed by commit `bb6364b0`), by direct measurement, not by inspection: once the fix correctly
  filters `_sight_in_regard_sweep`'s steps through `within_field_of_regard`, a **free scan** or a
  commanded **`ahead`** scan loses all three in-regard legs (`wide`/`narrow_near`/`narrow_far`)
  simultaneously above a measured altitude, and — because neither of those two sectors ever
  produces an out-of-regard remainder (`logger._sight_out_of_regard_sweep` returns `[]` for both,
  by construction) — the idle search cycle has nothing left to step through at all and falls to
  `_idle_sight_rest`: the sight stops searching entirely and holds a fixed aim (last position, or
  dead-ahead/level) until something becomes worth a look.** #status/open

  **Measured** (this branch's tuned constants, `SIGHT_SEARCH_NEAR_M=2333`/`MID_M=5647`/
  `FAR_M=13556`, `_SIGHT_WIDE_SEARCH_FAR_M≈8282`): `wide`/`narrow_near` already empty out by
  **2333 m AGL** (their shared near edge's own depression first exceeds the far edge's at that
  altitude); `narrow_far` — which reaches furthest out and so survives longest — empties out
  between **3630 m and 4000 m AGL** (its own far edge's depression first passes the `-15°`
  down-regard limit at `13556 * tan(15°) ≈ 3630` m). At and above that point, for `free`/`ahead`
  only, all four sequences (`sight_wide_search`/`sight_narrow_near_search`/`sight_narrow_far_search`
  /`sight_out_of_regard_search`) are simultaneously empty.

  **Not a crash, hang, or busy loop — verified directly.** `_idle_sight_search`'s `first_nonempty_
  leg` loop is bounded (`len(_SEARCH_LEG_ORDER)` iterations) and returns `None` on exhaustion,
  handled by `_idle_sight_rest`, which holds the last (already-validated) aim or `(0.0, 0.0)` —
  both always within regard. Reran `decide()` 20 polls at 5000 m AGL with all four sequences empty:
  stable, no exception, `within_field_of_regard` holds every poll.

  **Not true of every commanded sector.** `left`/`right`/`full` each produce a genuine out-of-regard
  remainder by construction (`_split_sector_by_regard`'s own worked examples), so their idle search
  continues via the out-of-regard binocular leg — `BINOCULAR_OPTIC` has no field-of-regard limit at
  all — even well above 4000 m AGL. Confirmed by direct measurement at 3000/4000/5000 m AGL for
  `free`/`ahead`/`left`/`full`.

  **Not a required fix for the security patch that surfaced it.** The patch's own "reject, not
  clamp" choice is correct and this is its honest downstream consequence, not a defect the patch
  introduced carelessly: above this altitude there genuinely is no elevation within the search
  band (2333–13556 m) that the mount can still reach, for a sector with no binocular remainder to
  fall back on. `implementation.md`'s own "what the pilot will notice" note undersold the
  magnitude, though — it describes only the near-edge band dropping out (true at 1000 m AGL), not
  that the *entire* idle sweep for `free`/`ahead` goes static above ~3.6–4 km AGL.

  **Needs**: a decision on whether this altitude band is operationally relevant for the Mi-24P
  (attack-helicopter employment is typically low-level, so ~4 km AGL transit/orbit may be rare
  enough not to matter), and if it is, whether the idle fallback should do something better than
  hold a fixed aim here — e.g. parking the sight at its own `-15°` down-regard boundary rather than
  at `(0.0, 0.0)`, or widening `free`/`ahead`'s synthesized sector so it too gets an out-of-regard
  binocular remainder the way `left`/`right`/`full` already do. Not explored with the user yet —
  do before Architect, per `AGENTS.md`'s "Explore Before Deciding," if this is picked up.

  **2026-10-20 — the altitude figures above are level-flight-only, not a general threshold.**
  `feature/9k113-narrow-search`'s F5 fix (`docs/acceptance/2026-10-20-sortie-feedback.md`) made
  `_sight_in_regard_sweep`'s regard check pitch/bank-relative, per the user's own correction: *"It
  is not about distance, but angles relative to boresight."* Every depression figure measured
  above (2333 m, 3630–4000 m) was computed with pitch/bank both zero, so they are still correct —
  but only at wings-level, nose-level flight. Nose-down raises the altitude at which `narrow_far`
  empties out (a 10° nose-down attitude recovers roughly the geometry a ~1700 m-lower, level-flight
  altitude would have — `tan(15°+10°) / tan(15°) ≈ 1.76×` the reachable depression-driven range at a
  fixed AGL, worked the other way as AGL); nose-up lowers it the same way. So **BL-B86's "idle
  search goes fully static" window moves with attitude, not with AGL alone** — a free/ahead idle
  search at nominally-empty altitude is not stuck if the nose is down, and can go static markedly
  below 3.6 km if the nose is up. This does not change BL-B86's own fix (still open, still the same
  needed decision) — it only means a future fix sized against "the ~4 km band" should be sized
  against boresight depression, not AGL.
