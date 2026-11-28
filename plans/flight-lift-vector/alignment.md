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

## Goal check — 2026-11-24 — LV-1 amendment, fourth re-fly

**Verdict:** CONCERNS

Branch `feature/bl16-lift-vector-law` at `efdfd839`. Inputs: `docs/acceptance/2026-11-24-sortie-feedback.md`
"Fourth re-fly" to the end (the specification); `plan.md` B, D, E, G, I and the LV-2/LV-3 scope;
`explore-notes.md` (U3, "Slowing down"); `body-layer/ROADMAP/BL-16.md` decisions 3 and 5 and the
hover note *"the slower the flight, the more gentle inputs need to be"*; the goal check of
2026-11-20 above (E1–E10). Code read only to confirm existing behaviour: `flight_profile.lua`
(`speed_accel_cap_mps2 = 0.5`, `theta_min_deg = −15`, `c_theta = 0.5`, the RPM and blade-stall
collective-rate caps of 0 inside their margins), body-layer `MAX_ACCEL_MPS2 = 1.0`,
`RETREATING_BLADE_STALL_IAS_KMH = 250`, `MAX_TURN_BANK_DEG = 20` (the bank of a commanded
continuous turn), and `config/rules/flight.lua` ("turn left/right" with no degrees = continuous
turn; "stop turn"; "level flight").

### Why

The player hands over mid-whatever and turns to the sight. They can only do that if Petrovich
**carries on what the aircraft was doing** and, when told to change something, does it **the way the
player would have** — brisk, small, constant corrections — so the aircraft is never late, never
lurching and never wandering while nobody watches it.

Asked why once more: the first answer is "fix the turn and speed up the speed change"; the second is
that **slowness is itself the defect the user flew.** Every complaint in this report is a lag: the
take levels off before resuming, speed takes 60 s instead of 20, pedal trails collective, pedal
changes too slowly and oscillates, corrections "lag the actual flight state". The founding promise
(decision 5, "S-curves, no oscillation") is still the goal; the user's diagnosis is that oscillation
here comes *from* sluggish corrections, not from fast ones. So the amendment is judged by
promptness *and* smoothness together, and a fix that buys smoothness by slowing things down again
moves away from the why.

### Player expectations

These extend E1–E10 of 2026-11-20; where one changes an earlier expectation it says so.

