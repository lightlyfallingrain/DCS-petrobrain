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
