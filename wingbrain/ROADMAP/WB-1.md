# WB-1 — Wingman control recon: what DCS lets a script command an AI wingman to do

- [ ] **WB-1 — Find out how a script can set an AI wingman's speed, heading and altitude while it
  flies, and how it can make the wingman engage one given unit, with a given weapon if possible.
  Reconnaissance only: findings to `wingbrain/research/`, probes allowed, no pipeline code.**
  #status/open Filed 2026-11-19 from `docs/concept/wingbrain.md`, "Prerequisites". An
  investigator task.

  **Moved here from `[[X-B41]]` on 2026-11-19**, when wingbrain got its own roadmap. X-B41 asked
  the same question in general terms (*"investigation into how and what we can command DCS AI
  wingman units to do"*, user, 2026-11-17); this entry adds the concept's two concrete goals. It
  takes a new ID because an ID belongs to one directory's sequence.

  ## Flight parameter control

  > *"Goal: find a way to control wingman speed, heading, altitude dynamically via lua."*
  >
  > *"Either by writing some parameter that DCS AI then flies or likely by using a dynamic waypoint
  > to set these parameters. If dynamic waypoint, then something like this:*
  > *- insert steering waypoint as next waypoint*
  > *- set it 1.5 km away in desired heading -> heading control*
  > *- set desired altitude and speed*
  > *- when waypoint closer than some limit (800m?) reset it to 1.5 km away*
  > *- when desired params change (or there is need to correct AI wingman drifting, update the
  >   waypoint"*

  Answer, for each candidate mechanism: does a wingman in the player's group accept it, does it
  leave formation and come back to it, how fast it reacts, and what it does to the group's route.
  Also: how to hold at a point (orbit, or hover for a helicopter), which `[[WB-3]]` needs.

  ## Attack control

  > *"Goal: find a way to set target and engage it from lua."*
  >
  > *"We need to find a way to specify which target AI engages and command engagement. - if
  > possible, what weapon to use. I have no idea how this can be done, needs investigation."*

  Answer: can the wingman be told to attack one unit by its DCS id, can the weapon be chosen, and
  how much of *how* it attacks (direction, altitude, number of passes) a script can set. The
  concept expects the last to be mostly out of reach.

  ## Already known, to start from

  - The mission-scripting bridge exists and has shipped since 2026-09-13: `net.dostring_in` from
    a hook script, polled at 1 Hz by the F10 command hook
    (`aircraft-layer/research/2026-09-22-mission-bridge-already-shipping.md`). Commands to a
    wingman's controller would go the same way.
  - `[[WB-3]]` needs the flight half only; `[[WB-6]]` needs the attack half. Either can be
    reported first.