- **E11 — A take in a bank keeps the bank.** On "you have controls" (or an unpark) with |bank| ≥ 5°
  and no standing heading goal, the bank stays within a few degrees of what it was at the take, the
  aircraft keeps turning the same way, ball centred, and keeps doing so until the player commands
  something. With |bank| < 5°, the wings come level and the heading holds on the take heading. The
  5° is a first cut, tunable. (Decision 3, *"keep the turn going"*; amends E1's "settles into the
  desired state" for this case.)
- **E12 — Mode 2 → mode 1 mid-turn never rolls level first.** When mode 2 had a heading goal and
  was turning, the bank continues smoothly through the handover and the aircraft rolls out once, on
  the mode-2 heading. No wings-level moment between.
- **E13 — While a held bank flies, height and speed hold** (main loop's assumption, not yet asked;
  Q3 below). The altimeter does not sag through the circle.
- **E14 — Speed change in about 20 s for 100 km/h.** On "speed 250" from 150 km/h level: within 1–2
  s the nose is at about −15°, collective up and right pedal in with it, ball centred, altitude
  held. The nose stays near −15° until about 230 km/h, then comes up, collective down, pedals
  follow, and speed settles on 250 without overshoot or hunting. Total about 20 s. Beyond −15° only
  briefly and only when height is being traded for speed (no current command asks for that).
- **E15 — Deceleration mirrors it, with a slow roll-out.** Nose up, collective down, left pedal,
  promptly; near the target speed, nose down and collective **up smoothly over about 5 s**, so the
  rotor RPM does not drop and the aircraft does not sink. Consistent with the 2026-11-20 rule
  *"slowing down is always pitch back and also less collective"*.
- **E16 — Inputs are fast, frequent and small.** Watching the controls: cyclic moves quickly and
  often in small steps; pedals keep up with collective changes rather than trailing them; a small
  collective correction is quick; a large collective change (above all an increase) is spread out.
  Never one large jump at a fast rate. **Amends E7:** gentleness at low speed is in the *size* of
  each correction, not in slowing the input rate — *"The input changes themselves can be fast
  always… the amount of delta needs to get slower as speed slows."*
- **E17 — Breaks fly as an escape (LV-2).** Bank goes steep and **stays** steep until near the break
  heading; the nose does not rise (speed is kept, as E5 already said). Sharpens E5's "measured" to
  "aggressive and controlled".

Not expectations of this amendment (tuning or later stages, recorded so they are not lost): wobble at
the take; pedal lag on collective increases (covered by E16 as an outcome); ~50 km/h left yaw out of
control on row 10 (LV-3 low-speed scope, and LV-1's slow-flight row did its job of finding the edge).

### Open assumptions

- **What "hold the bank" is.** Serves the why: a continuous turn at the **bank measured at the take**
  (averaged over the take's own wobble), held as bank. Would not: reusing the existing commanded
  continuous turn ("turn left" with no degrees) as is — it flies the turn rate of
  `MAX_TURN_BANK_DEG` = 20°, so a 40° turn taken over rolls out to 20° and a 10° turn rolls in to
  20°. Finding 2.
- **What ends a held bank.** Serves the why: a heading-type command — "turn heading", "turn left/right
  [NN]", "stop turn", "level flight", a break — ends it; a speed or altitude command changes speed or
  height *inside* the turn. Would not: any desired-state write ending it. A speed command that
  re-applies the whole desired state (heading included, e.g. heading = current) would level the
  aircraft — exactly the levelling the user just rejected, arriving one command later. Q3.
- **Bank held or turn rate held while speed changes inside the turn.** Serves: bank, as the user
  said; the turn tightens as speed falls, which is what a pilot holding a bank sees. Would not
  matter much either way; listed so the plan says which.
- **The 5° rule's input.** Serves: the averaged bank at the take, with the threshold in the
  profile. Would not: the single take frame, where the "wobbly" take can flip a 5–6° bank either
  side of the line.
- **Mode 2 → mode 1 turn direction.** Serves: keep turning the way the aircraft already turns toward
  the mode-2 heading (that is what mode 2 chose). Would not: recomputing the shortest arc at the
  handover, which can only disagree if mode 2 was flying the long way round on a commanded
  direction — rare, but it would roll the aircraft through level into the other bank.
- **Where 20 s comes from.** Serves: 20 s is an outcome on the card, reached by whatever lets the
  nose go to −15° in 1–2 s. Would not: raising `speed_accel_cap_mps2` alone. 100 km/h in 20 s is
  ~1.4 m/s² *average* with a 1–2 s onset; body-layer's own `MAX_ACCEL_MPS2 = 1.0` ceiling alone
  means ≥ 28 s plus the S-curve tails. Finding 4 covers the deeper half.
- **What "pedals move more slowly in Mi-24 anyhow" asks for.** Serves (per the flight report):
  Petrovich's pedal corrections become faster and more frequent, because the aircraft's own yaw
  response is already slow — *"pedal inputs change quite slowly, which may cause overshoot and
  oscillation"*, *"cyclic and pedal changes are slow"*. Would not: the main loop's paraphrase
  "pedals slower" read as "keep or add a slow pedal rate limit". Finding 1; Q5.
- **How a large collective increase is made gentle.** Serves: the increase is spread over its time
  (~5 s at a decel roll-out) **by design**, so RPM never droops. Would not: commanding it fast and
  relying on the RPM guard — that guard is reactive (`collective_rate_cap_near_rpm_floor = 0` inside
  a 5 % margin), so RPM droops to the margin first, then collective freezes and the aircraft sinks at
  the end of a deceleration. Finding 3.
- **How "fast inputs" meets the blade-stall guard at 230–250 km/h.** Serves: E14's own settle
  (nose up, collective **down** from ~230) runs into nothing — the guard only caps collective
  *increases* inside 230–250 km/h. Would not matter unless the acceleration overshoots or sags near
  250, where collective cannot rise and speed gives (U3) — a silent "does less", per E8. No action;
  noted because 250 is both the user's example target and the guard's line.

### Findings

1. **"Pedals slower" filled literally keeps the oscillation the user reported.** Lens: purpose.
   - **Assumption:** the main loop's reading *"pedals slower in the Mi-24 anyway"* becomes "pedal
     corrections stay slow / get a slower rate than cyclic".
   - **The user's words:** rows 4 and 7 and the general observations say the pedal is **too slow**
     now and that is what oscillates. The sentence "pedals move more slowly in Mi-24 anyhow" reads,
     in context, as a fact about the aircraft, not a request.
   - **The pilot would see:** yaw offset after every collective change and slow overshoot, again
     (against E16 and E7's "no oscillation").
   - **Grounded in:** `2026-11-24-sortie-feedback.md`, rows 4, 7, general observations, answer 3.
   - **Suggests:** treat it as a question until answered (Q5), and plan pedal toward *faster and
     with collective* in any case — that is what the report asks for either way.

2. **Reusing the continuous turn for a held bank resets the bank to 20°.** Lens: unit of action /
   the non-obvious case.
   - **Assumption:** "hold that bank" is built as the existing mode-1 continuous turn, which is the
     natural existing mechanism (and should be reused, per "do not reinvent").
   - **In the code:** the continuous turn flies the turn rate of `MAX_TURN_BANK_DEG` = 20° at
     current speed.
   - **The pilot would see:** hand over in a 45° turn, and the aircraft rolls out to 20° and keeps
     circling wider — a visible attitude change at the take, against E11 and E1's "no bank
     excursion".
   - **Grounded in:** user, *"If bank is more than that, maintain bank"*; `flight_control.py`
     `MAX_TURN_BANK_DEG`; `flight.lua` continuous turn.
   - **Suggests:** reuse the continuous-turn mechanism, parameterised by the bank captured at the
     take; "stop turn" / "level flight" already end it.

3. **The RPM guard is not the "gently" the user asked for.** Lens: world truth (the user's).
   - **Assumption:** "collective up fast" for the speed changes is made safe by the existing RPM and
     blade-stall guards.
   - **The user's words:** *"collective needs to be raised fairly slowly to give the engines time to
     spool up… otherwise rotor RPM drops fast. Say ~5 seconds"*, and earlier *"Rotor blade load is
     what causes both RPM drop and retreating blade stall."* The spool-up time is something to
     anticipate, not detect.
   - **The pilot would see:** at the end of every deceleration, RPM droops, collective freezes, the
     aircraft settles below its height (against E15).
   - **Grounded in:** answer 2; explore-notes "Slowing down"; `flight_profile.lua` RPM cap.
   - **Suggests:** large collective increases are shaped in time by the law itself; the guard stays
     as the backstop it is.

4. **Two recorded design premises pull against E14 and need restating, not quietly overriding.**
   Lens: purpose; flags earlier decisions.
   - **(a) Plan section I / E1:** *"a take 50 km/h below the desired speed is a gentle transition,
     not a lurch."* With E14, the same speed shaper after an m2→m1 take with desired 200 at 150
     km/h pitches the nose to −15° within 2 s of the take — which the user may call a lurch, and
     which lands on top of the take's known wobble. Either the take keeps a gentler speed
     transition or the brisk profile applies there too; only the user can say (Q2).
   - **(b) Plan section D:** the pitch target is a half feed-forward (`c_theta = 0.5`) plus a trim
     loop deliberately "several seconds" slow, the stability argument of the law, and BL-16's
     *"feedback, not a model… applied incrementally and smoothly"*. The observed −8° and 60 s are
     what that produces. E14's −15° in 1–2 s cannot come from a several-second trim loop; it needs
     the pitch to be reached promptly. The user's own rule reconciles this with decision 5 and
     "feedback, not a model": **many small corrections at a fast cadence** is still incremental
     feedback, and **no overshoot on the approach** (the settle from ~230) is still the S-curve. What
     changes is the *onset*: fast. So decision 5 does not conflict with "aggressive, 20 s" — it
     governs the approach, not the start — but the plan's "slow trim" premise does, and the
     Architect should say so explicitly rather than retune around it.
   - **Grounded in:** `plan.md` I and D; `BL-16.md` decision 5 and the lift-vector "feedback, not
     a model" line; feedback answers 1 and 3; `flight_profile.lua` values above.

5. **Vignette: handover while the player is rolling out.** Lens: the non-obvious case.
   - **Situation:** the player is rolling out of a turn onto a heading, passing 12° bank, and says
     "you have controls" so as to look at the sight.
   - **By the rule:** 12° ≥ 5°, so Petrovich holds 12° and keeps circling, away from the heading the
     player was rolling out on, until told "stop turn".
   - **The pilot would see:** a slow, unexpected circle while their eyes are in the sight.
   - **Grounded in:** the rule as stated; the agent's own reading of what a pilot means by handing
     over mid-roll-out — so this is a question (Q4), not a finding against the rule.

### Questions for the user

1. Accelerating, you put in "lots more collective… all in 1–2 s"; you also said large collective
   increases need to be gentle (~5 s at the end of a deceleration). Is the acceleration entry an
   exception — engines already at cruise power — or should that increase also be spread out?
2. A take with a speed gap (mode 2 → mode 1, desired 200 while flying 150): fly the brisk speed
   change straight away, or a gentler one because it is a handover? (Plan I currently says gentle.)
3. After a take in a bank, does a speed or altitude command end the held turn, or only a heading
   command, "stop turn" or "level flight"? And does the held turn hold height and speed?
   (Recommend: only heading-type commands end it; height and speed held.)
4. If you hand over while rolling out of a turn (bank passing ~12°, coming level), should he keep
   circling at 12° per the 5° rule, or finish the roll-out? (Recommend: keep the rule as stated —
   "stop turn" is one phrase — unless this is a handover you make often.)
5. "Pedals move more slowly in Mi-24 anyhow": do you mean the aircraft's yaw response is slow, so
   Petrovich's pedal corrections should be **faster** than now? (Recommend: yes, per rows 4 and 7.)

## Plan alignment — 2026-11-24 — LV-1 amendment

**Verdict:** CONCERNS

Checked `plan.md` "LV-1 amendment (2026-11-24, fourth re-fly)" to the end (branch
`feature/bl16-lift-vector-law`, detached at `2ce1b61a`) against the goal check above (E11–E17) and
the five answered questions, plus `docs/acceptance/2026-11-24-sortie-feedback.md`'s own answers.

| expectation | stage | status |
|---|---|---|
| E11 — take in a bank keeps the bank | A | met — new `hdg_mode="bank"`, `bank_hold_deg=φ̄` (averaged), 5° threshold, `a_r,d = g·tan(bank_hold_deg)` bypassing the turn-rate path finding 2 named |
| E12 — mode2→mode1 mid-turn never rolls level first | A (E12 sub-section) | met, flagged — fix located in `law_init_at_take`'s unpark branch by symptom (t=366.5/409.5 trace), not yet by line; ships inside LV-1 per answered U10, not its own stage |
| E13 — height/speed held through a held bank | A, diagram 1 (HOLD2) | met — explicit, both in prose ("E13" cited directly) and the diagram |
| E14 — speed change ~20 s, −15° onset in 1–2 s | B, C | met in design intent; **contradicted in part** by stale rotor-RPM text in C's own header and lead-in — see Finding 1 |
| E15 — deceleration mirrors it, collective up over ~5 s | C | met — same RPM-gated taper formula serves both, by design; same Finding 1 caveat on which RPM it reads |
| E16 — fast, frequent, small corrections; pedal keeps up with collective | D, E | met, with an unverified margin — gain increases (ball P-term, torque FF 0.25→~0.6) are asserted to close the 0.16/s → ~0.9/s gap from one measured case (row 4); not computed for rows 7/8-9's conditions. Not a contradiction — same "first cut, card measures" posture as every other gain here — but worth naming, see Finding 2 |
| E17 — breaks fly as an aggressive escape | F → **LV-2** | deferred → Stage LV-2 (`F. Breaks — LV-2, recorded only`; the user's verbatim complaint is carried into F's text, and the roadmap diagram names LV-2's card "breaks, floor, RPM dummy") |
| Q1 — collective rate depends on engine state, not manoeuvre | C (same-day correction) | met for the corrected design itself; **contradicted** by un-updated text elsewhere in the same section's lead-in and the "Decisions answered" paragraph — Finding 1 |
| Q2 — speed change is brisk, including on a speed-gap take | B, I (dated note) | met — section I itself carries the restriction to the speed channel, not silently overridden |
| Q3 — only heading-type commands end a held turn; height/speed hold | A, "What reading the code turned up" §1 | met — shown to be already true of `apply_set`'s per-field writes, confirmed by a direct code read, not merely asserted |
| Q4 — keep the 5° rule as stated, vignette 5 accepted | "Decisions answered" | met — no design change, accepted as a named consequence |
| Q5 — pedal should get faster, not slower | D, "Decisions answered" | met — explicitly closes goal-check Finding 1, with the measured aircraft cap (~0.9/s) and Petrovich's own rate (p99 0.16/s) as the gap to close |

### Findings

1. **Three passages still reason on the wrong RPM after the same-day engine/rotor correction.**
   Lens: evidence rule / purpose.
   - **Assumption:** the correction box at the top of section C ("gate on **engine** RPM, not rotor
     RPM... wherever the text *below* says RPM, read engine RPM") fully supersedes every earlier
     mention.
   - **In the plan:** it does not reach backward. Three places still describe the *rotor*-RPM
     reading as the mechanism:
     - The section's own header, unchanged: `### C. Collective rate — E14/E15/Q1, **the
       rotor-RPM-gated schedule**`.
     - "Decisions answered," Q1: *"Built as a **rotor-RPM-gated** collective-rate schedule (new,
       see 'Collective rate' below), reading the existing `read_rotor_rpm_pct()` once its
       calibration is confirmed (U9)."* `read_rotor_rpm_pct()` reads arg 42 — rotor RPM, not the
       engine args (40/41/838/839) the correction requires.
     - "What reading the code turned up," point 2: *"A rotor-RPM read already exists, flagged for
       exactly this use... no new telemetry, no engine/torque proxy needs inventing; this is the
       calibration flight that reading was always waiting for."* This directly contradicts the
       correction, which **does** require a new read (args 40/41, operator 838/839) that no cited
       function currently reads.
   - **The pilot would see:** if an implementer builds from these three passages rather than the
     correction box, the schedule gates on rotor RPM — exactly the inversion the user's cockpit
     readings were given to prevent (fast collective allowed precisely when the engines are
     spooled down, because rotor RPM is then at its *highest*, 100%).
   - **Grounded in:** `plan.md` lines ~940 (header), ~828–829 (Q1 decision text), ~758–765 ("what
     reading the code turned up" point 2), against the correction box immediately below the header
     and the user's cockpit readings in the sortie feedback.
   - **Suggests:** before Implementer, reword the header to "the engine-RPM-gated schedule," amend
     the Q1 decision paragraph to name args 40/41/838/839 and drop "reading the existing
     `read_rotor_rpm_pct()`," and correct point 2 to say a new engine-RPM read is needed (it is not
     "the calibration flight that reading was always waiting for" — that line described the rotor
     read, now relegated to the unchanged generator-trip floor).

2. **Pedal gain increases are asserted to close the 0.9/s gap from a single measured case.** Lens:
   evidence rule. Not a contradiction — the plan explicitly treats `c_theta`, the collective
   schedule's thresholds, and these pedal gains the same way ("first cut... measured on the LV-1
   card"), which is this project's own established posture for every gain in this law. Flagging
   only because the task asked specifically: the row-4 climb's measured "~0.6 per unit collective
   rate" is the only case computed; rows 7 and 8–9 (take at 70 km/h, take-from-bank) are not
   checked against whether the same gain reaches close to ~0.9/s under their own collective-rate
   and ball-error magnitudes. No suggested change — the card is where this gets settled, same as
   the rest of section D.

### Questions for the user
- None — all open questions from the goal check (Q1–Q5) are answered and the answers are reflected
  in the plan's decisions (modulo Finding 1's stale text, which is a plan-wording fix, not a
  question).

## Plan check — 2026-11-27 — LV-2 amendment (breaks)

**Verdict:** CONCERNS

Checked `plan.md` "LV-2 amendment (2026-11-27)" to the end (branch `fix/bl16-flight-epoch-bound`,
tip `866fb63b`; the amendment's final paragraph records U11 answered and the diagrams approved)
against E5/E17 (goal check, 2026-11-20) and the user's own verbatim LV-2 answers in
`explore-notes.md`, "LV-2 explore — breaks (2026-11-27)." No dedicated goal-aligner pass exists for
LV-2; the explore answers serve as the settled expectations, per the task brief, so E18–E21 below
are reconstructed directly from the user's own words, not derived by this pass.

| expectation | stage | status |
|---|---|---|
| E5 — break: steep, fast, measured | B (bank/rate cap), C (height-gives routing) | met in shape; the G actually reached runs higher than intended — Finding 1 |
| E17 — breaks fly as an aggressive escape (deferred here from LV-1) | Design Overview, B, C, "what reading the code turned up" §1 | met — closes the LV-1 amendment's deferral; steep bank, no separate end condition, roll-out on break heading all addressed |
| E18 — ~2 G accepted, momentarily (*"I seem to go to about 2 G"*) | B (`break_max_bank_deg = 65°`) | contradicted in part — the cap itself yields 2.37 G, and B's own "Effect, by speed" note shows it binds continuously (not momentarily) at all three card speeds — Finding 1 |
| E19 — less, smoother pull-back: turn from bank + collective, not aft cyclic; no violent oscillation | C (class-aware shortfall routing) | met — `effective_shortfall` scaled toward 0 while height has budget, which is the pitch-back/bank-easing the user reported |
| E20 — height gives first, bounded by both ≤ 100 m loss AND ≥ 50 m AGL | C, D | met — `break_floor = max(break_floor_agl_m, break_entry_h_m − break_max_height_loss_m)`, both budgets live together, confirmed against the same-day correction text |
| E21 — break = ordinary heading goal (±90°/±180° break-away), flown more aggressively, no new end condition | "What reading the code turned up" §1, B | met — shown already built by a direct code read (`axes_break_turn`/`law_apply_goal`/the settling clear), not re-derived |

U11 (does the new 50 m break floor also move the ordinary-flight floor?) is answered ("only
breaks") and carried correctly into D: `break_floor_agl_m` (new, 50) is break-only;
`floor_agl_m` (40) and the unpark seed clamp are untouched. The diagrams were approved by the user
before this check.

### Findings

1. **The break's bank cap is picked to land "a touch above" the user's own G figure, and the plan's
   own stated reason for why that is safe is contradicted by its own next paragraph.** Lens: world
   truth / internal consistency.
   - **Assumption:** `break_max_bank_deg = 65°` is chosen "close to the ~2 G the user accepts
     momentarily... deliberately a touch above 2.0 G rather than below it... the rate-cap below, not
     this angle alone, is what actually bounds the load a break reaches in practice."
   - **In the plan's own numbers:** 65° gives `n = 1/cos(65°) ≈ 2.37 G`, not ~2.0 G (60° gives
     exactly 2.0 G, inside the same 60–80° window). The very next subsection, "Effect, by speed,"
     shows the 65° cap **binds at all three card speeds** (120/180/250 km/h all need 67–79° for a
     bare 40°/s turn), meaning the break flies at the full 65° cap, not under it, for the bulk of
     each turn (2.5–5.2 s depending on speed) — the opposite of "the rate cap... bounds the load in
     practice." The rate cap is what *drives* the bank to 65° and holds it there; it does not keep
     the load below 65°'s own G.
   - **The pilot would see:** roughly 2.37 G held for several seconds in every break at every card
     speed, not a brief overshoot — a number the user did not say and a duration that sits uneasily
     with "momentary."
   - **Grounded in:** `plan.md` section B, "Chosen to land inside..." and "Effect, by speed";
     `1/cos(60°) = 2.0`, `1/cos(65°) ≈ 2.366`; `atan(ω·V/g)` at 120/180/250 km/h ≈ 67°/74°/79° (own
     arithmetic, checked against the plan's cited values).
   - **Suggests:** either tighten the cap to 60° (exact 2.0 G, still inside E5's 60–80° window and
     matching the user's own figure, still landing above the old 40°/s-implied bank at every card
     speed), or ask the user directly whether ~2.37 G held for several seconds counts as the
     "momentary... about 2 G" they described — the Risks section already flags 65° as a first cut
     the card measures, but it does not flag this specific tension between "momentary" and
     "continuously binding," which is new information from reading the plan's own two paragraphs
     together.

### Questions for the user
1. Finding 1: is roughly 2.37 G, sustained for the 2.5–5.2 s a break's roll takes at the 65° cap,
   still what you meant by "momentary overload... about 2 G" — or should the cap come down to 60°
   (exact 2.0 G) to match your own figure more directly? (Recommend: 60°, since it still sits inside
   E5's 60–80° window and still binds tighter than the old uncapped rate at every card speed.)

## Plan check — LV-3 amendment (2026-11-28)

**Verdict:** CONCERNS

Checked at `0c03b0a4` (`fix/bl16-flight-epoch-bound`). Inputs: `explore-notes.md` "LV-3 explore
(2026-11-27)" and "LV-3 diagram review corrections (user, verbatim, 2026-11-28)"; this file's
2026-11-20 goal check (E1–E10, open assumptions, Findings 1–2); `plan.md` "LV-3 amendment
(2026-11-27)" through the end, including sections C and E's "Corrected 2026-11-28" notes and the
"Answered 2026-11-28" U12–U17 block.

The LV-3 expectations, read from the explore answers (no separate numbered E-list exists for
hover; the user's four answers plus the two 2026-11-28 corrections are the expectations):

| expectation | stage | status |
|---|---|---|
| LE1 — yaw cue is nose/yaw-rate, not ball; yaw-rate damper added in all flight | D (unexplained-yaw overlay, every speed) | met |
| LE2 — blend starts higher, top at 80 km/h (was 50) | A, diagram 2 (`lambda_forward_kmh = 80.0`) | met |
| LE3 — pedal leads collective at the same moment | D, finding 5 (existing torque feed-forward, unchanged) | met |
| LE4 — hover heading change calm, 45° in ≤10 s | C (hover `ω`/rate/accel caps, finding 3's numbers) | met |
| LE4b — pedal bounded ±0.3 of hover-stable value | E, gated correctly to "during a commanded heading change only" per the 2026-11-28 correction | met — but see Finding 1 (diagram 2's note states it unconditionally) |
| LE5 — below 80 km/h, slower *rate* of change, not smaller values; collective/pedal lead; altitude held through stop; transitional lift/ground effect left to existing integrators, no model | G | met |
| LE6 — drift at speed 0 accepted, no fixed-spot hold | B ("a position is not held … drift at speed 0 accepted, user answer 4") | met |
| LE7 (2026-11-28 correction) — bank is not "never"; crosswind countering and sideways translate still use bank; only turning-to-heading uses pedal, not bank | C (corrected text, in writing) | met in prose — but see Finding 1 (diagram 2's note still says "never bank") |
| LE8 (U13 answer) — full pedal range, no artificial ±0.5 cap | U13 answer (`pedal_limit_positive = 1.0`, `pedal_limit_negative = -1.0`) | met — but see Finding 2 (a Risks entry built on the removed cap is not rewritten, only covered by a blanket substitution that breaks its sentence) |
| LE9 — U17: low-slow-RPM "accelerate" class leaves LV-3 | deferred → `[[BL-16]]` "Open, within BL-16" list | deferred; target is named and the user's own answer places it there, so this is a clean deferral, not a drop |

### Findings

1. **Diagram 2 (the one the user reviewed and corrected) still carries both statements the
   2026-11-28 correction overturned.** Lens: in the sim / the pilot would see.
   - **Assumption:** the correction note under section C — *"carried into `plan.md` LV-3 sections
     C and E"* — covers every place in the plan that asserted the pre-correction reading.
   - **In the plan:** diagram 2's hover note (the `stateDiagram-v2` under "One blend, three
     regimes") still reads, unchanged since before the correction: `pedal owns heading (yaw-rate
     loop), never bank` and, on the next line, `pedal within +-0.3 of the learnt hover pedal` with
     no qualifier. Both are exactly what the user struck down: bank is not "never" (crosswind,
     sideways translate), and the ±0.3 band applies only during a commanded heading change, not to
     hover generally.
   - **The pilot would see:** nothing wrong in flight if the implementer reads section C in full —
     the prose is correct. But this diagram is the one the user looked at and corrected
     (AGENTS.md's diagram-review step); leaving its own text contradicting the correction it
     prompted means the artifact the user approved no longer matches the plan it sits beside, and
     an implementer skimming diagrams first (the diagrams exist precisely so a reader does not have
     to parse every paragraph) carries the wrong rule into the drift-hold or hover-pedal-band code.
   - **Grounded in:** `plan.md` lines ~1627 and ~1629 (diagram 2's hover note) against the
     "Corrected 2026-11-28" text under section C (bank) and section E (pedal band gate).
   - **Suggests:** redraw diagram 2's hover note to say what C and E now say — pedal owns the
     *turn-to-heading* share of yaw; bank stays available for drift/crosswind and later translate;
     the ±0.3 band binds only while a commanded heading change runs. Same memory pattern as
     `[[project_bl16_lv1_amendment_rpm_correction_not_backpropagated]]` and
     `[[project_lift_vector_u8_floor_removed_but_not_grepped_everywhere]]`: a same-day correction
     box reliably reaches the text below it, not diagrams or summaries that sit elsewhere in the
     document and were not named.

2. **The U13 Risks entry is "fixed" by a blanket substitution that makes it nonsensical, not
   actually rewritten.** Lens: purpose.
   - **Assumption:** the Answered-2026-11-28 instruction — *"Where the plan above says 'existing
     absolute limits stay where they are' or '+0.5', read full range"* — correctly patches every
     earlier mention of the old cap, including the Risks & Unknowns entry: *"If a stable hover
     needs more right pedal than `t_y`'s +0.5 clamp, hover cannot hold heading — the trace shows
     `t_y` pinned at +0.5 with a left yaw."*
   - **In the plan:** substituting "full range" (1.0) for "+0.5" turns that sentence into "if a
     stable hover needs more right pedal than the full range clamp, hover cannot hold heading" —
     which is vacuous (nothing needs more than 100% of the axis by definition) and loses the real
     content of the risk, which was specifically about the *artificial* half-travel cap. The actual
     remaining risk — whether the real Mi-24P's hover need exceeds what the aircraft physically has
     — is a different, much smaller risk that this sentence no longer states.
   - **The pilot would see:** nothing directly (this is a planning artifact, not flown code), but
     an implementer or reviewer reading only the Risks section comes away either confused by a
     nonsensical sentence or under the impression the old +0.5-clamp risk is still live, when the
     reason it existed (the cap) is gone.
   - **Grounded in:** `plan.md` lines ~1995–1997 (Risks & Unknowns, "The DCS Mi-24P's hover pedal
     need is unknown…") against the U13 answer's blanket substitution instruction and its own
     stated reasoning (the cap was "a software cap… never a request to cap the command").
   - **Suggests:** rewrite the Risks entry rather than relying on the find/replace: the open risk
     after U13 is narrower ("if the Mi-24P's real hover need exceeds what full pedal travel gives,
     row 3 shows a `t_y` pinned near the limit with residual yaw" — still worth watching on the
     card, just not the same statement).

Both findings are plan-text hygiene issues, not behavioural gaps — the *behaviour* the LV-3
amendment specifies (E, C corrected; U13 answered) already serves the why. They are raised because
root `CLAUDE.md`'s own calibration ("a stale risk entry reads as settled when it is the opposite of
settled") and this role's own memory on this exact plan flag this as the recurring failure mode for
same-day corrections in `flight-lift-vector/plan.md`.

### Questions for the user
None — both findings are plan-hygiene corrections the main loop can apply directly (redraw diagram
2's hover note; rewrite the Risks entry) without needing a decision from you. Flagging here so the
implementer does not build diagram 2's uncorrected reading.

## M3 terrain floor — goal check (2026-11-28)

**Verdict:** CONCERNS

Inputs: `explore-notes.md` "M3 terrain floor explore (2026-11-28)" to the end (the specification);
`plans/flight-control/plan.md` old M3 (~L3045), old Stage 3 (~L1895), the 2026-10-31 AGL-over-trees
risk (~L2026); `body-layer/ROADMAP/BL-16.md`; this plan's LV-1..LV-3 law (priority chain G, LV-2 D);
today's code at `34c1ecb4` (`flight_control.lua` altitude shaper ~L1100–1140 and take seed
~L2880–2925, `belief/flight_control.py` `clamp_altitude`, `config/rules/flight.lua` altitude rules).
Superseded by the explore and not re-raised: the "Climbing for terrain." callout (E7 of the old
plan), the 40 m floor, the 5 m/s climb cap, the AGL-trend × 5 s look-ahead.

### Why

When Petrovich flies in mode 1 the pilot's eyes are elsewhere — on the 9K113 sight, on targets, on
the map — and a barometric hold knows nothing about the ground under it. The floor exists so that
**handing him the controls never means flying into terrain**, while **the pilot still decides how
low they go**: 50 m above bare ground is the height he keeps when nobody has said otherwise, and a
height the pilot explicitly names is flown as named. Asked once more — why not simply always 50 m?
Because low is how this helicopter is flown, and a crewmate who overrides "height 20" is one the
pilot stops trusting (*"Allow player to command any altitude and then accept it"*).

### Player expectations

- **E1 — Barometric hold toward rising ground.** He starts climbing before the rise, crosses it no
  closer than 50 m to bare ground, and comes back to the commanded barometric altitude once the
  ground falls away. The commanded altitude stays the goal throughout (a later speed or heading
  command does not lose it). Nothing is said.
- **E2 — Low cruise toward a ridge.** He climbs early enough to cross the crest at ≥ 50 m (or the
  explicit lower height, E5). If the climb does not fit, **speed gives first**: nose back, less
  speed, more climb; the commanded speed comes back once the climb fits again. No numeric climb
  cap — the aircraft's own power is the limit. Nothing is said.
- **E3 — Past the crest.** He returns to the commanded height without lingering high; at cruise
  speed there is no descent-rate limit, at low speed the existing VRS guard (Decision 31) applies.
- **E4 — Clearance is owed where he will be, not everywhere within 1 km.** On a long, steady
  upslope he stays near the commanded height (or 50 m) over the ground he is flying over, not far
  above it because higher ground lies further along. *(Derived from "accept any altitude" and the
  user's worked table, `climb needed = speed × slope ahead`; at stake in Finding 1.)*
- **E5 — An explicitly commanded height below 50 m is flown as commanded.** "Altitude 20" reads
  back "20 meters." and is flown at 20 m over the ground; the look-ahead protects 20 m, not 50. The
  height stays in force across later speed, heading and turn commands, and across park/unpark,
  until another altitude command or a hand-back. Trees at that height are the pilot's problem
  (*"My 40 m floor includes tree avoidance"* — below it, he owns the trees).
- **E6 — In fog he sees less far, so he anticipates less.** He reacts to terrain only once it is
  inside the atmospheric visibility (and never beyond the configured 1 km); in thick fog the climb
  starts later and the slowing is harder. He never climbs for a ridge he could not have seen.
- **E7 — A break near the floor.** A break never takes him below the effective floor (50 m, or the
  explicit lower height); height gives first down to it, then speed, then turn rate (LV-2's order,
  now against the one floor).
- **E8 — Hover and slow flight.** The floor still holds him above the ground beneath him; a hill
  ahead that he is not moving toward does not lift him, and yawing on the pedals at hover (LV-3)
  does not make his height pump as the nose sweeps across terrain. *(At stake in Finding 1.)*
- **E9 — Silence.** No terrain callouts in any of the above (*"drop all call-outs, the player can
  see the terrain just as well"*).
- **E10 — Mode 2 is untouched.** While ED's AI flies (parked) the floor and look-ahead do nothing;
  an explicit low height commanded during mode 2 still holds when he takes over in mode 1 on unpark
  — no 50 m jump at the unpark.

### Open assumptions

- **What drives the climb from the 15–18 grid points** — serves the why: each point's clearance
  owed in proportion to how soon he reaches it, started early (a lead), so slowing down really does
  reduce what is needed; would not: climb now to clear the highest point in the grid (the main
  loop's reading, "climb early against the highest point ahead" — not the user's words). Finding 1.
- **What "explicitly commanded" covers** — serves the why: any altitude command whose readback
  names the lower height ("altitude 20", "descend 30" ending below 50, "hold altitude" read back as
  "Holding 20 meters"), carried with the altitude goal itself; would not: only the
  `altitude <n>` form, or a flag that does not survive park/unpark or the take seed. Finding 2.
- **A later command that changes only speed, heading or turn** — serves the why: explicitness is a
  property of the altitude goal and survives (the desired state's altitude stamp does not move);
  would not: re-deriving it per goal message, which drops it on the first speed-only command.
- **An explicit barometric goal whose AGL equivalent is below 50 m** — serves the why: floored at
  50 m (*"the 40 m floor is especially for barometric mode, we don't want to fly to terrain"*);
  "explicit lower" is an AGL ("radar") height. Would not: treating any spoken barometric number as
  an explicit permission to go low.
- **Visibility source** — serves the why: the look-ahead shrinks to what the fog allows; would
  not: a silent fallback to the full configured 1 km when visibility cannot be read, which is
  seeing through fog (`visibility.py` ~L120 already notes there is no fog input). Question.
- **Which floor a break uses** — serves the why: the one effective floor, min(50 m, explicit), with
  LV-2 D's 100 m loss budget beside it; LV-2 D's separate `break_floor_agl_m` beside the 40 m
  ordinary floor was "kept separate, deliberately" under U11 ("only breaks") and is now superseded
  by *"one floor is better, use 50 m"*. Would not: keeping two floors.
- **"Ahead"** — serves the why: boresight, as the user chose (*"for simplicity use boresight as
  ahead"*); in coordinated forward flight track and nose are close. It only matters at hover and in
  a pedal turn, where Finding 1's filling decides whether it matters at all.
- **Mode 2** — serves the why: floor and look-ahead are mode 1's only, as the SAU was left to ED's
  AI (*"Let ED AI do whatever it does with SAU"*); would not: body-layer clamping the AI wheel's
  altitude goal.

### Findings

1. **"Highest point ahead" climbs him far above the commanded height on any long upslope and in a
   hover near a ridge** — lens: purpose / non-obvious case
   - **Assumption:** the climb target is the highest of the grid's points plus the floor, flown now
     (the explore's own reading: *"Climb early against the highest point ahead"*).
   - **In the sim:** the grid reaches 1 km whatever the speed. On a steady 10 % upslope the point
     1 km ahead is 100 m above the ground below him, so the target is ~150 m over the ground he is
     actually flying over, for as long as the slope lasts (5 %: ~100 m). At hover, 50 m up, masked
     30 m below a crest 400 m ahead, the target becomes crest + 50 m: he climbs ~80 m and ends 50 m
     **above** the ridge he was hiding behind — the BL-16 key case is exactly the pilot on the 9K113
     with Petrovich flying. A pedal turn at hover (LV-3) sweeps the grid across hills, so his height
     follows the yaw.
   - **The pilot would see:** "height 60" toward rising ground flown at 150 m; a hover behind cover
     turning into a pop-up nobody asked for. Contradicts **E4**, **E8**, and E5 at low heights.
   - **Grounded in:** the user's *"Allow player to command any altitude and then accept it"*; the
     main loop's own worked table shown to the user, *climb needed = speed × slope ahead* — a
     clearance-on-arrival model; *"climb early. Slow down a bit if necessary so that we can climb
     faster"* — the user did not say "climb to the highest point".
   - **Suggests:** what each point ahead asks of him should depend on how soon he gets there (at
     hover, nothing ahead is urgent), with an early start as the lead. How is Architect's. Q1.
2. **"Explicitly commanded" must travel with the altitude goal, or he contradicts his own
   readback** — lens: crew sense
   - **Assumption:** the obvious filling marks only `altitude <n>` as explicit and keeps today's
     floor clamps with 40 → 50 (`clamp_altitude`, and the unpark take seed's
     `seed.alt_m < fc_limits.floor_agl_m` clamp, `flight_control.lua` ~L2892).
   - **In the sim:** at 20 m, "hold altitude" reads back *"Holding 20 meters."* (`flight.lua`
     `hold_altitude`) and "descend 30" from 60 m reads back "30 meters." — and he would then climb
     to 50 m. A "height 20" commanded in mode 2 is clamped to 50 at the unpark seed, a 30 m jump at
     the unpark.
   - **The pilot would see:** Petrovich saying one height and flying another. Contradicts **E5**,
     **E10**.
   - **Grounded in:** the user's *"if player explicitly commands lower altitude it is allowed"*;
     the project's rule that he never says one value and flies another (LV-1 U8's reasoning,
     `plan.md` ~L746).
   - **Suggests:** explicitness belongs to the altitude goal in the desired state and goes
     wherever it goes (set, step, hold, park/unpark seed); everything else floors at 50. Q2 settles
     the edge.
3. **A take below 50 m with no height spoken climbs him to 50 m** — lens: non-obvious case
   - **Assumption:** the settled reading floors "default hold at take" at 50 m.
   - **In the sim:** the pilot at 20 m — or in a low hover behind cover, about to move to the
     9K113 — says "you have controls" and nothing else; Petrovich's first act is a 30 m climb.
   - **The pilot would see:** an unasked-for pop-up at the moment he looks away. Consistent with
     the user's words (handing over is not an explicit height), which is why this is a question and
     not a concern. Q3.
4. **No visibility input exists; the obvious fallback sees through fog** — lens: bounded knowledge
   - **Assumption:** if fog cannot be read, use the configured 1 km.
   - **In the sim:** in 300 m fog at 200 km/h he would climb for a ridge 18 s away that nobody in
     the cockpit can see. Contradicts **E6** (*"no further than atmospheric visibility (ie fog)"*).
   - **Grounded in:** the user's words; `body-layer/src/perception/visibility.py` ~L120 (no fog
     input today). Needs recon before planning; what to do if recon finds nothing is Q4.

Not raised: the AGL source (telemetry AGL, bare ground — settled), the removal of the climb and
descent caps (settled, VRS guard kept), and whether the look-ahead should also lead an AGL hold
that is well above the floor (nothing the user said asks for it; the reactive AGL hold covers it,
and Flight M-B's "hold 60 m over rising ground" will show any sag).

### Questions for the user

- **Q1.** Toward rising ground, should he clear each point ahead by the time he reaches it (on a
  long 10 % upslope he stays about 50 m over the ground; in a hover nothing ahead lifts him), or
  climb now to clear the highest point within 1 km (~150 m over the ground on that slope; a hover
  400 m behind a ridge pops him above it)? *Recommend the first, with an early start — it matches
  "accept any altitude" and the speed × slope table you answered.*
- **Q2.** Does "hold altitude" at 20 m (he answers "Holding 20 meters") or "descend 30" ending
  below 50 m count as explicitly commanding the lower height? *Recommend yes — otherwise he reads
  back one height and flies another.*
- **Q3.** If you hand over below 50 m without saying a height — e.g. low behind cover before
  moving to the 9K113 — should he climb to 50 m, or keep the height you gave him?
- **Q4.** If DCS's fog distance turns out not to be readable, how far should he look ahead: the
  full 1 km, a shorter fixed distance, or the mission's weather setting?
- **Q5.** Over a crest at cruise speed, should he follow the far slope down straight away, or ease
  down?
- **Q6.** At night without NVG, does the look-ahead shrink the way it does in fog, or does only fog
  limit it? *(Low priority.)*

## M3 terrain floor — plan check (2026-11-28)

**Verdict:** CONCERNS

Checked against `plan.md` "## M3 amendment (2026-11-28)" (L2105–2784) at tip `19734a33`, including
the "Answered 2026-11-28" block under "Decisions Requiring User Input (M3)" (U20 = 10 m/s, U22 =
"every climb trades speed", not the plan's own earlier recommendations of 5 m/s and "terrain only").
Design sections A–F, the diagrams, and the Co-moving table were all written or revised to the
answered values — no stale number or branch survives there. Three spots elsewhere in the same
amendment still read as if the recommendation, not the answer, had landed; none of them changes the
law (sections A–D are consistent), but each could mislead an Implementer or Reviewer checking the
work against the user's actual decision.

| expectation | stage | status |
|---|---|---|
| E1 — baro hold toward rising ground | A (floor beneath), C (floor into shaper) | met — card row 3, test (terrain driver, E1) |
| E2 — low cruise, speed gives first then resumes | B/C/D | met — card row 4, test (terrain driver, E2) |
| E3 — past the crest, returns without lingering, VRS kept | C (ease-down), Decision 31 | met — card row 5 |
| E4 — clearance owed where he will be, not everywhere in 1 km | B (Q1→A, per-point clearance), U21 (yes) | met — test ("altitude 60" stays in U21 band, not 150 m), card row 6 |
| E5 — explicit lower height flown as commanded | A (`F_eff = min(50, AGL goal)`) | met — card rows 2, 7, 8 |
| E6 — fog limits anticipation | — | deferred → `[[BL-B138]]` (plan.md L2404–2406, L2707; `BL-B138.md`'s own entry names this as its "second consumer," BL-16 M3, verbatim) |
| E7 — break never below floor | A (break floor = max(F_eff, entry − 100)) | met — card row 10 |
| E8 — hover/pedal turn does not pump height | B (ground-speed-along-nose gate, `V_f ≥ terrain_min_speed_mps`) | met — card row 9, test |
| E9 — silence | F ("No speech at all") | met — card row 15 |
| E10 — mode 2 untouched, no jump at unpark | F, A (unpark seed clamp removed) | met — card row 12, 7 |

### Findings

1. **Risks bullet (plan.md L2697–2698) still describes the superseded U22 recommendation, not the
   answer** — lens: consistency / crew sense
   - **Assumption:** "Removing the 5 m/s cap changes every altitude command, not only terrain: big
     climbs go to available power (U22) and big descents at speed are fast." "Go to available power"
     is exactly what "terrain only" (the recommendation) would mean — a commanded climb keeps its
     speed and just climbs as fast as power allows.
   - **In the sim:** U22 was answered *"every climb trades speed"* — "altitude 500" at 220 km/h with
     nothing in the way (the plan's own card-row-11 example) now also slows toward U19's ~100 km/h
     floor before using available power, exactly like a terrain climb.
   - **The pilot would see:** nothing wrong in the cockpit — this is a Risks-section description, not
     code — but a reader checking the plan against the Answered block would read this line and
     conclude ordinary big climbs keep their speed, which is the opposite of what was decided.
   - **Grounded in:** the Answered block itself, L2747–2750 ("the lead is `w_ref_lead_max_mps` for
     ordinary commanded climbs too; no terrain-only branch").
   - **Suggests:** reword to "big climbs also trade speed, down to U19's floor, before using
     available power (U22)."
2. **Card row 11 (plan.md L2677) names U22 without saying what it now means** — lens: non-obvious case
   - **Assumption:** "'Climb 300' at 220 km/h: no 5 m/s cap; speed per U22; no overshoot at the top."
     "Speed per U22" was written generically enough to cover either answer, and was never updated once
     U22 landed on the non-recommended side.
   - **In the sim:** this exact row is the worked example the Answered block uses ("Altitude 500 at
     220 km/h, nothing in the way"). The pilot flying this row should see the aircraft slow — not just
     "whatever U22 says" — and come back to 220 after.
   - **The pilot would see:** a correctly-behaving aircraft, but the card gives whoever flies it no
     concrete thing to check against, so a real regression (speed *not* giving on an ordinary climb)
     could pass the card unnoticed.
   - **Grounded in:** every sibling row (4, 6, 9) states the concrete expected reading; row 11 is the
     one row that doesn't, and it is the row that most needs to since it is U22's test case.
   - **Suggests:** "speed falls toward U19's ~100 km/h floor and returns after, per U22's 'every
     climb' answer."
3. **Tests section has no explicit assertion for U22's actual case** — lens: non-obvious case
   - **Assumption:** the "No cap" bullet (plan.md L2636–2638) checks `w_ref − w ≤
     w_ref_lead_max_mps` under capped authority, and the terrain-driver bullet (L2628, E2) checks
     `speed_goal_mps` unchanged while speed falls toward a *terrain* climb — but nowhere does a test
     drive an **ordinary, non-terrain** altitude-step command (no grid demand at all) through capped
     authority and assert `v_ref` yields the same way. That is exactly the behaviour U22 (as answered)
     added beyond what "terrain only" would have needed.
   - **In the sim:** if a future change narrowed the governor's lead back to 0 for a plain climb (the
     "terrain only" shape the plan almost shipped), no test here would catch it — the terrain-driver
     test only exercises the terrain-bound case.
   - **Grounded in:** the Answered block's own framing of U22 as a distinct behavioural case from
     terrain climbs ("a commanded climb with no terrain in the way").
   - **Suggests:** add one toy-plant case to the "No cap" bullet: a plain "altitude 500" step, capped
     climb authority, no terrain grid — assert `v_ref` yields toward `speed_give_floor_kmh` the same
     way the terrain case does, and returns once the shortfall ends.

Not raised as findings: the ease-down value (10 m/s, U20) is consistent everywhere it is restated —
no stale "5" survives outside the historical recommendation text under "Decisions Requiring User
Input," which the project keeps on record below its own "Answered" block by convention (not stale,
by design). The deferred rows (E6) correctly name `[[BL-B138]]`, whose own roadmap entry already
mentions this plan's M3 as its "second consumer" — the deferral has a tracked home.

### Questions for the user

None — the three Findings are text the main loop can correct directly before Implementer; no
decision beyond what is already on record (U18–U22) is needed to fix them.
