# WB-3 — Flight control: fly heading/altitude/speed, fly to a point then hold or continue

- [ ] **WB-3 — A wingbrain can make its wingman fly a heading, altitude and speed, or fly to a
  point and then hold there or go on to the next waypoint. DCS AI keeps flying formation until
  told otherwise.** #status/open Filed 2026-11-19 from `docs/concept/wingbrain.md`, "Flight
  control". Needs `[[WB-1]]`'s flight half and `[[WB-2]]`.

  > *"Default behaviour for DCS AI wingmen is they fly formation with flight lead (player). Keep
  > that initially. Only control flight patameters when necessary. At some later stage, if ever, we
  > may build taking control of wingmen flight parameters immediately after takeoff."*
  >
  > *"If using the dynamic waypoint solution, that may mess up with the flight plan route. In first
  > phase, ignore that, let it happen. We'll fix it at some point."*
  >
  > *"Flight control modes:*
  > *- fly heading, alt, speed*
  > *- fly to a point*
  >     *- hold there (orbit or hover) or turn and fly to next waypoint"*

  Built as actions with explicit parameters, with the *when* kept in Lua rules (root `CLAUDE.md`,
  "Behaviour as actions and params").

  **Open for the plan:** how a wingman goes back to flying formation once a command is done. The
  concept keeps formation as the default but does not say what ends a commanded mode.

  Route damage is accepted for now: `[[WB-B1]]`. Taking control right after takeoff:
  `[[WB-B2]]`.
