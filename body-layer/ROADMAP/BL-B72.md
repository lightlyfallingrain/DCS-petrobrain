# BL-B72 — A firing unit gives itself away, out to the player bubble

- [ ] **BL-B72 — While a unit is actively firing, muzzle flash and tracers make it detectable at any
  range out to the player bubble, through tree cover, regardless of the optic's own distance
  limits — detection only, and only while it fires.** #status/open Filed 2026-10-15 from user
  direction; his words and the structural reading are in
  `docs/acceptance/2026-10-15-firing-unit-visibility.md`.

  **The rule, as a modification to `check_visibility`'s existing gate chain** — this is the form the
  work takes, and the asymmetry is the whole item:

  | gate | firing unit |
  |---|---|
  | gaze | still applies — he must be looking that way |
  | cockpit mask | presumably still applies (open question 2) |
  | optic FOV | **still applies** — the user names it: *"with optic where FOV allows seeing"* |
  | range / size | **bypassed**, out to `PLAYER_BUBBLE_RADIUS_M` |
  | terrain / building LOS | **open** (question 1) |
  | tree cover | **bypassed** — *"a unit firing from a forest gives it location away"* |

  **Detection only.** It admits at `PRESENCE` and must not raise `CLASS` or `TYPE` — a muzzle flash
  at 9 km says *something is shooting there*, not *that is a BMP-2*. **Strictly time-bounded** by the
  DCS start/stop firing events: *"once it stops firing, we cannot see it anymore."* What survives is
  an ordinary decaying memory of having seen it, not a continuing sighting.

  ## Why this is worth more than its size

  It is **the first perception path where the target's own behaviour decides whether it is seen**,
  rather than the observer's instrument or the geometry. Everything so far is a function of range,
  size, optic and occlusion; this adds an emitter.

  And it closes a gap the pilot would notice immediately: today a unit shooting from 4 km is
  invisible to Petrovich, because that is past the naked eye's ~2.3 km presence threshold for a 7 m
  vehicle (`7 / LOWRES_ANGULAR_RADIUS_RAD`). **The thing most worth telling the pilot about is
  currently the hardest for Petrovich to see.** Measured on the 2026-10-15T17:55 sortie, where the
  attack target sat unresolvable between 2.6 km and 2.36 km for fifteen seconds.

  ## Blocked on a probe, not on a plan

  **DCS firing events are not exported today** — `grep` over `aircraft-layer/dcs-export/Export.lua`
  and `aircraft-layer/src` finds no shooting event of any kind. So this needs new aircraft-layer
  work, and its feasibility is unverified in the specific way that decides the entry's cost:

  `S_EVENT_SHOOTING_START`/`S_EVENT_SHOOTING_END` are **mission-scripting** events
  (`world.addEventHandler`). This project's export lives in a **GameGUI Hook**, and whether a Hook
  can observe those events at all is an open question. **Investigator before Architect** — if the
  answer is no, the fallbacks (a polled per-unit firing flag, if one exists; or nothing) are
  materially worse and change whether this is worth building as specified.

  Related: `[[BL-B64]]` (the optic model this bypasses a gate of), `[[BL-B70]]`/`[[BL-B71]]` (the
  attack-run work whose `", obstructed"` semantics question 1 interacts with), `[[BL-2]]`
  (contact decay, which owns what happens after the firing stops).
