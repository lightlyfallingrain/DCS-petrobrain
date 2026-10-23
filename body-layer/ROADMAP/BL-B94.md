# BL-B94 — Parameter comparisons in effector-sequence conditions (dome-light POC)

- [ ] **BL-B94 — Let a sequence-file `condition` compare a named state parameter, not only a
  switch, starting with an outside light level so the operator dome light follows day and night.**
  #status/open Filed 2026-10-23 at user direction, from the behaviour-trees explore
  (`plans/behaviour-trees/explore-notes.md`, rounds 4 and 5, and its "Decision" section). Builds on
  `[[BL-B90]]`; do not start before BL-B90 merges.

  > *"We'll stick with effector sequences for now and add parameter comparisons there, see the light
  > level example. That is a good POC for the decision trees as well."*

  **The user's example, verbatim:**

  - *"at start, if twilight or night, set dome light to white"*
  - *"takeoff, if twilight or night, set dome light to red"*
  - *"guidance unit ready, set dome light off."*

  **What it needs that BL-B90 does not have:**

  1. **Conditions on state params.** Today's grammar is `<effector> = <value>` / `!=` only
     (`effector_sequences.py`, `_CONDITION_RE`). Add comparisons on named params (`=`, `!=`, and
     ordered comparisons for numeric ones, e.g. `agl_m > 10`). The params form a small, explicit,
     documented catalogue, generated into a reference file the way `triggers.md` is and checked by a
     staleness test.
  2. **A light-level param.** *"light level outside, but we probably cannot get that from DCS, but we
     might get sun position that would allow us to approximate light level"*. Values roughly
     day / twilight / night, derived from sun elevation. **Unverified: whether DCS exposes sun
     position, or the mission date, time and location to compute it.** Needs an investigator pass
     first.
  3. **A `guidance-unit-ready` trigger.** Already an open BL-B90 decision (*"it should really be it's
     own trigger for a sequence file"*). The 960 READY lamp edge currently speaks from code.
  4. The dome light itself: `LTG-COCKPIT-OP-PTR`, arg 682, WHITE/OFF/RED, `-1/0/1` in
     `config/sequences/mi-24p/switch-reference.md`. Which value is which colour is unverified.

  **Shape constraint, so this stays a step towards `[[BL-B95]]`:** each param is a named read-only
  query over body state with a declared type and value set. It is not ad-hoc parsing inside the
  sequence engine, so a future behaviour tree can read the same catalogue unchanged.

  Done when the three dome-light rows run from a sequence file in a flight, at night and by day.
