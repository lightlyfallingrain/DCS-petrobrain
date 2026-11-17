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
