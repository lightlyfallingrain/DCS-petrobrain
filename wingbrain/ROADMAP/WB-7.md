# WB-7 — Player commands, stage 2: set target and engage

- [ ] **WB-7 — The player sets a wingman's target with "set target <unit> <where>", the same way
  as setting Petrovich's target, and orders the attack with "engage". The target is wingbrain
  state.** #status/open Filed 2026-11-19 from `docs/concept/wingbrain.md`, "Commands from player",
  stage 2. Needs `[[WB-4]]`, `[[WB-5]]` and `[[WB-6]]`.

  > *"Stage 2:*
  > *- attack commands:*
  >     *- "set target <unit> <where>" - in similar way as setting target to Petrovich*
  >         *- target is wingbrain internal state*
  >     *- "engage" - in similar way as command to Petrovich*
  >         *- AI wingman to engage set target"*

  Reuse Petrovich's existing target-setting wording and resolution rather than writing a second
  one (root `CLAUDE.md`, "Do not reinvent the wheel").
