# BL-16 mode 1 lift-vector control law — alignment

## Goal check — 2026-11-20

**Verdict:** CONCERNS

Branch `goal/lift-vector`, cut at `5b76822c` (`feature/bl16-lift-vector-law`). Inputs: the user's
words in `plans/flight-desired-state/explore-notes.md` (branch `feature/bl16-desired-state-s34`),
"Mode 1 control principles" and "Stage 1–2 card, rest of the flight"; `body-layer/ROADMAP/BL-16.md`
(lift-vector item, same branch); `plans/flight-control/explore-notes.md` (2026-10-26 lift-vector
direction, 2026-11-18 break, 2026-11-19 goal-check answers and mode-1 hover);
`docs/acceptance/2026-11-20-sortie-feedback.md`; `aircraft-layer/research/2026-11-20-motion-telemetry-frames.md`,
`2026-11-20-slip-ball-recon.md`, `2026-11-18-bl16-m0-flight-axes-findings.md`;
`plans/flight-control/plan.md` (Decisions 23, 27–32); `Petrobrain/flight_control.lua` at this tip.

### Why

The player hands the helicopter to Petrovich so they can look out and work the sight. That only
helps if they can **stop watching the aircraft**: it has to fly as a competent pilot flies it, so
the player never has to wonder what it is doing. Today it does not. It holds a heading with a
standing bank and crossed controls, turns without pedal, flies the break with back-cyclic that comes
in too late and then too hard, and a voice take produced "stupid attitude changes". Mode 1 is also
the only mode another helicopter will ever have (mode 2 is Mi-24 only), so it has to be the good one.

Asking why once more: the lift vector is the user's *mechanism*, the way they fly it themselves. The
*purpose* is felt flying quality: smooth, coordinated and predictable. The plan is judged by what
the player sees from the seat (wings, ball, nose, altimeter, how fast things move), not by whether
the law solves for a 3D vector.

### Player expectations

All of these are in forward flight, in mode 1, with Petrovich holding the controls. The speed range
is Q1's answer; today it is MIN_IAS 80 to MAX_IAS 280 km/h.

- **E1 — Take without upset.** On "you have controls" or an unpark, the controls do not visibly jump
  on the first frame. Within a few seconds the aircraft settles into the desired state (heading,
  altitude, speed) through smooth, monotonic changes. No pedal kick, and no bank or pitch excursion
  the player would call an attitude change. A take that starts away from the desired state (after
  m2→m1, desired speed 200 while flying 150) gets there through a gentle transition, not a lurch.
- **E2 — Heading hold looks like a pilot holding heading.** The wings are within a few degrees of
  level, the ball is centred (raw arg 943 near its centred +0.03), and the heading is steady on the
  HSI. No standing bank against standing pedal.
- **E3 — Coordinated turns.** An ordinary turn rolls in smoothly, holds a steady bank with the ball
  centred, which means pedal goes in with the turn ("use pedals"), and rolls out on the commanded
  heading without overshooting past the band or hunting back and forth.
- **E4 — Altitude held through turns.** In a level turn, and in an ordinary turn at any bank the
  rate asks for, altitude stays in its band, because collective adds lift as the bank increases.
  The aircraft does not sag in the turn and balloon on the roll-out.
- **E5 — Break: steep, fast, measured.** Bank goes steep (60–80°) quickly, and back-cyclic and
  collective come in **promptly and in proportion**: not late, then too much. Speed stays near the
  entry speed (some fluctuation allowed). Height loss is at most about 100 m, and never below
  40 m AGL. Pedal goes toward the turn. The roll-out lands on the break heading.
- **E6 — Speed and altitude changes are coordinated.** Accelerating tilts forward *and* raises
  collective, so the aircraft does not sink. Slowing tilts back *and* lowers collective, so it does
  not balloon. A climb or descent does not swing the speed by more than its band.
