# BL-B83 — Point the idle 9K113 at the mission objective area when it is within range

- [>] **BL-B83 — With `observ on` and no commanded scan sector, the idle sight should search the
  mission objective area when it is within range, before falling back to the flight direction.**
  #status/deferred User direction, 2026-10-20 (`docs/acceptance/2026-10-20-sortie-feedback.md`,
  F4/F5): aim priority is *"1 commanded scan sector. Mission objective area if wihtin range,
  flight direction as normal default"* — and for the objective area, *"skip for now"*.

  Deferred because body-layer has **no mission objective area at runtime**: the Mission
  Interpreter's waypoints reach `mission_phase` (`[[BL-7]]`), which nothing in flight reads. A
  waypoint is not an objective, so using the next waypoint as a stand-in was not chosen.
  Needs an objective-area datum from the Mission Interpreter before this can be built.
