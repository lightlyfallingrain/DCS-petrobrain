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

  ## What it is not

  **Not the slew *time* model.** §8's requirement — the sight takes time to move, so Petrovich
  cannot expect instant alignment — is satisfied inside `advance_sight_aim` by rate-limiting
  `actual` toward `desired` at the device spec's 20°/s azimuth and 10°/s elevation. That is
  body-layer only, needs no cockpit write, and belongs with `[[BL-B64]]`/`[[BL-B66]]`. This entry
  only makes the **real head follow** a pointing direction that is already correctly paced.

  Related: `[[BL-B66]]` (the switch half, unblocked), `[[BL-B63]]` (hard dependency),
  `[[BL-B64]]` (perception, lands first), `[[BL-B67]]` (the ATGM run, which is built out of this
  loop and cannot exist without it).
