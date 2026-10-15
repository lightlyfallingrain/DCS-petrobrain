# BL-B74 — A SAM launch's smoke trail shows where the launcher was

- [ ] **BL-B74 — `S_EVENT_SHOT` admits the launcher at `PRESENCE`, at its launch-time position, for
  a tunable dissipation period after the event ends — the first perception source with a decaying
  external lifetime.** #status/open Split out of `[[BL-B72]]` at Architect stage, 2026-10-15 —
  `plans/emitter-visibility/plan.md` Stage C, Decision 2. User direction: *"SAM missiles leave smoke
  trail, so that especially gives away the launcher position. Pick a constant to simulate smoke
  trail dissipation -> SAM launch shows where the launcher was for quite a while."*

  **`S_EVENT_SHOT` is the right event here and `SHOOTING_START` is not** — the former covers
  missiles and explicitly excludes machine-gun/autocannon fire, which is exactly the opposite split
  from `[[BL-B73]]`'s and happens to be what each half needs.

  **Three design points, from the plan:**

  - **The position is frozen at event time and never rewritten.** It reveals where the launcher
    *was*, not where it is — a TEL that drives away must not drag the sighting with it. Applied by
    `dataclasses.replace()` on the candidate, never fresh construction.
  - **The smoke outlives the launcher.** A launcher destroyed seconds after launch is the normal
    case under attack, so the entry needs to survive the world object disappearing — a synthetic
    candidate minted from the emitter record. This is the one asymmetry with `[[BL-B73]]`, where a
    dead unit's firing entry is removed immediately.
  - **`LAUNCH_SMOKE_DISSIPATION_S` is behaviour-affecting and wrong in both directions**: too short
    and the pilot never gets the warning, too long and Petrovich keeps pointing at smoke. `tuning.
    real`, `status="judgement"`, retuned by a sortie.

  Blocked on `[[AC-B8]]` and on `[[BL-B73]]`'s collector state machine.

  Related: `[[BL-B72]]`, `[[BL-B73]]`, `[[AC-B8]]`, `[[BL-2]]`.
