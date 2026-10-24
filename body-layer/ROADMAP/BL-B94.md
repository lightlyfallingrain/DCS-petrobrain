# BL-B94 — A named, checked catalogue of state params (light level as the example)

- [>] **BL-B94 — Expose body state as a named, typed, documented catalogue of read-only params, the
  vocabulary `[[BL-B95]]`'s scripts will read.** #status/deferred Filed 2026-10-23 at user direction
  from the behaviour-trees explore (`plans/behaviour-trees/explore-notes.md`).
  **Rescoped 2026-10-24**, and deferred.

  **History.** Filed as "parameter comparisons in effector-sequence conditions", with the user's
  dome-light rules as the proof of concept:

  - *"at start, if twilight or night, set dome light to white"*
  - *"takeoff, if twilight or night, set dome light to red"*
  - *"guidance unit ready, set dome light off."*

  The next day the user settled that *"Tables are good for cockpit switches, they are like
  checklists. For behaviour, I'd want scripting language like lua."* The dome-light rule is
  behaviour, so the table condition syntax was dropped. Lua would replace it. What both routes need
  is what remains here: the param catalogue.

  **Deferred, user 2026-10-24:** *"the dome light is simply an example (though a nice touch), no need
  to actually build the light level things yet. There are more important things first."*

  **When this is picked up:**

  - Each param is a named, read-only query over **Petrovich's belief**, never DCS truth. This is the
    `Percept` boundary applied to scripts, and it is the easiest place for omniscience to leak in.
    Each has a declared type and value set.
  - The catalogue is generated into a reference file the way `config/sequences/triggers.md` is, and
    kept current by a staleness test.
  - The light level is the worked example, approximated from sun position (*"light level outside,
    but we probably cannot get that from DCS, but we might get sun position"*). Unverified whether
    DCS exposes sun position, or the date, time and location to compute it. That needs an
    investigator pass.
  - The dome light is `LTG-COCKPIT-OP-PTR`, arg 682, `-1/0/1` for WHITE/OFF/RED. Which value is
    which colour is unverified.
  - The `guidance-unit-ready` trigger is not here. It is already an open `[[BL-B90]]` point.

  Until then, new code follows root `CLAUDE.md`, "Behaviour as actions and params", so params exist
  as named queries when this catalogue is built.
