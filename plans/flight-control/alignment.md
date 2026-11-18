# BL-16 — Petrovich flies the helicopter: behaviour alignment

## Goal check — 2026-10-31

**Verdict:** CONCERNS

Checked against: the user's words in `plans/flight-control/explore-notes.md` (both 2026-10-26
addenda included), the three concept pages `docs/concept/flight-control-{1,2,3}.jpeg` (read; the
transcription matches them), `body-layer/ROADMAP/BL-16.md`, the existing plan
`plans/flight-control/plan.md` (merged `e898da05`, eleven user decisions), `[[BL-B101]]`,
`[[BL-B95]]`, `[[BL-B67]]`, `docs/concept/long-term-high-level-plans.md` and the memories on the
opposite seat and the 50–800 m AGL envelope.

The existing material is unusually well settled: the handover, takeover continuity, stick
handling, the release jump, refusals, readbacks, the altitude source and the control law's shape
were all decided by the user in his own words, and the plan carries them faithfully. Nothing below
reverses a decision. The concerns are **gaps the decisions leave open**, where a planner would
otherwise fill in an assumption. Two of them, how to stop a turn and how fast an emergency
take-back is, matter in the seat.

### Why

When the pilot hands over, he gets his attention back without the aircraft wandering. He can look
out and spot, since *"the one not controlling"* spots, or work the map, the radios or the kneeboard.
ED's AI flying, *"very badly and unreliably"*, cannot give him that.

Asking "why" once more gives the deeper purpose: *"Aircraft controlling is needed for both."* The
same controller later lets Petrovich fly the pilot into the 9K113 launch envelope while the player
works the sight (pilot-Petrovich, and page 2 priority 5 "align with 9K113").

So the near-term why is **trustworthy hands-off time in the pilot seat**, and the lasting why is
**a crewmate who can be trusted with the aircraft at low level**. Both rest on one thing: the
pilot must be able to stop watching the aircraft. Anything that makes him monitor it (drift,
silent failure to reach a goal, ambiguity about who has it) defeats the purpose, however well the
loop closes.

### Player expectations

- **E1 — Handover is unambiguous and confirmed.** After "you have controls", the pilot hears "I have
  controls" only once Petrovich is actually flying. If Petrovich will not take over, the pilot hears
  "unable, <reason>" and still has the aircraft. *(Settled: explore point 2, plan Stage 1, Decision 5.)*
- **E2 — Nothing jumps at takeover, and the aircraft keeps doing what it was doing.** A turn
  continues at its rate, a climb or descent levels off smoothly at the height reached, and the IAS is
  held. *(Settled: point 3, Decision 1.)* Gap: when a near-level drift counts as "straight", see F2.
- **E3 — With Petrovich flying, the pilot's stick, collective and pedals do nothing.** An accidental
  bump never moves the aircraft. *(Settled: point 2, "it must be ignored.")* The pilot's 3D cockpit
  controls should move with Petrovich's inputs, as linked dual controls do. Plan S0-1 checks that
  the args follow the write, and this is the pilot's main silent cue that someone else is flying.
- **E4 — Every spoken goal gets a short readback, then happens smoothly with no overshoot.**
  "20 left", "heading 3 1 5", "300 meters", "speed 2 2 0". *(Settled: Decision 10, point 5.)*
- **E5 — The pilot can stop a turn by voice.** A continuous "turn left", or a turn inherited at
  takeover, can be ended with a short spoken word. **Not settled, see F1.**
- **E6 — "I have controls" gives the aircraft back at once, including in an emergency.** It is
  never held up by a "confirm?" prompt. Partly settled; see F3.
- **E7 — If Petrovich cannot do, or keep doing, what was asked, he says so.** That covers refusing a
  command (settled: "unable, <reason>", Stage 4), climbing for terrain (settled: one call per event,
  Stage 3), and handing back on his own (settled: urgent "you have controls!" with a reason). It also
  covers a goal accepted but not being reached. **Not settled, see F4.**
- **E8 — Petrovich never flies into the ground from the current height.** Over rising ground he climbs
  on his own. *(Settled: point 7, Stage 3.)* The pilot still owns look-ahead (`[[BL-B101]]`), and the
  clearance the floor actually gives over trees and buildings is open (F6).
- **E9 — While Petrovich flies he has no optics.** *(Settled: point 2.)* Whether he still calls
  anything by naked eye, or a threat, is open (F5).
- **E10 — Flight-control speech arrives without model latency.** Handover tokens act at least as
  fast as today's deterministic commands. Cross-link to `BR-2`, noted rather than decided: goal
  commands ("turn heading…") could later go through the brain, but the two handover tokens are the
  case where an extra second of interpretation costs most.

### Open assumptions

- **Which turn rate counts as "a turn in progress".** Serves the why: a deliberate turn continues,
  and a drift of a degree or two of bank is taken as straight and held on heading. Would not: the
  measured rate becomes the goal however small, so the aircraft slowly orbits while the pilot is
  heads-down.
- **The altitude reference for the implicit hold at takeover.** Decision 9 sets radar as the
  default for a spoken altitude. The level-off at takeover (Decision 1) does not name one. Serves
  the why: whichever the pilot would expect a crewmate to hold at that height, which is a question
  for the user. Would not: picking one silently. Radar-referenced at 50 m over broken ground means
  constant pitching to follow every rise. Barometric means terrain clearance changes underneath.
- **What "hold" means over forest and buildings.** Radar altitude may not read (Decision 7), so the
  DCS AGL fallback is likely the only source in practice. Serves the why: the pilot knows what
  clearance a spoken "50 m" actually buys. Would not: 50 m over the ground under a canopy that is
  not counted.
- **What the stop word is.** Serves the why: one short word that ends any turn and holds heading.
  Would not: making the pilot compute and say a heading to stop a turn.
- **What happens on a seat jump while Petrovich has the controls.** Serves the why: a defined
  outcome the pilot can predict. Would not: an outcome left to whatever ED's AI pilot does in the
  vacated seat (plan S0-10 already suspects a second writer).

### Findings