- **E7 — Gentleness scales with speed.** The slower the aircraft, the softer and slower the inputs.
  Near 80 km/h nothing is abrupt, and at 250 km/h a commanded change still happens briskly. Between
  commands nothing moves for no visible reason: no "stupid attitude changes", no oscillation, no
  control hunting the player can see.
- **E8 — Envelope first, and silent.** The rotor RPM floor, retreating-blade stall above about
  250 km/h, the VRS descent cap below 50 km/h and the 40 m AGL floor are never crossed to chase a
  goal. When one of them binds, the aircraft just does less (a shallower turn, a slower climb),
  silently (E15 of the 2026-11-19 check). Low, slow, with RPM dropping: accelerate (Q-M1-2).
- **E9 — The same across the envelope.** E1–E8 hold from about 50 to 800 m AGL, and across the speed
  range from Q1's lower bound to 280 km/h. They hold regardless of how the player trimmed before
  handing over.
- **E10 — Nothing new to hear.** The law changes how the aircraft flies, not what Petrovich says.
  Readbacks, "unable", and "You have controls!" on an envelope release stay as they are. A law
  that cannot reach a value says nothing more than the existing flags already allow.

### Open assumptions

- **What "measured acceleration" is.** It serves the why if trajectory error is measured as
  *kinematic* acceleration (velocity change: along-track, vertical, and turn rate × speed), and if
  `LoGetAccelerationUnits` is used for what it is, the *felt* load: body-frame specific force with
  gravity included. Its y reading tells how long the lift vector is, and its lateral reading tells
  how well the turn is coordinated. It does not serve the why if the felt load is compared directly
  with a desired kinematic acceleration. See Finding 1.
- **What the pedal regulates.** It serves the why if, in forward flight, the pedal centres the ball
  (with the collective-torque feed-forward and a nudge into the turn), and bank owns heading and
  turn rate. In hover (later), the pedal owns heading. It does not serve the why if the pedal runs
  a yaw-rate or heading loop in forward flight. See Finding 2.
- **What gives first when the lift vector cannot be long enough.** It serves the why if the order
  depends on the manoeuvre: in a break, turn rate, then speed, with height giving way within its
  100 m budget; in ordinary flight, the user's answer to Q2. It does not serve the why if one fixed
  order is carried over from today's "floor, then altitude, then speed", or if a joint solve spreads
  the shortfall evenly across all three. See Finding 3.
- **What heading and speed refer to.** It serves the why if forward flight references the
  aircraft's own heading (the nose, true, as the HSI shows) and IAS, the units the desired state is
  written in, and lets the aircraft drift with the wind. Hover would be ground-referenced (user,
  2026-11-19, Q1 "ground speed"). It does not serve the why if the direction and length of the
  world-frame velocity vector stand in for heading and speed. In wind that flies ground track and
  ground speed, so the HSI ends up off the commanded heading, and the user has said the desired
  value is exact (sortie 2026-11-20, "desired value must be correct").
- **What "desired 3D acceleration" means at low speed.** It serves the why if forward flight down
  to Q1's bound uses the same law with softer gains (E7), and hover is a later extension of the same
  law, in which lateral cyclic translates and the pedal yaws. It does not serve the why if the
  centripetal term V·r is pushed toward zero speed, where bank-to-turn stops making sense (user:
  *"Bank in hover is not the way to change heading"*).
- **Gains by speed.** It serves the why if the gains are scheduled by IAS, or by something
  equivalent, so that E7 holds. The slip-ball calibration already shows the response to pedal
  changes with speed. It does not serve the why if one set of gains is tuned at cruise and then
  flown at 80 km/h.
- **Channels not yet calibrated** (accel x/z, velocity x/z, wind vector, AoA and sideslip getters).
  It serves the why if only channels whose sign is confirmed close a loop, and the rest are logged
  until a probe settles them. It does not serve the why if they are used because "raw telemetry"
  was asked for: a wrong sign runs away, which is worse than a slow derived value. Q4 asks which
  should come first, the probe or the law.
