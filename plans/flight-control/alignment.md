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
