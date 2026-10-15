# BL-B66 — The 9K113 sight, entry 2 of 3: effectors

- [ ] **BL-B66 — Make the real cockpit systems move: the warm-up sequence, OBSERV as an actual mode,
  the slew closed loop, and pinpoint-on-request. Everything that is visible to the pilot in the
  cockpit rather than only inside Petrovich's head.** #status/open
  **Specification: `docs/concept/9K113.md`** plus
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §5, §8.
  **Reconnaissance: `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`** — the full
  11-switch sequence, the 3–4 min and 10–15 s timings, and the device/command/argument numbers.

  Minted 2026-10-15 from the `[[BL-B64]]` split (user direction §5: *"We'll then add actually
  manipulating the systems in cockpit"*). Entry 2 of 3; `[[BL-B64]]` is perception, `[[BL-B67]]` is
  the attack run. **Sequenced after `BL-B64` and before `BL-B67`, by his explicit ordering.**

  ## Slewing is a *rate* command, so pointing the sight is a control loop (direction §12)

  **This is the single most consequential constraint on this entry, and it is not what the first plan
  assumed.** The sight is slewed by a joystick-like device whose axes command angular **speed**:

  > *"The axis input is the slew *speed*. Not desired angle, but angular speed of slew. To get it to
  > where we want to point it… we need a constant inspect and adapt loop to happen so that we check
  > whether the sight is where we want it and if not we command angular velocity in desired
  > direction. There's a maximum to angular velocity of course, and that is why it takes time to move
  > the 9K113 from one point to another."*

  So **"point the sight at X" is not an action with an argument — there is no angle to write.** Read
  where the sight is, compare against where it should be, command an angular *velocity*, repeat until
  converged. **Slew time is the consequence of a rate limit inside the loop, not a delay to wait
  out.** Four consequences, all design constraints rather than observations:

  1. **The sight's current angle must be readable every iteration**, or the loop has no feedback term
     and cannot close. **This promotes the probe below from useful to load-bearing for this stage.**
  2. **Loop rate is a correctness property, not a performance preference.** A rate-commanded loop
     closed at body-layer's current 1 Hz would **overshoot every time**. That makes `[[BL-B63]]`'s
     selective fast lane a **hard dependency of this entry**, not the optional optimisation its entry
     reads as — the same mechanism it was already filed for (missile guidance), arriving one stage
     earlier than it expects.
  3. **What we command is *deflection*, not a rate, and there is no maximum-rate constant to know**
     (§12a: *"we do not need to know it, actually. DCS limits it and we just command the 'joystick'
     deflection. At max deflection the sight moves as fast as it can."*). **The command side needs no
     calibration at all** — nothing has to establish what a unit of deflection means physically,
     which removes one measurement from the probe below and one number that could drift between DCS
     versions. **The feedback half is untouched**: without the current angle there is no error term.
  4. **The plant is unknown, so the loop is purely reactive.** It cannot predict where the sight will
     be after a command, only observe where it ended up — no feed-forward, no time-to-target
     estimate. **Proportional deflection, not bang-bang**: full deflection until the error flips sign
     chatters, while reducing deflection as the error shrinks settles, and needs no knowledge of the
     rate because the error *is* the signal. **The empirical constants are the
     deflection-versus-error response and a deadband**, and those belong in `X-T26`'s tunable set
     (`body-layer/config/defaults.toml`, `src/tuning.py`).

     **One caveat for this stage's own plan:** proportional control against an unknown plant with a
     one-poll feedback delay can still limit-cycle, so **the deadband is load-bearing rather than a
     refinement** — and it cannot usefully be finer than the readout's resolution, which is why the
     probe has to report arg 876's read *granularity*, not only that it is readable.

  **What `[[BL-B64]]` is doing to make this cheap.** Per the user — *"We don't need this modeled
  before the effectors, but we must be ready for how it will work with the effectors so we don't have
  to redo much of the mechanism"* — the perception entry keeps **desired aim** and **actual sight
  direction** as two distinct fields, with `actual := desired` instantly. **This entry is then a
  controller inserted at one existing call site** (`advance_sight_aim()` in `logger.py`), not a
  refactor. If `BL-B64` ships with those collapsed into one value, that collapse is the rework this
  direction exists to avoid — check it before starting here. Plan §15a.

  ## The probe that is owed, and it belongs here rather than earlier

  **Run an `investigator` pass before this entry is planned, not before `BL-B64`.** It is
  **load-bearing for the slew loop** (consequence 1 above), not merely useful. The question:

  - Can `performClickableAction` actually move args **673 / 955 / 885 / 886 / 963** on **`WEAP_SYS`
    (device 6)** and **`I9K113` (device 7)**, and does the lamp state follow?
  - Does `list_indication` on `ccGunnersCPanel` (**index 8, never tried**) read the `READY` lamp?
  - **Can the sight's current angle (args 874/876) be read at loop rate, and at what resolution?**
    Added 2026-10-15 from §12/§12a — **this is the loop's feedback term**, so a negative answer does
    not merely degrade this stage, it means the loop cannot close as designed and the stage needs a
    different plan. The *resolution* matters because it floors the deadband (consequence 4 above).
    **Note what this question is no longer:** it is not *"what is 876's degrees-per-unit"*, because
    §12a removes the need to convert a command into physical units — only the error term needs to be
    readable and comparable, not calibrated.
  - Can the OBSERV readout (arg **886**) be sampled at loop rate?

  **Why it is not run yet.** The write channel is proven live only on **device 30** (the AI wheel)
  and **device 55** (SPU-8) — every argument number in the warm-up table is cross-referenced from a
  2026-09-11 probe of a *different device set*, and the numbers are **positional**, so an ED patch
  inserting a table entry shifts them. Regenerate before coding against them. This is the single
  largest risk in the 9K113 series and the whole reason perception was separated out ahead of it.

  ## What this entry contains, in dependency order

  1. **The cockpit-action channel.** A new `op` on `Export.lua`'s existing inbound command listener
     (`poll_command_socket`, which already dispatches `petrovich_search` and already calls
     `performClickableAction` live), plus 9K113 state args **874/876/886** pushed as telemetry with
     the change-epsilon pattern `push_spu8_state` established. Spans
     `aircraft-layer/dcs-export/Export.lua`, `src/collector/command_sender.py`, `src/api/server.py`,
     `src/schema/`, and `body-layer/src/aircraft_client.py`. **HTTP/JSON across the subproject
     boundary**, as aircraft-layer ↔ body-layer already does.
  2. **Warm-up and OBSERV as real modes.** The 3–4 min and 10–15 s timings are **two timers** — the
     research note is explicit that collapsing them is wrong — with the *"Guidance unit ready"* and
     *"Observ on/off"* callouts, and the constraint that OBSERV is not left on. **If the lamp probe
     comes back negative, readiness is a timer Petrobrain owns**: honest, and the manual itself
     presents the timing as elapsed-time gates.
  3. **The slew closed loop** — reading args 874/876 back and writing the AI axis (3060/3061).
     876's degrees-per-unit is unmeasured — but per §12a **that no longer blocks anything**, since
     the command is a deflection and needs no physical calibration; only the readout's availability
     and resolution matter. Note that the AI axis (3060/3061) is *position* while the player axis
     (3025/3026) is *velocity* — do not generalise one from the other, and note that **§12 says the
     crewman's own control is a velocity command**, so which of those two axes this loop should drive
     is itself an open question for this stage's plan rather than a settled choice. Needs
     `[[BL-B63]]` first (consequence 2 above).
  4. **Pinpoint-on-request** — the surviving non-ATGM use.

  ## What this entry does *not* contain

  - **The ASP-17 crosshair-hold use case. It does not exist as work.** User direction §1:
    *"ASP-17 must not be manipulated directly. It shows the pilot where the 9K113 is pointing, but
    that's automatic, not manual."* The mark follows the sight's pointing by itself, so there is no
    action to build, no `AUTO/MAN` switch step (arg 553) and no PUVL selector step (arg 523) needed
    for it. It is a **consequence** of this entry, not a deliverable of it. The earlier plan treated
    it as one of two non-ATGM uses; that was wrong and is marked superseded in
    `plans/9k113-sight/plan.md`.
  - **Nothing of the slew is deferred *out* of this entry.** An earlier draft of the plan recommended
    a slew rate limit live in `BL-B64`; **§12 overrode that** — a rate limit would have been the
    wrong mechanism, not merely an early one, since the real thing is a closed loop. `BL-B64` carries
    only the desired/actual field split that lets this entry's controller slot in.
  - **`[[BL-B65]]`** (the weapons safety circuit switch, arg 673) stays its own entry, as the
    specification requires, and gates `[[BL-B67]]`.

  ## Acceptance is unusually expensive, and that shapes the work

  **~3 minutes of warm-up before anything is testable**, plus a failure mode the specification does
  not model: a gyro toppled by an excessive-rate manoeuvre needs `GUID.UNIT POWER` cycled and
  **another 3–4 minutes**. A single mistake mid-test costs a full reset. **Budget acceptance in
  sorties, not in attempts, and build the flag-gated debug logging up front** rather than bolting it
  on after the first failed sortie.

  ## Second-order effect

  If built, this makes the cockpit-write channel a **general facility**: the SPU-8 and AI-wheel
  channels are each one-off, and a sequenced switch-action op would be the first reusable one, which
  `[[BL-B65]]` and anything else cockpit-side would inherit.

  Related: `[[BL-B64]]` (entry 1, perception — must land first, and owes this entry the
  desired/actual field split), `[[BL-B67]]` (entry 3), `[[BL-B65]]` (gates entry 3),
  `[[BL-B63]]` (**a hard dependency of this entry as of direction §12** — a rate-commanded loop
  cannot close at 1 Hz; `AC-B3` remains *not* a prerequisite, the dependency runs the other way).