- **The SAU state at handover.** It serves the why if the law behaves acceptably with the K/H/T
  channels on and off, or the plan states which one it assumes. It does not serve the why if it is
  tuned in one state and silently misbehaves in the other: M0 showed attitude spread roughly three
  times smaller with the SAU on.
- **Per-aircraft profile.** It serves the why if gains, curves, limits and rotor direction live in
  one Mi-24P profile table (BL-16, user). It does not serve the why if they are scattered across
  module constants. This is already decided, so it is listed only so that the plan carries it.

### Findings

1. **The felt load is not the acceleration to steer by, and treating it as one makes the aircraft
   sink in every bank.** Lens: world truth.
   - **Assumption:** "Read acceleration from raw telemetry, what a pilot feels" is filled with
     `LoGetAccelerationUnits` used as the measured acceleration in the error "desired minus
     measured". The research note's own first approach recommends exactly this for the vertical
     channel: use y in place of the VS derivative.
   - **In the sim:** that reading is body-frame specific force with gravity included (research note,
     finding 1; M0 measured y at 0.69–1.35 g in near-level cruise). In a level turn at 60° bank, y
     reads about 2 g while vertical acceleration is zero, and the lateral reading is about zero
     because the turn is coordinated.
   - **The pilot would see:** a vertical channel that reads "+1 g too much" in a 60° bank cuts
     collective in every turn and break, so the aircraft sinks (against E4 and E5) and balloons on
     the roll-out. Unfiltered, the same reading at 140 Hz also carries rotor vibration (the
     0.69–1.35 g spread in near-level cruise), so the controls hunt (against E7).
   - **Grounded in:** `2026-11-20-motion-telemetry-frames.md` finding 1, which says gravity is
     included and the frame is the body; the M0 numbers; and the user's own framing that the
     reading is what a pilot *feels*. The physics is the agent's own, but the frame and gravity
     facts are the research note's.
   - **Suggests:** keep the two uses apart. The felt load tells how long the lift vector is (y) and
     whether the turn is coordinated (lateral), which is the same thing the ball shows. The
     trajectory error is kinematic: velocity change, and turn rate × speed. The plan should say
     which signal closes which loop.

