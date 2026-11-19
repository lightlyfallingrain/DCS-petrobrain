# WB-6 — Attack control: engage a given unit, with a given weapon if possible

- [ ] **WB-6 — A wingbrain can make its wingman engage one given unit, chosen by DCS id or
  similar, and choose the weapon if DCS allows it.** #status/open Filed 2026-11-19 from
  `docs/concept/wingbrain.md`, "Attack control". Needs `[[WB-1]]`'s attack half.

  > *"We need to be able to specify which unit(s) AI wingman is to engage. Preferably by setting a
  > certain unit by DCS id or something like that. It is ok to break no-omniscience rule to
  > accomplish this. We need to get AI to engage that target. If possible control *how* AI engages
  > it, but likely that is outside what we can do from lua."*

  **The no-omniscience exception is narrow:** it covers handing DCS the unit's id so the AI
  engages the right thing. Which units a wingbrain knows about still comes from its belief
  (`[[WB-5]]`, later `[[WB-10]]`).
