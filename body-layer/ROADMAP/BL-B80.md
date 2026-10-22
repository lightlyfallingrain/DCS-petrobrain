# BL-B80 — The 9K113 pointing loop: pointing the sight on the AI axis

- [~] **BL-B80 — Drive the sight head to Petrovich's modelled aim by closing a loop on the AI axis
  (3060/3061), a position target that works only while DCS's own AI Petrovich is on and only while
  re-asserted every frame.** #status/in-progress Split out of `[[BL-B66]]` on
  2026-10-17 by user direction (*"OK to split BL-B66, do not start working on it yet"*), after the
  slew probe settled which channel exists. **The channel changed from the player axis (3025/3026)
  to the AI axis (3060/3061) after the 2026-10-21 probes — see the SUPERSEDED block immediately
  below.** This heading used to still say "player axis"; it did not, and the body text already
  carried the correction — fixed here by the 2026-10-22 DoD pass on Stages 1-3.

  **Re-planned 2026-10-22: `plans/9k113-sight-pointing/plan.md` (v2 — simulated sight is
  Petrovich's sight, DCS sight slaved to it). The status block below describes the v1 build
  (`plan-v1-position-model.md`); its Stage 4 sortie is not to be flown.**

  ## Status, 2026-10-22 — Stages 1-3 built, Stage 4 (live sortie) outstanding

  `feature/9k113-sight-pointing` (tip `8b2967008f7654f41be52d2779cc430c5605c32d`) implements the
  elevation calibration + carried-forward `home_phase` fix (Stage 1), the Export.lua per-frame
  sight owner + `sight_target` wire op + AI-on/off detector (Stage 2), and the body-layer
  write-through + readback-preferring `advance_sight_aim` (Stage 3) — `plans/9k113-sight-pointing/
  plan.md`. DoD passed all mechanical checks (ruff/mypy --strict/pytest clean both subprojects,
  `luac5.1 -p` clean) and confirmed both Reviewer required-fix rounds and all Security/Performance
  verdicts are APPROVED. **Not yet merged to `main`** — Stage 4, the live sortie, has not flown.
  Acceptance card: `docs/acceptance/2026-10-22-bl-b80-sight-pointing-sortie.md` (published artifact
  linked from DoD's report). **Not tagged `#needs-flight`** — that tag is for a shipped, merged
  change awaiting its sortie (`docs/TAGS.md`); this entry has not merged yet, so `#status/
  in-progress` ([~]) is the correct state. Add `#needs-flight` only if this ever merges before
  Stage 4 flies.

  **What Stage 4 must still verify, not yet checked by anything automated:**
  - The derived (not measured) elevation degree&harr;raw conversion, at the two mechanical stops
    (+20&deg;/&minus;15&deg;).
  - The gyro-alignment window (no spurious `ShowMenu`, no sight reports, for ~10s after OBSERV
    on).
  - No spurious `ShowMenu` in ordinary flight.
  - `home_phase` following DCS's own automatic OBSERV-off, not only the spoken command.
  - The overlay reopening after the pilot closes it by hand.

  **This blocks `[[BL-B67]]` (the ATGM run)**, which needs a trustworthy pointing channel and the
  verified elevation calibration as its guidance-accuracy baseline — per the plan's own
  "Second-order effect" section, a Stage 4 correction to the elevation formula must land here
  before `BL-B67` is planned, not after.

  > **SUPERSEDED AGAIN 2026-10-22 — read this block first; both blocks below predate it.**
  > Probe runs 1–10 (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md`, merged to `main` as
  > `6d6c99a9`) overturned the 2026-10-21 channel model:
  > - The AI axis (3061/3060) is a **rate** command at the spec rates (20°/s az, 10°/s el per
  >   unit), not a position target, with the overlay on or off. 874/876 echo the demand; the only
  >   readback is the ASP-17 mark (565/566, 555/556), inside the HUD field (~±4.3°).
  > - DCS **obeys it intermittently** (ignored 3–100+ s, invisibly, position-independent). A small
  >   fast **dither** on the command (0.6° at 8 Hz) kept it obeyed in runs 9–10. Stick park toggle
  >   and the overlay are not the gate.
  > - **Л5, arg 898** lights when gyro alignment is done (T+10 s after OBSERV on, five runs); arg
  >   **960** is very likely the guidance-unit READY lamp ([[BL-B66]] concluded it unreadable).
  >
  > **Design direction (explore, 2026-10-22, `plans/9k113-sight-pointing/explore-notes.md` on
  > `feature/9k113-sight-pointing`):** Petrobrain's simulated sight is Petrovich's sight (*"what
  > Petrovich could plausibly see with a sight that works as it should"*), held to gimbal limits
  > and maximum slew rate; the DCS sight is a best-effort slave with tiny dither always on; inside
  > the HUD, any trick that gets it on the simulated direction is allowed, and for ATGM the mark
  > must sit within ~0.02° (BTR at 3–4 km). Gate on 960 and 898. **The branch
  > `feature/9k113-sight-pointing` was built on the position model and is to be re-planned.**
  > **Run 11 (merged `d6ed947f`):** DCS takes the axis only when its value **changes** (pilot's
  > hypothesis, confirmed: constant 3/10, per-frame flicker 18/18). Holding with 0.6° / 8 Hz dither:
  > 0.006–0.013° RMS, inside the ATGM budget.
  > Status: probe phase closed; v2 plan on `feature/9k113-sight-pointing`, Stages 0–4 being built.
  >
  > **SUPERSEDED 2026-10-21 — read this block first; the text below it predates the finding.**
  > Probes flown 2026-10-21 (`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-findings.md`,
  > "Pointing probe runs 2–3") settled the channel. It is **not** the player axis and **not** a
  > rate loop. It is the **AI axis (3061/3060), an exact position target**: readback matched every
  > target to 0.1°, and the pilot saw the ASP-17 crosshair follow. Two conditions:
  > **DCS AI Petrovich must be on**, and **the target must be re-sent every frame** while we hold
  > the sight. With him off, writes are inert and 874/876 read 0. When we stop re-sending, he takes
  > the sight back. **`[[BL-B63]]` is therefore not a dependency.** The readback is trustworthy
  > under those conditions, so it serves as the check.
  >
  > **User direction, 2026-10-21, verbatim:**
  > *"These findings mean one additional thing: DCS Petrovich AI overlay *must be on* when
  > Petrobrain uses 9K113. We must ensure that in code. Turn AI overlay ON when with OBSERV ON and
  > make sure it keeps ON, even if player closes it, open it again immediately. Turn overlay OFF
  > with OBSERV OFF. Note that DCS AI may turn OBSERV OFF at too hard manouvres (or player can
  > turn any switch at any time), so OBSERV state in code must come from OBSERV state in DCS."*
  >
  > So, in scope here:
  > - **AI overlay follows the observed OBSERV state** (arg 886 readback), never the commanded one.
  >   On when OBSERV reads on, re-opened at once if closed, off when OBSERV reads off.
  > - **Open before planning.** The only known control is `ShowMenu` (device 30, cmd 3001), and it
  >   is a **toggle**. Keeping the overlay on therefore needs a readable "is it open" signal, or a
  >   blind toggle could close it. Candidate: whether `list_indication(10)` (the wheel, already
  >   exported as `petrovich_wheel`) is empty while it is closed. Unverified. Also unverified:
  >   whether closing the overlay is the same thing as switching his AI off.
  > - **Update, same day:** the wheel can't be the signal. User: *"Since we have to keep overlay
  >   open, I'd rather hide the wheel, it's possible in DCS settings. We need some other way."*
  >   **Proposed:** detect his AI from the pointing readback itself. If 874/876 stay 0 for ~0.5 s
  >   while the target is non-zero, his AI is off: press `ShowMenu` once and recheck. Aim 0.5° off
  >   a centre target, because centre reads 0 either way. The user confirmed: with the wheel hidden,
  >   `ShowMenu` still toggles his AI (*"yes"*), and one press reliably flips it (*"yes"*). Still to
  >   measure: how fast the readback obeys after he comes back on. Probe planned for 2026-10-22.

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