2. **A "tail-rotor force loop" that regulates yaw or heading rebuilds tonight's crossed-controls
   heading hold.** Lens: purpose / crew sense.
   - **Assumption:** "Pedals as a tail-rotor yaw-force loop" (BL-16 item) is read as the pedal
     closing on yaw rate or heading error, while bank closes on turn rate. Two loops then own the
     heading.
   - **In the sim:** that is the failure the user flew: *"Petrovich increased left pedal quite a lot
     -> left yaw -> bank right to compensate -> ends up maintaining heading with right bank"*. Today's
     `phi_i` integrator on the turn-rate error is the bank half of it.
   - **The pilot would see:** a standing bank against standing pedal, with the ball off centre
     (against E2 and E3).
   - **Grounded in:** the sortie feedback of 2026-11-20 (the take, and "use pedals" in turns); the
     slip-ball calibration (the ball is centred by feedback, *"not straightforward function of pedal
     deflection"*); and the user's *"Bank in hover is not the way to change heading"*, which implies
     bank is the way in forward flight.
   - **Suggests:** in forward flight the pedal owns the ball: centre it, with the torque
     feed-forward ("more collective → more right pedal") and a nudge toward the turn. Bank owns
     heading and turn rate. Only one of the two owns heading at any speed, and the handover between
     them belongs to hover, which comes later. Q6 settles how much pedal into a break, beyond
     centring the ball, the user wants.

3. **One fixed priority order contradicts the break.** Lens: purpose.
   - **Assumption:** when collective is capped (RPM floor or blade stall), the new law keeps the
     existing saturation order, "floor, then altitude, then speed" (Decision 23's test list).
     Alternatively, a joint solve spreads the shortfall over all three components.
   - **In the sim, and in the user's words:** in a break the user wants a fast turn and *"Keep the
     speed up at about what is was when starting the break"*, with *"Moderate altitude drop allowed
     (~100 m, but never below 40 m AGL)"*. So in a break, height gives way first, within its budget,
     and speed is kept. When low, slow and losing RPM: *"accelerate"*, so speed comes before height
     there as well.
   - **The pilot would see:** with "altitude over speed", a break bleeds speed to hold height,
     which is exactly *"pulls too much cyclic and speed drops fast"* (against E5). With an even
     spread, every manoeuvre goes vaguely soft.
   - **Grounded in:** `plans/flight-control/explore-notes.md`, the 2026-11-18 break and speed notes
     and the 2026-11-19 Q-M1-2 answer.
   - **Suggests:** the order is part of the manoeuvre, carried with the desired state the way the
     break's rate override already is, and the envelope always comes first. The order for ordinary
     turns is Q2.

4. **"The lift-vector law fixes the erratic voice take" has not been shown.** Lens: purpose, the
   non-obvious case.
   - **Assumption:** the off → mode 1 "weird control writes" on the Stage 1–2 card are a
     flying-quality problem, so the new law is their answer (explore notes: *"the lift-vector law is
     the planned answer to mode 1's flying quality"*).
   - **In fact:** nothing has diagnosed them. That card ran the new mode authority (Stage 2), and
     the same flight also unparked to off instead of mode 1, which points at the take path. If the
     cause is the seed, a stale goal or the authority, the new law inherits it.
   - **The pilot would see:** the same erratic take on the first lift-vector flight, with two
     possible causes and no way to tell them apart. BL-16 kept the law on its own stage precisely so
     that *"a bad flight has one cause"*.
   - **Grounded in:** the explore notes, "Stage 1–2 card, rest of the flight"; the BL-16 lift-vector
     item.
   - **Suggests:** the plan treats E1 as something the law must not break, not something it repairs,
     and the take is retested on desired-state Stages 3–4 before the law flies. This is a
     sequencing note; nothing here needs the user to answer it.

5. **Vignette: a break entered at about 100 km/h.** Lens: the envelope.
   - **Situation:** the break keeps speed "about what it was". At 100 km/h, though, the plan's
     kinematic bank for the break rate (about 40°/s) is around 70°. At that speed a steep, loaded
     turn costs speed quickly. If IAS sinks under MIN_IAS minus the margin for `ENV_HOLD_S`, the
     envelope hands back, "You have controls!", in the middle of a 70° bank, low.
   - **The pilot would see:** a hand-back at the worst moment.
   - **Grounded in:** the merged `check_envelope` (the IAS release is still live; the bank release
     was removed under F-M1) and E7, "the slower, the more gentle".
   - **Suggests:** at low entry speed, a break is gentler (a lower turn rate) rather than released.
     This follows from E7 and E8, and it is a question only if the user disagrees.

### Questions for the user

1. Does this law fly forward flight only, with hover later as you said? And what is the slowest
   speed it should fly: today's 80 km/h hand-back, or down to about 50 km/h (the VRS limit), since
   25–50 km/h was "acceptable" in your hover answer?
2. In an **ordinary** turn, when the rotor cannot give more lift (RPM or blade stall), what gives
   first: turn rate (shallower turn), altitude or speed? (Recommend: turn rate first, keeping height
   and speed. A break keeps turn rate and speed and gives height within 100 m, as you said.)
3. When you hand over, are the SAU channels usually on? Should mode 1 fly the same with them off?
4. Some telemetry axes still lack a confirmed sign: forward and sideways acceleration, and velocity
   north/east. Fly a short probe before the law, or fly the law first on what is already confirmed
   and add the rest later? (Recommend: law first; probe rows on the same card.)
5. Holding a heading in a crosswind: hold the **nose** on the commanded heading and drift with the
   wind (what the HSI shows), not the ground track. Agreed? (Recommend: nose heading, which keeps
   the desired value exact.)
6. In a break you said "pedal to direction of turn". Is that the pedal it takes to keep the ball
   centred, or a deliberate extra yaw into the turn, ball off centre, to tighten it?

## Plan check — 2026-11-20

**Verdict:** CONCERNS

Plan: `plans/flight-lift-vector/plan.md`, architect pass + same-day amendment for U1–U7, branch
`feature/bl16-lift-vector-law` tip `2c42e2f9`. All six goal-check questions were answered by the
user and traced below; U5's extra pedal, the felt-load collective loop, and the Q6 ball-offset
target were checked against the full plan text (grep, not just the amendment header) and found
nowhere left as live design — fully superseded. U8 ("no floor") is a different story: see Finding 1.

| expectation | stage | status |
|---|---|---|
| E1 — take without upset | I, LV-0 card | met |
| E2 — heading hold, wings level, ball centred | D, F; LV-1 | met |
| E3 — coordinated turns, pedal with the turn | D, F; LV-1 | met |
| E4 — altitude held through turns | E (feed-forward on bank); LV-1 | met |
| E5 — break: steep, fast, measured | G (break chain), LV-2 | met |
| E6 — speed/altitude changes coordinated | C, G (slowing-down rule); LV-1 | met |
| E7 — gentleness scales with speed | B (schedule G(V)); LV-1 | met, undermined at the low end — Finding 1 |
| E8 — envelope first, silent | G (priority chains); LV-1/LV-2 | met |
| E9 — same across the envelope, any speed (Q1) | LV-1 (forward scope) → deferred → LV-3 (λ blend, ground-speed ref, pedal yaw loop) | met in LV-1's declared scope; the gap between that scope and Q1/U8's "any speed, no floor" is Finding 1, not closed by the LV-3 deferral |
| E10 — nothing new to hear | U1 removes `TOO_SLOW` speech; U8 removes the clamp-readback that would have added a new line | met |

Goal-check findings 1–5: all five resolved in the plan as built (no felt-load channel closes a loop,
sect. E; pedals never run a heading loop in forward flight, sect. F; priority order travels with the
manoeuvre, sect. G; the law is explicitly not assumed to repair the erratic take, sect. I, LV-0
retests it alone; the slow-break vignette is now a carded LV-2 row, U6).

Open assumptions (goal check): all eight settled the way that serves the why — kinematic
acceleration for trajectory error (A, E), pedal-centres-ball with bank owning heading in forward
flight (D, F), per-manoeuvre priority order (G), nose heading/IAS in forward flight with
ground-speed only near hover (C, U2), the λ blend as the hover extension of the same law (diagram 5),
speed-scheduled gains (B), unconfirmed channels logged-only and gated on LV-0 (A), and the SAU state
the law assumes stated explicitly (off, U4). No silent assumption-filling found among these eight.

### Findings

1. **U8's final answer ("no floor") was never carried into the plan's own design text, and the
   stale text describes a mitigation that no longer exists.** Lens: world truth / internal
   consistency.
   - **Assumption:** the plan's closing paragraph (U8) says the implementer should apply "no floor"
     "wherever the plan above still says 'floored at 50 km/h' or 'until LV-3'" and names four places
     (Affected Modules, the LV-1 build, the Co-moving table, the LV-1 card's low-speed rows).
   - **In the plan:** at least three more places still say the floor protects LV-1 and were not
     named: diagram 5 (`Blend, 25 to 50 km/h`, `λ = 1 throughout and the commanded speed floored at
     50 km/h`), diagram 6 (`LV1[... commanded floor 50 km/h]`), the "Removed and kept" table
     (`MIN_IAS_KMH` row: "50 km/h in LV-1, removed in LV-3"), the Tests section ("a take at 40 km/h
     is accepted and flown to the 50 km/h floor without a jerk (LV-1)"), and — the one that matters
     most — the Risks & Unknowns entry itself: *"LV-1 below 50 km/h is flown by the forward law with
     gentle gains, no ground-speed reference and no pedal yaw loop. **The commanded floor keeps the
     law from being asked to go there**; a sag below it is a gentle return, watched on the 70 km/h
     take row."* That sentence is now false: U8 removed the floor, so a *commanded* speed below
     50 km/h is no longer refused or clamped — the law will be asked to go there, in LV-1, with no
     ground-speed reference and no pedal yaw loop, and the one card row that would watch this ("a
     voice take at about 70 km/h") never goes below 50.
   - **The pilot would see:** exactly the gap the architect's own (overruled) U8 recommendation
     warned about — "a 'speed 20' command would be flown by the forward law with no ground-speed
     reference and no pedal yaw loop" — except now untested and undocumented as live risk, because
     the Risks section still reads as if the floor prevents it.
   - **Grounded in:** `plan.md` lines 152, 229, 235–236, 260–262, 434, 470–474, 497, 517, 540,
     593–594 (`grep -n "50 km/h\|floor" plan.md`) against the final U8 answer at lines 657–663.
   - **Suggests:** this is the user's own informed risk ("what does not work, I will bring back and
     we fix," Q1) and not a reason to reopen U8 — but the Implementer is working from a document
     that still tells a different story about what protects LV-1 below 50 km/h in at least seven
     places, three of which the amendment's own fix-list missed. The Risks entry should say plainly
     that nothing protects LV-1 below 50 km/h except the gain schedule, and the LV-1 card should gain
     a row near the new floor-less bottom (e.g., a voice take or a slow command at 20–30 km/h) so the
     first time this is seen is a card, not a flight.

2. **The SAU-on-at-handover rule has no stage or ID to carry it, and is explicitly excluded here.**
   Lens: purpose / crew sense.
   - **Assumption:** `explore-notes.md`'s "SAU in mode 1" section records a user rule independent of
     SAU stage 2 — "whenever mode 1 hands the controls to the player (mode off), switch SAU H, K, T
     (and B) ON" — with the effectors already named
     (`body-layer/config/sequences/mi-24p/switch-reference.md`). The plan (line 577) says this rule
     "is independent of this law and not part of this plan," and the card preamble (line 445–448)
     only reacts to it conditionally ("if the separate rule is built before a card is flown...").
   - **In fact:** I checked `body-layer/ROADMAP/BL-16.md` (the lift-vector item's own source branch),
     `todo/todo/` and `todo/backlog/`, and grepped the graph (not indexed past 2026-11-17, so a miss
     here is weak evidence, confirmed with grep too) — this rule exists nowhere outside
     `explore-notes.md`'s own prose. No `[[ID]]`, no named stage, no backlog entry.
   - **The pilot would see:** nothing wrong from this plan directly (stage 1 doesn't touch the
     handover path), but a settled, concrete, already-specified rule (mechanism and effectors named)
     sits in a plan's explore-notes with no destination — exactly the retro-2026-11-13 shape ("a
     deferral with no tracked home is an expectation quietly dropped"), except here it is not even
     labelled deferred.
   - **Grounded in:** `explore-notes.md` "SAU in mode 1" and "Main-loop reading"; `plan.md` lines
     445–448, 577.
   - **Suggests:** mint a backlog ID for it now (it is small, well-specified, and independent of
     every LV stage) rather than letting it live only in explore-notes.

### Questions for the user

1. Finding 1: should the Risks & Unknowns entry and the LV-1 card be corrected to reflect "no floor"
   honestly (no mitigation below 50 km/h besides the gain schedule, and a low-speed row added), or
   is the existing LV-1 scoping ("the card avoids flying below about 60 km/h on purpose") the answer
   — i.e. accept the gap as untested until it is flown, per Q1's own terms?
2. Finding 2: should the SAU-on-at-handover rule get its own backlog ID now, since it is fully
   specified and independent of every lift-vector stage, so it does not quietly disappear?
