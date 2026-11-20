# BL-16: one desired flight state, one mode authority — alignment

## Goal check — 2026-11-20

**Verdict:** CONCERNS. There are three. Each is an assumption that a planner would fill in the
obvious way from "one desired state, a mode change simply keeps flying it", and each filling breaks
a named expectation below. C1 and C3 can be settled from the user's own recorded words. C2 needs
one answer from the user (Q1). The other questions do not block planning.

Inputs: `plans/flight-desired-state/explore-notes.md` (the user's direction, verbatim, and the main
loop's call that the desired state and the mode both live in Export.lua);
`docs/acceptance/2026-11-20-sortie-feedback.md`; `body-layer/ROADMAP/BL-16.md` (the open items);
`plans/flight-control/plan.md` (Decisions 21–25, the mode 2 readback and 700 m rules);
`plans/flight-control/alignment.md` (E-P12–E-P21, F-P6/F-P7, Q7/Q8).

### Why

Tonight a mode 2 → mode 1 change crashed the aircraft. A command was acknowledged and then never
flown. The altitude that was set was 116 m when the player had said 100. Each failure has the same
cause: **every part of the system kept its own idea of what Petrovich was meant to be doing and
which mode he was in, and those copies drifted apart.**

Why does that matter to the pilot? A crewmate flying for you has one intention at a time, and it
is the one you gave him. **The pilot has to be able to trust that the last thing he said, and heard
read back, is what the aircraft is doing now and will go on doing**: through a press of Request
Aircraft Control, a seat swap, or a mode 2 limitation. He should never have to check the wheel or
say it again. One store of desired values and one store of the mode is how that intention is kept.
Neither store is the purpose.

### Player expectations

- **E1 — A command is flown or refused aloud; it is never silently dropped.** Every readback is
  followed by the aircraft moving toward that value. Otherwise he hears "Unable, <reason>". This
  holds in mode 1, in mode 2, and in a break or an alignment (E-P19, and tonight's "acknowledged,
  but nothing happens").
- **E2 — The value set is the value he said.** "Altitude 100 radar" sets 100 radar, not 116. The
  aircraft may wander within the band (about ±10 %, Decision 18), but the target does not
  (user, 2026-11-20).
- **E3 — The latest command always wins**, including one given during a break or an alignment
  (user, 2026-11-20: *"Latest player command always wins."*).
- **E4 — A mode change keeps flying what he last commanded**, in both directions: park, unpark,
  and a seat swap that parks or unparks. Nothing jumps and nothing is forgotten. The case that
  matters most: he says "speed 200" in mode 2 and unparks while the wheel is still ramping. Mode 1
  goes on to 200. It does not stay at the wheel's half-way value, and the controls do not freeze
  (tonight's crash; user: *"mode 1 must keep flying the set targets from mode 2"*).
- **E5 — A take holds the current state; no old target comes back.** When Petrovich takes the
  controls from the player, by "you have controls" or by a park, he keeps doing what the aircraft
  was doing at that moment. That includes a turn in progress (settled point 3, *"keep the turn
  going, that is what I mean by maintaining current state"*). A heading he was told an hour ago,
  before the player took the controls back, never comes back.
- **E6 — An evasion is never undone by a target set before it.** After "break left", the
  aircraft does not swing back toward the heading it had before the break. That holds when the
  break ends, and it holds when the mode changes during or after the break (F-P7, *"yes, as
  proposed"*).
- **E7 — Petrovich always knows which mode is flying the aircraft**, and he acts in it. A command
  he cannot fly in that mode gets "Unable, <reason>" (for example "Unable, AI overlay."). He never
  answers as if he were in a mode he is not in. He never says "not ready" while he is in fact
  holding the controls (sortie feedback, second handover).
- **E8 — Mode changes the player makes in the cockpit are silent; losing the stick is not.** A
  park, an unpark or a seat swap switches the mode without a word (U5). Any change that leaves
  nobody flying the aircraft, whatever its cause, is the urgent "You have controls!" once.
- **E9 — Whatever mode 2 cannot do, he says so, in words that tell the pilot what is flying
  now.** Examples: a speed between the wheel's steps, or a radar altitude above 700 m. The pilot
  must never hear one value and see another being held without having been told.
- **E10 — A body-layer restart leaves the aircraft in a known state.** Mode 1 lets go, and ED's
  AI keeps flying in mode 2 (user: *"yes let go"*). Whatever Petrovich does afterwards, the pilot
  can tell who is flying.

### What is a desired value and what is a manoeuvre

This is a recommendation only. The architect decides the structure.

| thing | what it is | writes the desired state? |
|---|---|---|
| heading, "turn x left/right", compass point | desired heading | yes, the target |
| "turn left/right" with no degrees (mode 1 only) | a desired *turn*, not a heading | yes, as "turning, rate r". Unable in mode 2, as today |
| "stop turn" / roll-out | desired heading = wherever the roll-out ends | yes |
| altitude, with AGL/radar or baro reference | desired altitude **plus its reference** | yes |
| altitude step, hold altitude | desired altitude | yes |
| speed, speed step, speed max | desired speed | yes |
| "level flight" | heading, altitude and speed = current | yes, all three |
| break left/right, break away | a manoeuvre (mode 2 CBTM presses, mode 1's own law) | **yes, it must clear or replace the desired heading** (C3) |
| align | a manoeuvre; afterwards the alignment heading is the set heading (Q7) | yes, when it ends (heading = the one it reached) |
| align for launch, recovery | a manoeuvre plus a restore sequence (FLT first, then the pre-align altitude, then speed one step at a time, Q8) | the restore writes the pre-align altitude and speed. The dive itself writes nothing |
| HVRT translate, hover up/down, hold | mode 2 manoeuvres in the hover (mode 1 hover is deferred) | "hold" sets speed 0 and the current heading and altitude; a translate does not write |
| take / release, park / unpark | mode authority, not a desired value | a take **seeds** the desired state from the current state (C1) |

The rule underneath: **after any manoeuvre ends, the desired state must describe what the aircraft
should do next, in terms a different mode could fly.** If that rule does not hold, a mode change at
that moment turns the aircraft back toward something stale.

### Open assumptions

- **What the desired state holds while the player flies (mode off).** Serves the why: it is not
  authoritative while he flies, and **every take seeds it from the aircraft's current state**.
  The take rules are those of Decision 24: under 5° of bank, hold the heading, otherwise keep
  turning; a climb levels off where it stops; hold the IAS. On a park, that also means mode 2's P1
  altitude snapshot. Would not: keeping the last desired values through "I have controls" and
  flying them at the next take (C1). Clearing it to nothing while the player flies is fine, and so
  is following the aircraft. Which of the two is used does not matter to the pilot, provided the
  take seeds it.
- **Which mode limits apply to the desired value, and which only to how it is flown.** Serves the
  why: the aircraft's own limits shape the desired value. Mode 1's IAS bounds and the AGL floor
  are examples, already clamped and read back (Decision 14). **Mode 2's limits shape only how it
  is flown**: speed steps, the 700 m radar cap, HVR/FLT/CBTM. So "speed 220" stays 220 in the
  desired state, mode 2 flies the step it can, and mode 1 flies 220 after an unpark. Would not:
  storing mode 2's snapped value as the desired value. Mode 1 would then inherit 200, the player's
  220 would be lost, and E2 and E4 would break. What he *hears* in that case is Q1.
- **What "unable" from mode 2 does to the desired state.** Serves the why: it depends on whether
  mode 2 can fly the value at all. For an approximation (a speed step, baro in place of radar),
  the desired value is kept. For something mode 2 cannot do at all ("turn left" with no degrees),
  he says unable and the command is not stored, because an "unable" that comes back to life
  silently after an unpark breaks E1 the other way round. Would not: one blanket rule either way.
  The user's *"keeps flying to it (as much as mode 2 allows)"* fits the first case. The pilot's
  ordinary reading of "unable" fits the second. Q2.
- **The altitude reference when the player gives none.** Serves the why: one rule, applied once,
  when the command is stored, so the stored value carries an explicit reference and both modes fly
  the same thing. Would not: each mode filling it in at the moment it flies. Today mode 1 defaults
  to AGL (Decision 9 REVISED) and mode 2 keeps the wheel's current reference, which is baro after
  takeover (Q6, P1). Under one stored value, "altitude 200" would mean 200 AGL until a park and
  200 MSL after it. Over a 300 m valley floor that is a 300 m climb nobody asked for. Q3.
- **Unpark during a break.** Serves the why: the break's purpose (evasion) carries over to mode 1.
  It either finishes its 90° or 180° in mode 1, or it continues as the inherited turn (the take
  rule, over 5° of bank) until the next command. Either way the desired heading has already been
  cleared by the break (C3), so nothing turns it back. Would not: mode 1 seeding the heading the
  break started from. Q4.
- **Unpark during "align for launch" or its recovery.** Mode 1 cannot align (E-P20). Serves the
  why: treat it as the abort (E-P15). Level off and restore the pre-align altitude and speed,
  which are already the desired values the recovery is restoring. Would not: holding the bottom of
  the dive at the overspeed it reached, as the take rule "levels off where the climb or descent
  stops" would do. Low stakes, because the unpark is the player's own press in the middle of his
  shot. It is recorded so that a planner does not leave it to the take rule.
- **Mode changes ED makes inside mode 2** (CPG view → CBTM, hover transitions). Serves the why:
  they are below the mode authority. Petrovich cycles back silently to the sub-mode the desired
  state needs (Q4 of 2026-11-15, U3). Would not: treating them as a change of mode 1/2/off. That
  would wake up the transition rules and the speech for something ED did on its own.
- **Whether ED's overlay can switch itself off with nobody pressing anything** (damage, ground
  contact, its own envelope). This is the agent's uncertainty about DCS, not a finding. Serves the
  why, if it happens: the mode authority in Lua reports it like any other change, and E8's urgent
  line follows if nobody is left flying. Q5.
- **What body-layer adopts after its own restart while the aircraft is parked.** The user said two
  things: *"yes let go"* on a reset, and *"if mode 1/2 is ON in aircraft layer, body must use that
  state"*. Serves the why: body-layer reports mode 2 truthfully (ED's AI is flying), the desired
  state is reseeded from the current state, and Lua is **not** armed. An unpark afterwards then
  gives the player the stick with the urgent "You have controls!". Would not: re-arming silently,
  so that a later unpark has Petrovich take the stick after a fault the user calls *"an error
  situation"*. Also would not: an unpark that hands the stick to the player with no word. Q6.
- **Seat swaps.** Serves the why: a swap changes nothing in the desired state (A8). Where it
  changes the mode (a swap to the pilot seat while parked behaves as an unpark, M0-J3), it is a
  mode change like any other under E4 and E8. Would not: treating a swap as a release.

### Findings

1. **C1: "Keep the desired state, a mode change keeps flying it", applied to a take from the
   player, brings back a stale target.** Lens: the non-obvious case, crew sense. Breaks E5.
   - Assumption: the user's *"the desired state is already known and mode change simply keeps
     flying to it"* is read as covering every transition. That includes off → mode 1 ("you have
     controls") and off → mode 2 (a park from player-flies, 2026-11-17).
   - In the sim: the player says "heading 060", later "I have controls", and flies by hand to 270.
     Ten minutes later he says "you have controls". Petrovich turns left 150° toward 060.
   - Grounded in: settled point 3 (2026-10-25), *"keep the turn going, that is what I mean by
     maintaining current state"*; Decision 24's take rules. The user's 2026-11-20 words are about
     *mode 1 ↔ mode 2*, which is a change in how Petrovich flies while he keeps the controls. They
     are not about the player handing over.
   - Suggests: the desired state carries across mode 1 ↔ mode 2 only. Every change of *who* flies
     reseeds it from the current state. No question is needed, because both rules are in the
     user's words. The architect should state it.

2. **C2: Decision 24's "goals in progress are dropped, in both directions" is superseded. Its
   reason (2) is still live, and it now has to be answered rather than avoided.** Lens: world
   truth. Breaks E4 if Decision 24 is followed, and E2/E9 if reason (2) is ignored.
   - Assumption: a planner reads `plans/flight-control/plan.md` Decision 24 as still current.
     It says that on a mode switch "goals do not carry" and that "mode 2's 'unparking drops the
     goal' stays exactly as built".
   - The user reversed this on 2026-11-20: *"On change to mode 1, mode 1 must keep flying the set
     targets from mode 2"*, and *"mode change simply keeps flying to it"*. Decision 24's own
     reason (2) is why it had dropped goals. In mode 2 the altitude keeps the current reference
     and is capped at 700 m on radar, mode 1 defaults to AGL, and mode 2's speed moves in about
     50 km/h steps, so *"a carried goal would be a translation, not a carry"*. That reason did not
     go away. It is now the list of things the desired state must hold exactly (the reference,
     the unsnapped speed), and the list of things mode 2 must tell the pilot it is only
     approximating (E9).
   - The pilot would see: with Decision 24 followed, tonight's crash, or the wheel's half-way
     value. With reason (2) ignored, an unpark that turns "200 m" into a different altitude, or a
     speed that creeps 20 km/h after an unpark with nothing said.
   - Grounded in: the 2026-11-20 sortie feedback, verbatim; plan.md Decision 24, reason (2).
   - Suggests: the plan marks Decision 24's carry clause as superseded, and why, so that later
     readers do not plan from it. E-P10's "nothing resumes" falls with it. Reason (2) becomes the
     open assumptions above (the reference rule, mode-limit vs desired) and Q1–Q3.

3. **C3: If manoeuvres are kept as "mode-specific actions that do not touch the desired state",
   F-P7 comes back through the mode change.** Lens: purpose, because a break is an evasion. Breaks
   E6.
   - Assumption: the obvious split is "desired values in the store; breaks, align and HVRT as
     separate actions". F-P7's fix (a break supersedes an outstanding heading goal) lived in mode
     2's own goal logic. With a single store, a break that does not write the store leaves the
     pre-break heading in it as the desired heading.
   - In the sim: "heading 090" is set. He sees a ZSU: "break left", in mode 2. Mid-break, or just
     after it, he unparks to take the shot from the seat he is in. Mode 1 picks up the desired
     heading 090 and turns back toward the ZSU. The same happens without a mode change when the
     break's presses finish and the overlay returns to FLT.
   - Grounded in: F-P7 and its answer (*"yes, as proposed"*, 2026-11-18); tonight's latest-wins
     settlement (*"a goal older than the break is superseded by it"*).
   - Suggests: every manoeuvre leaves the desired state saying what to do next (the table above).
     A break clears or replaces the desired heading at its start, and align sets it to the heading
     it reached (Q7).

Vignette (the user's own case, walked over one state). The aircraft is in mode 2, FLT, at
120 km/h. "Speed 2 2 0." Mode 2 can only show 200 or 250. Under the assumptions above, the desired
speed is 220 and the wheel steps toward 200. The readback is Q1. Two seconds later, with the wheel
showing 150 on its way up, he unparks. In the same frame mode
1 takes, with IAS 130 ≥ `MIN_IAS_KMH`, and accelerates to 220, not 150. He hears nothing (U5). Now
change one step: he said "speed 0" instead. The desired speed is 0, and the aircraft is at 60 km/h
and slowing when he unparks. Mode 1 cannot fly 0 (forward flight only, Decision 3). If IAS is
already below `MIN_IAS_KMH`, Lua refuses the take and he hears the urgent "You have controls!",
which is right. If IAS is still above it, mode 1 takes and then clamps the desired 0 to
`MIN_IAS_KMH`. He asked to stop and the aircraft holds 80 km/h. Decision 14's clamp readback was
designed for a spoken command, and here there is no command to read back, so nothing is said.
That case is part of Q1.

### Questions for the user

- **Q1** — Mode 2 cannot fly some values exactly. Examples: "speed 220" (the wheel has 200 or 250),
  "altitude 900 radar" (radar caps at 700, so it sets baro), "speed 0" carried into mode 1. Which
  should he do? (a) Read back what he will actually fly, as today ("speed 2 0 0"), and keep your
  220 for mode 1. (b) Say "unable, <reason>" and fly the nearest. (c) Read back your value and fly
  the nearest silently. Recommend (a) plus your value kept, because it is honest about now and
  keeps your word for later. Your *"something it cannot do → unable"* may instead mean (b).
- **Q2** — When mode 2 says "unable" because it cannot do something at all (for example "turn
  left" with no degrees), should that command be dropped, or kept so that mode 1 flies it after
  an unpark? Recommend dropped, because "unable" should mean nothing changed.
- **Q3** — "Altitude 200" with no reference: is it AGL in both modes (today's mode 1 rule, which
  would make mode 2 hold radar or convert to baro), or "keep the current reference" in both (today's
  mode 2 rule)? The answer has to be the same in both modes, or a park changes your altitude.
- **Q4** — If you unpark in the middle of a mode 2 break, should mode 1 finish the 90°/180° and
  then hold, or just keep the turn going until you say something (today's take rule)?
- **Q5** — Have you seen ED's AI overlay switch itself off without anyone pressing Request Aircraft
  Control (damage, touching down, anything else)?
- **Q6** — After a body-layer restart with the aircraft parked, and then an unpark: should you get
  the stick ("You have controls!"), or should Petrovich take it in mode 1 as normal? Recommend the
  stick, because that is your "let go" and the restart was a fault.

## Plan check — 2026-11-20

**Verdict:** ALIGNED.

| expectation | stage | status |
|---|---|---|
| E1 (acked or refused aloud) | §3 (ack ring, refusal/timeout speech) | met |
| E2 (set value = commanded value) | §1 (`alt_m`/`ias_kmh` exact, stamped) | met |
| E3 (latest command wins) | §3/§4 (`stamp` priority, `manoeuvre_seq`) | met |
| E4 (mode change keeps flying last command, incl. mid-ramp unpark) | Stage 3 (unpark seed = desired, not the wheel's display) | met |
| E5 (take holds current state, no stale target) | C1 rule, handover table (`law_init_at_take` reseed) | met |
| E6 (evasion not undone by an older target, incl. across a mode change) | §4 (break write replaces every older heading; Q4 finishes the break) | met |
| E7 (Petrovich always knows the mode, acts in it) | §2 (`fd_mode` derived, nothing sets it directly); Stage 2 card names the "unable, not ready while holding" case | met |
| E8 (cockpit mode changes silent, losing the stick is urgent) | `decide_flight_speech` (urgent only on a change into off whose cause ≠ release/stop/reset) | met |
| E9 (mode 2's approximations are spoken) | §3 (`m2_flown` readback) | met, contingent on U2 → [[U2]] (same plan, open) |
| E10 (restart leaves a known state) | handover table, "body-layer reset" row | met |
| C1 (take/hand-back reseeds, m1↔m2 carries) | "The rule underneath (C1)" + handover table | met |
| C3 (break replaces the older heading) | §4 break row ("replaces every older heading (F-P7 automatically)") | met |
| Q1a (readback what will fly; exact value stays desired) | §3 | met |
| Q2 (unable → dropped, nothing written) | §3, §4 refusal rows | met |
| Q3 (AGL default both modes, baro only if spoken) | §1 `alt_ref`, Stage 4 | met |
| Q4 (unpark mid-break finishes it, then holds) | §4 "Unpark during a manoeuvre: break" | met |
| Q5 (pilot-seat swap always unparks; copilot seat does not self-switch) | handover table, both seat-swap rows | met |
| Q6 (restart while parked → unpark gives the stick) | `armed` cleared by reset, handover table "unpark, refused/unarmed" | met |
| mode-2-is-Mi-24-only, isolable | §6 "The mode-2 seam" (nil-check, `fd_has_m2`, `flight_mode()` gate) | met |
| crash: fixed controls at mode-2's half-way value | Stage 3 (desired, not overlay display, seeds the unpark) | met |
| crash: AI wheel shows wrong mid-adjustment value | Stage 3, same mechanism | met |
| ack'd command never flown (F-P7 over-reach) | §4 "Latest wins" (`command_order_seq`/F-P7 deleted), Stage 4 card | met |
| set ≠ commanded (116 vs 100) | §1 exact fields; §3 exact-set tolerances | met |
| take/ack mismatch ("unable, not ready" while holding) | Stage 2 ("there is no phase left to disagree") | met |
| stale Lua / stale deployment | §5 epoch re-handshake; Risks, "stale deployment" | met |

### Findings

None that change the verdict. The plan's own "Expectation trace" section independently restates
E1–E10 against the same stages, and the two traces agree.

1. **E9's "he is told" half rides on U2, which is still open.** Lens: the non-obvious case.
   - Assumption: none — the plan names this itself ("E9 → `m2_flown` readback, plus U2").
   - In the sim: a value carried from mode 2 into mode 1 that mode 1 clamps (mode 2's "speed 0"
     landing at `MIN_IAS_KMH` in mode 1) is flown correctly either way; only whether Petrovich
     *says* so is undecided.
   - The pilot would see: nothing different if U2 is answered "no" instead of the plan's
     recommended "yes" — E9 would then read `contradicted`, not `met`, for exactly this case.
   - Suggests: ask U2 before Stage 3 ships (it is the stage that carries values across a mode
     change), not deferred to Stage 4 — the plan's own stage split does not gate it there, so this
     is a scheduling note, not a plan defect.

### Questions for the user

- U1, U2, U3, U4 as the plan states them (reproduced there, not repeated here). U2 is the one with
  behavioural weight for E9: whether Petrovich must say, once and unprompted, the value mode 1 is
  actually holding after it carried a value mode 1 cannot fly exactly.
