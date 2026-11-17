# BL-17 — Spoken commands as Lua rules: behaviour alignment

## Goal check — 2026-11-17

**Verdict:** CONCERNS. Two assumptions, each filled the obvious way, break a named expectation:
Finding 1 breaks **E4** and Finding 2 breaks **E8**. Everything else is aligned, and the open
questions are listed separately.

Inputs: `body-layer/ROADMAP/BL-17.md`, `plans/behaviour-trees/explore-notes.md` ("2026-11-17:
speech commands as Lua rules", rounds 1–3), `body-layer/ROADMAP/BL-B95.md`. **Settled after those
were written, per the coordinator (user's words):** magnetic vs true is *"use existing convention
in code"*, and there is no ×5 checksum on any direction slot (*"allow any three digit value"*);
the checksum on today's "scan bearing" goes with the rename. Neither is re-opened here.

### Why

The pilot wants to add or change what Petrovich does on a spoken command (its wording, its
readback, which actions it chains) by editing a rule file instead of waiting for a code change.
Asking "why" a second time gives the purpose: the command vocabulary is still being found out in
flight, and each sortie produces a "say it like this" or a "he should answer that". Today every one
of those costs a full build sequence. So the purpose is **fast iteration on the crew dialogue, with
no loss of the reliability the fixed-wording path has in the cockpit.** *"to get the deterministic
(=fast) path, I use fixed wording."*

### Player expectations

- **E1:** A command the pilot uses today is recognised just as reliably once it is ported. It does
  the same thing, at the same speed, and its readback tells him at least as much. From the seat he
  cannot tell which commands are rules yet. The one deliberate exception is the bearing→heading
  rename.
- **E2:** To change a rule's wording, readback or chained actions, the pilot edits a rule file and
  restarts (Q4 says which restart). No code change. He hears the difference on the next attempt.
- **E3:** A direction is never guessed. `heading` + three digits is a compass direction. `bearing`
  + three digits is relative, with 0 on the nose. `<1–12> o'clock` is a clock position. If the
  type word is missing, or the utterance fits two rules, the answer is "say again" and nothing is
  done. (*"numeric direction value must specify what type it is"*)
- **E4:** A phrase the pilot already says does one of two things: what it did before, or an audible
  refusal. It never does something different without telling him. Where the user chose to change a
  meaning (the rename), the readback must make plain which meaning was understood.
- **E5:** If a rule fails to load, Petrovich says so once on the intercom, at startup or mission
  start, and says what is missing. The pilot should not first find out through a "say again" when
  he needs the command. The other rules keep working. This follows the existing precedent for a bad
  effector sequence file: that file is disabled on its own, and one spoken "System error, bad
  sequence file…" line is held until the intercom gate opens.
- **E6:** Adding or changing a rule never quietly changes what another command does, and never
  turns ordinary speech to Petrovich into a command. The precedent is "attack" vs "tanks"
  (`vocabulary.py:645`): "the tanks are on the ridge" has to keep falling through to the brain.
- **E7:** If a command cannot be carried out, Petrovich answers with "unable <because>" or "no
  contact". He never stays silent and never leaves it half-done, such as a target selected but no
  attack run. (*"report no contact"*; project memory: "say again" means not understood, "unable"
  means the action is unavailable.)
- **E8:** A mark is a fixed point on the ground. It sits at terrain elevation, keeps its lat/long
  and stays put as the aircraft moves. Its readback says its number, which the pilot will need
  later. Numbers count 1, 2, 3 within a mission and are never reused or renumbered. A wrong mark is
  ignored, not deleted. (*"point to come back to, to use as reference for scanning or flight
  waypoint"*, *"Only ever add marks"*)
- **E9:** "Mark heading 315, 2 km" and "mark 1 o'clock, 3 km" are measured along the ground from
  where the aircraft was **when the pilot said it**. For o'clock, the reference is the nose at that
  moment.
- **E10:** An action has the same effect whether the pilot uses the fixed wording (a rule) or says
  it loosely (the brain, `[[BR-2]]`).

### Open assumptions

- **Mark elevation.** Serves the why: the terrain elevation at the offset point. Would not: the
  ownship altitude, which is what Example 2's `currentPosition().translate()` gives if read
  literally. That is Finding 2.
- **Reference moment for an offset mark.** Serves the why: ownship position and nose at the moment
  the pilot spoke. The capture process already mints a `correlation_id` at PTT release. Would not:
  "current position" whenever the handler happens to run. The two are the same in straight flight
  and diverge in a turn (vignette below).
- **Which commands accept relative `bearing`, and when.** Serves: none of the ported scan/report
  commands until the pilot has said how a habitual "scan bearing 320" should be treated. Would not:
  accepting it everywhere as soon as the slot type exists. That is Finding 1.
- **If a ported rule fails to load.** Serves: the command is missing and Petrovich says so (E5).
  Would not: quietly falling back to the old Python handler, which hides the failure and keeps two
  definitions of one command; or a "say again" in flight with no warning beforehand.
- **Which rule wins a collision.** Serves: found and announced when rules load, and resolved by a
  rule the pilot knows (Q6). Would not: whichever file happened to load first.
- **Reference for "mark heading NNN".** Marks are a new use of heading with no existing convention
  in code, so the user's "existing convention" decision does not reach them. Serves: whatever
  instrument the pilot is reading when he says the number (Q3).
- **First port and test flight.** Serves: commands flown from the seat the player normally flies
  in, with an effect the pilot can see, and with one rule edit between two runs. Would not: a port
  that proves only the plumbing (Finding 3).

### Findings

1. **After the rename, "scan bearing 320" still matches a valid command, and it now points
   somewhere else.** Lens: crew sense / the non-obvious case.
   - *Assumption:* once relative bearing is "supported", the scan and report commands take a
     `heading | bearing | oclock` direction, as in the round-2 sketch `<dir:heading|oclock>` with
     `bearing` added.
   - *In the sim:* today, "scan bearing three two zero" means compass 320, which scans the NW
     sector. After the change it means 320 relative, 40° left of the nose, about 10–11 o'clock.
     The two meanings coincide only when flying heading 360:

     | ownship heading | "scan bearing 320" today | after the rename | apart |
     |---|---|---|---|
     | 000 | NW (320 compass) | 320 compass | 0° |
     | 090 | NW | 050 compass (NE) | 90° |
     | 180 | NW | 140 compass (SE) | 180° |

   - *The pilot would hear and see:* "Bearing three two zero", the same words he said, so it sounds
     like a correct readback. Meanwhile Petrovich looks the wrong way, and whatever is in the NW
     goes uncalled.
   - *Grounded in:* the user, 2026-09-19: *"'<verb> bearing 320' is entirely possible"*. The
     2026-09-23 card had the user say **"scan bearing three two zero"**
     (`docs/acceptance/2026-09-23-eyes-and-voice-sortie.md:80`). The user, 2026-11-17, on relative
     bearing: *"Rarely used, but let's support it."*
   - *Suggests:* the rename itself is the user's decision and is not in question. What needs
     settling is how the old phrase is handled. Either no ported command takes `bearing` until
     there is a reason to (it is "rarely used"), or every bearing readback names the direction
     in a way the pilot cannot mistake, such as the clock position. The user chooses (Q1).

2. **An offset mark placed at ownship height cannot be used as a scan reference.** Lens: world
   truth (the calibration table's "ownship elevation" case).
   - *Assumption:* the mark is `currentPosition()` translated horizontally, keeping its altitude.
     That is the user's own Example 2, read literally.
   - *In the sim:* at 500 m AGL, a mark 2 km out at ownship height sits about 14° above the ground
     point the pilot meant. If Petrovich scanned "mark 2", he would sweep the sky above it. A
     waypoint does not care about the height. A scan reference does, and the user named both uses.
   - *Grounded in:* the calibration case (*"Ground units are on the ground, at the terrain
     elevation where they stand"*) and the user's *"reference for scanning"*.
   - *Suggests:* an offset mark is the terrain point at that ground distance and direction. "Mark
     here" is the point under the aircraft. "Mark target" is already the contact's believed
     position.

3. **First port: "scan heading NNN", plus "mark here".** Lens: purpose. This is a recommendation,
   not a concern.
   - Port `scan_bearing_deg` as **"scan heading NNN"**. That one port exercises the rename, a
     three-digit typed heading slot (now with no checksum), Petrovich's core job of looking, an
     effect the pilot can check (where the sight sweeps, what gets called), and a readback the rule
     writes itself. It is flown from the pilot seat and depends on nothing new.
   - Port **"mark here"** as well. It has no slot, and its readback carries a counter. This covers
     the numbered mark (E8) and checks that the rule speaks a value the action returns.
   - The user's own Example 1, "turn left 20", is the most visible command of all, but it needs the
     player in the operator seat with Petrovich flying. Stage P2, which it runs on, was merged with
     its 2026-11-17 card not yet reported. If it misbehaved, it would be impossible to say whether
     the rule or P2 was at fault. It makes a good second-batch port once P2's results are in.
   - **The flight should include one rule edit between two attempts**, a changed readback being
     enough. Without that, the flight shows the engine works but says nothing about the why (E2).
   - Cross-checked against *"take one or two rules and port them"*: consistent. The choice is the
     user's (Q5).

4. **Marks are already numbered. What is missing is anything that uses the number.** Lens:
   purpose.
   - *In code now:* `MissionMemory.append` numbers marks from 1 within each mission, the mission
     reset restarts the count, `mark here` already reads back "mark N set", and the brain resolves
     `MARK_N` (`mission_memory/store.py:179`, `body.py`'s `_mark_here_fn`). The explore note that
     says *"`MarkPayload.index` … always written as 0; a spoken mark number would be new"* is
     wrong: 0 is only the placeholder the caller passes in.
   - *The pilot would notice:* he hears "mark three", but no command yet lets him scan or fly to
     mark three, so the number is a promise for now. He also has to remember what mark three was;
     a human front-seater would write it on the kneeboard (Q2).
   - *Suggests:* porting must keep the existing numbering exactly as it is (E1, E8). The command
     that first uses a mark number should be named as a backlog entry, so the promise is visible.

5. **Load failures and collisions follow the precedent the project already has.** Lens: crew
   sense. This is aligned, recorded so the plan inherits it.
   - A bad rule file behaves like a bad sequence file: it is disabled on its own and announced once
     on the intercom (E5). A static collision check at load time catches overlapping fixed patterns.
     It does not catch fuzzy near-misses like "tanks"/"attack", which only show up when a real
     transcript scores close to two rules. The pilot expects the same outcome in both cases: if it
     is unclear which command he meant, he gets "say again", and never the wrong action (E3, E6).
     The only collision he should ever meet mid-mission is that runtime ambiguity, because rules
     load at startup.

6. **Two "heading NNN" commands will mean slightly different directions, by the user's choice.**
   Lens: world truth. Recorded, not raised again.
   - Under "existing convention in code", compass scans stay centred on **true** north
     (`docs/acceptance/2026-10-25-bl-b89-sector-scan-flight.md:217`), and "heading NNN" turns use
     *"whatever the HSI uses"* (`plans/flight-control/plan.md` Decision 8; the getter is S0-6's
     answer). After the rename both are spoken "heading 320". If the HSI is magnetic (unverified
     here), the two differ by the local variation. A 45° scan sector hides that difference. A
     marked point does not, which is why Q3 asks about marks alone.

**Vignette, off the happy path.** Ownship is in a hard left turn at about 20°/s, 300 m AGL. The
pilot says "mark two o'clock, three kilometres" at the moment a vehicle column crosses that clock
position. Recognition and dispatch take a couple of seconds, by which time the nose has swung about
40°. If the mark is anchored to the nose when the handler runs, it lands about 2 km from the column.
If it is anchored to the PTT-release moment, it lands on the column. In straight flight the two are
indistinguishable, so this shows up only in the manoeuvring the Mi-24 envelope is made of (E9).

**Not a concern:** the user's own *"report no contact"* already settles the "engage a unit he has
not seen" case. Target choice staying in code keeps the unit-of-action lens satisfied: a rule
receives one unit or `nil`, never a group centroid.

### Questions for the user

- **Q1:** After the rename, if you say "scan bearing three two zero" out of habit, should Petrovich
  refuse it ("say again" or "unable, say heading"), or treat it as relative and say where that is
  ("bearing three two zero, ten-thirty")? And which commands should take a relative bearing at all
  in the first stages?
- **Q2:** Should a mark appear somewhere you can look at later, such as the F10 map or the kneeboard,
  or is the spoken number enough?
- **Q3:** For "mark heading 315, 2 km", what are you reading the 315 off: the HSI, or the F10 map?
  Marks have no existing convention to inherit.
- **Q4:** When you edit a rule file, is restarting body-layer between attempts fine, or should a
  mission restart pick the change up?
- **Q5:** For the first port and test flight: "scan heading NNN" and "mark here" (recommended,
  flown from the pilot seat), or your Example 1, "turn left/right NN", which needs the operator seat
  and Stage P2's results first?
- **Q6:** If two rules claim the same phrasing when they load, what should happen? Both disabled
  with a spoken warning, or one of them winning by a rule you set?

## Plan check — 2026-11-17

**Verdict:** ALIGNED. Both goal-check concerns are resolved by explicit user decisions recorded in
`body-layer/ROADMAP/BL-17.md` and correctly carried into the plan: Finding 1 (rename ambiguity) by
D12's plain relative readback (U9), Finding 2 (mark elevation) by the plan's own Answers table.
Stages 0–3 are detailed and trace cleanly to E1–E7, E10. The marks expectations (E8, E9) and the
target-choice half of E7 are deferred to the later-stages table (Stage 7/8), which names and
mentions each. U17 (rename scope) and U18 (where rule files are edited), still open with the user,
are both non-behavioural — internal naming reach and a file-edit location, neither reaching the
cockpit — so either answer leaves this verdict unchanged.

| expectation | stage | status |
|---|---|---|
| E1 | 1a / 2 | met — D3 (a ported rule keeps its token's name, slot names and readback) plus Stage 2's pre-deletion differential test; later ports (the Stage 4–9 table) inherit the same obligation under D3 but are not yet detailed, per the plan's own stated scope |
| E2 | 1b, 2, 3 | met — D11 `--print-rules`, D2 re-push, mission-restart reload (U11); card step 3 cites E2 directly |
| E3 | 1a, D7, D8 | met — typed slots with a fixed digit count per type; a near-tie sets `ambiguous=True` and the existing "say again" disposition applies |
| E4 | D12, D3, D6 | met — the rename's readback ("Scanning bearing three two zero.") names which meaning was heard (U9); a Lua error at dispatch rolls back one-shot transitions so nothing half-happens silently |
| E5 | D6, Stage 1b/3 | met, narrowed by U13 — the spoken line is one fixed phrase ("Action file error."), not a per-cause description; "what is missing" lives only in the stderr banner. This is the user's own later choice (U13) overriding the goal check's "says what is missing" wording — see Finding 1 |
| E6 | D9 | met — rule×rule, rule×legacy, and a free-speech guard naming the "attack"/"tanks" case as a pinned test |
| E7 | D6 (met); Stage 7 (deferred → [[Stage 7]]) | met for load/dispatch failure (rollback, the `unable` catalogue); the target-choice "no contact" case defers to Stage 7, whose table row names it ("target choice as an action returning one unit or `nil` (U5)") |
| E8 | deferred → Stage 8 | Stage 8's table row names terrain elevation; U14 (numbered, append-only, spoken number only) is mapped there explicitly in the Decisions list |
| E9 | deferred → Stage 8 | the Answers-to-assumptions table names the PTT-release-pose mechanism for Stage 8; R7 flags the one open implementation risk, see Finding 2 |
| E10 | D5 | met — by construction: a rule id is the one dispatch path for both a spoken phrase and a brain-carried command, same as BR-2's E3 |

### Findings
1. **E5's wording is narrowed by U13, by the user's own later choice.** Lens: crew sense.
   - *Assumption:* the goal check's E5 ("Petrovich says... what is missing") reads as a spoken,
     per-cause explanation.
   - *In the sim:* the user's actual decision (`BL-17.md`, U13) is one fixed phrase — "Action file
     error." — with the cause only in the stderr log, not on the intercom. D6 follows U13.
   - *Suggests:* nothing to change. Per this task's own framing, `BL-17.md`'s decisions override
     the alignment file's wording where they differ, and the user made this choice knowingly
     ("One fixed phrase, not a per-cause description"). Recorded so a later reader does not mistake
     the gap between E5's prose and D6's behaviour for an oversight.

2. **R7's "may have to carry the timestamp" undersells how close it already is.** Lens: grounded
   in the code.
   - *In the code:* `audio-adapter/src/capture_loop.py` already mints `t_ptt_release_wall` at PTT
     release and threads it through `POST /transcribe` (`transcribe_client.py:54`,
     `server.py:357-412`) — but `server.py:387-400` uses it only for `_log_latency`. The
     `TranscriptEvent` actually pushed to the queue body-layer reads stamps `t_wall=time.time()`
     at match-completion (`server.py:395`), confirming R7's suspicion that today's `t_wall` is not
     release time.
   - *Suggests:* Stage 8 does not need a new timestamp mechanism for E9, only to thread the
     already-existing `t_ptt_release_wall` into `TranscriptEvent`/`transcript_queue` and
     body-layer's read of it. Worth one line in the Stage 8 plan when it is written; not a blocker
     now, and not a reason to revisit this verdict.

### Questions for the user
None beyond Q1–Q6 already on file above, and U17/U18, already open — neither changes this
verdict regardless of how they are answered (see Verdict).

## Goal check — next stages (matching foundation + flight-control port), 2026-11-17

**Verdict:** CONCERNS. Three assumptions, each filled the obvious way, break a named expectation:
Finding 1 breaks **E17**, Finding 2 breaks **E13**, Finding 3 breaks **E13/E16**. Everything else is
aligned. The open questions are listed separately.

Scope: (a) a matching foundation: fuzzy tolerance, number words, the two performance fixes, and a
speech-to-text hint that follows Petrovich's seat and state; (b) porting the flight-control
commands (plan Stage 4 row) plus "you have controls". Base `c309092b`. Inputs: `BL-17.md` (every
2026-11-17 section), this plan's D1–D12 and later-stages table, `BL-16.md`, `BL-B123.md`,
`plans/flight-control/alignment.md` (E-P1..E-P11), the 2026-09-19 whisper research notes, and the
memories on "say again" vs "unable" and on Petrovich working the opposite seat. E1–E10 above still
stand; numbering continues from them.

### Why

The key case is the player in the operator seat on the 9K113 while Petrovich flies (BL-16 A7:
*"this is a key reason"*). In that case the pilot's voice is the only way he steers the aircraft.
So the purpose is that **flight commands are as reliable to say as they are today, or more
reliable, once they move to rules**, and that the crew's answers stay honest: he either does it,
says why he can't, or asks for it again.

Asked "why" a second time, the foundation is what keeps E1 true. Exact-literal matching would make
every ported command harder to say (*"STT is imperfect, we'll need some fuzzy matching"*).
Narrowing the hint is there so recognition gets better as the vocabulary grows (*"STT reliability
and whisper speed might increase if we limit the excepted command set"*). Neither is a goal in its
own right. Both are measured by one thing: what the pilot hears back when he speaks.

### Player expectations

- **E11** — Every ported flight command still matches when the fixed words have a near-miss (a
  filler, a verb heard slightly wrong), at least as often as the legacy matcher manages today.
  "Turn left thirty", "turn left 30" and "turn left three zero" all turn 30° left.
- **E12** — Fuzziness forgives the *words*, never the *values*. A number, a direction (left/right),
  an altitude reference (radar/barometric) or a bare HVRT word is either heard exactly, after the
  number-word collapse, or the answer is "say again". "Thirteen" never becomes 30, and "right"
  never becomes "sight".
- **E13** — A command he understood but cannot carry out in his current seat or state gets
  "unable, <reason>". The reason names something the pilot can act on, such as "not flying". It is
  never a readback of a goal he will not fly, and never "say again" (user: *"As you recommended, I
  agree with that"*; memory `project-say-again-vs-unable`).
- **E14** — Questions about what he believes and what mission memory holds, and "describe", are
  answered in every seat and state (*"Regardless of state, Petrovich must answer…"*).
- **E15** — Once Petrovich starts or stops flying, the next transmission is transcribed with the
  hint for the new state. A flight command spoken a second or two after the handover is recognised
  as well as one spoken a minute later. The same holds after a seat change.
- **E16** — Narrowing never makes any command harder to recognise than it is today. In-state
  commands are recognised at least as well as now. Out-of-state commands are still heard well
  enough to be refused *with a reason* (E13).
- **E17** — The pilot always knows who is flying. "I have controls" from Petrovich means he really
  is flying. In AI-overlay mode the handover is the park, with no words needed (E-P1, E-P2). While
  he flies, the pilot's take-back phrase is always in the expected set.
- **E18** — Ported flight commands keep their behaviour and readbacks as built in BL-16 P2 (E1),
  except where E13 says otherwise. Speed reads back as the wheel step ("two hundred", E-P3).
  Altitude names the reference actually achieved. "Level flight", "hold altitude" and "straight" /
  "level off" mean what they mean today.

### Open assumptions

- **Which state the hint follows.** Serves the why: the same state the dispatcher checks for
  "unable". In mode 2 that is `ParkedFlightState.parked_active`, which tracks arg 852, the park
  that *is* the handover. The player's seat comes from `apw_seat`, and later mode 1 adds its
  handover phase. Would not: the spoken phrase "you have controls", or any second copy of the
  state. *Belief or DCS truth:* these are crew facts. A real crewmate knows which seat he is in and
  whether his hands are on the controls, so reading them from cockpit args is not omniscience
  (lens: bounded knowledge, silent). What breaks E13 is a hint and a refusal that follow different
  states.
- **What fuzzy forgives.** Serves: the literal words of the pattern only, slot spans excluded, as
  D8 already says. Word-set slots, number words and HVRT bare words stay exact. Would not: running
  `_phrase_match_ratio` over the whole utterance, values included, or making the number-word table
  fuzzy. That breaks E12 (Finding 4).
- **Which number forms count.** Serves: the forms the pilot actually says, measured. Would not: a
  general English number parser that accepts forms nobody uses and so widens what can collide. For
  `heading`, "three fifteen" collapses to 315 but is not three digits spoken. Whether it counts is
  the user's call (Q10).
- **When the state is judged for "unable".** Serves: a command spoken just after the handover is
  not refused because body-layer had not caught up yet (Q12). Would not: today's per-dispatch
  check, which during takeover settle answers NOT_READY, because `held_heading` is `None` until the
  menu-open readback.
- **How the hint narrows.** Serves: a measured choice between removing words and putting the
  in-state words first (Finding 3). Would not: removing the out-of-state words and shipping
  unmeasured.
- **What "priority" changes.** Serves: what he does and says first while flying (Finding 5). Would
  not: a tie-break that turns an unclear transmission into a flight action, which contradicts E3.
- **Collision check scope (D9) once vocabularies are per state.** Serves: the check runs over
  *every* rule, because matching always covers every rule (user: *"keep matching every
  command"*). Would not: checking only within each state's set, which misses two commands from
  different states that both match one utterance. A looser fuzzy match makes such collisions more
  likely, as `BL-17.md` itself notes.
- **Scan commands while flying.** The user's text says *"eyes stay free for naked-eye scanning"*.
  The table under it lists only flight commands, queries and describe. Serves: whichever the user
  confirms (Q8). Would not: reading BL-B123's *"no optic at all"* as covering the naked eye. The
  code models the naked eye as `UNAIDED_OPTIC`, so a literal reading would blind him while he
  flies, against A5 / E-P11.

### Findings

1. **In AI-overlay mode, "you have controls" is not what starts Petrovich flying.** Lens: world
   truth / whose job. **Breaks E17.**
   - *Assumption:* the brief's "'you have controls' as the trigger for him to start flying" means
     the ported rule starts the takeover, and the "has controls" vocabulary is keyed to it.
   - *In the sim:* the only flying built today is mode 2. There the handover is the player's own
     "Request Aircraft Control" binding (arg 852). The 2026-11-16 flight found that out: Batch A
     was watching the wrong signal and never saw the handover. E-P1 says *"Parking is the
     handover … without the player saying anything."* No handover token exists in
     `audio-adapter/src` or `body-layer/src`. The spoken handover belongs to mode 1, which is
     unbuilt and next in BL-16. Flight-control D-e (what the spoken phrases mean while parked) is
     still open, and the plan check flagged it as conflicting with *"Handover is spoken only"*.
   - *The pilot would hear:* a rule built the obvious way either does nothing (the controls are
     already parked) or answers "I have controls" when he is not flying. If the hint is keyed to
     the phrase, it never switches to flight words in the key case, because the player parks and
     never says it.
   - *Grounded in:* `BL-16.md` (2026-11-16 flight, arg 852); `plans/flight-control/alignment.md`
     E-P1; `plans/flight-control/plan.md` D-e.
   - *Suggests:* in this stage the vocabulary follows the actual flying state. What "you have
     controls" and "I have controls" do in mode 2 is the user's call (Q7). Their full meaning
     arrives with mode 1.

2. **Porting faithfully would carry over a readback for a goal that is never flown.** Lens: crew
   sense. **Breaks E13.**
   - *Assumption:* D3 / E1, "a ported rule keeps its readback".
   - *In code now:* `_handle_turn_heading` and `_handle_set_speed` set the goal transition without
     checking whether he is flying, and read back "Heading three one five." and the speed.
     `_apply_ai_pilot_wheel_goal` then drops the goal without a word when not parked
     (`body.py:3288`). The relative commands check only `held_*`, the overlay readback, and
     BL-B117 says those overlay fields are not reset on export stop. So "heading 315" spoken while
     he is not flying sounds accepted and nothing happens. Where the code does refuse, it says
     "Unable, not ready", which does not tell the pilot the reason is that Petrovich does not have
     the controls.
   - *Grounded in:* the user's wrong-state decision (*"unable, <reason>"*), memory
     `project-say-again-vs-unable`, and the code above.
   - *Suggests:* each flight action checks the flying state itself and returns its reason, which
     the rule speaks. This is the deliberate exception to E1 and should be recorded as one. The
     reason's wording is Q9.

3. **A narrowed hint has never been measured, and every recognition threshold assumes the full
   one.** Lens: the envelope (recognition is the envelope here). **Breaks E13 / E16 if shipped
   unmeasured.**
   - *Measured:* `--prompt` took the user's corpus from 90.5% to 98.4%, and cut repaired matches
     from 85 to 19. `ACT_FLOOR = 0.60` is *"defensible on this row and no other"*, meaning
     prompted with the full vocabulary (`audio-adapter/research/2026-09-19-corpus-bench-results.md`).
     The model sweep counts **unsafe wrong commands** as the column that matters.
   - *The risk:* with out-of-state words taken out of the hint, an out-of-state command
     ("observ on" while flying) is more likely to come back as text that scores "say again", which
     loses the "unable, <reason>" the user chose. Worse, it may come back as a *different, in-state*
     command, which is the unsafe class. Meanwhile the in-state gain is unmeasured, and the
     shipped vocabulary is still inside the 224-token cap (a test enforces it), so the cap does
     not force narrowing yet.
   - *Suggests:* the user's direction stands. What should change is the order: measure each
     state's hint with `stt_bench.py` on the user's corpus, with flight phrases recorded through
     `record_corpus.py`, since the September corpus predates them (Q13). Count unsafe errors and
     out-of-state answers, not only accuracy. Also measure "in-state words first" as well as
     "out-of-state words removed".

4. **Fuzzy matching must leave values alone. D8 already says so, and the number-word parser must
   follow it.** Lens: unit of action (a value is what the aircraft acts on). Aligned; recorded so
   the plan inherits it.
   - `difflib` ratios: "right"/"sight" 0.8, a collision already measured and the reason HVRT bare
     words are matched exactly (`command_matcher.py:389`); "thirty"/"thirteen" ≈0.71 and
     "fifty"/"fifteen" ≈0.67, both above `_WORD_REPAIR_FLOOR` (0.5). A positional repair of a
     number word would turn 13° into 30°. The research note warns that repair *"can repair a wrong
     verb into a valid command"*.
   - So: fuzzy scoring covers the literal words with slot spans taken out (D8). Word-set slots,
     the number-word table and the bare words stay exact. A value heard wrong gets "say again"
     (E12).

5. **"Priority" should be something the pilot notices, never a tie-break.** Lens: crew sense.
   This is a recommendation; the user confirms (as `BL-17.md` already says).
   - A tie-break toward flight commands while flying turns a near-tie, which E3 says must be "say
     again", into an aircraft action. That is the worst place to guess.
   - What a pilot would notice and value while Petrovich flies: his flight readback is spoken
     before any queued contact callout (the `CalloutScheduler` busy model already decides what
     waits); flight words come first in the hint; and while flying, a flight command never waits
     behind a long description. When not flying, scanning and detection calls lead. Q11.

**Vignette, handover then an immediate command.** The player sits in the operator seat at 300 m
AGL. He presses Request Aircraft Control and keys the mic about a second later: "turn left thirty".
Arg 852 flips, Export's 5 Hz tick reports it, body-layer's poll sees `parked_active`, and the hint
is rebuilt. Whisper runs only after PTT release, two or three seconds after the press, so the
flight hint is most likely in place (E15 holds). The dispatch is the weak point. The takeover
sequence (0.5 s centre tap, menu open, altitude correction) leaves `held_heading` `None` until the
menu-open readback, so the ported rule answers "Unable, not ready." to a correct command at the
moment it is most natural to say it. Whether he should hold the command and fly it once ready is
Q12. Today's P2 behaves the same way, so this is not a regression, but it is where the "unable"
contract gets tested first.

**Not a concern:** making queries and describe exempt from narrowing (E14) follows the user's words
directly. The performance items (rule anchors cached per load, prompt built per change) have no
behavioural content beyond E15: the prompt must be rebuilt on a *state* change as well as on a rule
push.

### Questions for the user

- **Q7:** In AI-overlay mode the handover is your "Request Aircraft Control" press, and Petrovich
  takes over with no words needed. What should "you have controls" do there? Options: nothing yet
  (it belongs to mode 1, built later); an acknowledgement ("I have controls") only once he is
  really flying; or something else. And what about "I have controls" from you while parked?
- **Q8:** While he flies, should naked-eye scan commands ("scan two o'clock", "scan left") still
  be expected, since your text says his eyes stay free? Or only flight commands, queries and
  describe, as the table shows?
- **Q9:** What reason do you want to hear for a command in the wrong state? Suggested: "unable,
  not flying" for a flight command while he isn't flying; "unable, your sight" (or "pilot seat")
  for a 9K113 command when he's in the pilot seat; "unable, hands busy" for binoculars while he
  flies.
- **Q10:** Which number forms do you actually say for speed and altitude: "speed two hundred",
  "speed two twenty", or "two two zero"? "Altitude three hundred" or "three zero zero"? "Climb
  fifty"? And for a heading, would you ever say "heading three fifteen", or always "three one
  five"?
- **Q11:** By "priority while flying", do you mean his flight readbacks come before any queued
  callout and flight commands are recognised best? Recommended. Or something else? Recommend also:
  an unclear transmission is never resolved toward a flight command; it stays "say again".
- **Q12:** If you give a flight command right after the handover, before his takeover has settled,
  should he hold it and fly it once ready, or say "unable, not ready"?
- **Q13:** Will you record a short corpus of the flight commands (`record_corpus.py`) so the
  narrowed hint can be measured on your voice before it ships? The September corpus has none of
  them.

## Plan check — Revision 2, 2026-11-17

**Verdict:** CONCERNS. One expectation is contradicted by the plan's own text: E11's named example
("turn left thirty") is asserted fixed in two places (Stage 3a's test list, Stage 4's flight card)
by a mechanism that cannot reach it (Finding 1). Everything else — E12–E18, and all three of the
user's post-goal-check decisions (the second goal check's Q7–Q13 answers, category gates, rules
writing effectors) — traces cleanly to a named stage and decision letter.

Inputs: `plans/speech-rules/plan.md` Revision 2 (D13–D20, U19–U24, Stages 3a/3b/3d/3c/4), this
file's "Goal check — next stages" section (E11–E18), `body-layer/ROADMAP/BL-17.md` (every
2026-11-17 section, especially "Answers to the second goal check," "Category gates, before any
rule runs," "Rules can write effectors, from the start"), and the shipped
`audio-adapter/src/rule_patterns.py` (checked directly: `angle` calls only `_consume_digit_run`
today, confirming Finding 1 rather than assuming it).

| expectation / decision | stage | status |
|---|---|---|
| E11 | Stage 3a (D13), Stage 4 (D18) | **contradicted, partial** — "Turn left, 30." and "turn left three zero" are met via D13's literal fuzz and today's existing digit grammar. "Turn left thirty" (the user's own canonical number-word example) is not: see Finding 1 |
| E12 | Stage 3a (D13) | met — a `SlotElement`/`WordSetElement` never gets the fuzzy fallback; a value is heard exactly or the rule does not match |
| E13 | Stage 3b (D16), Stage 4 (D18) | met for `flight_control` (gate-first `UNABLE("NOT_FLYING")`, hold-and-retry on `settling`); the seat/hands-busy half (`"PILOT_SEAT"`, `"HANDS_BUSY"`) is deferred → Stage 5/6, named explicitly in D16/D18 as pending `[[BL-B123]]` |
| E14 | — | met, unaffected — no stage in this batch touches the legacy query/describe path; D16 states plainly "this mechanism governs rules only" |
| E15 | Stage 3b (D16's `CrewState`), Stage 3c (D17) | met — one `CrewState`, computed once per poll, feeds both the gate check and the `PUT /crew_state` push (Co-moving Fields table, revision 2) |
| E16 | Stage 3c (D17, U23) | met — reordering, never removal, is the default; the narrowed/removed variant ships only if the recorded-corpus measurement clears U23's safety bar (zero new unsafe errors, zero new lost "unable"s) |
| E17 | Stage 3b (D16), Stage 4 (D18) | met — `has_controls` reads `ParkedFlightState.parked_active` (arg 852), never the spoken phrase; "you/I have controls" is a silent no-op, category `"always"` (Q7) |
| E18 | Stage 4 (D18) | met — readback text pinned verbatim from BL-16 P2 by the differential tests; only the refusal path moves from a generic message to the gate's named reason |
| "Category gates, before any rule runs" (BL-17.md) | Stage 3b (D16) | met — matches the verbatim correction exactly: one gate per category, run before any matched rule in that category executes, "unable" before the handler ever runs; the coordinator's own worked example (copilot rule vs. pilot seat) is correctly deferred → Stage 5/6, named rather than stubbed |
| "Rules can write effectors, from the start" (BL-17.md) | Stage 3d (D20) | met — `_execute_switch_row` extracted and shared between the trigger-run and new ad-hoc-run passes inside `effector_engine.advance`, so this is the existing engine extended, not a second write path; no sequence file is migrated and no shipped rule calls it yet, exactly as scoped |
| "Answers to the second goal check" (Q7–Q13) | Stages 3a–4 (D13–D19) | met — each answer traces to a named decision: fuzzy forgives words only → D13; "Request Aircraft Control" as the real handover → D16's `CrewState.has_controls`; Q7 (no-op) → D18; Q8 (scan stays while flying) → D17's active-set note; Q9 (reasons) → D16/D18's reason catalogue; Q10 (number forms) → D14, checked against the Stage 3c corpus below; Q11 (priority, never a tie-break) → D17/D19; Q12 (hold and fly when ready) → D16's `HOLD`/`drain_pending_rule_dispatch`; Q13 (record a corpus) → Stage 3c item 3 |

### Findings

1. **"Turn left thirty" is asserted fixed twice, by a mechanism that cannot reach it.** Lens:
   grounded in the code / the non-obvious case. **Breaks E11.**
   - *Assumption:* Stage 3a's own test list ("turn left thirty"/"Turn left, 30."/"turn left three
     zero" all still resolve... "closing the Reviewer-flagged gap from Stage 1b/2") and Stage 4's
     flight card ("'turn left thirty' (number word)"; "the fuzzy near-miss cases from 3a ('turn
     left thirty' by the near-miss route...)") both treat "turn left thirty" as resolved by D13's
     literal-fuzz work.
   - *In the plan and the shipped code:* `turn_heading_relative`'s degree slot is `<degrees:angle>`
     — Stage 4 item 2 says this explicitly ("the existing `angle`/word-set types (relative turn,
     HVRT directions)" are unaffected by the number-word work). D14 says plainly: "`heading`,
     `angle`, `oclock` are **not** touched." D13's fuzzy fallback applies only to a
     `LiteralElement`; "a `SlotElement`/`WordSetElement` never gets this fallback" (D13's own
     text). Checked directly against the shipped code: `audio-adapter/src/rule_patterns.py:220`
     registers `"angle"` as `_consume_angle`, which calls only `_consume_digit_run` — no
     number-word branch exists or is added anywhere in Revision 2. Nothing in D13, D14 or Stage
     3a/4 teaches "thirty" to parse as 30 in this slot.
   - *The pilot would hear:* exactly the defect the Reviewer already flagged at Stage 1b/2 —
     "turn left thirty" still falls to "say again" — the first time he actually tries the phrase
     BL-17.md names as the reason number words were asked for at all, in flight, after the card
     told the tester it would work.
   - *Grounded in:* `BL-17.md`, "Number words count: 'turn left thirty'" — the user's own
     canonical example, answered "yes, I'd actually say that." E11 names it as one of three
     equivalent forms that must all turn 30° left.
   - *Suggests:* a one-line fix to D14, not a redesign — either give `angle` the same number-word
     branch `quantity` already has, bounded 1–359 so it cannot be confused with a three-digit
     `heading`/`bearing`, or redirect `turn_heading_relative`'s `degrees` slot to `quantity` with a
     range check in the action. This should be settled before Stage 3a is built, since Stage 3a's
     own test suite currently pins a result its own stated mechanism cannot produce.

### Questions for the user
None. Finding 1 needs an architect-side fix (one line in D14) before Stage 3a/4 are built, not a
user decision — the user already said yes to the phrase it breaks. U19–U24 stay open as recorded
in the plan; none of their recommendations conflict with anything the user has already decided
(U22's "build it" extends Q11's own "flight readbacks jump ahead of queued callouts" rather than
contradicting it, and U21's "latest wins" is the same precedent `AiPilotGoalRequest`/E-P4 already
set, applied one level up).
