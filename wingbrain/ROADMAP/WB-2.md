# WB-2 — Wingbrain lifecycle: one per wingman, started and stopped with the mission

- [ ] **WB-2 — At mission start, find how many members the player's flight has and start a
  wingbrain for each AI wingman; stop them at mission end. A flight of one starts nothing.**
  #status/open Filed 2026-11-19 from `docs/concept/wingbrain.md`, "General concepts".

  > *"Wingbrain should be it's own service/thread. One parallel thread/instance per wingman. You can
  > challenge this if it's not a good idea. When mission start, detect how many members there are
  > in player's flight. Start a wingbrain to control each of them. On mission end, stop wingbrains.
  > If flight of one, only player, wingbrain is not needed, radio layer is not needed."*
  >
  > *"How existing Petrobrain code and modules can be reused needs planning. Prefer to use existing
  > code/modules instead of duplicating or writing new. If needed refactor existing code to
  > modulirize it so that wingbrain can simply call it or parts of it."*

  **Decision D1 is settled here** (index, "Open decisions"): where wingbrain runs, and whether
  each wingman gets a thread. Inputs to it:

  - Wingbrain needs body-layer's rule engine (`[[BL-17]]`), Petrovich's belief (`[[WB-5]]`), the
    aircraft client and the speech path. A separate service would duplicate them or need a second
    in-process import exception; living inside body-layer's process would not.
  - 0–3 wingmen, one usually. Perception is meant to be cheap and statistical (`[[WB-10]]`), and
    every command to DCS goes through the one mission-scripting bridge.
  - Each wingbrain needs its wingman's own state (position, heading, speed, altitude): a telemetry
    source for an aircraft that is not the player's, which `[[X-B21]]` named as the architectural
    difference from everything built so far.
  - The flight's mission understanding comes from Mission Interpreter, shared by every wingbrain.
