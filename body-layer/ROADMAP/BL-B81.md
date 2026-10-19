# BL-B81 — Radio check

- [ ] **BL-B81 — Radio check: a command whose only job is to get an answer.** #status/open Raised
  by the user 2026-10-19, to be built after `[[BL-15]]`'s Stage 1.

  ## The user's request, as given

  > - Player: "radio check"
  > -> Petrovich: "loud and clear"
  >
  > Alternative
  > - Player "good morning|day|evening|night Petrovich"
  > -> Petrovich "good morning|day|evening|night commander"
  >
  > Why?
  > - if intercom is off, there's no response. This is an easy check that A) intercom is ON and
  >   volume good B) that Petrobrain is operational.
  >
  > Note: radio check does not end silent mode on ground.

  ## What it has to fit

  - **It is just another command — silence is not touched.** First read as "answers through
    silence without ending it"; **dropped by the user, 2026-10-19**: *"Radio check is usually for
    engine start sequence. Now that ground silence logic changes, let's not modify the normal
    silence, radio check is just another command."* With the on-ground silence default replaced by
    `[[BL-B82]]`, there is no silence on the ramp for it to work around. Like any command, it ends
    an explicit `silence`.
  - **Greeting echoes the pilot's word** ("good evening" → "good evening, commander"), not the sim
    clock.
  - **In `[[BL-15]]`'s refusal mode** (world model not loaded), every command answers "system error,
    world model not loaded". That answer serves the check just as well — the pilot hears that
    Petrobrain is up and what is wrong — so radio check takes the refusal like every other command.
  - Input surfaces: voice, crew-text, and F10 if a menu item is wanted.
