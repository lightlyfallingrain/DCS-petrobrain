# BL-16 — one desired flight state, one mode authority: plan

Architect pass, 2026-11-20. Branch `feature/bl16-desired-state`, base `e4792254`.

**Amended 2026-11-20** with the user's answers (`explore-notes.md`, the last two sections, verbatim):
- **U1 answered, wait for Lua.** The readback is spoken only after Lua accepts. New subsection
  "3a. Waiting for Lua" (latency, deadline, timeout, speech order, gates). First needed in Stage 3.
- **U2 answered, yes.** A carried value the new mode cannot fly exactly is announced once, not
  urgent (section 3, "What it cannot fly").
- **U3 answered, the AI wheel's reference in both modes.** Desired heading is stored in the overlay
  course's reference. Mode 1 converts with the live variation `Heading − LoGetMagneticYaw`. Stage 1
  reports true and magnetic both, so the card settles which one the overlay uses.
- **Align and align for launch re-specified** (user's semantics): align is one-shot, read back from
  the overlay after `MODE_READ_SETTLE_S`; align for launch is continuous and the desired heading
  follows the overlay course while it runs. Manoeuvre table, unpark-during-manoeuvre, Co-moving
  Fields, Stage 4 and its card changed. Unpark or recovery now keeps the last aligned heading, not
  the measured one.
- **U4 answered, Stages 1 and 2 ship together on one card.** Their content is unchanged except the
  heading-reference reporting above.
- New open questions: U5 (readback latency), U6 (unpark in the second after an align press).

Inputs read in full: `explore-notes.md` and `alignment.md` (this directory), `docs/acceptance/
2026-11-20-sortie-feedback.md`, `body-layer/ROADMAP/BL-16.md` (open items), `plans/flight-control/
plan.md` (Decisions 13, 21–27, 32), `plans/flight-control/debug.md` (2026-11-20 reports),
`plans/flight-control/implementation.md` (the reset and fail-loud sections), and the code named in
the brief. The coordinator's mid-task note (mode 2 is Mi-24 specific, see "The mode-2 seam") is
part of the brief.

### Goal

Export.lua becomes the only place that holds **what Petrovich is trying to fly** (one desired
heading/turn, altitude with its reference, and speed) and **who is flying and how** (off / mode 1 /
mode 2). Mode 1's control law and mode 2's wheel presses both fly that one desired state.
Body-layer becomes guidance only: it turns spoken commands and its manoeuvre logic into numbered
requests on one channel, and reads the mode, the desired state and each request's
accept/refuse from the polled status.

### Verdict on the architecture call

**It stands.** Nothing found breaks it. Four refinements, each needed to make it work:

1. **Relative commands are resolved in body-layer; the wire carries absolute values only.**
   "Turn left 30", "climb 50" and "speed up" become an absolute heading, altitude or speed before
   they are sent. The readback then names exactly the value Lua will hold (E2). Lua stays a store
   plus two controllers, with no command grammar. Body-layer resolves against the desired-state
   mirror with its own unacknowledged requests applied on top (`predict_desired`, Stage 3). That
   prediction is used only to turn a relative command into an absolute one and holds no
   authority. It is a few hundred ms stale at worst, and the band covers that. (Amended for U1:
   the readback is no longer predicted. It is spoken from the accepted request, see 3a.)
2. **Mode 2's one-parameter-at-a-time rotation moves from body-layer into Lua.** The rotation
   needs to know every outstanding desired value at once, and those values now live in Lua.
   Keeping it in body-layer would mean keeping a second copy of the goals, which is the defect
   being removed.
3. **The `arm` message goes away.** Lua arms itself on every park edge while body-layer's lease is
   fresh, and the lease becomes an unnumbered heartbeat. Body-layer never states the mode, which
   is the user's rule. Q6 (after a restart while parked, an unpark gives the player the stick)
   follows from this: a reset clears the arm, and only a park *edge* sets it again.
4. **Align-for-launch's pre-align snapshot disappears.** The dive writes nothing to the desired
   altitude and speed, so they *are* the pre-align values. Only the heading moves: it follows the
   overlay course while the alignment runs (amended, user 2026-11-20). Recovery becomes "stop the
   dive and fly the desired state again, altitude first", on the last aligned heading. This deletes
   `FlightSnapshot`, `seed_recovery_goal` and most of `align_phase`.

One finding that changed the plan: **the heading reference was not settled.** Mode 1 flies true
heading (`LoGetSelfData().Heading`). Mode 2's overlay course, and the HSI the player reads, are
probably magnetic. On the Caucasus that is a 7.3° difference
(`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`, "The HSI check is still
owed"). Today's unpark seed already copies the overlay course into mode 1's true-heading law, so
an unpark may carry a 7° error *now* (fixed in Stage 3, when the unpark seed becomes desired with
the conversion). **U3, answered:** the desired heading is in the overlay course's reference, in
both modes. See "Heading reference" in section 1.

### The picture

```mermaid
flowchart LR
  subgraph BL[body-layer: guidance]
    V[voice rules + actions] --> R[request builder\nresolve relative, predict readback]
    W[launch watcher\npayload/AGL/IAS] --> R
    R -->|"POST /command/flight\n{epoch, seq, kind, ...}"| C
    L[lease every poll\n+ limits] -->|"POST /command/flight_lease"| C
    M[mirror: mode, desired, acks] --> V
  end
  C[collector] -->|UDP| FD
  subgraph EX[Export.lua]
    FD[flight_desired.lua\nauthority + desired + acks\naircraft-generic]
    FC[flight_control.lua\nmode 1 law\naircraft-generic]
    AW[ai_pilot_wheel.lua\nmode 2 consumer\nMi-24 only]
    FD -- desired, read every frame --> FC
    FD -- desired, read every overlay tick --> AW
    FC -- fc_mode edges, law settle writes --> FD
    AW -- parked_active, overlay set values, manoeuvre end --> FD
  end
  FD -->|"fd_* status 5 Hz"| C --> M
```

```mermaid
stateDiagram-v2
  OFF: off - player flies
  TK: taking (voice take, capture pending)
  M1: m1 - Petrovich, raw axes
  M2: m2 - Petrovich, AI overlay
  OFF --> TK: take request accepted
  TK --> M1: capture done - RESEED desired from law init
  OFF --> M2: park edge - RESEED desired from overlay once takeover settles; arm if lease fresh
  M1 --> M2: park edge - CARRY desired; self-arm
  M2 --> M1: unpark, armed, preconditions ok - CARRY desired (Q4 break finishes)
  M2 --> OFF: unpark not armed / refused - urgent "You have controls!"
  M1 --> OFF: release request / envelope / NaN / dead
  TK --> OFF: release / capture failed
  M2 --> M2: reset - desired reseeded from overlay, arm cleared (Q6)
  M1 --> OFF: reset - lets go
```

**The rule underneath (C1):** a change of *who* flies (off→anything) reseeds the desired state from
the aircraft. A change of *how* Petrovich flies (m1↔m2) carries it. A transition to off clears it.
Mode 2's own sub-modes (FLT/HVR/HVRT/CBTM) sit below the authority and never count as a mode change.

### 1. The desired state

**Lua, `flight_desired.lua`, one table `desired`** (a table, not locals, to protect the 200-local
budget):

| field | units / values | written by | meaning |
|---|---|---|---|
| `hdg_mode` | `"heading"` / `"turn"` / `nil` | requests, seed, law settle | `nil` = not yet known (gates HOLD) |
| `heading_deg` | 0–360, **the overlay course's reference** (U3) | `set`, seed, roll-out settle, align read, align-for-launch follow | the target heading (`hdg_mode="heading"`) |
| `turn_dir` | -1 / +1 / `nil` | `set` | direction of the change; `nil` = shortest way. Needed for break away's 180° |
| `turn_rate_deg_s` | deg/s, signed | `set` (break), seed (inherited turn), `turn` | with `heading`: the rate override (Decision 27), `nil` = normal rate. With `turn`: the continuous rate |
| `turn_style` | `"normal"` / `"break"` / `"break_away"` | `set` | mode 2's choice of presses. Mode 1 ignores it (the rate carries the meaning) |
| `alt_m` | metres | `set`, seed, hover step | target altitude, **exact** as commanded (E2) |
| `alt_ref` | `"agl"` / `"baro"` | `set`, seed | always explicit. Q3: body-layer sends `"agl"` unless "barometric" was spoken |
| `ias_kmh` | km/h, ≥ 0 | `set`, seed, hover hold | exact as commanded; mode 2's step snapping never written back (Q1a) |
| `stamp.hdg` / `.alt` / `.spd` | request seq | every write | which request last wrote each part: mode 2's priority, and "written after the take" protection |
| `manoeuvre` | `none`/`break`/`break_away`/`align`/`align_for_launch`/`launch_aligned`/`recovering`/`translate` | Lua only | what is running now. Reported, never written by body-layer |
| `manoeuvre_seq` | int | Lua | the request that started it |

**Aircraft limits shape the desired value; mode limits shape only how it is flown** (alignment,
"Which mode limits apply"). Body-layer clamps a mode-1 speed into [`MIN_IAS_KMH`, `MAX_IAS_KMH`]
and an altitude to the AGL floor **only when it writes the request in mode 1**, as today
(Decision 14). Mode 2's speed steps and 700 m radar cap are never written into the desired state.
A value carried across a mode change that the new mode cannot fly exactly (mode 2's "speed 0"
reaching mode 1) is clamped by the flying mode at the moment it flies it. The desired value is not
rewritten. What the pilot hears about that is U2 (answered yes: once, not urgent; section 3).

**Heading reference (U3, answered).** *"True vs magnetic - which ever the AI wheel uses should be
used in both modes."* So `heading_deg` is stored in whatever reference the overlay course is in,
and every heading body-layer resolves, sends or reads back is in that reference.
- **Lua owns the choice:** one constant in `flight_desired.lua`, `HEADING_REF` (`"mag"` or
  `"true"`), set from the Stages 1–2 card result, and reported as `fd_hdg_ref`. Body-layer reads
  it and never hard-codes a reference.
- **Mode 1 converts** when `HEADING_REF="mag"`: its law flies true heading, so each frame it takes
  `target_true = heading_deg + (LoGetSelfData().Heading − LoGetMagneticYaw())`, wrapped to 0–360.
  The variation source is that live difference, not a table: the M0 log measured it at 7.27–7.31°
  on the Caucasus, steady, which is the theatre's variation
  (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`). If either call returns
  non-finite, the law holds its last finite variation and the fail-loud path applies after the
  existing NaN guard. With `HEADING_REF="true"`, there is no conversion.
- **Settle and roll-out writes** convert back the other way (measured true → overlay reference)
  before they write `heading_deg`.
- Until the card settles it (Stages 1–2), the shadow desired heading is tagged with the reference
  of whichever handler wrote it (see Stage 1).

**Wire, `fd_*` status line (5 Hz, new route key `fd_mode`).** It carries every field above, plus
the authority fields from section 2 and `fd_epoch`, `fd_last_seq` and `fd_acks` from section 5. It
also carries **both** measured headings, `fd_hdg_true_deg` (`LoGetSelfData().Heading`) and
`fd_hdg_mag_deg` (`LoGetMagneticYaw`), plus `fd_hdg_ref`, AGL, MSL and IAS, which body-layer
needs to resolve "current" and relative values, and `fd_has_m2` (see "The mode-2 seam"). Integers are
encoded as integers. `fmt_num_or_null` blanket-formatting killed the fc line for a day
(`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`), so
the schema test asserts the exact encoding of each field.

**Who reads it:** `flight_control.lua` every frame, and `ai_pilot_wheel.lua` every 5 Hz overlay
tick, both through `flight_desired.get()`, read-only. Body-layer reads it from the mirror. The
existing `fc_goal_*` echo and `held_targets()` are deleted (Stages 3 and 4).

### 2. Mode authority

**Lua derives the mode every frame; nothing sets it directly.** `flight_desired.tick(t)` runs from
`LuaExportBeforeNextFrame`, right after `run_flight_control`. It reads `fc_mode` (already
off/taking/active/armed) and `ai_pilot_wheel.is_parked()`, and derives:

`fd_mode = "m2" if parked_active` else `"m1"` if fc_mode = active, `"taking"` if fc_mode = taking,
otherwise `"off"`.

It detects edges itself and records `fd_mode_n` (incremented on every change) and `fd_mode_cause`
(`take`/`release`/`park`/`unpark`/`unpark_refused`/`unpark_unarmed`/`envelope`/`nan`/`dead`/
`reset`/`stop`). Deriving the mode, rather than adding a setter at each of `flight_control.lua`'s
twelve `fc_mode =` sites (lines 1554–1956) and `ai_pilot_wheel.lua:1388`, means no construction
site can forget to notify. The edge handler is also where seeding and clearing run (section 4).

**Arming moves into Lua (refinement 3).** On a park rising edge, `fc_mode` goes to `armed` if
Petrovich was in m1, as it does today, **or if he was off and the lease is fresh**. The second
clause replaces body-layer's `arm` message: the 2026-11-17 answer means every park gives him the
overlay, and `plans/flight-control/plan.md`'s U5 (not this plan's U5) means every unpark from it
goes to mode 1. After `reset(epoch)` while parked,
`armed` is cleared and nothing re-arms it until the next park edge. That is Q6.

**Lease:** `{"op":"flight_lease","epoch":E,"limits":{...}}`, unnumbered and sent every poll
(today's `arm` resend cadence, U10). It refreshes `fc_arm_last_t` and carries the `limits` block
that today rides every `flight_control` message. Lua ignores a lease whose epoch is not its own.

**Body-layer: what is deleted, kept and changed**

| item | fate |
|---|---|
| `FlightControlPhase`, `FlightControlState.phase/take_seq/took_at_sim/unpark_take/wire_seq/lua_last_cmd_seq` | **deleted** (Stage 2 phase, Stage 3 seqs) |
| `decide_flight_control`'s six branches | **replaced** by `decide_flight_speech(prev_mirror, mirror, pending)`: speaks on `fd_mode_n` changes (urgent "You have controls!" for any change into off whose cause is not `release`/`stop`/`reset`, per E8) and on request outcomes (section 3) |
| `take_controls`/`release_controls` pure fns | **become request builders**. The body-side refusals stay as guidance: `ON_GROUND`, `TOO_SLOW`, `ATTACK_RUN_ENGAGED`, and the overlay no-op. Lua re-checks IAS/AGL on a voice take too (today it trusts the voice take), reusing `check_unpark_preconditions` |
| `CrewConsole.flight_mode()` | **kept, reduced to a map of the mirror**: m2→`"overlay"`, m1/taking→`"axes"`, off→`None` |
| `CrewState.has_controls` | **mirror**: `fd_mode ≠ off`, **or a take request is pending and unacknowledged**. The second clause keeps "you have controls, heading 090" working in one breath, as `TAKING` does today. It describes a request in flight, not a mode. Lua orders the two requests by seq |
| `CrewState.held_*` | the **desired** mirror, falling back to measured when `hdg_mode` is nil |
| `ParkedFlightState` | **kept** as the overlay mirror (held_* overlay text, ai_mode, seat, takeover diagnostics, payload counts). Its goal/align/cbtm/order fields are **deleted** (Stage 4) |
| `FlightControlState` | **kept** as the mode-1 diagnostics mirror (in_band, slip ball, measured, takeover_mode) |
| `_resolve_command_reset` | **kept, widened**: re-sends the reset whenever `fd_epoch` ≠ own epoch, not only until the first confirmation. This also covers a DCS-side reload of Export.lua (see Risks) |

**Handover, restated over one state**

| event | mode | desired state after |
|---|---|---|
| "you have controls" (off) | off→taking→m1 | reseeded from `law_init_at_take` (Decision 1 REVISED: under 5° of bank hold the heading, else a `turn` at the measured rate; stopping height; measured IAS), **except parts stamped after the take's seq** |
| "I have controls" (m1/taking) | →off | cleared |
| "I have controls" (m2) | m2, unchanged | unchanged. Lua refuses `wrong_mode`; "Unable, AI overlay." (U9) |
| park from off | off→m2 | reseeded from the overlay's set values once the P1 takeover settles: course, the corrected altitude and reference, the speed step. HOLD until then (Q12) |
| park from m1 | m1→m2 | **carried**. A `turn` is converted to `heading` = the overlay course after takeover (ED rolls level, probe v2; mode 2 cannot hold a continuous turn, so the turn must not come back at the next unpark: Q2's logic) |
| unpark, armed | m2→m1 | **carried**: the law is initialised with desired as the seed (Decision 32 and Q4 fall out: a break's heading, rate and style are in desired) |
| unpark, refused/unarmed | m2→off | cleared, urgent line |
| seat swap to pilot while parked | m2→m1 (Q5: always unparks) | as unpark |
| seat swap to copilot, auto-AI setting | m1→m2 or off→m2 | as park (after `AI_PILOT_SEAT_CHANGE_SETTLE_S`) |
| envelope/NaN/dead | m1→off | cleared, urgent line |
| body-layer reset | m1→off; m2 stays, disarmed | m1: cleared. m2: reseeded from the overlay (E10) |
| mission restart (`on_stop`) | →off | cleared |

### 3. Mode 2 as a consumer

`ai_pilot_wheel.lua`'s goal tick stops reading wire-fed targets. Every overlay tick it computes
**what mode 2 will fly** from the desired state, using one pure function, `m2_flown(desired, agl)`:

- **heading:** desired heading. `hdg_mode="turn"` cannot occur in m2, because the park converts it.
- **speed:** the nearest wheel step to `ias_kmh` (steps `0,60,120,150,200,250`, MAX above the
  top). The steps travel in `limits`, from body-layer's existing tunable `AI_PILOT_SPEED_STEPS_KMH`.
- **altitude:** `alt_m` in `alt_ref`, except that agl ≥ 700 m (`AI_PILOT_QUICK_PATH_MAX_AGL_M`)
  flies the same number barometric. This is today's 700 m rule.

It then presses toward the first part whose overlay set value differs from `m2_flown`. Heading,
and altitude to the nearest metre, use the exact-set tolerances from tonight (0.5); speed must
match the step exactly. **Priority:** the highest `stamp` first, so the latest command wins (E3).
Ties go altitude, then speed, then heading, which gives recovery's altitude-before-speed order for
free. `AI_PILOT_GOAL_SLICE_S` (sent in `limits`) still rotates between parts while more than one
differs, except while `manoeuvre="recovering"`. These are the rules `decide_ai_pilot_wheel` holds
today, moved, not new ones. Mode cycling (FLT/HVR), the bounded retry and `mode_blocked` are
unchanged.

**What it cannot fly (Q1a):** body-layer computes `m2_flown` with the same function (body-side
twin, same constants, parity-tested) and **reads back what mode 2 will fly**: "speed 2 2 0" is
read back as "Speed 2 0 0.", and "altitude 900 radar" as "900 meters barometric.". The exact value
stays desired. Lua does not refuse approximations.

**A carried value the new mode cannot fly exactly (U2, answered yes).** On an m1↔m2 change that
carries the desired state, body-layer compares, per part, the desired value with what the new
mode flies: `m2_flown` on m1→m2, and mode 1's clamp (`MIN_IAS_KMH`/`MAX_IAS_KMH`, `FLOOR_AGL_M`)
on m2→m1. For each part that differs it says the flown value **once, not urgent**, after any
mode-change line ("Speed 8 0."). The mode change itself stays silent, as before. The trigger is
the `fd_mode_n` change with cause `park`/`unpark`. It is the same readback renderer, so no new
wording. A part that matches says nothing. First needed in Stage 3 (carry starts there for m2→m1)
and Stage 4 (m1→m2).

**What it cannot do at all (Q2):** continuous "turn left/right", and the mode-1-only manoeuvres.
Body-layer refuses from the mirror before sending ("Unable, AI overlay."). If the mirror was stale
and the request reaches Lua in m2, **Lua refuses the whole request** (`refused:wrong_mode`) and
changes nothing. Body-layer then speaks the refusal. An "unable" never writes the desired state.

**How a refusal and a readback reach the player.** Every numbered request is acknowledged in
`fd_acks` (section 5). **U1, answered: wait for Lua.** *"Readback on acting on command -> wait for
lua."* Petrovich speaks a readback only after Lua has accepted the request, and a refusal speaks
"Unable, <reason>." and nothing else. The mechanism is 3a. The voice take keeps Decision 22's
contract, which was already this shape: "I have controls." is spoken only when `fd_mode` reaches
m1 for that seq. **`[[BL-B122]]` (a failed `ai_pilot_goal` write marked sent) is closed by
construction** and should be marked so when Stage 4 merges.

### 3a. Waiting for Lua (U1)

First needed in **Stage 3**, the stage that introduces the numbered `flight` channel. Stages 1–2
keep today's command paths and today's readback timing.

**Latency.** Body-layer polls at 1 Hz (`_DEFAULT_POLL_INTERVAL_S = 1.0`, `body.py`; the 5 Hz
figure is Export.lua's push rate, not body-layer's). Each tick reads status first, then dispatches
voice rules, then sends. So a request sent in tick *k* is applied by Lua within a frame, appears
in the `fd_*` line within 200 ms, and is read at tick *k+1*. **The readback arrives about one
second after the command is dispatched, where today it is immediate.** Occasionally it is two
seconds, when tick *k*'s work runs long enough that the push lands after tick *k+1*'s read. That
cost is what U1 buys; U5 asks whether to cut it.

**The deadline: Lua refuses a request that is too old, so a timeout is always the truth.** Without
this, a request Lua accepts late (UDP delay, a long tick) can arrive after body-layer has already
said "Unable" for it, and the aircraft then flies something the pilot was told it would not. So:
- Each request carries `until` = the mirror's model time at send + `FLIGHT_REQUEST_ACCEPT_WINDOW_S`.
  Lua refuses `stale` if `LoGetModelTime() > until`. Body-layer and Lua share DCS model time, so
  a pause stops both clocks together. No Lua constant: the window arrives inside the request.
- Body-layer's own deadline is `HANDOVER_ACK_TIMEOUT_S` after send, on the same model-time clock,
  and it must exceed the Lua window by at least one poll plus the push interval. Ack matching runs
  **before** the timeout check in each tick, so an ack and a deadline in the same tick resolve as
  the ack.
- **Numbers:** `FLIGHT_REQUEST_ACCEPT_WINDOW_S = 1.5` (new tunable in `belief/flight_control.py`,
  `lo=0.5`, `hi=10.0`, status `judgement`), and `HANDOVER_ACK_TIMEOUT_S` raised from 2.0 to **3.0**
  in Stage 3, since it now bounds two polls rather than one take. Anything Lua accepted is in the
  status line by about `until + 0.2 s`, and at least one poll falls between that and body-layer's
  deadline. A unit test pins `HANDOVER_ACK_TIMEOUT_S ≥ FLIGHT_REQUEST_ACCEPT_WINDOW_S + 1.0 + 0.2`
  so tuning one cannot silently break the other.
- **Timeout speech:** no ack by the deadline → "Unable, not ready." The request is dropped, and by
  construction Lua will refuse it if it ever arrives. If an *accepted* ack still turns up for a
  dropped request (a clock anomaly), body-layer logs a WARNING and speaks its readback anyway: the
  aircraft is flying it, and E9 says the pilot is told.

**What is read back.** The ack carries the mode Lua applied it in: `N:a:m1`, `N:a:m2`, `N:r:<reason>`.
The readback is the request's own absolute value in m1, or `m2_flown` of it in m2. That uses the
mode at apply time, not the mirror's guess, so the mode-change instant the old U1 recommendation
worried about cannot produce a wrong readback. `predict_desired` is still needed, but only to
resolve relative commands before sending (refinement 1).

**Refusal speech.** Each Lua reason maps onto an existing `render_unable` token
(`belief.speech._UNABLE_TEMPLATES`): `wrong_mode` → the "AI overlay" wording in m2 (U9), else
`NOT_READY`. `stale`, `epoch`, `not_flying` and `precondition` map to their existing equivalents,
otherwise `NOT_READY`. `bounds` → the existing clamp wording. **No new spoken wording.** If the
Implementer finds a reason with no fitting token, it uses `NOT_READY` and flags it, rather than
writing a new line.

**Order with the speech worker.** The worker is a FIFO, and an urgent line calls `interrupt()`,
which clears the queue (`belief/speech_worker.py`). So `drain_flight_speech` emits lines in one
tick in this order:
1. Mode-change lines first (`fd_mode_n` changed). An urgent "You have controls!" is enqueued before
   anything else from the tick, so its interrupt cannot wipe readbacks enqueued after it.
2. U2's carried-value lines, if any.
3. Ack outcomes in **seq order**, never arrival order. "Climb 50, climb 50" reads back the two absolute
   altitudes in the order they were spoken. A refusal or timeout takes its seq's slot.

Two suppression rules:
- **A change into off in the same read** (cause not `release`/`stop`/`reset`) suppresses the
  readbacks of requests accepted in that read. Their values were cleared with the mode, and the
  urgent line is the truth.
- **Requests sent after a pending take** ("you have controls, heading 090" in one breath) hold
  their readbacks until the take resolves. On take success: "I have controls.", then the
  readbacks in seq order. On take failure or timeout: "Unable, not ready." once, and the held
  readbacks are dropped. Lua cleared desired on taking→off, so nothing they set is being flown.

**The gates in `rules/gates.py` do not change.** They decide *before* a request is sent. A `hold`
(`NOT_READY`, for example a heading command while `hdg_mode` is nil during the off→m2 settle) is
re-checked every poll against the current `CrewState` for up to `RULE_GATE_HOLD_TIMEOUT_S` (5 s),
then sent or spoken as unable, as today. After the send, the ack wait above applies. So a held
command's worst case is the hold plus the ack deadline. **A Lua refusal is final and is never
retried**: retrying would make it unclear which attempt the readback describes. The gate hold
stays the only retry. A newer match still replaces a held command (U21, latest wins). A request
already sent cannot be recalled, and its ack is still spoken in seq order.

### 4. Manoeuvres

| manoeuvre | how it is expressed | mode 1 flies | mode 2 flies | desired state after |
|---|---|---|---|---|
| heading / compass / "turn x left/right" | `set` heading (absolute, resolved body-side), style normal | law | goal tick | heading = target |
| "turn left/right" (no degrees) | `set` `turn=±1` | law (rate at `max_turn_bank_deg`) | **refused**, unable | `hdg_mode=turn` |
| "stop turn" | `set` `turn=0` | law rolls out, then **Lua writes** heading = where the roll-out settled (Decision 12) | heading = overlay course now (body-side) | heading |
| altitude / step / hold altitude | `set` alt (+ref), absolute | law | goal tick | alt |
| speed / step / max | `set` ias, absolute (MAX = `MAX_IAS_KMH` in m1, the sentinel in m2) | law | goal tick (snapped) | ias exact |
| "level flight" | `set` all three = current measured | law | goal tick | all three |
| **break left/right** (C3) | `set` heading = measured ± 90, `turn_dir`, `turn_rate_deg_s = ±BREAK_TURN_RATE_DEG_S` (flight.lua), style `break` | law, rate override (Decision 27). The **settle clears the override**, and Lua writes `turn_rate=nil`, style normal | CBTM long press (today's `ai_pilot_cbtm`), started because the newest heading write has style break. When the press releases: cycle to FLT and trim the course to the desired heading (the sortie's "should have changed to FLT") | heading = break heading. It replaces every older heading (F-P7 automatically) |
| **break away** | as break, ±180 **left**, style `break_away` | same | two presses + gap, as today | heading = entry − 180 |
| **align** (m2 only, one-shot) | action `align` | refused: "unable" (user, 2026-11-20: *"align is possible only in mode 2 -> unable"*) | CBTM align tap: ED's overlay sets its course to the 9K113 azimuth once. Lua sets `manoeuvre=align`, waits `MODE_READ_SETTLE_S` (existing, 1.0 s, the overlay's own "set values readable again" settle) so the overlay has updated, **then reads the overlay course into `heading_deg`**, stamped with the align seq, and sets `manoeuvre=none`. The goal tick does not press heading while `manoeuvre=align` | heading = aligned heading (alignment Q7) |
| **align for launch** (m2 only, continuous) | action `align_for_launch` | refused: "unable" | CBTM up press. ED keeps re-aligning the course to the current 9K113 azimuth (slewing the sight steers the helicopter) and also aligns pitch for the launch parameters. `manoeuvre=align_for_launch`, then `launch_aligned`. **Every overlay tick while it runs, Lua copies the overlay course the AI is flying into `heading_deg`**, keeping the align-for-launch request's seq as the stamp. The goal tick presses nothing (the overlay is flying). Altitude and speed are not written | heading = last aligned heading. Alt/speed unchanged = pre-align values (refinement 4) |
| **recovery** | body-layer's launch watcher (payload drop, `AI_PILOT_RECOVER_AGL_DROP_M` below the AGL recorded at the align-for-launch request, `AI_PILOT_RECOVER_IAS_CEILING_KMH`) sends action `recover` while the mirror shows `launch_aligned` | n/a | ends the CBTM episode. The heading already holds the last aligned course from the follow, so it is kept. Lua **re-stamps alt and speed with the recover seq** so they press next, altitude first (Decision 26, by tie order). `manoeuvre=recovering` until both match | pre-align alt/speed, last aligned heading |
| HVRT translate / hold / step | actions `translate{dir}`, `hover_hold`, `hover_step{up\|down}` (m2 only; m1 refuses, as today `NOT_READY`) | refused | as today. `translate` pauses the goal tick. **Any `set` ends a translate** (latest wins, today's arbitration) | translate writes nothing. `hover_hold`: Lua writes ias = 0, heading/alt = overlay set values. `hover_step`: Lua writes alt ± 2 m |
| take / release / park / unpark | `take`/`release` requests, cockpit edges | — | — | section 2 |

**Latest wins, in one sentence:** any request newer than the running manoeuvre's `manoeuvre_seq`
ends that manoeuvre's remaining presses. This is tonight's Lua rework generalised, and body-layer's
`command_order_seq`/`cbtm_action_order`/F-P7 code is deleted.

**Unpark during a manoeuvre** (amended: the last aligned heading is kept, per the user's
*"that heading is kept when recovering from align"*):
- **break:** mode 1 finishes it (Q4).
- **align, after the read:** nothing to do; `heading_deg` is already the aligned course.
- **align, before the read** (unpark within `MODE_READ_SETTLE_S` of the press): Lua writes
  `heading_deg` = the last overlay course it read, and ends the align. That may be the pre-align
  course if ED had not updated yet. This is U6.
- **align for launch / launch aligned / recovering:** the abort. Mode 1 flies the desired alt and
  speed (the pre-align values) **and the desired heading, which is the last aligned course** the
  follow wrote. Mode 1 never holds the bottom of the dive.

The same holds for any other way out of the alignment. A newer request (latest wins) leaves
`heading_deg` at the last aligned course unless the request itself writes a heading. A reset while
parked reseeds from the overlay, which is the same course.

All of these run in the m2→m1 edge handler before `law_init_at_take` reads desired.

### 5. One running number

**`{"op":"flight","epoch":E,"seq":N,"until":T,"kind":K,...}`** replaces `flight_control`
(goal/take/release/arm), `ai_pilot_goal` (goal fields, `hvrt_*`, `cbtm_*`) and their three seq
spaces. Kinds: `set`, `take`, `release`, `align`, `align_for_launch`, `recover`, `translate`,
`hover_hold`, `hover_step`.

- **One body-layer counter, `ConsolePerceptionRunner.command_seq`, for the whole process.**
  It is preserved across mission restarts and never reused. "Mission-wide" is satisfied strictly.
  Nothing reconciles against Lua's floor any more: the `wire_seq = max(...)` fix-up and
  `lua_last_cmd_seq` are deleted.
- **Lua applies a request only if `epoch == fd_epoch`, `seq > fd_last_seq` and
  `LoGetModelTime() ≤ until`** (3a). It acknowledges every request it receives in a ring of the
  last 8, with the mode it applied it in: `fd_acks = "N:a:m1;N+1:r:wrong_mode;..."`.
  Reasons are a closed set: `wrong_mode`, `not_flying`, `bounds`, `epoch`, `stale`, `precondition`.
  A refusal applies nothing (whole request, the `[[AC-B14]]` posture); the API checks closed
  vocabularies and `math.isfinite` first, and Lua checks again.
- **The reset epoch:** `reset(epoch)` sets `fd_epoch`, sets `fd_last_seq = 0` and runs both
  modules' `on_stop` as today. Body-layer's counter keeps counting from where it is, which is fine
  because every value is above 0. Body-layer re-handshakes whenever the echo differs, which covers
  a body-layer restart (new epoch), and an Export.lua reload on mission or DCS restart (echo
  becomes null). The `sight_target`/`cockpit_switch`/... channels carry no seq and stay as they
  are.
- The unnumbered `reset` and `flight_lease` ops are idempotent by design, as `reset` is today.

### 6. The mode-2 seam (Mi-24 only)

The desired state, the authority, the channel and mode 1 are aircraft-generic. Mode 2 is one
optional consumer behind one seam per layer:

- **Lua:** `ai_pilot_wheel.lua` is the only file that knows the wheel exists. `flight_desired.lua`
  reads it only through `ai_pilot_wheel ~= nil and safe_call(ai_pilot_wheel.is_parked)` (today's
  "unknown is never a licence to assume" posture) plus three callbacks it exports:
  `overlay_seed()`, `on_desired_written(parts)` and `manoeuvre_kind_supported(kind)`. If
  `ai_pilot_wheel` is nil, `fd_has_m2=false`, `fd_mode` is never m2, park edges never happen, and
  every m2-only kind is refused `wrong_mode`. Deciding *when* to load it (an aircraft-type check in
  `Export.lua`'s loader) is the future-aircraft milestone, not this one. The seam is the nil check.
- **Wire:** `fd_has_m2` on the fd line. The `apw_*` line simply never appears for another aircraft.
  Every `fd_*` field is meaningful without mode 2.
- **Body-layer:** `flight_mode()` never returns `"overlay"` unless the mirror says m2.
  `_by_mode`'s overlay bodies, `m2_flown`, the launch watcher, `ParkedFlightState` and the
  CBTM/HVRT rules are all reached only through `"overlay"`. Rules and gates need no aircraft check:
  a mode-2-only command on an aircraft without mode 2 lands in the axes body, which already answers
  unable. The mode-2 Python moves into `belief/ai_pilot_wheel.py` only (no new module), so
  isolating it later is a file boundary that already exists.

### Affected modules / files

**aircraft-layer**
- `dcs-export/Petrobrain/flight_desired.lua` — **new**, aircraft-generic: desired table, authority
  tick, edge handler (seed/carry/clear), `flight` and `flight_lease` handlers, acks, `reset`,
  `on_stop`, `fd_*` push, `get()`. Justified as a new module: it removes the duplication of two
  goal stores, two command channels and three seq spaces, and it keeps the authority aircraft-
  generic and outside the Mi-24 file.
- `dcs-export/Export.lua` — load `flight_desired` before `ai_pilot_wheel`/`flight_control`.
  Call `flight_desired.tick` after `run_flight_control`, `push_state` at 5 Hz, and include it in
  `on_stop`.
- `dcs-export/Petrobrain/flight_control.lua` — reads desired, applying changed parts by stamp
  (replaces `apply_goal_fields`). `law_init_at_take`'s seed comes from desired (rate override and
  style too). Self-arm from off. Voice-take precondition check. Settle writes back to desired.
  Delete the `goal`/`arm` handlers, `fc_goal_*` and the `held_targets` call.
- `dcs-export/Petrobrain/ai_pilot_wheel.lua` — goal tick reads `m2_flown(desired)`, with priority
  and rotation. CBTM is started by break style or an action kind. Manoeuvre-end writes. Delete
  `handle_ai_pilot_goal_command`'s goal/cbtm fields and `held_targets`. Export the seam callbacks.
- `dcs-export/Petrobrain/commands.lua` — `flight`, `flight_lease`. Retire `flight_control`
  (Stage 3) and `ai_pilot_goal` (Stage 4). `reset` also calls `flight_desired.reset`.
- `src/schema/flight_desired.py` (new), `src/collector/{cache,server,command_sender}.py`,
  `src/api/server.py` — `GET /flight_desired/latest`, `POST /command/flight`,
  `POST /command/flight_lease`, validation, and retiring the two old POSTs in their stages.
- `aircraft-layer/CLAUDE.md` — the write-path bullets.

**body-layer**
- `src/belief/flight_authority.py` — **new**: `FlightAuthorityState` mirror (single construction
  site `advance_flight_authority`), `DesiredMirror`, `PendingRequest`, `predict_desired`,
  `match_acks`, `decide_flight_speech`, request builders.
- `src/belief/flight_control.py` — shrinks to the limits/constants, clamps, the mode-1 diagnostics
  mirror and the readback helpers.
- `src/belief/ai_pilot_wheel.py` — shrinks to the overlay mirror, `m2_flown` (the twin), and the
  launch watcher.
- `src/belief/crew_console.py` — the overlay and axes action bodies become one desired-state
  writer per command, with the mode only selecting readback and refusal. `_by_mode` stays for the
  mode-only actions. `flight_mode()`, `current_crew_state()`, and the drains replaced by one
  `drain_flight_speech`.
- `src/rules/actions.py` — the `_by_mode` pairs collapse where both bodies now do the same write.
- `src/rules/gates.py` — unchanged in shape. It reads the new `CrewState`.
- `src/body.py` — `_apply_flight_control` and `_apply_ai_pilot_wheel_goal` are replaced by
  `_apply_flight_requests` (send queued requests and the lease). `_resolve_command_reset` widened.
- `src/aircraft_client.py` — `write_flight`, `write_flight_lease`, `read flight_desired`. The old
  writes are removed in their stages.
- `config/rules/flight.lua` — wording unchanged. The break calls lose `cbtm_` only if the actions
  are renamed (not required).
- `config/defaults.toml` — regenerated, since the docstrings of moved constants change.
  `AI_PILOT_ALTITUDE_TOLERANCE_M` and `AI_PILOT_HEADING_TOLERANCE_DEG` (no consumer, debug.md) are
  deleted in Stage 4.
- `body-layer/CLAUDE.md` — the invariants "park and unpark change the mode, never who" (still
  true, re-worded over fd_mode), "`axes_*` never writes `ai_pilot_*` one-shots" (dissolves: there
  is one request queue), and the `flight_control.py`/`ai_pilot_wheel.py` module-map entries.

**plans**
- `plans/flight-control/plan.md` — pointer lines at Decision 24's carry clause and at E-P10, added
  in this commit ("Superseded in part" below).

### Existing constants checked (step 4a)

Grepped `body-layer/src` and `config/defaults.toml` plus the three Lua modules. **One new
behaviour constant, added by the U1 amendment:** `FLIGHT_REQUEST_ACCEPT_WINDOW_S` (3a). Nothing
existing governs "how old a flight request may be when Lua applies it". `HANDOVER_ACK_TIMEOUT_S`
is body-layer's wait, the other half of the pair, and `RULE_GATE_HOLD_TIMEOUT_S` bounds a
pre-send hold. Re-grepped for the amendment: the align read delay reuses `MODE_READ_SETTLE_S`
(Lua, 1.0 s), so no new constant there. `HEADING_REF` is a reference choice, not a behaviour
tunable; it stays a Lua literal set from the card.

- **Reused:** `ARM_LEASE_S` (lease), `HANDOVER_ACK_TIMEOUT_S` (every request's ack, widened from
  take-only, default 2.0 → 3.0 in Stage 3), `AI_PILOT_GOAL_SLICE_S` and `AI_PILOT_SPEED_STEPS_KMH` (now sent to Lua in
  `limits`), `AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M` / Lua `AI_PILOT_QUICK_PATH_MAX_AGL_M` (the 700 m
  twin, parity-tested), `TAKEOVER_LEVEL_BANK_DEG`, `MIN_IAS_KMH`/`MAX_IAS_KMH`/`FLOOR_AGL_M`/
  `SPEED_STEP_KMH`, `COMMAND_RESET_RESEND_INTERVAL_S`/`COMMAND_RESET_CONFIRM_TIMEOUT_S`,
  `AI_PILOT_RECOVER_*`, Lua's `AI_PILOT_GOAL_ALT_EXACT_TOLERANCE_M`/`AI_PILOT_HEADING_TOLERANCE_DEG`
  (0.5), `MODE_READ_SETTLE_S` (wait for a readable overlay before the off→m2 seed),
  `AI_PILOT_SEAT_CHANGE_SETTLE_S`.
- **The ack ring size (8)** is a protocol constant, not behaviour. It stays a literal.

### Implementation plan

Each stage ships on its own and is flown before the next, except that Stages 1 and 2 ship and fly
together (U4). Behaviour that works tonight keeps
working at every stage. That is mainly the unpark take, the break in both modes, latest-wins, the
exact set values and the reset.

**Stage 1 — shadow: authority and desired state reported, nothing reads them.**
- Lua `flight_desired.lua`: authority tick, edge detection, desired table. Seeded and written by
  **today's** handlers (mode 1 `apply_goal_fields`, mode 2 `handle_ai_pilot_goal_command`, at
  receipt, exact values), cleared and seeded per section 2. Pushes `fd_*`.
- **Heading reference reporting (amended, U3):** the `fd_*` line carries both measured headings,
  `fd_hdg_true_deg` (`LoGetSelfData().Heading`) and `fd_hdg_mag_deg` (`LoGetMagneticYaw`), in
  place of the single "HSI reference" heading. Because the reference is not known yet, the shadow
  `desired.heading_deg` is tagged with the reference of whichever handler wrote it:
  `fd_hdg_ref = "true"` when mode 1's `apply_goal_fields` or the law seed wrote it, `"overlay"`
  when mode 2's handler or the overlay seed wrote it. Nothing converts in Stage 1. Once the card
  says which reference the overlay uses, Stage 3 sets `HEADING_REF` and `fd_hdg_ref` becomes that
  constant.
- Collector schema, cache and `GET /flight_desired/latest`. Body-layer mirror
  (`FlightAuthorityState`) logged on the flight-control status line, read by nothing.
- Deletes nothing. Risk to tonight's behaviour: none, since there are no readers.
- **Card:** one card with Stage 2 (U4); see the end of Stage 2.

**Stage 2 — the mode authority is live.**
- Lua: self-arm from off on the park edge while the lease is fresh. `flight_lease` op (lease and
  limits). `arm` removed. A voice take re-checks IAS/AGL.
- Body-layer: `flight_mode()`, `has_controls` and `held_*` read the fd mirror.
  `decide_flight_speech` replaces `decide_flight_control`'s phase machine. Mode-change speech comes
  from `fd_mode_cause`. `_resolve_command_reset` re-handshakes on epoch mismatch.
- **Deletes:** `FlightControlPhase`, `phase`, `unpark_take`, `took_at_sim`, the `arm` send and
  resend, and `decide_flight_control`'s park/unpark/self-release branches. The goal channels are
  untouched.

**Stages 1 and 2 ship together, on one card (U4, answered).** User, verbatim: *"Build both, we'll
refine if something does not work."* Stage 1 is still built first and is still the safety net:
if a Stage 2 row misbehaves, the `fd_*` log shows whether Lua's view of the mode or body-layer's
reading of it was wrong. **Combined card** (the two former cards merged, content unchanged except
the heading rows):
1. Every row of the section 2 handover table, with `fd_mode`/`fd_mode_cause` read off against the
   cockpit: handover in both directions, park/unpark from off and from m1, seat swaps, an envelope
   release.
2. A body-layer restart while parked, then an unpark (Q6).
3. The second-handover "unable, not ready while holding" case from the sortie. It must not recur:
   there is no phase left to disagree.
4. **Heading reference (U3):** steady on three headings. Read the HSI and note the time; the log
   has `fd_hdg_true_deg` and `fd_hdg_mag_deg` for the same moment. Then park and note the overlay
   course against both. This settles which reference the overlay course (and the HSI) uses.
5. **Optional, for Stage 4's align read:** in mode 2, press align once with the 9K113 off the
   nose. The 5 Hz `apw_*` log then shows how long the overlay course takes to change, which checks
   `MODE_READ_SETTLE_S` (1.0 s) as the align read delay. Costs one press. Drop it if the sortie is
   long.

**Stage 3 — one channel; mode 1 flies the desired state; mode 2 commands are recorded into it.**
- Lua: `flight` op with epoch, seq and acks. Kinds `set`/`take`/`release` (the mode-2 kinds return
  `refused:wrong_mode` until Stage 4). Mode 1 applies desired by stamp. Seed and carry rules.
  Unpark seed = desired (and `held_targets` deleted), so **a mid-ramp unpark flies what the player
  said** (E4, tonight's crash case). The roll-out settle and the break settle write back.
- Lua also: `HEADING_REF` set from the Stages 1–2 card, mode 1's per-frame conversion and the
  settle writes' reverse conversion (section 1, "Heading reference"). The `until` deadline and the
  mode letter in each ack (3a).
- Body-layer: `command_seq`, the request queue, `predict_desired`, relative resolution, ack
  matching, and **3a in full: readback only on accept, refusal speech, the deadline pair
  (`FLIGHT_REQUEST_ACCEPT_WINDOW_S` new, `HANDOVER_ACK_TIMEOUT_S` 2.0 → 3.0), speech order and the
  two suppression rules.** U2's carried-value line on unpark. Every `axes_*` action writes a
  `set`. **Every mode-2 voice goal also writes a `set`** (exact value) alongside the still-live
  `ai_pilot_goal` message. Mode-2 breaks write their break heading. Lua writes the align read and
  the align-for-launch follow into `heading_deg` in-process (both are reads of the overlay course,
  section 4), so an unpark after an alignment already keeps the aligned heading in this stage.
- **Deletes:** the `flight_control` op and `POST /command/flight_control`, `FlightControlGoal
  Request`, `wire_seq`/`lua_last_cmd_seq` and the reconcile, `fc_goal_*`, `held_targets()`, the
  `flight_control_transition`/`flight_control_goal_transition` one-shots.
- **Card:** mode 1 heading/alt/speed/turn/stop turn/break/break away, each read back and flown.
  Exact set values. "Heading 090" flown to 090 on the HSI (the conversion). The readback comes
  about a second after the command (U5 is judged here). "Speed 200" in m2, unpark mid-ramp (must
  go to 200). Unpark mid-break (finishes the break). "Speed 0" in m2 then unpark (U2's one line,
  "Speed 8 0."). Two commands in one breath ("climb 50, climb 50" → +100, read back in order).
  "You have controls, heading 090" in one breath ("I have controls." first, then the heading).

**Stage 4 — mode 2 is a consumer of the desired state.**
- Lua: the goal tick reads `m2_flown` with priority and rotation. Breaks are started by style.
  `align`/`align_for_launch`/`recover`/`translate`/`hover_hold`/`hover_step` kinds. Align is a
  one-shot press plus the delayed read; align for launch is a continuous episode during which the
  goal tick presses nothing and `heading_deg` follows the overlay course (section 4, amended).
  Both are refused `wrong_mode` in m1. Recovery keeps the followed heading and re-stamps alt and
  speed. Manoeuvre-end writes. Park m1→m2 carries, with the turn converted. Latest-wins by
  `manoeuvre_seq`. Q3 radar default in mode 2.
- Body-layer: the overlay action bodies write `set` and speak `m2_flown` readbacks. The launch
  watcher sends `recover`.
- **Deletes:** the `ai_pilot_goal` op and POST, `AiPilotWheelGoal`, `request_goal`, `set_parked_*`,
  `goal_param_for_wire`, `decide_ai_pilot_wheel`'s rotation and F-P7, `FlightSnapshot`,
  `seed_recovery_goal`, `align_phase`, `pre_align_snapshot`, `cbtm_action_sent`/`_order`,
  `command_order_seq`, `cbtm_break_entry_heading_deg`, the four `ai_pilot_*_transition` one-shots,
  the two body-side tolerance tunables with no consumer, and `[[BL-B122]]` (closed).
  **After this stage there is exactly one seq-carrying channel.**
- **Card:** mode 2 heading/alt/speed (exact set, snapped readback), "altitude 900 radar"
  (barometric readback, then unpark flies 900 AGL), "turn left" (unable), break then heading
  (latest wins, overlay returns to FLT), "align" and "align for launch" in mode 1 (unable, nothing
  written), align then unpark (mode 1 holds the aligned heading), align for launch with a sight
  slew (the helicopter follows) then recovery (pre-align altitude first, then speed, on the last
  aligned heading), align for launch then unpark (same heading, pre-align alt/speed), HVRT
  translate/hold/step, park from m1 mid-turn (wings level, no turn after a later unpark).

Stage 2 depends on Stage 1's mirror. Stage 4 depends on Stage 3's channel. There is no parallel
path.

### Co-moving Fields

Built from the construction sites, not only the narrative. In Lua: the twelve `fc_mode =` sites
in `flight_control.lua`, `ai_pilot_wheel.lua:1388` (`ai_pilot_parked_active`), both modules'
`on_stop`/`reset`, and the new `desired` writes. In body-layer: `advance_parked_flight_state`
(`ai_pilot_wheel.py:514`), `FlightControlState` replace sites, and the new
`advance_flight_authority`. **The Implementer re-greps `desired%.` / `desired = ` and
`FlightAuthorityState(` before each stage's tests**, and every new site gets a row or a test.

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `fd_mode` | Lua derivation only | any `fc_mode`/`parked_active` change | equals the derivation the same frame. `fd_mode_n` incremented once per change, never twice for one edge |
| `desired.*` | requests, edge handler, law settle, m2 manoeuvre end | off→taking→m1 | parts with `stamp < take_seq` reseeded from the law init. Parts with a later stamp kept, and applied on the first active frame |
| `desired.*` | edge handler | off→m2 | nil until the P1 takeover settles and the overlay is readable, then the overlay set values. Requests in between are kept |
| `desired.hdg_mode` | edge handler | m1→m2 | `turn` → `heading` = overlay course. `heading` carried with its rate and style |
| `desired.*` | edge handler | m2→m1 | carried. A running `align`/`align_for_launch`/`launch_aligned`/`recovering` is ended first. `heading_deg` keeps the last aligned course (amended; not measured). An align still inside its read delay writes the last overlay course read (U6) |
| `desired.heading_deg` / `stamp.hdg` | `ai_pilot_wheel` | align press + `MODE_READ_SETTLE_S` | `heading_deg` = overlay course, `stamp.hdg` = align seq, `manoeuvre=none`, the same tick |
| `desired.heading_deg` | `ai_pilot_wheel` | every overlay tick while `manoeuvre ∈ {align_for_launch, launch_aligned}` | `heading_deg` = overlay course in the `HEADING_REF` reference. `stamp.hdg` unchanged (the align-for-launch seq). `alt_m`, `ias_kmh` untouched. Goal tick presses nothing |
| `desired.heading_deg` | `flight_control` | any settle / roll-out write | written in `HEADING_REF`, converted from measured true |
| body readbacks held behind a take | body | take resolves | success: spoken after "I have controls." in seq order. Failure/timeout: dropped, one "Unable, not ready." |
| `desired.*`, `manoeuvre` | edge handler, `on_stop`, `reset` | →off (any cause), mission stop | cleared, `manoeuvre=none` |
| `desired.*` | `reset` | reset while m2 | reseeded from the overlay. `fc_mode` ≠ armed |
| `fc_mode` (armed) | park edge (Lua) | park from off, lease fresh | `armed` |
| `fc_mode` (armed) | `reset` | reset while parked | not `armed` until the next park edge (Q6) |
| `fc_law` | `flight_control` | m2→m1 | initialised with desired as the seed, including the rate override (Q4) |
| `fc_law.rate_override` / `desired.turn_rate_deg_s` / `turn_style` | law settle | break reaches band | all three cleared **the same frame** (one write) |
| `manoeuvre` / CBTM press | `ai_pilot_wheel` | any request with seq > `manoeuvre_seq` | press released, `manoeuvre=none`, unless the request itself starts one |
| `ai_pilot_goal` tick part | `ai_pilot_wheel` | desired written | re-picked by stamp priority on the next tick. An open hold whose part is no longer the pick is released |
| `CrewState.has_controls` | body mirror + pending take | take sent, not yet acked | true. On a refused/timed-out take, false and "Unable, not ready." |
| body `pending` requests | body | ack received / timeout / epoch change | removed. On an epoch change all are dropped unspoken (Lua lost them, and the reset already let go) |

### Tests

Real-Lua harness (`aircraft-layer/tests/test_*_lua.py`, function extraction). Add every new local
to the extraction tuples: the silent-default trap from tonight's exact-value fix.

- **S1:** derivation table, one test per section 2 row (`fd_mode`, `fd_mode_cause`, `fd_mode_n`
  once). Desired cleared/seeded per row. `fd_*` encoding exact (ints as ints). Schema round-trip
  and collector route.
- **S2:** self-arm from off only with a fresh lease. Reset while parked → unpark gives
  `unpark_unarmed`. Body: `has_controls`/`flight_mode` pure mirror (the differential test that
  today pins `CrewState` with axes inactive is kept). Speech per cause. Epoch re-handshake.
- **S3:** seq/epoch/stale/refusal ack ring (wrap at 8). A set during `taking` survives the seed.
  Unpark mid-ramp flies desired 200, not the overlay value (toy plant, as in
  `TestUnparkTakeSeedFromMode2SetTargets`). Unpark mid-break keeps the override until settle, then
  all three are cleared together. Roll-out writes the settle heading. Body:
  `predict_desired` with two unacked relatives. **3a:** no readback before the ack; refusal speaks
  only "Unable, <reason>."; timeout speech; Lua refuses `stale` past `until`; the timeout-pair
  inequality pinned; an ack and a deadline in the same tick resolve as the ack; acks arriving out
  of order are spoken in seq order; an urgent off-edge in the same read is enqueued first and
  suppresses that read's accepted readbacks; readbacks behind a pending take are held, then
  spoken or dropped; a late accepted ack is spoken with a WARNING. The m1 readback equals the sent
  value, and the ack's mode letter selects the m2 readback. U2: a carried speed below
  `MIN_IAS_KMH` on unpark gives exactly one non-urgent line. Heading conversion: `HEADING_REF="mag"`
  with a 7.3° variation flies 090 magnetic as 097.3 true, and the roll-out write converts back. Every deleted path has a test proving it is gone (the old POST returns
  404).
- **S4:** `m2_flown` twins parity (Lua and Python over a table of cases, including 220→200, ≥250 →
  MAX, 900 agl → 900 baro). Priority (latest stamp, then tie order). Recovery presses altitude
  before speed. A break by style, then a newer heading ends the press and trims in FLT (tonight's
  `test_a_goal_arriving_mid_break_*` re-pointed). Align writes the overlay course after
`MODE_READ_SETTLE_S`, not before. Align for launch follows the overlay course every tick with the
stamp unchanged and alt/speed untouched; recovery keeps the followed heading; unpark mid-align-for-
launch keeps it too. "Align" and "align for launch" in m1 are refused with nothing written. Park m1→m2 converts
  a turn. A `set` ends a translate. "Turn left" in m2 is refused with nothing written. A request
  with no mode 2 (`ai_pilot_wheel = nil`) → `wrong_mode`, and `fd_has_m2=false` (**the seam
  test**).
- body-layer per stage: the fast set while working, the full suite at DoD (root `CLAUDE.md`).
  `luac5.1 -p` and the GETGLOBAL sweep on every touched Lua file.

### Superseded in part

- **Decision 24, "Goals in progress are dropped, in both directions"**
  (`plans/flight-control/plan.md`) is **superseded for m1↔m2** by the user's 2026-11-20
  direction (*"mode 1 must keep flying the set targets from mode 2"*, *"mode change simply keeps
  flying to it"*). The desired state carries. Its reason (2) is not dropped. It becomes the rules
  above: an explicit reference (Q3), the exact value kept, and mode 2's approximation read back
  (Q1a). Its take rules for a change of *who* flies stand (C1).
- **E-P10, "nothing resumes on the next park"**, is **superseded in full** for the carry. What
  remains: an unpark releases every open press the same frame.
- Pointer lines are added at both places in `plans/flight-control/plan.md` in this commit. The
  original text stays.

### Expectation trace (alignment.md)

E1 → section 3 (ack, refusal speech, timeout). E2 → section 1 (exact desired, readback = what is
flown). E3 → stamp priority and `manoeuvre_seq` latest-wins. E4 → carry on m1↔m2 (Stage 3 fixes
the crash case). E5 → reseed on who-flies (C1). E6 → a break is a heading write, the settle
clears only the rate, and m1→m2 converts a turn. E7 → mode from Lua only, plus Lua's `wrong_mode`.
E8 → speech by `fd_mode_cause`. E9 → `m2_flown` readback, plus U2's carried-value line (answered
yes). E10 → reset rows. E1 is now stricter under U1: nothing is read back that Lua has not
accepted (3a).

### Risks & unknowns

- **Heading reference (U3, answered: the overlay's).** Which reference the overlay course uses is
  still unmeasured; the Stages 1–2 card settles it before Stage 3 makes one desired heading
  load-bearing. If the overlay is magnetic, mode 1 has flown spoken headings 7° off all along.
  **If the card shows the HSI and the overlay course in different references**, the user's rule
  still decides (the overlay's), but "heading 060" read off the HSI would then not be the number
  flown. Raise it then; it is not expected.
- **Readback latency (U1).** About one second per command, sometimes two (3a). The user chose
  this over an immediate readback; U5 asks whether to shorten it.
- **The align read delay.** `MODE_READ_SETTLE_S` (1.0 s) is borrowed from the overlay's
  readability settle. If ED updates the course later than that, the read takes the pre-align
  course. The optional step on the Stages 1–2 card measures it.
- **Export.lua reload on mission restart:** module state may or may not persist (the comments
  say `fc_last_cmd_seq` survives a mission restart). The design does not depend on it, because
  the epoch echo triggers a re-handshake either way. It is no longer a question to investigate.
- **Mode 2 trimming the course to an exact break heading after the CBTM press:** if ED's break
  overshoots, a few degrees of correction follow. The user's *"it sets heading ±90 and flies
  that"* says the target is the same, so the risk is small. Watch it on the Stage 4 card.
- **Lua budget:** `flight_desired.lua` is a new chunk with its own 200 locals.
  `ai_pilot_wheel.lua` gains the rotation (≈ +80 lines) but loses the wire parse. Keep new state
  in tables. Check the 60-upvalue ceiling on `run_ai_pilot_wheel`
  (`reference_lua51_60_upvalue_ceiling.md`).
- **A stale deployment** (old `Petrobrain/*.lua` with a new body-layer) is caught by the existing
  fail-loud ("System error, aircraft scripts out of date."), because there is no `fd_epoch` echo.
  No backward-compatible shims are added.
- **Scope:** the slip-ball/`K_beta` work, mode 1 hover and the pitch-loop tuning are untouched and
  stay open on `BL-16`.

### Second-order effect

A future aircraft gets mode 1, the channel and the authority with no change (only the loader's
choice of modules), which was the coordinator's constraint. Desired-state writes are exactly the
"actions with explicit params" `[[BL-B95]]`'s event scripting will want. Mode 1 hover (deferred)
already has its representation (`ias_kmh = 0`, `hover_hold`).

### Decisions Requiring User Input

(Heading spelled as `.claude/scripts/accepted-items-ledger.sh` matches it; the earlier lower-case
form was invisible to the ledger.)

**Answered 2026-11-20 (user, verbatim; `explore-notes.md`):** **U1** *"Readback on acting on
command -> wait for lua"*. **U2** *"yes"*. **U3** *"True vs magnetic - which ever the AI wheel uses
should be used in both modes."* **U4** *"Build both, we'll refine if something does not work."*
Align in mode 1: *"align is possible only in mode 2 -> unable"*. Where each landed: U1 → 3a and
Stage 3; U2 → section 3 and Stage 3; U3 → section 1 "Heading reference", Stage 1 reporting,
Stage 3 conversion; U4 → the combined Stages 1–2 card. The original questions and
recommendations are in this file's history (commit `df4e23e7`).

### Open Decisions (not yet answered)

Kept under their own heading so the ledger does not count them as accepted.

- **U5: Is a readback about one second after the command acceptable, or should it be faster?**
  Waiting for Lua costs one body-layer poll (1 Hz). A faster version is possible: in a tick that
  sent a flight request, re-read the status every 100 ms for up to ~500 ms and speak as soon as the
  ack shows, so the readback lands in about 0.3 s. Its cost is that tick's perception work running
  up to half a second late. Recommend: **build the plain one-poll version in Stage 3, and judge it
  on the Stage 3 card**; add the fast re-read only if it feels slow. Why: it is a small, separate
  addition, and the delay is easier to judge in the cockpit than on paper.
- **U6: Unpark within about one second of an "align" press.** ED may not have moved the overlay
  course yet, so Lua cannot know the aligned heading. Recommend: **mode 1 holds the last overlay
  course Lua read** (possibly the pre-align one), with no extra speech. Why: it is a one-second
  window the pilot opened himself by unparking, and the alternative (the measured heading) is no
  more right. Say if you would rather he says the heading he is holding.

**Answered 2026-11-20** (user, verbatim): *"1 - 1 s is acceptable"* (**U5**: plain one-poll
version; no fast re-read) and *"2 - overlay updates in a few frames. Anyhow, take whatever value
the overlay has."* (**U6**: on an unpark, mode 1 takes the overlay course as it is at that moment,
no extra speech). The second answer also bears on the align read delay: the overlay updates within
a few frames, so the implementer should use a delay of a few frames rather than borrowing
`MODE_READ_SETTLE_S` (1.0 s), and say what was chosen.