1. **The first vocabulary cannot stop a turn.** — lens: purpose, non-obvious case
   - Assumption: the user's four forms (turn x left/right, turn heading, hold, speed) are enough to
     fly with.
   - In the sim: a takeover mid-turn keeps turning (point 3), and "turn left" with no degrees is
     continuous (Decision 10's readback "left"). Neither ever ends by itself.
   - The pilot would see: Petrovich orbiting until the pilot works out a heading and says it. Page 2
     lists **"level flight"** as priority 2, ahead of "maintain current state", yet no spoken form
     maps to it.
   - Grounded in: page 2 (the user's priorities), point 6 (the vocabulary), Decision 10.
   - Suggests: one stop/level word in the first vocabulary that rolls out and holds the current
     heading. Which word is the user's call (Q1).

2. **"Maintain current state" has no threshold between a turn and a drift.** — lens: non-obvious case
   - Assumption: plan Stage 2 sets the goal to the measured turn rate at takeover.
   - In the sim: a pilot flying "straight" by hand carries a small bank most of the time.
   - The pilot would see: he hands over to look at the map, and two minutes later the aircraft is
     40° off heading, flying exactly as told.
   - Grounded in: the why (hands-off time), and the user's "keep the turn going", which is about a
     turn, not a drift.
   - Suggests: below some rate or bank the turn is treated as straight and held on heading. The
     value belongs in body-layer tuning. Confirm the intent (Q2).

3. **Emergency take-back depends on speech recognition, and on the confirm band.** — lens: crew
   sense, whose job
   - Assumption: the plan makes both handover tokens act only from the act band, with the confirm
     band needing a "yes" (plan, Risks, "Misrecognised handover"). That guards against a false
     release.
   - In the sim: the stick is ignored by decision. So when the pilot sees a ridge or a tracer, his
     only way back is to say "I have controls" and have it recognised. A "confirm?" at that moment is
     the worst possible reply. The user just lowered the voice-confirm bar on main (`d15563cc`),
     which shows confirm prompts are already felt as friction.
   - The pilot would see: he yanks the stick, nothing happens, he says "I have controls", and
     Petrovich asks "confirm?".
   - Grounded in: point 2 ("only spoken"), the plan's own risk note. This does **not** re-ask the
     stick decision.
   - Suggests: the two failure directions are not symmetric. A false release while Petrovich flies
     hands back an aircraft whose stick is somewhere the pilot did not put it. A missed or delayed
     take-back leaves the aircraft flying when the pilot wants it. Only the user can rank them, and
     say whether a bound key as a non-voice backup is acceptable (Q3).

4. **A goal accepted but not reached is silent.** — lens: crew sense
   - Assumption: Decision 10 says no callout when a goal is reached. That is right for reached goals.
   - In the sim: some goals will not be reached, or only slowly. Speed at a heavy weight in a climb,
     collective at its limit (the user: *"the lift vector is the only control if collective is at
     limit"*), right-pedal margin at low speed (the user's asymmetric-yaw note), or the terrain floor
     holding him above a spoken height.
   - The pilot would see: "speed 2 2 0" acknowledged, then 190 indefinitely, with no word.
   - Grounded in: Decision 10 (covers reached goals only), the user's lift-vector and yaw
     constraints, `[[project-say-again-vs-unable]]` ("unable <because>" is the preferred form).
   - Suggests: a single "unable 2 2 0, <reason>" type call when a goal stalls. That is a crew
     behaviour to confirm (Q4), not a callout on reaching the goal.

5. **What Petrovich still perceives and says while flying is not stated.** — lens: crew sense,
   bounded knowledge
   - Assumption: plan Stage 1 suppresses optics via `flying` and leaves the rest of his speech
     unspecified. The plan's own wording is ambiguous ("suppressed / naked-eye decision").
   - In the sim: a human crewmate flying at 50 m still shouts "tracer, 2 o'clock" or "tank, right"
     if he sees it. The user ruled out optics, not eyes.
   - The pilot would see either a Petrovich who goes mute on contacts the moment he takes the
     aircraft, or one who keeps reporting naked-eye sightings while the pilot spots.
   - Grounded in: point 2 (optics stop), the user's "the one not controlling" spots (that is the
     primary spotter, not the only one).
   - Suggests: the user states whether naked-eye spotting, threat calls and answers to "what do you
     see?" continue while Petrovich flies (Q5).

6. **The terrain floor's real clearance over forest and buildings is unknown.** — lens: world truth,
   envelope
   - Assumption: the floor and the radar-referenced hold use one AGL source, radar when valid and
     otherwise `LoGetAltitudeAboveGroundLevel` (Decision 7). The user already notes radar may never
     read.
   - In the sim (agent's understanding, **unverified**): DCS ground-level height may measure to bare
     terrain, ignoring trees and buildings. If so, a 50 m hold over a 20–25 m canopy leaves about
     25–30 m of real clearance.
   - The pilot would see: a spoken "hold 50" that is lower over forest than over fields.
   - Grounded in: Decision 7 and the 50–800 m AGL envelope (50 m is in the normal band). The DCS
     behaviour itself is a question, not a fact.
   - Suggests: Stage 0 S0-6 records it over a forest and a town, and the user knows which clearance a
     spoken height buys (Q6).

7. **Near-term value versus the lasting why.** — lens: purpose, whose job
   - Assumption: the plan's pilot-value check frames handover mainly as "the player becomes the
     spotter".
   - In the sim: in the pilot seat the player spots with his eyes (binoculars when not flying, per
     `long-term-high-level-plans.md`). Petrovich spotting with the 9K113 optics is the better spotter,
     and handover switches those optics off. So for spotting alone, handing over can be a downgrade.
     The uncontested gains are attention freed for the map, radios and kneeboard, and the foundation
     for pilot-Petrovich.
   - The pilot would see: no problem in a transit leg. In a search, fewer contacts called than if he
     had kept flying.
   - Grounded in: the user's own concept (optics off while flying; the "needed for both" rationale).
   - Suggests: nothing to change now. Acceptance should be judged against what the pilot actually
     does with the time (Q7), and choices that only serve copilot-Petrovich should not be
     over-invested in when pilot-Petrovich is the destination.

8. **A seat jump during Petrovich's flying is an unhandled moment the user will meet.** — lens:
   non-obvious case
   - Assumption: the plan treats the seat as fixed (Petrovich in front). S0-10 records ED's AI pilot
     as a possible second writer, and nothing else.
   - In the sim: the user jumps seats routinely in 9K113 work. By his own rule
     (`[[project-petrovich-operates-opposite-seat]]`) Petrovich then occupies the pilot seat, and
     that is pilot-Petrovich, arriving early.
   - The pilot would see: an undefined result. Petrovich keeps flying from the other seat, or
     releases, or two writers fight.
   - Grounded in: the opposite-seat memory, explore "DCS let's me jump between seats", plan S0-10.
   - Suggests: the user names the intended outcome for BL-16 (Q8). Even "release with the urgent
     call" is a defined behaviour.

**Vignette walked (non-obvious case).** Low level in hills: 60 m AGL, 200 km/h, a gentle 5° bank
the pilot does not notice, over a forested valley. He hands over to check the F10 map.

Petrovich takes over cleanly and keeps the 5° bank, as the plan specifies (F2). He holds 60 m on
the fallback AGL, which may be bare terrain, so about 35 m above the canopy (F6). The valley turns;
the floor sees the ground rising under him and climbs, and he says so once. The pilot, in the map
view, hears it.

He looks up and wants straight and level. He has no word for it, so he says "heading 2 7 0" (F1).
A ridge appears. He pulls the stick, nothing happens, and he says "I have controls". If recognition
lands in the confirm band, he hears "confirm?" (F3). Each of these is minor alone; together they
are the opposite of hands-off time.

### Questions for the user

1. What word stops a turn and holds heading — "level", "roll out", "straight", something else — and
   should it be in the first vocabulary?
2. If you hand over with a slight bank you did not mean as a turn, should he hold heading instead of
   continuing a slow turn? Roughly how many degrees of bank is "a turn"?
3. In an emergency take-back, is a "confirm?" after "I have controls" ever acceptable? Would you
   want a bound key as a non-voice backup, the stick staying ignored?
4. If a goal stalls (speed not reachable, collective at its limit, floor holding him above your
   height), should he say "unable 2 2 0, <reason>" once?
5. While he flies, does he still call contacts and threats he sees with his eyes, and still answer
   "what do you see?"?
6. At takeover in level flight, should he hold radar height or barometric? And does a spoken
   "50 m" mean above the trees, or above the ground under them?
7. What do you mainly expect to do with the hands-off time in the pilot seat: look out, binoculars,
   map, radios, or something else?
8. If you jump seats while Petrovich has the controls, should he keep flying from the pilot seat, or
   hand back with an urgent "you have controls!"?

## Plan check — 2026-10-31

**Verdict:** CONCERNS

Checked against: the goal check above; `plans/flight-control/explore-notes.md` in full, including
the 2026-10-31 "Goal-check answers", "The key challenge: parked controls", "Two control states",
"Steering ED's AI is rejected", "Probable solution: overpower the axes", and "Wobble on the flight
axes" sections; `plans/flight-control/plan.md` at `7ab9b500` (P1–P4, A1–A9, Decisions 1–20, D-a to
D-e); `body-layer/ROADMAP/BL-16.md`; `docs/BEHAVIOUR_ALIGNMENT.md`; and the Windows desk-recon note
`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md` (merged in at `bd56b82f`, after
this check had started). The plan traces unusually cleanly against the original E1–E10/F1–F8 — every
one of goal-check's eight open questions has a user answer (A1–A9) and a matching plan change, and
the parked-controls material that arrived after the goal check (P1–P4) is folded into Decision 20 and
the stage-0 gate rather than argued around. The gaps below are two later-arriving user requirements
the plan's current text does not yet carry, plus one place the plan's own recommendation would
re-open a decision the user already made.

| expectation | stage | status |
|---|---|---|
| E1 handover unambiguous, confirmed, "unable" on refusal | Stage 1, Decision 13 | met |
| E2 nothing jumps, turn/climb/IAS continue, <5° → level | Stage 1/2, Decision 1 REVISED | met (F2 resolved by A2) |
| E3 stick does nothing while he flies | Decision 6, S0-1/S0-2, Stage 1 | met, pending Stage 0's measurement — see Finding 3 |
| E4 short readback on every command | Decision 10 | met |
| E5 pilot can stop a turn by voice | `level_out`, A1, Decision 12, Stage 2 | met (F1 resolved) |
| E6 "I have controls" acts at once, no confirm | A3, Decision 13 | met |
| E7 refuses/climbs/hands-back/says-so | Decision 14 (A4: no call on a stalled goal, by the user's own choice) | met — the open half of E7 was resolved by the user toward silence, not toward a callout; the plan matches that answer |
| E8 never flies into the ground from current height | Stage 3, Decision 7 | met |
| E9 optics off, naked eye on while flying | A5, Decision 15 | met |
| E10 handover speech at today's latency | Decision 19 | met |
| F1 stop word | A1, Decision 12 | met |
| F2 turn-vs-drift threshold | A2, Decision 1 REVISED | met |
| F3 emergency take-back vs. confirm band | A3, Decision 13 | met |
| F4 goal stalls silently vs. "unable" | A4, Decision 14 | met (user chose silence) |
| F5 naked-eye calls while flying | A5, Decision 15 | met |
| F6 AGL clearance over trees/towns | A6, S0-6 (and the new desk-recon's `master`/SAU-marker angle, see Finding 2) | met, pending Stage 0 |
| F7 near-term value vs. lasting why | A7 | met — pilot-value check rewritten around the key case |
| F8 seat jump while flying | A8, Decision 17 | met |
| P1 key case is ED's AI, not the player's stick | Decision 16, S0-P gate | met |
| P2 two control states, both must-haves, per-state effector | Decision 20, S0-P/S0-c split, go/no-go | met |
| P3 steering ED's AI rejected as a control path | S0-P3 scoped to off-switches only | met |
| P4 overpower-the-axes hypothesis probed first | S0-P2 | met |
| **W1 — invisible wobble required on every flight-axis write, both states** (`explore-notes.md`, "Wobble on the flight axes", 2026-10-31) | none | **missing** — see Finding 1 |

### Findings

1. **The plan has no wobble on the flight axes, and Decision 6 says the opposite of what the user
   just required.** — lens: purpose, non-obvious case
   - Assumption: `grep -i wobble plans/flight-control/plan.md` returns nothing. Decision 6 reads
     *"Stick override: measure first (S0-2), explore options only if it fails"* — wobble/dither/
     flicker is written up as a fallback tried **only if a held constant write loses**. S0-2's own
     row frames it the same way: *"flicker fails but dither holds → dither; both fail → Decision
     6."* S0-P2 frames parked-state wobble the same way, as one candidate among "constant vs.
     flicker vs. dither" to be compared, not a given.
   - In the sim: the user's words are unconditional — *"Regardless of how writing control axis
     values are done, that (invisible) wobble is needed on the control axises, similar to 9K113
     axises."* Not "if the plain write fails," every frame, both states.
   - The pilot would see: nothing wrong yet, because this is a measurement-stage gap, not a built
     behaviour — but if Stage 0 is run against the plan as written, a held constant write that
     happens to win on the bench (e.g. because the AI only re-asserts its own value at some longer
     interval) would read as a pass and the wobble would never be built in, until a later flight at
     a different airspeed or altitude shows the lapse the 9K113 work already measured for the sight
     axis (intermittent obedience without a per-frame value change, 9K113 run 11).
   - Grounded in: the user's own words (binding), the 9K113 precedent the plan itself cites for P4
     (`plans/9k113-sight-pointing/plan.md`, `SERVO_WOBBLE`), and the new desk-recon's own read of
     *why* the 9K113 override won — *"It won by changing value every frame, which suggests ED's
     consumer reacts to new input and otherwise falls back to its own source"* — which argues the
     same mechanism is needed for the flight axes from the start, not as a contingency.
   - Suggests: Decision 6 is superseded — the wobble is mandatory on cyclic pitch/roll, pedal and
     collective in both effectors, not a fallback probed only on failure. S0-1/S0-2/S0-P2 should
     measure the wobble's own bound (how large before it is felt in the aircraft or seen in the
     cockpit stick/collective/pedal animation), not whether wobble is needed at all. This is a plan
     text change, not a user decision to make — the user has already made it.

2. **S0-P2's pass criterion may read as a pass on an override that is not actually flying the
   aircraft.** — lens: world truth, non-obvious case
   - Assumption: S0-P2 passes when *"the aircraft follows the written value; args track `v`, not the
     AI, every frame"* — read as the cockpit stick/collective/pedal animation args (1100–1113 per
     the new desk-recon, generically "cockpit stick/collective/pedal args" in the plan).
   - In the sim (desk-recon, new): if ED's AI pilot flies through the SAU channel (device 10) rather
     than writing the stick position directly — a real possibility the recon raises and cannot rule
     out from the files alone — then the **stick animation args may stay centred while the SAU's own
     deflection (`au_roll_position`/`au_pitch_position`/`au_rudder_position`/`au_height_position`,
     Controls Indicator) does the flying**. Reading only 1100–1113 would then show "args track v"
     regardless of who is actually flying, because the AI's real channel is a different arg the plan
     does not name.
   - The pilot would see: a Stage 0 report that says the parked override won, then a Flight 4b where
     ED's AI is still visibly in command of the aircraft — exactly the failure the go/no-go gate
     exists to catch before anything is built.
   - Grounded in: the desk-recon's §6 (`au_*` markers, `LoGetHelicopterFMData().master`, the two
     plausible paths (a)/(b)) and its own suggested first probe, which the plan's S0-P2 row does not
     yet cite.
   - Suggests: S0-P2 and S0-P2a add the Controls Indicator's `au_*` markers and `master` to what is
     logged and compared, alongside the stick-position args, before declaring a pass. This is a
     measurement-completeness point for Stage 0a/0b, not a change to what the plan is trying to
     build.

3. **D-e's recommendation (auto-take on park) would re-open "handover is spoken only," which the
   user already settled.** — lens: crew sense, whose job
   - Assumption: D-e asks whether parking without a prior "you have controls" should make Petrobrain
     take over automatically and say "I have controls," and *recommends* that it should, once S0-12
     gives a reliable park signal.
   - In the sim: the 2026-10-25 settled point 2 (carried into `BL-16.md` and the goal check's E1/E6)
     is *"Handover is spoken only"* — the explore conversation's own second settled item, never
     revisited. An auto-take on park is not a spoken handover; it is Petrovich taking the controls
     on a cockpit-switch event the player did not narrate.
   - The pilot would see: he parks the controls to work the 9K113 (as DCS requires) without having
     said "you have controls" first, and Petrovich speaks over him anyway — a second, unasked-for way
     to take the aircraft, which cuts against E1 ("unambiguous... after 'you have controls'") even
     though D-e's own text frames it as serving A8's spirit.
   - Grounded in: the 2026-10-25 settled point 2 (`explore-notes.md`, `BL-16.md`), goal check E1/E6.
   - Suggests: D-e is correctly flagged as "Decisions Requiring User Input" and not yet built, so
     nothing in the plan has acted on it — but the recommendation itself should be read against
     "spoken only" before the user answers, since it is the one place in this plan where the
     Architect's own suggestion, if accepted as written, would contradict a decision already on
     record rather than fill a genuine gap. (Q1 below.)

4. **Stage 0a's pending input has landed and is folded in; no other action needed here.** — lens:
   purpose
   - The 2026-10-31 desk-recon (`aircraft-layer/research/2026-10-31-mi24p-park-controls-ai-pilot.md`)
     that Stage 0a named as pending is now on the branch. Its headline — park state and the AI pilot
     are native-code, not Lua, so no flag disables the AI while parked and it must be probed — matches
     what the plan already assumed (S0-P3's "none → blocker" branch). Nothing in it reverses a plan
     decision beyond Findings 1 and 2 above.

### Questions for the user

1. D-e recommends Petrovich take the controls automatically when you park without having said "you
   have controls" first. That is a second way he takes the aircraft, not a spoken one — is that what
   you want, or should parking without a prior handover leave the controls with ED's AI until you
   say "you have controls"?

## Goal check — parked mode (2026-11-15)

**Verdict:** CONCERNS

Addendum for **mode 2 only** (controls parked, Petrovich drives ED's AI pilot through the HELPER_AI
wheel), now the first build of BL-16. The 2026-10-31 goal check above stands for mode 1; E1–E10
there are not re-derived. Checked against: `explore-notes.md` from "Decision: skip probe v3, two
modes" to the end (the user's wheel write-up, the short-right typo correction, "We'll have to do
with ED's control then"), the user's direction of 2026-11-15 relayed by the main loop (park itself
activates parked mode — quoted below; the main loop has recorded it in `explore-notes.md`),
`aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md` §5, `body-layer/ROADMAP/BL-16.md`,
`body-layer/ROADMAP/BL-B67.md`, plan rows S0-P3b and S0-12.

> *"Since AI helper takes over automatically and immediately when controls are parked, so should
> Petrobrain flight controlling mode activate for the AI helper. Regardless of Player commanding
> 'your controls' or not."* (user, 2026-11-15)

That answers the plan check's question 1 above: parking is the handover. There is no spoken
exchange on park.

### Why

The player parks for one reason, the 9K113 sight view. DCS then gives the aircraft to ED's AI, and
nothing can stop that (stage 0, closed). Without help, the player has to run that AI from the
sight seat through a wheel menu. That costs him his hands and eyes when he needs them on the
crosshair, and ED's AI makes two mistakes on its own: it sinks right after the park, and it dives
into the ground after a launch if it is left in ALIGN FOR LAUNCH.

Asked once more: why does the player need the AI run for him? So he can **keep his eye in the
sight from the moment he parks until the missile hits, and trust that the aircraft will not hit
the ground meanwhile**. Parked mode does not make the flying good. The user has accepted that
(*"We'll have to do with ED's control then"*). It fixes ED's interface (voice in place of the wheel)
and ED's two known traps. The earlier why, "replace ED's AI because it flies badly", still belongs
to mode 1 and does not apply here.

What the player **gets**: the flight parameters set by voice, alignment by voice, and protection
from the park sink and the post-launch dive. What he **does not get**: smooth or precise flying,
the S-curve response (decision 5), continuation of a turn already in progress at takeover (decision
3; at the park, ED's AI does what it does), arbitrary speeds, or more terrain awareness than ED's AI
plus the two fixes. The plan and the test card must say this, so a sloppy hold is not filed as a
defect of parked mode.

### Player expectations

- **E-P1: Parking is the handover, and the aircraft holds what it was doing.** Within a second or
  two of the park, without the player saying anything, the aircraft stops the ED sink and holds the
  current altitude (the user's "set altitude first on park"). If ED's AI also drifts heading or
  speed on park, the same rule applies to those. Seen from the seat: the altitude readout does not
  wind down after the park.
- **E-P2: The player hears one short line when Petrovich takes over on park**, so he knows the
  aircraft is managed and not just ED's AI on its own. The wording is open (Q1). It is never a
  question, and it never waits for an answer.
- **E-P3: Spoken heading, altitude and speed goals happen, approximately and honestly.** The
  readback names what the AI will actually hold. A speed goes to the nearest wheel step, so
  "speed 2 2 0" is read back as "two hundred" and not as "two twenty". Altitude is good to about 20
  m, heading to what the overlay sets. After the readback, silence (settled 2026-10-31 answer 4: no
  "unable" for a goal not quite reached). Several goals at once all start moving early, through
  interleaved steps, not one after another.
- **E-P4: The latest spoken goal wins.** A new command replaces one still in progress, and the
  readback names the new goal. Petrovich does not narrate mode hops, presses or partial progress.
- **E-P5: Petrovich never undoes the player.** If the player works the wheel himself (a set value,
  a mode change, HDG LOS), Petrovich does not fight it or press it back. The new set values become
  the goal. What "not fighting" means for a mode the player selected is open (Q4).
- **E-P6: Petrovich never presses HDG LOS (short right).** The user called this an invariant
  (*"We must not"*).
- **E-P7: Alignment happens on the player's word, and only then.** "Align" (heading to the 9K113
  azimuth) and "align for launch" (boresight onto the sight vector) are said by the player in the
  sight seat. Petrovich presses ED's CBTM option. He never starts an alignment on his own, because
  choosing the target and the moment is the shooter's job.
- **E-P8: After the launch, the aircraft levels off and the missile stays guidable.** Once the
  missile leaves, Petrovich takes the AI out of ALIGN FOR LAUNCH and back to level flight on his
  own (the user's second issue), without a spoken word. He does it so the target stays inside the
  sight's limits until impact (F-P2).
- **E-P9: Parked, the aircraft never flies into the ground because of a mode Petrovich put it in.**
  This is decision 7 ("whoever flies avoids the terrain") as it applies here. ED's AI is flying, so
  Petrovich's share is the traps he can see: the park sink, the dive in ALIGN FOR LAUNCH before and
  after launch, and an alignment abandoned without a launch (F-P1).
- **E-P10: Unparking gives the aircraft back at once.** The moment the controls unpark, Petrovich
  stops pressing (a press being held is released) and drops any unfinished goal. He does not
  re-apply it on the next park. A new park is a fresh takeover, E-P1. What he says, if anything,
  is Q2.
- **E-P11: He keeps being a crewmate while "flying".** Naked-eye contact and threat calls continue,
  as in the 2026-10-31 answer 5. The wheel work is silent background work.

### Open assumptions

- **What happens on park.** Serves the why: hold current altitude, heading and speed as found, with
  altitude first because that is the trap. Would not: holding only altitude while the AI settles on
  a stale heading or speed it carried from an earlier park. Whether ED's AI resets heading and speed
  on park is for the user (Q3).
- **Which altitude reference parked mode holds.** Serves the why: radar by default. Over rising
  ground ED's AI then follows the terrain, which is the only terrain avoidance parked mode has
  beyond the two fixes. This is decision 9's default carried over. Would not: keeping whatever
  reference the overlay happened to show, which can be barometric at 50 m over hills. It needs the
  user's confirmation that ED's AI really follows terrain in radar mode (Q6).
- **When ALIGN FOR LAUNCH ends.** Serves the why: it ends on the launch, on the player aborting, or
  when height drops below a floor. Would not: ending it on launch only, which is the obvious reading
  of the user's text. See F-P1.
- **What "level flight" after the launch means.** Serves the why: hold the current heading (or
  track the sight's azimuth) so the target stays in the sight until impact, and an altitude that is
  safe. Would not: a return to FLT that lets ED's AI turn back to the heading it held before the
  alignment, swinging the target out of the sight while the missile is still flying. See F-P2.
- **Where parked mode sits relative to BL-B67.** Serves the why: the parked case is the player on
  the sight. He tracks, he launches, and Petrovich runs the AI. Would not: wiring parked mode into
  BL-B67's ATGM run, which is built on Petrovich holding the sight and the pilot launching. See
  F-P3.
- **What a mode change by the player means.** Serves the why: the player's mode is his intent, so
  Petrovich defers to it. Would not: cycling straight back to FLT to finish a speed step and
  pulling the player out of CBTM. Q4.
- **Which goal a parked command answers to after an alignment.** Serves the why: the alignment
  overrode the goal, so after launch level flight is the new goal. Would not: resuming an earlier
  spoken heading that points away from the target. This is part of F-P2.

### Findings

1. **F-P1: Ending ALIGN FOR LAUNCH only on launch leaves the dive unguarded.** Lens: the non-obvious case,
   and whose job (decision 7).
   - Assumption: the trap is "after the launch", so the exit is triggered by the launch.
   - In the sim (user's words): the AI *"keeps that alignment … constant speed increase and altitude
     decrease … flies the aircraft into ground"*. The dive comes from holding the boresight on a
     target below. It begins when the alignment begins, not when the missile leaves.
   - The pilot would see: he aligns at 60 m AGL on a target 4 km out, the missile takes a few seconds
     to get permission, or he decides not to fire, and the aircraft keeps descending with nobody
     pulling out. A player who has said "align" and then gone quiet can fly into the ground with no
     launch ever happening.
   - Grounded in: the user's issue 2 and decision 7, *"whoever flies avoids the terrain"*.
   - Suggests: the exit has three triggers (launch, a spoken abort or cancel, and a height floor). The
     floor is Petrovich acting unbidden, as in decision 7. The user should confirm that an
     automatic pull-out before launch is wanted (Q5), because it can spoil a shot the player was
     about to take.

2. **F-P2: Leaving ALIGN for "level flight" must not turn the target out of the sight.** Lens: unit of
   action. The action is a missile guided to impact, not "the aircraft is level".
   - Assumption: post-launch means switch to FLT and set altitude.
   - In the sim: the 9K113 is guided by the operator until impact, and the sight can only look so far
     off the nose. FLT holds a set heading. If that set heading is still the one from before the
     alignment, ED's AI turns back to it, and the target may leave the sight's limits mid-flight.
     "One parameter at a time" makes this worse if altitude is set first and heading second.
   - The pilot would see: a good launch, the aircraft swings off, the crosshair hits its stop, and the
     missile is lost.
   - Grounded in: the user's FLT/CBTM model (FLT holds set heading) and the sight's gimbal limits as
     modelled in `belief/sight_head.py`. **Whether FLT resumes the pre-alignment heading is the
     agent's inference, so it is Q7.**
   - Suggests: on leaving ALIGN, the first press makes the set heading the current heading (or the
     sight's azimuth), and the altitude comes after. The altitude target is the pre-alignment
     altitude or a safe floor, not wherever the dive ended (Q8).

3. **F-P3: "BL-B67's parked case" is a role swap, not a variant of the ATGM run.** Lens: whose job.
   - Assumption (from the dispatch): parked mode serves BL-B67's attack run.
   - In the project: BL-B67 is Petrovich on the sight (pin, single-unit aim, range calls, guidance
     transmitter reset), with the pilot launching. Parked, the **player** is on the sight and
     launches, and Petrovich is in the pilot's place running ED's AI. None of BL-B67's sight
     behaviour applies. Its alignment is unparked (user, 2026-11-15: *"BL-B67's own is unparked"*).
   - The pilot would see: if a planner wired parked mode through BL-B67's run, Petrovich would try to
     drive or announce a sight the player is holding.
   - Grounded in: root `CLAUDE.md` "Whose job is whose", BL-B67's entry, the user's 2026-11-15 line.
   - Suggests: parked mode re-uses only BL-B67's **launch detection** (loadout −1 from the payload
     feed) as the post-launch trigger, which is what Petrovich could perceive from the seat.
     Alignment is called by the player's voice (E-P7). Range calls for the player's own shot are
     out of scope unless the user asks for them.

4. **F-P4: Taking over on park is consistent with decision 3, which is why it is not autonomy creep.**
   Lens: crew sense. Informational, nothing at stake.
   - The user's "set altitude first on park" looks like Petrovich acting unbidden. It is decision 3
     ("on takeover he maintains the current state") applied to a takeover that the park, not a word,
     triggers. ED's AI would otherwise change the state. Read this way, E-P1 also covers heading and
     speed (Q3) and needs no separate rule. The one truly unbidden act is the alignment exit
     (F-P1/F-P2), and decision 7 covers it.

5. **F-P5: The player on the sight cannot tell ED's AI from Petrobrain-managed ED's AI.** Lens: would
   the pilot notice and use this?
   - The same AI flies in both cases, with the same sloppiness. Without E-P2's line on park, the only
     sign that Petrobrain is working is the sink not happening. The line on park is not ceremony.
     It is the only way the player knows his voice commands have a listener.

Vignette walked (off the happy path): the player parks at 70 m AGL and 200 km/h, enters the sight
(DCS switches to CBTM), and Petrovich cycles to FLT to set altitude. The player says "align". Back
to CBTM, ALIGN TO 9K113. Then "align for launch": the nose drops toward a target 3 km out, and
the player waits for the lamp. Height falls to 35 m with no launch yet. Today nothing catches that
(F-P1). He fires, Petrovich goes to FLT, ED's AI holds its old heading 40° off, the target leaves
the sight, and the missile is lost (F-P2). Each step follows the user's model as written. The gaps
are only in what triggers the exit and in what order things are set on the way out.

### Questions for the user

- **Q1** — When you park, what should Petrovich say, if anything: "I have controls", something
  else, or nothing?
- **Q2** — When you unpark (take the stick back), should he say "you have controls", or stay
  silent?
- **Q3** — On park, does ED's AI also wander off in heading or speed, or only sink? Should he
  re-set heading and speed to current as well as altitude?
- **Q4** — If you change the AI wheel's mode yourself (e.g. to CBTM) while he is midway through a
  goal, should he leave your mode alone and drop his goal, or finish his goal and cycle back?
- **Q5** — Before launch, in ALIGN FOR LAUNCH, should he pull out on his own if height drops below
  a floor (and say so), even though that may spoil the shot?
- **Q6** — With ALT REF on radar, does ED's AI follow rising terrain well enough that this can be
  parked mode's terrain avoidance?
- **Q7** — When the AI leaves CBTM for FLT, does it go back to the heading set before the
  alignment, or hold the heading it has now?
- **Q8** — After the launch, which altitude: the one held before the alignment, or the current
  one (with a floor)? And which heading: current, or follow the sight's azimuth until impact?

### Answered by the user (2026-11-15)

Verbatim answers: `plans/flight-control/explore-notes.md`, "Answers to the parked-mode goal
check". In short, numbered against the questions:

- **Q1** nothing on park. **E-P2 is withdrawn**: no line on park.
- **Q2** silent transfer on unpark; Petrobrain keeps flying unless the player commands otherwise
  (the unparked follow-on handles the rest).
- **Q3** the AI sets current heading and nearest speed step itself; reset **altitude only**.
- **Q4** the player is assumed not to change modes; DCS does (CPG view → CBTM, hover
  transitions), and Petrovich cycles back to the mode his goal needs.
- **Q5** yes. Recovery triggers: launch, spoken abort, **AGL below 40 m** or **IAS above
  280 km/h** (both tunables). He says *"leveling off"* and restores the pre-alignment
  parameters. A break-turn call afterwards is the player's decision. Resolves F-P1 and E-P9.
- **Q6** radar hold follows terrain but is jerky; baro hold is smoother and preferred, with
  terrain avoidance then Petrovich's own job (BL-B101 territory).
- **Q7** FLT after CBTM holds the current heading; the alignment heading becomes the set heading.
  Resolves F-P2: no swing-back.
- **Q8** quick transition to level flight keeping the heading and altitude at the transition
  moment, then a smooth climb to the pre-alignment altitude, speed back one step at a time.

**Verdict after answers: ALIGNED** for the plan re-cut; expectations E-P1, E-P3–E-P11 stand,
E-P2 withdrawn, E-P9 refined by Q5's floor and ceiling.

## Plan check — parked mode (2026-11-15)

**Verdict:** CONCERNS

Checked `plans/flight-control/plan.md`, "Revised 2026-11-15 — parked mode (mode 2) is the first
build" (Stages P0–P6) against the goal check above, as amended by the user's Q1–Q8 answers.

| expectation | stage | status |
|---|---|---|
| E-P1 | P1 | met — park-rising resets altitude only (Q3), no speech (Q1), matches F-P4's reading without over-reaching into heading/speed |
| E-P3 | P2 | met — rounded readback, 20 m/5° tolerance, silence after, interleaved start |
| E-P4 | P2 | met — `goal_seq`, latest wins, Co-moving Fields table |
| E-P5 | P2, via **U3** | **contradicted** — see Finding 1 |
| E-P6 | P1 | met, with a caveat — see Finding 2 |
| E-P7 | P3 | met |
| E-P8 | P4 | met |
| E-P9 | P4 | met — AGL floor/IAS ceiling per Q5 |
| E-P10 | P1 | met — unpark drops all state, nothing resumes on next park |
| E-P11 | P5 | met — explicit check, `optic_policy` untouched |
| F-P1 | P4 | met — launch/abort/AGL-floor/IAS-ceiling triggers, per Q5 |
| F-P2 | P4 | met — FLT holds current heading (Q7), altitude/speed restored per Q8's order |
| F-P3 | "Launch detection" section, P5 | met — payload-drop signal re-implemented locally, not imported from `atgm_run.py`; sight untouched |

### Findings

1. **E-P5 is marked "closed" by a posture that does the opposite of what it requires.** Lens:
   whose job / the non-obvious case.
   - Assumption: the traceability table (plan.md line 302) reads E-P5 ("Petrovich never undoes the
     player... does not fight it") as satisfied by Stage P2's "assume no player mode change"
     posture, cross-referenced to **U3**.
   - In the sim: U3 asks exactly the case E-P5 names — the player presses the wheel himself — and
     recommends *"always reassert at once"*, i.e. cycle back to whatever mode Petrovich's goal
     needs, overriding the player's own press. That is fighting the player, the thing E-P5 calls
     out as the one thing never to do, alongside "a set value" and `HDG LOS`.
   - The pilot would see: he nudges the wheel to CBTM himself mid-flight for some reason of his
     own, and Petrovich silently cycles it straight back to FLT a moment later — the aircraft
     answering to a command the player didn't give, which is the "disconnecting the wire" feeling
     decision 4 (mode 1) was written to avoid in a different context.
   - Grounded in: E-P5's own wording (goal check, not re-derived here) and U3's recommendation in
     the same plan.
   - Suggests: this is Q4 narrowing E-P5, the [[project_bl_b111_decision_narrows_just_answered_expectation]]
     shape — but Q4's own words only cover *DCS-driven* mode changes ("DCS does automatically in
     certain situations"); Q4 says the **player** case is "assumed not to happen," not "and if it
     does, override him." U3 goes further than Q4 licenses and the table's "closed by" wording
     hides that gap. The row should read **contradicted**, not met, until the user either (a)
     confirms U3's "always reassert" for the player case too — accepting that E-P5 does not hold
     for a self-inflicted mode press, only for DCS-driven ones — or (b) asks for a short grace
     window before reasserting, closer to E-P5's actual wording. Either answer is fine; the plan
     currently asserts the first without having asked for it.

2. **E-P6's structural guarantee rests on no function ever existing that could combine `short` +
   `right`, which the plan states but does not yet pin down in code shape.** Lens: the non-obvious
   case.
   - Assumption: "short-right is never in the press vocabulary at all" (plan.md line 303).
   - In the sim: the design as described keeps this true by construction — mode-cycle is always
     `short-left`, speed is always `short-up/down`, heading is always `long-left/right`, so no
     described code path ever pairs `short` with `right`. But this holds because every caller
     happens to need a different (direction, duration) pair, not because a generic
     `press(direction, duration)` is withheld from existing. If the Implementer builds one generic
     press primitive for convenience, `short-right` becomes reachable by a typo in a constant.
   - The pilot would see nothing until the one time it goes wrong — the aircraft snaps to
     wherever he's looking, mid-flight, with no warning. This is exactly the invariant the user
     called out unprompted (*"We must not"*).
   - Grounded in: the user's correction and invariant on `HDG LOS`.
   - Suggests: not a blocker, since the design as written doesn't call for a generic combinator —
     but worth a one-line note to the Implementer that the five action functions
     (`set_parked_heading`/`altitude`/`speed`, `cbtm_align`, `cbtm_align_for_launch`) should each
     hard-code their own fixed press shape in Lua, with no shared `press(direction, duration)`
     entry point that could be called with `("right", "short")`.

### Questions for the user

- **Q-P1** — U3 recommends always reassert the AI wheel's mode at once, even if you pressed it
  yourself. Q4 only said to assume you won't do that for the DCS-automatic case; it didn't say
  Petrovich should override a mode you set on purpose. Is overriding you here acceptable for the
  first build (matching U3), or should Petrovich leave your mode alone for some window before
  reasserting it (closer to E-P5 as written)?

### Plan check Q-P1 answered by the user (2026-11-15)

> *"reassert at once — the goal is to use the wheel command via Petrobrain, not player directly."*

U3 stands. E-P5 is narrowed by the user to: the player is not expected to operate the wheel while
parked mode runs; if he does, Petrovich's goal wins. **Plan check verdict after the answer:
ALIGNED.** In the same message the user gave the short-left cycle orders (`FLT > CBTM > FLT`;
`HVR > HVRT > CBTM > HVR`), the automatic transitions, a full spoken vocabulary for parked mode,
and a prerequisite: audio capture must gate on both the pilot's (arg 738) and the operator's
(arg 856) ICS trigger, equally. Verbatim: `plans/flight-control/explore-notes.md`, "U3 decided,
mode-cycle orders, and the player command vocabulary". These go to a plan amendment.

## Plan check — amendment (2026-11-15)

**Verdict:** ALIGNED, with two findings worth fixing before Implementer and one question.

Scoped to `plans/flight-control/plan.md`'s "Amended 2026-11-15 (vocabulary, ICS capture, cycle
orders)" and the stage rows it edited (P-ICS, P1, P2, P3, P4) — the rest of the plan check stands
from the previous pass above.

### Vocabulary trace

Every spoken phrase in the user's verbatim list (`explore-notes.md`, "U3 decided...") maps to a
token, a mode gate and a press shape in the amended table (plan.md lines 103-121); none dropped,
none re-interpreted.

| Spoken (user) | Token | Checked against |
|---|---|---|
| "level flight" | `level_flight` | stabilise to current, not a numeric target — matches |
| "Heading <deg>" / "<compass point>" | `turn_heading` | both forms present, compass→degrees translation noted as new slot work |
| "Turn left/right <deg>" | `turn_heading_relative` | computed once at command time, matches "relative, not re-derived" |
| "Break turn left/right" | `cbtm_break` | long press, no hold, 90° — grounded in the wheel research (`2026-11-14-mi24p-ai-pilot-wheel-layout.md` line 143), not plan-invented |
| "Break away" | `cbtm_break_away` | two long-left presses, `BREAK_AWAY_GAP_S = 2.0` — the user's own "wait 2 s" verbatim |
| "Align" / "Align [for] launch" | `cbtm_align`/`cbtm_align_for_launch` | unchanged from Stage P3, carried forward |
| "Straight" / "level off" | `level_off` | one token, two meanings gated by `align_phase` — correctly matches the task brief's reading that this is F-P1's spoken abort while aligning, and an ordinary turn-stop otherwise |
| "Speed <value>" (incl. "max") | `set_speed` | matches |
| "Slow down" / "Speed up" | `speed_step` | matches |
| "Hover" | `set_speed(0)` | matches; correctly triggers the automatic FLT→HVR transition rather than a separate mode press |
| "alt <value> [radar/barometric]" | `set_altitude` | matches |
| "climb/descend <m>" | `altitude_step` | matches |
| "hold altitude" | `hold_altitude` | matches |
| "left/right/forward/back", held until "Hold" | `hvrt_translate`/`hvrt_hold` | HVRT-only, held press released on "Hold" **or** `HVRT_TRANSLATE_MAX_HOLD_S` — see Finding 2 |
| "up/down" | `hvrt_step` | discrete short press, 2 m/tap — grounded in the same wheel research (`alt_change_step = 2`), not plan-invented |

The ICS requirement is carried faithfully: Stage P-ICS extends `push_ptt_state` to arg 856
alongside 738, and the schema layer's `intercom`/`radio` properties become an OR across both raw
values — this is "treat them equally" as a design, not an assertion. **Verified by grep, not
trusted:** `grep -rn "intercom\|radio" audio-adapter/src aircraft-layer/src body-layer/src`
confirms `audio_adapter/src/ptt_source.py`'s `DcsPTT.is_down` is the only reader of those two
booleans (the one `body-layer/src/aircraft_client.py` hit from the same grep is a
`to_api_dict`-pattern false positive, not a PTT consumer) — so "no change needed there" holds.
`aircraft-layer/src/schema/spu8.py`'s `Spu8Sample.gate_open` (`net1_on and ics_power_on`) already
ANDs the pilot's NET-1 (377) and the co-pilot's ICS-power (664) switches regardless of which seat
is talking, confirmed by reading it directly — the plan's "no change needed" claim for the SPU-8
gate holds too.

### Other checks

- **HVRT dispatch gate is belief, not omniscient DCS truth.** `ai_mode` is declared a state param
  ("mirrors Lua's parsed `mode_text`... never DCS truth directly") fed by the same
  `list_indication` readback the player himself would see on the overlay, polled every tick — not
  a bypass read of DCS's internal mode variable. This is the right boundary (root `CLAUDE.md`'s
  no-omniscience rule) and the plan's own "read the mode every tick, never assume" posture already
  covers the one latency risk this creates (a stale `ai_mode` for one poll around a mode
  transition).
- **No existing vocabulary collision.** The plan's own grep check (`crew_console.py`'s
  `_RELATIVE_SCAN_TOKENS`/step-through, `audio-adapter/src/vocabulary.py`'s `PHRASES`) is correct
  as far as it goes; checking the one table it did not name,
  `body-layer/src/belief/voice_commands.py`'s `CANCEL_TOKENS`, turns up no bare "left"/"right"/
  "hold"/"forward"/"back"/"up"/"down" there either — the new HVRT tokens remain the first bare
  single-word phrases in the vocabulary, confirmed rather than assumed.
- **`MODE_CYCLE_MAX_ATTEMPTS = 3` and `HVRT_TRANSLATE_MAX_HOLD_S = 15` don't contradict user
  wording.** The first is derived arithmetic from the user's own cycle orders, not a guess. The
  second is a safety ceiling under a hold the user described as open-ended ("Hold until Player
  says Hold") — it doesn't contradict that wording for ordinary flight (15 s covers any plausible
  deliberate translate), and the plan already flags it, unprompted, as the architect's own
  judgement call rather than passing it off as settled. See Q-P2 below rather than treating this
  as a finding.
- **E-P6's structural guarantee still holds mechanically after the vocabulary grew.** No generic
  `press(direction, duration)` entry point is described anywhere in the amendment; every "right"
  in the new table is either a long press, no hold (`cbtm_break`) or a long held press released on
  "Hold"/timeout (`hvrt_translate`) — never short. `up`/`down` (the only short presses added) never
  pair with `left`/`right`. The guarantee is unchanged in kind from the prior pass's Finding 2: it
  holds because every caller happens to need a different (direction, duration) pair, not because
  one is withheld from existing.

### Findings

1. **The new vocabulary is never routed into `audio-adapter/src/vocabulary.py`'s
   `TOKENS`/`PHRASES` tables, which is what actually gets a word into Petrovich's ears.** Lens:
   do not reinvent the wheel / the non-obvious case.
   - Assumption: Stage P2's text says "new slot parsers needed for the full vocabulary table
     above" and stops there, as if `command_matcher.py`-level slot parsing is the whole of the
     audio-adapter work.
   - In the project: `audio-adapter/CLAUDE.md` states this as a rule, not a style preference —
     `vocabulary.py` is "a deliberate hand-synced duplicate" of `crew_console.py`'s token tables,
     kept in sync **by hand, with no automated check tying the three together**, and its
     `to_prompt()` biases whisper's recognition toward every `PHRASES` word by construction,
     enforced by `test_vocabulary.py`. The project's own account of why this matters: "Before
     2026-10-23 the prompt sampled 24 of 66 tokens' phrasings and missed silence, engage, set
     target, describe and every slot word — the cause of 'violence'/'same ahead' in the speech
     logs."
   - The pilot would see: he says "break away" or "hover" in the cockpit, and if the new tokens
     never reach `vocabulary.py`'s `PHRASES`/`TOKENS` (and hence whisper's bias prompt), the
     transcript comes back as something whisper guessed instead — the exact failure mode the
     2026-10-23 fix was written to close, recurring on this feature's own ~15 new tokens.
   - Grounded in: `audio-adapter/CLAUDE.md`, "Structure" → `src/vocabulary.py`'s entry.
   - Suggests: add one line to Stage P2 (and P3 for `cbtm_break`/`cbtm_break_away`, P4 for the
     dual-meaning `level_off`) naming `audio-adapter/src/vocabulary.py`'s `TOKENS`/`PHRASES` as
     something the Implementer must also extend, hand-synced against `crew_console.py` the way
     the file's own docstring already requires. Not a blocker to Implementer starting P-ICS/P1,
     but it is a real gap in P2/P3/P4's own content, not a stylistic nit.

2. **The prior pass's Implementer note (no shared `press(direction, duration)` entry point) still
   has not been written into the plan, and the vocabulary growth makes it more worth saying, not
   less.** Lens: the non-obvious case.
   - Assumption: carried from the previous "Plan check — parked mode" Finding 2, marked "not a
     blocker" there for a five-function vocabulary.
   - In the sim: unchanged in kind, but the surface has grown — `cbtm_break`, `cbtm_break_away`,
     and the four HVRT directions now all touch "right" with different timings (no-hold-long,
     held-long, discrete-short-elsewhere-only). The structural guarantee (checked above) still
     holds as described, but it holds only because the Implementer keeps hard-coding five-now-nine
     separate press shapes rather than factoring them into one parameterised helper — a natural
     refactor instinct once there are nine similar-looking call sites.
   - The pilot would see nothing until the one time `HDG LOS` fires unbidden — the user's named
     invariant ("We must not").
   - Grounded in: the user's own correction on `HDG LOS`, and the growth between this plan revision
     and the last.
   - Suggests: the same one-line note as before, now worth actually adding to the plan text (e.g.
     beside the "Architecture decision" section) rather than carrying it only in `alignment.md`
     across two revisions.

### Questions for the user

- **Q-P2** — `HVRT_TRANSLATE_MAX_HOLD_S` defaults to 15 s, the architect's own judgement call, as a
  safety ceiling in case a spoken "Hold" is lost. Is 15 s the right order of magnitude for how long
  you'd expect to hold a hover translate in ordinary use, or should it be longer/shorter/tunable
  from the start?

## Plan check — 2026-11-16 (Stage P1 takeover revision)

**Verdict:** CONCERNS

Checked `plans/flight-control/plan.md`'s "Revised 2026-11-16 — takeover after the Batch A
flights" (the replacement Stage P1, as amended "after the takeover rehearsal probe") against the
unchanged goal check above (E-P1, E-P6, E-P10 are the rows this stage closes) and against the
pilot's own words in `docs/acceptance/2026-11-16-bl16-batch-a-feedback.md`. P-ICS and P0 are
unaffected and not re-checked.

| expectation | stage | status |
|---|---|---|
| E-P1 (park is the handover, holds what it was doing) | revised Stage P1 | met — altitude snapshotted at the rising edge of arg 852 alone, corrected in two phases to that value; no sink in the measured 0.5 s window before the fix lands |
| E-P6 (never presses `HDG LOS`) | revised Stage P1 | met — no left/right press of any kind in the takeover sequence; only centre, `WHEEL_MENU_BUTTON`, and altitude up/down |
| E-P10 (unpark gives it back at once, nothing resumes) | revised Stage P1 | met — Co-moving Fields table's falling-edge row: open press released same frame, `takeover_stage` cleared, menu closed if opened, nothing carried to the next park |
| No sink, ends at the handover altitude (not wherever correction finishes) | revised Stage P1, phase 2 | met — phase 2 explicitly targets the fixed handover snapshot, not the live value phase 1 converges toward |
| Two-phase correction follows the pilot's workaround | revised Stage P1, Amended §2 | met — phase 1 ("hold down until current altitude... is reached") and phase 2 ("continue adjusting... to what it was at handover") map directly to the pilot's own verbatim words |
| Quick path honours the 700 m AGL radar cap | revised Stage P1, Amended §3 | met — attempted only below 700 m AGL, and the read (not the precondition) decides success, falling back to the two-phase hold when the pulse is refused |
| Menu stays open while the AI flies, reopens at once | revised Stage P1, point 3 + Co-moving Fields | met — reopens when belief disagrees with an all-nil read for more than `MODE_READ_SETTLE_S` |
| Nothing in the sequence surprises the pilot (no harder climb/dive than the bug itself, nothing after control is handed back) | revised Stage P1 | **contradicted** — see Finding 1 |

### Findings

1. **The fallback correction's own transient — the aircraft climbing well past the handover
   altitude before coming back down to it — is nowhere disclosed as expected behaviour, and the
   plan's own evidence is that this fallback is the likely common case, not a rare one.** Lens:
   the non-obvious case / would the pilot notice and use this.
   - Assumption: the two-phase design (Amended §2) is presented as *the fix* for "one continuous
     hold straight to the handover altitude would let it keep climbing the whole time" — read as if
     phase 1 removes the climb rather than bounding it.
   - In the sim, per the rehearsal probe's own numbers (quoted in the plan): phase 1's stopping
     rule is "hold toward the aircraft's *current* MSL, re-read live every tick" — a moving
     goalpost that only stops decreasing once it meets wherever the aircraft itself now is. The
     probe's T2 run shows exactly this: holding DOWN from a 1662 m target while actual climbed
     920 → 1050 m, releasing when the two met near 1058/1050 — **138 m above the 920 m handover
     value**, not at it. Phase 2 then has to come back down from there. The mechanism bounds the
     climb (it would be worse under a single fixed-target hold, which the plan's own prose argues),
     but it does not eliminate it, and the measured number is not small.
   - Whether this is the common case, not an edge case: the quick path (no transient at all, an
     instant reference-adopt) is only tried below 700 m AGL, and even then only succeeds if the
     *target's* AGL-equivalent is also under 700 m. The plan's own text states the wild target
     measured so far is "+740 m above handover twice, which is above 700 m AGL at any height" —
     meaning the two measured instances of the actual ED bug this stage exists to fix would *both*
     have refused the quick path and fallen to the two-phase hold with its climb. The transient is
     not a corner case this design mostly avoids; it is what happens on the bug it is built around.
   - The pilot would see: the aircraft he just parked climbs a hundred-plus metres above where he
     left it — in the opposite direction from the ED sink the fix exists to stop — before settling
     back down. The task brief's own worry ("climbing or diving harder than the bug itself would")
     describes exactly this: ED's bug sinks the aircraft; the fix's own fallback path visibly
     climbs it, by a comparable or larger margin, as a side effect of curing the sink.
   - Grounded in: the plan's own Amended §2 text and the rehearsal-probe numbers it quotes; the
     task brief's explicit instruction to check for exactly this.
   - Mitigated, not erased, by: the pilot designed this exact two-phase workaround himself,
     verbatim, having presumably watched the climb happen during his own manual testing that same
     day — this is not an invented mechanism the pilot has never seen. What is missing is not the
     mechanism but its disclosure as a *known, accepted* transient on the record this plan leaves
     for Flight P1 and beyond, in the style this plan already uses elsewhere (P0's "known
     limitation to state on the test card," P5's terrain-avoidance gap, the "AI always starts on
     radar" assumption flagged in Risks rather than silently carried).
   - Suggests: one line in "Risks & Unknowns (Stage P1 revision)" naming the measured transient
     (≈130–140 m climb-then-descend on the fallback path) as expected, not a defect, and one line
     on the revised "Flight P1" test card telling the pilot what to expect so a repeat of this
     climb is read as confirmation, not a regression report. See **Q1**.

2. **Flight P1's test card does not ask the pilot to distinguish which correction path actually
   ran.** Lens: the non-obvious case (minor, not blocking).
   - The card says to watch `apw_alt_text`/`apw_last_press` and "note how long convergence
     actually takes," but two different mechanisms can produce that convergence — the quick
     double-pulse (no transient) and the two-phase hold (the climb in Finding 1) — and the card
     does not ask which one fired. Without that, a flight where the quick path happens to succeed
     (AGL low enough and the wild-target bug happens not to recur that sortie) would look identical
     on the card to one where it didn't, and the fallback's own behaviour would go unverified by
     omission rather than by a reported pass.
   - Suggests: add the reference-toggle sequence (`apw_alt_ref` before/after) to what the card asks
     the pilot to watch, so a flight log shows which path ran.

### Questions for the user

- **Q1** — The fallback correction (used whenever the quick path is refused — which, per the
  measured wild-target bug, is both times it has been seen so far) makes the aircraft climb to
  roughly where the correction happens to catch up with the runaway target — about 130–140 m above
  the handover altitude in the measured case — before the second phase brings it back down. Is a
  transient of that size acceptable as the normal cost of fixing the sink, or does it need a
  tighter bound (e.g. cap how far phase 1 is allowed to let the aircraft climb before switching to
  a more aggressive correction), given it is the common path, not a rare fallback?

## Plan check — 2026-11-16 (Stage P2 ready to build)

**Verdict:** CONCERNS

Checked `plans/flight-control/plan.md`'s "Revised 2026-11-16 — Stage P2 ready to build" (the goal
channel, the rotation rule, the 700 m radar cap, the takeover-coexistence rule, the readback table,
and sub-stages P2a/P2b) against the goal check above (E-P3, E-P4) and the pilot's own vocabulary
table ("Amended 2026-11-15"), which this stage is scoped to deliver without reopening. The earlier
plan checks' own findings (vocabulary not routed to `audio-adapter`, U3/E-P5, the takeover
transient) are all fixed in this revision — confirmed by rereading, not re-litigated here.

| expectation | stage | status |
|---|---|---|
| E-P3 (spoken goals happen, approximately and honestly; several at once converge) | P2a | met |
| E-P4 (latest wins, no narration of mode hops/presses/partial progress) | P2a | met |
| FLT/HVR vocabulary rows (`level_flight` through `hold_altitude`) → token, goal, readback | P2a | met — traced row by row, see below |
| Readback names the step/reference actually set, not the one requested | P2a | met — 700 m radar-cap rule, speed-step rounding, altitude-step/hold wording all name the achieved value |
| A goal spoken during an in-progress takeover correction waits, doesn't fight it, and the pilot hears it was heard | P2a | met — `takeover_stage is not None` blocks promotion; readback still fires on acceptance |
| "Radar" above the 700 m cap gives an honest answer | P2a | met, provisional — Stage P0-rad (the probe that confirms the refusal-then-fallback mechanism against a live above-cap radar attempt) is explicitly unflown; disclosed in Risks, not hidden |
| Several goals at once converge without one starving another (`AI_PILOT_GOAL_SLICE_S` rotation) | P2a | met, open as **U4** — the ~17% dead-time cost is disclosed and the user is asked to confirm the tradeoff, not silently built |
| HVRT vocabulary (`left`/`right`/`forward`/`back`, `hold`, `up`/`down`) → token, goal, readback | P2b | met for the fields themselves |
| **HVRT is reachable by voice at all** | P2b | **missing — see Finding 1** |
| `mode_blocked` is silent, retried forever, never spoken | P2a | **CONCERNS — see Finding 2** |
| Nothing surprises the pilot or fights him | P2a/P2b | CONCERNS — both findings below are instances of this check |

### Findings

1. **Nothing in Stage P2 ever presses the wheel into HVRT, so the whole HVRT translate vocabulary
   is unreachable by voice alone — a player in HVR who says "left" gets silence, not a translate.**
   Lens: the non-obvious case / whose job / would the pilot notice and use this.
   - Assumption: the vocabulary table's HVRT rows ("left/right/forward/back", "Hold", "up/down")
     read as complete once each has a token, a mode gate, and a readback — this stage's own
     traceability treats them as closed.
   - In the sim: the vocabulary-collision note is explicit — `CrewConsole.handle_command` routes
     `hvrt_translate`/`hvrt_step`/`hvrt_hold` to the AI-wheel handler **only when `ai_mode ==
     "HVRT"`**, and "treat them as unmatched (fall through, same as any other out-of-context
     token) otherwise." The mode-cycle orders say HVRT sits one short-left press past HVR
     (`HVR > HVRT > CBTM > HVR`), and the only mode-cycle logic this plan describes is scoped to
     "a goal (one of heading/altitude/speed)" (Stage P2's Lua bullet) — there is no rule anywhere
     that presses short-left to enter HVRT when a bare direction word arrives in HVR. Because the
     command is dropped at dispatch before it ever reaches `ai_pilot_wheel.py`, `decide_ai_pilot_
     wheel` never even sees an attempt to set `hvrt_direction` while out of HVRT — there is nothing
     for its own "when" logic to act on.
   - The pilot would see: he says "Hover" (stops the aircraft, FLT→HVR fires automatically), then
     says "left" to nudge sideways — and nothing happens, with no readback, no "say again," no
     feedback of any kind. The only way into HVRT is pressing the physical wheel himself, which is
     exactly the thing U3 says Petrovich should make unnecessary (*"the goal is to use the wheel
     command via Petrobrain, not player directly"*).
   - Grounded in: the plan's own vocabulary-collision-check text (line ~132-134) and the Flight
     P2b card itself, which says "from hover, **cycle into HVRT**, say 'left'..." without ever
     saying how — the only place in the whole plan that assumes a manual step it never specifies.
     Also grounded in the plan's **own precedent for this exact problem**: `cbtm_align`/
     `cbtm_break`/`cbtm_break_away` are every bit as mode-exclusive as HVRT translate, and each one
     is explicitly built "cycle-then-press" — Stage P3's Lua bullet mode-cycles to CBTM before
     pressing, and the vocabulary table says `cbtm_break` "cycles to CBTM first if needed, same
     cycle-then-press shape as `cbtm_align`." HVRT translate is the one mode-exclusive action in
     this vocabulary that does not get that treatment, with no stated reason for the difference.
   - Suggests: either (a) give `hvrt_translate`/`hvrt_step` the same cycle-then-press shape every
     other mode-exclusive action already has — a bare direction word spoken while in HVR (not yet
     HVRT) triggers the short-left cycle first, then opens the press once the mode reads HVRT — or
     (b) if manual wheel entry into HVRT is the accepted design for this build, say so explicitly in
     the plan and the test card (the project's own practice elsewhere: P0's command-wheel cost, P5's
     terrain-avoidance gap), and confirm Petrovich's own mode-cycle-back (U3) won't immediately
     reassert HVR/FLT the moment the player enters HVRT with no goal of his own pending. See **Q1**.

2. **`mode_blocked`'s "no spoken line, ever" posture is derived from A4, but A4 was never about this
   failure, and the plan's own U1 recommends the opposite call for the sibling case.** Lens: crew
   sense / the non-obvious case.
   - Assumption: the Readbacks section reads `mode_blocked` as the same case A4/Decision 14
     already settled ("no 'unable' for a goal not quite reached... fly within parameters"), so no
     new decision is needed and Petrovich "keeps retrying silently next tick," forever, with
     nothing said "unless the player asks or it never resolves (out of this stage's scope)."
   - In the sim: A4 was about a goal the aircraft **cannot physically reach** — a speed limited by
     weight, a collective at its ceiling, a terrain floor holding him above a spoken height. That
     is a different failure from `mode_blocked`, which is Petrovich's **own control mechanism**
     failing to drive the wheel into the mode a goal needs at all (the short-left cycle exhausting
     `MODE_CYCLE_MAX_ATTEMPTS` without reaching FLT/HVR) — nothing about the aircraft's physics is
     stopping it; the wheel interaction is. The plan's own **U1**, written in this same document for
     the sibling case (`cbtm_align`/`cbtm_align_for_launch`), treats exactly this signal
     differently: *"a spoken 'unable, not ready' only if the mode-cycle to CBTM itself fails to
     resolve within the attempt bound... otherwise silent."* U1 is still open, but it already
     establishes that mode-cycle exhaustion is a case the user might want spoken — the Readbacks
     section forecloses that for heading/altitude/speed without asking the same question.
   - The pilot would see: he says "heading 090" at a moment the wheel's mode-cycle genuinely cannot
     resolve (the CBTM→FLT/HVR auto-transition is itself flagged elsewhere as "probably though not
     sure") — readback fires once, and then nothing, forever, with no way to tell "still working on
     it" apart from "stuck and will never happen." E-P3 promises goals happen "approximately and
     honestly"; perpetual silent failure of the mechanism itself is not dishonest in the way a wrong
     number would be, but it is not "honest" either — the pilot has no signal that this goal is the
     one case where honesty would mean saying something.
   - Grounded in: Decision 14/A4's own wording (goal not *reached*, not goal never *attempted*), and
     U1's still-open recommendation for the identical `mode_blocked` signal on a sibling action.
   - Suggests: this is a real question, not a foreclosed one — ask the user whether `mode_blocked`
     exhaustion for a continuous heading/altitude/speed goal should eventually get the same "unable,
     not ready"-style call U1 already contemplates for align, rather than treating A4 as having
     already answered a case it was not written for. See **Q2**.

### Questions for the user

- **Q1** — Stage P2's HVRT vocabulary ("left"/"right"/"forward"/"back", "up"/"down") only fires once
  the wheel is already in HVRT, and nothing in this plan ever presses the wheel into HVRT by voice —
  every other mode-exclusive command (`cbtm_align`, `cbtm_break`) cycles there first, but HVRT
  translate does not. Should a bare direction word spoken while in HVR trigger the same
  cycle-then-press sequence (reaching HVRT automatically, matching the CBTM commands), or is
  pressing the wheel into HVRT by hand the accepted way in for this build?
- **Q2** — `mode_blocked` (the wheel's short-left cycle exhausting its attempt bound without
  reaching the mode a goal needs) is planned as permanently silent for heading/altitude/speed
  goals, reusing A4's "no callout for a goal not reached" — but A4 was about a physical limit, not
  the wheel mechanism failing to engage at all, and the plan's own U1 recommends a spoken "unable,
  not ready" for the identical signal on `cbtm_align`. Should a heading/altitude/speed goal that
  never gets out of `mode_blocked` eventually say so too, or is silent-forever retry the intended
  behaviour here?

## Plan check — 2026-11-18 (mode 1, unparked, raw axes re-cut)

**Verdict:** CONCERNS

Checked `plans/flight-control/plan.md`'s "Revised 2026-11-18 — mode 1 (unparked, raw axes)
re-cut" (M0–M5) against the goal check — 2026-10-31 above, which is the mode-1 goal check and
whose E1–E10 are not re-derived. The mode-2 goal check and its E-P expectations are a separate
contract and are not in scope here. Also checked: that every open assumption and every numbered
Finding (F1–F8)/Question (Q1–Q8) from the 2026-10-31 goal check was actually closed, not merely
superseded by a later section's silence — all eight were traced to a specific user answer
(`explore-notes.md`, "Goal-check answers … 2026-10-31", A1–A9) or to a later direction quoted in
the re-cut's own "What changed" table. None was found open and unaddressed.

Confirmed against the live tree (not just the plan's own claims): `body-layer/src/belief/
optic_policy.py` has no `flying`/`has_controls` input today (grep — only a turbulence-based
"flying smoothly enough for binoculars" check at L1257), and `body-layer/config/rules/flight.lua`
on this tip still carries the pre-refactor `r.ok` shape and the two silent `"always"`-category
handover rules, both consistent with the re-cut's own account of what exists before M1 lands.

| expectation | stage | status |
|---|---|---|
| E1 (handover confirmed only once Lua is actually flying; "unable, \<reason\>" on refusal) | M1, Decision 22 | met |
| E2 (nothing jumps; turn/climb/IAS continuation at takeover) | M1 (bit-exact capture) + M2 (takeover modes, stopping height) | met |
| E3 (stick/collective/pedals do nothing while he flies) | M0-D (go/no-go, blocker not workaround), M0-B/M0-C, M1 | met — correctly gated, not assumed |
| E4 (short readback, smooth, no overshoot) | Decision 21 readbacks + M2 shapers (ζ≥1) | met — "no overshoot" is A9-revised to "converges into the band, no ringing"; that revision is the user's own (A9), not this plan's drift |
| E5 (stop a turn by voice) | M2 `level_off`/continuous `turn` (Decision 21) | met |
| E6 ("I have controls" at once, never "confirm?") | M1, `HANDOVER_TOKENS` (Decision 13), row 6 | met |
| E7 (he says when he can't/won't; silent on a goal merely not reached) | M1 refusals + M3 terrain call; Decision 14/A4 for the "not reached" half | met |
| E8 (never into the ground from current height) | M3 (unchanged old Stage 3) | met |
| E9 (no optics while he flies) | **deferred → U6**, which names M1 (if accepted) or `[[BL-B123]]` (if not) | deferred, but see Finding 1 |
| E10 (no model latency) | M1 (rule path only; Decision 19) | met |
| Open assumption: turn-vs-drift threshold at takeover | Decision 1 REVISED / A2 (5° bank) | settled |
| Open assumption: altitude reference at takeover | A6 / Decision 1, 9 REVISED (AGL default) | settled |
| Open assumption: AGL meaning over forest/buildings | A6 (radar "sees trees") + M0-A's optional forest/town pass | settled, confirmatory measurement only |
| Open assumption: the stop word | A1 (`level_off`/"straight"), Decision 12 | settled |
| Open assumption: seat jump while flying | A8, Decision 17, Co-moving row 10, M0-I | settled |

### Findings

1. **E9 is tracked as `deferred → U6`, but U6's "alternative" branch ships mode 1 in direct
   contradiction of an expectation the original 2026-10-31 goal check already recorded as
   settled, and of a standing user rule the plan itself quotes.** Lens: purpose, whose job.
   - Assumption: presenting U6 as a symmetric architectural choice ("build the one shared
     mechanism now" vs. "leave it wholly to `[[BL-B123]]`") is a fair framing of an open decision,
     with a recommendation attached.
   - In the sim: the 2026-10-31 goal check lists E9 as *"Settled: point 2"* — mode 1's "no optics
     while flying" was never an open question, it was already decided at the explore stage
     (`body-layer/ROADMAP/BL-16.md`, settled point 2: *"Petrovich's optics stop while he flies and
     come back when he hands over"*). `todo/todo/X-T29.md` (priority 3, the same list that puts
     mode 1 at priority 2 just above it) restates it as a standing rule in the user's own words:
     *"When Petrovich is flying (AI overlay or no-AI overlay) no optic can be used."* Grepping the
     live tree confirms `optic_policy.py` has no such input today for *either* mode. If U6
     resolves to its stated alternative, mode 1 — a priority-2 item that can ship and auto-merge
     on its own DoD pass — goes live with optics available while Petrovich flies, and stays that
     way until `[[BL-B123]]` (priority 3, not yet started) eventually closes it.
   - The pilot would see: he hands over, uses the 9K113 or binoculars while Petrovich flies, and
     nothing stops him — exactly the behaviour the goal check and the user's own 2026-11-17 rule
     already ruled out, reopened by how this one plan presents an already-settled requirement as a
     fresh 50/50 choice.
   - Grounded in: the 2026-10-31 goal check's E9 row, `BL-16.md` settled point 2, `X-T29`
     priority 3's verbatim quote, and the live-tree grep above.
   - Suggests: U6 is answered "yes" (as the plan itself recommends) before M1 is considered
     complete, not left to default silently — this is not a tidy generalisation opportunity, it is
     closing a gap against an already-decided requirement. If the answer is genuinely "no" for
     now, the plan and the mode-1 test card should say in those terms that mode 1 ships with a
     known, user-accepted regression against E9/BL-16.md point 2 until `[[BL-B123]]` lands, rather
     than letting U6's silence read as "deferred, no harm."

2. **No second finding changes the verdict** — everything else traced cleanly. U5, U7 and U8 are
   genuine open decisions (park-while-flying handoff, build/merge order relative to the probe, and
   the confidence floor for *taking* controls) and are correctly surfaced to the user rather than
   assumed; they do not bear on any E-expectation the way U6 does, so they are not findings here,
   only items for the Questions list below (restated from the plan, not new).

### Questions for the user

- **Q1 (from Finding 1)** — Should "no optics while Petrovich flies" (U6) ship as part of M1,
  covering both modes, as the plan recommends? If not now, should the mode-1 test card and
  `BL-16.md` record that mode 1 ships with optics still usable while he flies, as a known,
  accepted gap against the already-settled E9/point 2, pending `[[BL-B123]]`?
- U5 (restated from the plan) — does a park while mode 1 is flying hand over to mode 2 silently
  with mode-1 goals dropped, as recommended, or should heading/altitude/speed carry across?
- U7 (restated from the plan) — should M1+M2 merge be held until M0-D/M0-B/M0-C answer, even
  though DoD-pass auto-merge would otherwise land them the same day they pass?
- U8 (restated from the plan) — is "never confirm" the right floor for *taking* controls too (as
  it already is for giving them back), or should "you have controls" keep a confidence floor
  below which he asks?

## Plan check — 2026-11-18, amendment (U5–U10, seat rule)

**Verdict:** ALIGNED

Checked `plans/flight-control/plan.md`'s "Amended 2026-11-18 — the user's answers to U5–U8, and
the seat rule" (Decisions 24 and 25), the U9/U10 entries under "Decisions Requiring User Input
(mode 1 re-cut)", and the "What changed" table's seat-rule correction (M0-J4 removed), against:
the 2026-10-31 goal check's E1–E10 above (not re-derived); `explore-notes.md`'s page 1 ("maintain
current state", "stops writing axis values... can use the optics again" on "I have controls",
"must be ignored" for the physical stick) and settled point 2 ("Handover is spoken only");
`body-layer/ROADMAP/BL-16.md`'s "Mode 1" section, which restates the same answers and explicitly
records the prior CONCERNS (U6) as closed; and the live tree, confirming no dangling `M0-J4`
reference survives the removal (`grep -n M0-J4 plans/flight-control/plan.md` returns one hit, the
prose explaining the removal itself, and the M0 table at line 2894 runs J1–J3 only).

This is a re-check, not a fresh pass: the previous entry's single CONCERNS item (U6, which framed
an already-settled "no optics while flying" as a fresh 50/50 choice) is closed — **U6 answered
"yes"**, built in M1 for both modes, confirmed by this amendment's own text and by `BL-16.md`
line 301 ("Plan check `alignment.md` 2026-11-18: CONCERNS about U6 only, closed by the answer
below"). The rest of the previous pass's table (E1–E8, E10, the five open assumptions) is
unaffected by this amendment and stands.

| expectation / item | stage | status |
|---|---|---|
| E9 (no optics while flying) | M1, row 17 (`flying == CrewState.has_controls`) | **met** — U6 answered yes; no longer deferred |
| E2/E3 maintained across park and unpark (new ground, from U5) | Decision 24 (`armed`, same-frame unpark take, M0-J) | met |
| E6 ("I have controls" acts at once, never "confirm?") — for mode 1 itself | M1, row 6, Decision 13 | met, unaffected |
| "Handover is spoken only" (settled point 2) vs. the silent park/unpark mode switches | Decision 24's framing: park/unpark change *mode*, never *who holds the controls* | met — the silent events move between Petrovich's two mechanisms, never between Petrovich and the player; the one exception is forced and named below |
| **U5 — unpark no longer hands the stick to the player** | Decision 24; disclosed in Risks ("The test card says it in those words") and `BL-16.md` | met — Flight M-A step 9 ("unpark: he keeps flying in mode 1; then 'I have controls'") is the disclosure in the test card's own words, not just the plan's prose |
| **U9 — "I have controls" in the overlay** | row 9c; "Unable, AI overlay.", nothing remembered | met — matches the user's verbatim answer exactly; Flight M-A step 11 exercises it |
| **U10 — the arm lease** | `ARM_LEASE_S = 3.0`, re-sent every poll, Decision 2 unchanged for an *active* mode 1 | met — closes the park→unpark escape route U5 would otherwise remove, without adding a watchdog nobody asked for |
| **Forced "You have controls!" on an unpark outside the envelope** | row 9a; state diagram `OVL --> PLAYER: unpark when mode 1 cannot take` | met, with the tension named, not hidden — see below |
| Seat rule (never gated on seat) | Decision 25 | met |
| Seat-swap park-edge correction (M0-J4 removed) | "What changed" table, seat-rule bullet | met — no dangling reference, M0 table has only J1–J3 |

### Findings

None that change the verdict. Two items are worth recording as confirmed-consistent rather than
silent, since the task brief asked for them by name:

1. **The forced handover is the one place "player command only" does not hold, and the plan says
   so itself, in those words, twice.** Lens: whose job / the non-obvious case.
   - The Risks section states it directly: *"(U5) Forced handovers... This is the only place
     'player command only' is not met, and it is physical, not a choice."* The reason is
     structural, not a design shortcut: mode 1 is forward-flight only (Decision 3) and explicitly
     excludes hover for this first build, so an unpark in a hover or below `MIN_IAS_KMH` leaves
     nobody to fly the aircraft if Petrovich does not take it. The existing urgent "You have
     controls!" line (already used for the Lua self-release, row 7) is reused rather than a new
     string invented for the case.
   - This is not a gap the plan introduced and failed to notice — it is the plan naming its own
     exception against the rule it just adopted, with the reason, in the same section a reader
     would check. Nothing to ask the user; recorded here because the task named it as a thing to
     verify, not because it was found wanting.

2. **U9's "unable, don't remember" answer is a genuine, disclosed narrowing of the original E6,
   not a silent one.** Lens: purpose.
   - E6 (2026-10-31) reads "'I have controls' gives the aircraft back at once, including in an
     emergency," written before mode 2 (the AI overlay) existed as a destination. U9 answers the
     overlay-specific case the original E6 could not have anticipated: while parked, the player's
     stick is physically dead regardless of Petrobrain (DCS itself ignores `LoSetCommand` while
     parked, per probe v2), so "at once" cannot mean "flying resumes this instant" there — it can
     only mean "answered this instant," which is what "Unable, AI overlay." does. The player's
     actual escape (unpark, then "I have controls") is two deliberate steps, both disclosed in the
     test card (Flight M-A step 11) and in `BL-16.md`. This is the user's own explicit answer
     against two offered options, not an assumption the plan filled in, so it is not re-litigated
     here — recorded so a later reader does not mistake the narrowing for an oversight.

### Questions for the user

None. U5–U10 and the seat rule are all answered on the record; nothing in this amendment opens a
new question the main loop would need to carry to the user.
