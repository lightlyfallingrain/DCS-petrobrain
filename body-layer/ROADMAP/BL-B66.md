# BL-B66 — The 9K113 sight, entry 2 of 3: effectors

- [ ] **BL-B66 — Make the real cockpit systems move: the guidance-unit power-up sequence, OBSERV
  as an actual cockpit mode, and the weapon safety bar. Everything that is visible to the pilot in
  the cockpit rather than only inside Petrovich's head.** #status/open
  **SCOPE NARROWED 2026-10-17** (user direction, *"OK to split BL-B66"*): **the slew loop left
  this entry and is now `[[BL-B80]]`**, because it is blocked on `[[BL-B63]]` and this half is not.
  Pinpoint-on-request rides the slew loop and went with it.

  **The procedures are the user's, not the PDF's** —
  `docs/acceptance/2026-10-17-9k113-procedures-direction.md`, captured verbatim, supersedes
  `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`'s 11-switch table where they
  disagree. In his own words, the power-up is five switches: `MISSILE POWER`, `CPLR DISTR`,
  `Sight Power`, ЩО `PWR` B1, `L166V POWER`. **It is `Sight Power` that starts the 3–4 minute
  warm-up**, not ЩО `PWR` as the recon note has it. `OBSERV ON` needs `Sight Power` on, warm-up
  elapsed (`READNS.` lamp) and then an `X s` gyro wait — `X` is still open. **`OBSERV OFF` is one
  write and nothing else**: DCS boresights the sight, closes the doors and safes the gyros itself.
  The safety bar is pilot-commanded both ways, plus ARMED automatically at any attack-run start.

  **Two of the five switches have no known argument.** `CPLR DISTR` and `L166V POWER`: both
  name-match guesses were withdrawn by the user the same day — 761 sits on `ASP_17V`, the pilot's
  sight, so it is wrong by construction; 870's row disagrees with itself and the ЩО's `TEST LAMPS`
  is 956, not 870. **Settle them by reading arguments while the user throws each switch by hand**,
  not by clicking or by more table archaeology.

  **`CPLR DISTR` is the operator's** — user direction, 2026-10-17, placing it physically: *"right
  above missile power. right of FDI and left of OPER/TEST1/TEST2."* That adjacency matches
  `WEAP-DISTR-POWER-OP-PTR` (761) with `WEAP-DISTR-CONTROL-OP-PTR` (762) on its right, so **761 is
  reinstated as the probable mapping** after being withdrawn earlier the same day — his rejection
  was conditional on it being pilot-side, and the device column names the owning Lua device, not
  the seat (today's probe wrote operator panels from the pilot's seat). Still unverified; the
  read-probe settles it. **So all five power-up switches are the operator's and the sequence waits
  on nobody.**

  **Petrovich is the copilot, so pilot-side steps are not his** (user direction, 2026-10-17: *"The
  quickstart guide includes steps that the pilot does, like the ASP-17 switches. For now Petrovich
  is copilot only."*). Every `ASP_17V` row drops out, including the recon table's `AUTO/MAN` (553)
  and the PUVL selector (523). **Whether `CPLR DISTR` is operator-reachable is open, and it decides
  whether it belongs in this entry at all** — if it is pilot-side, the sequence either waits on the
  pilot or Petrovich asks for it, which is a behaviour question for the explore pass.

  **The warm-up is ~5 minutes, measured** (*"The guindace unit warmup took about 5 minutes, I
  measured."*) — longer than his own earlier 3–4 min and the recon note's 210 s program timer, and
  it supersedes both. Carried, not built against: the zero-warm-up direction still stands.
  **Specification: `docs/concept/9K113.md`** plus
  `docs/acceptance/2026-10-15-9k113-sight-direction.md` §5, §8.
  **Reconnaissance: `body-layer/research/2026-10-14-9k113-warmup-atgm-procedure.md`** — the full
  11-switch sequence, the 3–4 min and 10–15 s timings, and the device/command/argument numbers.

  **Probe flown 2026-10-17 — the switch question is ANSWERED, the sight question is not.**
  `Export.probe-9k113-effectors.lua`, card `docs/acceptance/2026-10-17-9k113-effectors-probe.md`,
  pilot's observations `docs/acceptance/2026-10-17-9k113-effectors-probe-results.md`.

  - **`performClickableAction` moves cockpit switches on devices 6 (`WEAP_SYS`) and 7 (`I9K113`)
    from the pilot's seat, against the operator's panels** — neither device had ever been written
    to. User's reading, and the operative one: *"several swithces moved -> assume we can move
    all."* Stage 2's switch sequence is buildable.
  - **The warm-up *sequence* this probe wrote is wrong, and is deliberately left wrong for now** —
    *"Let it be, we'll fix later. I can setup the warmup for now."* Writing a switch and ordering
    the procedure are different questions; only the first is answered.
  - **A switch write animates over ~3 frames** (`0.32 → 0.64 → 1.00`), so a readback taken
    immediately catches an intermediate value. The project's own 1 s inter-switch delay covers it.
  - **The `READY` lamp is not readable.** `list_indication(8)` (`ccGunnersCPanel`, never tried
    before) returns 0 bytes powered or not; `list_indication(0)` returns the sight viewport's
    element tree and key-binding help, byte-identical before and after power. A `Ready_9k113` node
    exists in that tree carrying no value. **Finding 2's `list_indication` workaround is closed as
    unavailable** — readiness stays a self-run timer.

  **Decision 1 is ANSWERED by the slew probe, 2026-10-17, and it inverts the plan's
  recommendation** (`aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`):

  - **The AI axis (3060/3061) is inert.** Five bearings and twelve staircase steps on each axis,
    in two separate runs, one with the aircraft correctly set up by hand and `OBSERV` confirmed
    on — args 874/876 never moved off `0.00000`. Every call returned `ok=true`, so the return
    value distinguishes nothing.
  - **The player axis (3025/3026) moves the head**, in the same run, same device, same
    `SetCommand` path, immediately after the AI axis did not: ~45° of azimuth in one ~3 s hold at
    0.5 deflection (13–16°/s), elevation the same shape and sign-inverted.
  - **So the rate loop is mandatory, not optional, and `[[BL-B63]]`'s fast lane is a hard
    dependency again** — as this entry said under direction §12 before `plans/9k113-effectors/
    plan.md` §0 argued it away on the strength of the 2026-09-11 AI-axis measurement. That older
    measurement is not overwritten: two live passes disagree and the reason is unknown.
  - **The plan's own scope caution now applies**: narrow this entry to the switch sequence and
    `OBSERV`, which are unblocked and buildable today, and file the slew loop as its own entry
    gated on `BL-B63`.
  - **The slew half left this entry on the strength of that**: `[[BL-B80]]`, with the `BL-B63`
    dependency and the one remaining probe run attached to it rather than to this one.

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

  ## Amended 2026-10-15 — architect pass: `plans/9k113-effectors/plan.md`

  **Planned. Two changes to what is written above, both by evidence rather than opinion.**

  **1. Zero warm-up, by user direction this session:** *"ignore until effectors built. Prepare code
  for it, but use no warmup time."* So the 3–4 min and 10–15 s timers above are **not built**, and
  the ЩО `READY` lamp is not modelled. The 11-switch table's **ordering and device/arg numbers stay
  structural** (they are what Stage 2 throws); only the *elapsed-time* gates are dropped. Readiness
  takes `advance_sight_aim`'s own seam shape — a named predicate answering "ready" immediately with
  one obvious place for a duration or a lamp read to land later. **The "acceptance is unusually
  expensive" section above no longer applies** — that was this entry's biggest cost driver.

  **2. The channel choice above assumes the rate loop; the repo already refutes its premises.**
  `aircraft-layer/research/mi24p-command-surface.md` §4.1.2 + its CORRECTION (2026-09-21) measured
  the **AI axis (3060/3061) live at five points** as an exactly linear *position* target, ratio
  `0.440000`, settling inside 0.25 s — *"pointing is a **single write** — no closed loop"* — while
  saying of the player rate axis *"**do not use it as an effector**"* and recording that generalising
  between the two channels **cost two probe flights**. The maximum rate is also not unknown:
  `Devices_specs/9K113.lua` publishes `h_axis_velocity = rad(20)/s`, `v_axis_velocity = rad(10)/s`.

  **§12 is not contradicted** — it describes how the *crewman* slews, and that stays the modelled
  behaviour; §8's slew time is delivered by rate-limiting `actual` toward `desired` inside
  `advance_sight_aim`, in body-layer, with no cockpit write involved. What is open is only which DCS
  command id we write, which this entry already called *"an open question for this stage's plan."*
  **It is now Decision 1 of the plan, recommending the position axis.**

  **Consequence for `[[BL-B63]]`: its hard-dependency status is *conditional on that decision*** and
  disappears under the position-axis answer, along with the controller, the deflection/deadband
  tuning pair, the limit-cycle risk and the feedback half of the probe.

  ## Second-order effect

  If built, this makes the cockpit-write channel a **general facility**: the SPU-8 and AI-wheel
  channels are each one-off, and a sequenced switch-action op would be the first reusable one, which
  `[[BL-B65]]` and anything else cockpit-side would inherit.

  Related: `[[BL-B64]]` (entry 1, perception — must land first, and owes this entry the
  desired/actual field split), `[[BL-B67]]` (entry 3), `[[BL-B65]]` (gates entry 3),
  `[[BL-B63]]` (**a hard dependency of this entry as of direction §12** — a rate-commanded loop
  cannot close at 1 Hz; `AC-B3` remains *not* a prerequisite, the dependency runs the other way).
