# BL-B80 — The 9K113 slew loop: pointing the sight on the player axis

- [ ] **BL-B80 — Drive the sight head to a commanded bearing by closing a loop on the player slew
  axis (3025/3026), which is rate-commanded.** #status/open Split out of `[[BL-B66]]` on
  2026-10-17 by user direction (*"OK to split BL-B66, do not start working on it yet"*), after the
  slew probe settled which channel exists.

  **Why it is its own entry rather than a stage of `[[BL-B66]]`.** The switch half of `BL-B66` is
  unblocked and buildable today — all five writes measured working. This half is blocked on
  `[[BL-B63]]`, needs a controller with an empirical deflection law, and needs one more probe run
  before any law can be fitted. Keeping them together would hold working code behind an unbuilt
  milestone, which is exactly the scope caution `plans/9k113-effectors/plan.md` raised against
  itself.

  ## What the probe settled, 2026-10-17

  `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`:

  - **The AI axis (3060/3061) is inert.** Five bearings and twelve staircase steps per axis, two
    runs, one with the aircraft correctly set up and `OBSERV` confirmed on — args 874/876 never
    left `0.00000`. Every call returned `ok=true`, so the return value distinguishes nothing.
  - **The player axis moves the head**: ~45° of azimuth in one ~3 s hold at 0.5 deflection
    (13–16°/s), elevation the same shape and sign-inverted, in the same run and through the same
    `SetCommand` path seconds after the AI axis did nothing.
  - **The user prefers this channel on its own merits**, not only by elimination — *"I much prefer
    the player axis approach"* (`docs/acceptance/2026-10-17-9k113-procedures-direction.md`). So
    the `BL-B63` dependency is a cost accepted knowingly, not one imposed by a negative result.

  ## Hard dependencies

  - **`[[BL-B63]]` — the fast lane.** A rate-commanded loop cannot close at 1 Hz. This is the
    dependency `BL-B66`'s entry carried under direction §12, which `plans/9k113-effectors/plan.md`
    §0 argued away on the strength of the 2026-09-11 AI-axis measurement; the probe restored it.
  - **One more probe run before a deflection law is fitted.** The slew probe sampled four times per
    hold and saw two plateaus rather than a ramp, so nothing separates *"the readback is quantised
    or lagged"* from *"the motion is stepped"*. The fix is per-frame logging of args 874/876 — a
    one-line change to `Export.probe-9k113-slew.lua`, not a new script.

  **The extra probe run may come free, 2026-10-21.** `BL-B66` Stage 4b adds per-frame logging of
  args 874/876 and a slot for the 3025/3026 command (user: *"Put logging in so that the slew loop
  can be adjusted based on data from logs. Actual vs desired angles especially, slew command
  values, etc."*), and the `BL-B66` sortie includes ~2 minutes of hand-slewing. If that log
  separates quantised / lagged / stepped readback, the probe above is done. **This entry must fill
  the command slot and add its loop internals** (deflection chosen, error, deadband in/out,
  converged) to the body-layer sight trace, so the loop is tuned from logs, not guessed.

  ## What it is not

  **Not the slew *time* model.** §8's requirement — the sight takes time to move, so Petrovich
  cannot expect instant alignment — is satisfied inside `advance_sight_aim` by rate-limiting
  `actual` toward `desired` at the device spec's 20°/s azimuth and 10°/s elevation. That is
  body-layer only, needs no cockpit write, and belongs with `[[BL-B64]]`/`[[BL-B66]]`.
  **Superseded 2026-10-21 (user direction, *"yes"*): the slew-time model moves *into* this
  entry** — `BL-B66` keeps `advance_sight_aim` a pass-through, and the model lands here beside the
  loop whose readback replaces it (`plans/9k113-effectors/explore-notes.md`, point 3). This entry
  only makes the **real head follow** a pointing direction that is already correctly paced.

  ## Field-of-regard limits: DCS enforces them once this lands

  **User direction, 2026-10-21**, on DoD's finding that `9k113-narrow-search` was the fourth time
  the simulated ±60°/+20°/−15° regard check shipped wrong (`notes/the-9k113-sight-bl-b64.md`):

  > *"DCS will enforce it. I'd rather rely on the real limits than simulation of them. Simulation
  > is just a temporary phase while the effectors are not build. Of course the logic behind where
  > we want to point the sight must behave correctly."*

  So the body-layer regard check in `belief/optic_policy.py` is a **stand-in** for the mechanical
  limits, needed only while no real head moves. Once this loop drives the head, the head stops
  where DCS stops it. What stays Petrovich's job is the **pointing intent** — choosing a sensible
  direction to look. Do not invest in hardening the simulated enforcement further.

  **What becomes of the simulated check when the loop lands — decided, user, 2026-10-21:** keep
  only enough of it that the intent never asks for a direction the head cannot reach (otherwise the
  loop chases a target it can never hit). In his words:

  > *"keep enough of it that Petrovich never asks for a direction the head can't physically reach
  > -> this. The +-60 azimuth limit especially. Might leave the vertical limit out, since that's
  > difficult for a real operator to judge."*

  So: **±60° azimuth stays as an intent constraint** — an operator knows where the head's side
  stops are. **The +20°/−15° elevation limits are likely dropped** from intent, because a real
  operator would not judge them reliably; DCS's own stop handles them. "Might" — the elevation
  half is his leaning, to be confirmed when this entry is planned, not a settled removal.

  Related: `[[BL-B66]]` (the switch half, unblocked), `[[BL-B63]]` (hard dependency),
  `[[BL-B64]]` (perception, lands first), `[[BL-B67]]` (the ATGM run, which is built out of this
  loop and cannot exist without it).
