# Explore notes: behaviour trees for Petrovich's drill

2026-10-23, main loop with the user (`/explore`). Not yet planned. This file captures the
conversation as it happens.

## The user's opening

> *"behaviour trees are a well known concept in game AI design. Effector sequence files are a small
> step in that direction. What would it take to use behaviour trees? Expose a certain set of
> commands and arguments and a file defines what happens. That way functionality would remain in
> code, but the what happens when would come from a behaviour trees file. That'd make expanding
> behaviour a lot easier, once we get a large enough set of functionality."*

## What was already on record

- No prior discussion of behaviour trees anywhere in the repo, graph or agent memory.
- `docs/concept/state-transitions.jpg` (the user's own diagram, transcribed in
  `STATE_TRANSITIONS.md`) is already tree-shaped. It has a default scan loop, priority
  interruptions (a missile aimed at ownship, a new detection, watched-unit changes) and player
  commands that redirect it.
- BL-B90 explore decision 3 (2026-10-21): gating stays in code. *"I may put some logic into those
  files, but most such things are dependent on aircraft state at level we better keep in code.
  Subject to change, but that's a much larger scope for later if ever."* This conversation is that
  "later".
- `docs/concept/long-term-high-level-plans.md`, Wingbrain: *"should do as much as possible with
  deterministic AI logic, as little as possible with LLM"*. The same direction, stated earlier for a
  different role.
- Memory `project_brain_layer_is_the_bottleneck`: defer judgement features to the brain layer. That
  needs reconciling with this: which part is drill, which is judgement?

## Answers

1. **Tree = drill, brain = judgement.** The main loop offered the analogy (tree is the crew's
   trained procedure, the brain is judgement and words). The user: *"Tree would be the drill, yes.
   Especially ones we get into Petrovich as pilot."*
2. **Most-edited behaviour is "what happens when I command something".** *"Eg scan ahead sector
   change that we made in code earlier would have instead been config file change that I could've
   made. These would be especially useful if/when Petrovich as pilot will fly the aircraft."* So
   the first value is the command-response layer, and the payoff grows with the pilot role
   (`long-term-high-level-plans.md`, "Petrovich as pilot").
3. **Interruption depends on context.** *"kinda depends. How far is it, where are we, doing
   what"*. Distance to the threat, where we are, and the current activity all decide whether and
   how he interrupts. That calls for context conditions, not one fixed priority order.
4. **Who edits, and which tree.** *"I would edit, or maybe you. Different trees likely based on role
   and mission type."* So: one tree per (role, mission type), edited by the user or by Claude.

## Round 2 (after a mock "scan ahead" tree and a context-dependent missile interrupt)

5. **Editable level: parameters of the drill, not the perception.** *"I would not want to edit
   detection logic, but possibly which sector, when and how long, scan Distance, Optic used. When
   flight control gets implemented, flight patterns."* So the file holds sector, timing/dwell, scan
   distance, optic choice (and later flight patterns). Detection, classification and LOS stay code.
6. **Interrupts come in two kinds.** The user's cases:
   - *"missile launch: observe if it aims at us. If it does, abort everything else and alert, deploy
     counter measures. If not, resume current activity."*
   - *"AAA fire: urgent report. But continue attack run unless pilot aborts, continue ATGM guidance
     unless pilot aborts."*

   Reading (main loop, to confirm): a **pre-empting** interrupt (missile aimed at us) aborts the
   current activity; a **concurrent** one (AAA, a missile not aimed at us) adds an urgent report
   while the current activity carries on. "Resume current activity" means activities must be
   resumable, not restarted. Only the pilot aborts an attack run or ATGM guidance.
7. **Tree structure: a common tree with mission branches, separate trees per role.** *"probably
   more like own branches of a common tree. Escort certainly would be its own since it's different
   from pure attack. Petrovich roles would mean different trees: copilot, pilot, wingman."*

## Round 3

8. **The operator seat can release countermeasures.** Asked whether "deploy countermeasures" was
   his own action or a call to the pilot: *"yes"*. So it is an effector action he takes himself.
9. **Resume if possible, else start new.** *"continue what was interrupted if possible. Missile
   evasion might make that impossible (no LOS) in which case start new."* An interrupted activity
   resumes where it was when its precondition (e.g. LOS) still holds, and restarts otherwise.
10. **The pilot's abort is spoken or inferred.** On whether "unless pilot aborts" was a command or
    inferred from manoeuvre: *"both"*.

## Round 4 (after a mock ATGM attack-run tree and a table of candidate uses)

11. **Missile at us during ATGM guidance: needs rules.** *"not so black and white, it'd need
    rules"*. "Abort everything" is not absolute; the tree has to weigh it.
12. **BL-B89's scan procedure is a good tree candidate.** *"yes, that would make it easy to modify,
    test and iterate to get correct without needing code changes"*.
13. **Context changes the drill.** *"it would, based on friendly/enemy territory, waypoint, phase of
    mission, target area, time of day, … Like player set a mark at village then could command scan
    south of village. The tree could specify how the scan would behave."*
14. **The user's own example, first imagined for effector sequences:**
    - *"at start, if twilight or night, set dome light to white"*
    - *"takeoff, if twilight or night, set dome light to red"*
    - *"guidance unit ready, set dome light off."*

    (Operator dome light = `LTG-COCKPIT-OP-PTR`, arg 682, WHITE/OFF/RED, `-1/0/1` in
    `switch-reference.md`. Which value is which colour is unverified.) Today's sequence-file
    condition grammar is only `<effector> = <value>`, so it cannot say "if night".
15. **The vocabulary is the real cost, and the real value.** *"Tree would certainly need to use
    params or variables that the engine would check for the rules. Possibly quite many. This would
    be a very powerful way to build Petrobrain behaviour. But it would need a comprehensive set of
    state params and actions, otherwise it's very limited."*

## Round 5

16. **The missile-during-guidance rule is a time race.** *"time to ATGM impact vs time to SAM/AAM
    impact."*
17. **Light level: approximate from sun position.** *"light level outside, but we probably cannot
    get that from DCS, but we might get sun position that would allow us to approximate light
    level"*. Whether DCS exposes sun position (or mission date/time to compute it) is unverified.
18. **Scan-area geometry is a tree decision.** Asked how far and how wide "south of the village" is:
    *"exactly the questions that a tree could decide"*.
19. **The big payoff is aircraft control.** *"The more useful behaviour trees would come with
    aircraft control."* The user's examples:
    - *"fly heading, alt, speed,…"*
    - *"move x km to left"*
    - *"hide behind ridge"*
    - *"attack run from southeast, pop up 3 km from target."*
    - *"evasive action behaviour automatically"*
    - *"lots of "sane" wingman behaviour to replace the "idiotic" wingman behaviour of standard DCS
      wingmen"*

## Status: concept only, not a plan

*"Do not architect anything yet. The whole behaviour tree thing is a concept that I want to explore,
it may also not be worth it. One option would be to build future behaviour with it and leave what we
have as is for now."*

## Decision, 2026-10-23: keep the direction, build the vocabulary first

*"Keep this idea, we'll move in this direction, but need the commands first. Future code should be
structured so that refactoring to decision trees can be easy.*

*We'll stick with effector sequences for now and add parameter comparisons there, see the light
level example. That is a good POC for the decision trees as well.*

*Add backlog item, reference notes, merge to main. No implementation now. But let's build the
commands, actions, params that these trees will need and create code so that it supports the tree
usage ones we get there."*

So:

- **Direction kept, no tree engine yet.** Filed as `[[BL-B95]]`, deferred until the vocabulary
  of commands, actions and params is large enough.
- **Next concrete step: parameter comparisons in sequence-file conditions**, with the dome-light rules
  as the proof of concept. Filed as `[[BL-B94]]`.
- **Standing direction for new code:** structure it as named actions plus named state params, with
  "when" decisions kept out of the action code, so a later move to trees is a refactor and not a
  rewrite. Recorded in root `CLAUDE.md`, "Behaviour as actions and params".
- Existing hard-coded behaviour stays as it is.

## 2026-10-24: the user's alternative, an event-driven system (evaluation asked, not designed)

> *"Further thoughts on the behaviour trees. I think we're better off expanding the effector table
> solution. That's already like a branch of a tree.*
>
> *Petrobrain would do better with an event driven system. Expand effector tables to define
> Petrovitch actions, not only cockpit effector. Add custom triggers that files can register and
> fire. Others can use them as triggers. That'd give us an event driven system.
> If's and while loops.*
>
> *That'd get us far.
> That's also much more like real scripting than just tables. Maybe use .lua then?*
>
> *Do not design anything yet, but evaluate my idea."*

Main loop's evaluation, in short: a good direction, closer to the existing code than trees. The one
thing it does not give for free is arbitration (several handlers wanting one sight, one voice), so
priority, resource claims, pre-emption and resume belong in the engine. Lua for logic, because
coroutines make "do, wait, do" plain code. Cost: the `lupa` dependency, weaker load-time checking,
and a need for offline replay testing.

### The user's answer and API sketch, 2026-10-24 (verbatim)

> *"Tables are good for cockpit switches, they are like checklists. For behaviour, I'd want
> scripting language like lua."*

> *I vision somehting like:*
>
> *- fixed set of functions to call*
> *- set of effector names (exists) action names (does not exist) and both fixed triggers from code
>   (partially exists) and custom triggers from script.*

```
setup()
    .aircraft(<mi-24p>)
    .role(<copilot>)   ; copilot, pilot, crew, wignman, any   (crew = pilot or copilot)
    .trigger(<trigger-name>)

effector(<effector-name>)
    .get()
    .set(<value>)
    .increment(<value>)  ; degative value decrements

param(<param-name>)
    .get()
    .set()  ; some params would be read-only

action(<action-name>)
    .arg(<arg-name>)
        .get()
        .set(<value>)
    .start()
    .stop()
    .pause()
    .continue()

trigger(<trigger-name>)
    .register()
    .fire()
    .listen()
        .then(<function to execute>)
; some mechanism for trigger().playerCommand("scan *").listen().then(scanFunction) <- would need the full text as param to scanFunction

speak()
    .ics("<text to speak>")
    .radio("<text to speak>")

interrupt(<interrupt-name>)  ; interrupts are triggers, same things apply except interrupt gets priority
```

> *That'd allow*

```
setup().aircraft(mi-24p).role(copilot)

trigger(start-navigation).register() ; this script may fire this trigger
trigger(take-off).listen().then(takeOffActions)
trigger(take-off-clearance).listen().then(takeOffClearanceActions)

function takeOffActions() {
  effector(missilePower).set(on)   ; or maybe effector.executeSequence(sequence-name)
  effector(guidanceUnit).set(on)
  if (timeOfDay != day) {
    effector(domeLight).set(red)
  }

  trigger(start-navigation).fire()
}

function takeOffClearanceActions() {
  speak("Commander, we are cleared for take-off")
}
```

> *"Something along those lines. Not exact, just ideas and pseudocode."*

Main loop's response (a Lua rendering with a scan handler and an interrupt): the sketch's boundary
is right; `register()` enables load-time checking; `pause()`/`continue()` match round 3's resume.
Gaps raised:

1. scripts must read Petrovich's belief only, never DCS truth (the `Percept` boundary);
2. waiting and completion (coroutines, `done()`, succeeded/failed);
3. interrupts need a priority and the resources they claim (sight, voice, hands, later controls),
   which gives both pre-empt and concurrent kinds;
4. several scripts on one trigger;
5. player commands as parsed slots plus raw text, not a glob;
6. `speak():radio` needs SRS; writable params are shared script state, kept apart from belief
   params.

### Answers, 2026-10-24

- **Mission scripts add to the common one, never replace it.** *"add to common"*.
- **Audience: the user now, any user later.** *"for now, only me. Eventually, any user who wishes to
  use it could write their own."* So the sandbox and the load-time checks must eventually hold for
  strangers' scripts (fits the public open-source intent), but they need not be hardened for that yet.

### Outcome, 2026-10-24

The user approved re-scoping the backlog (*"yes, that's good"*) and added: *"the dome light is
simply an example (though a nice touch), no need to actually build the light level things yet.
There are more important things first."* So:

- `[[BL-B95]]` was re-scoped from behaviour trees to event-driven Lua scripting. Deferred.
- `[[BL-B94]]` was narrowed to the param catalogue. The table condition syntax was dropped and the
  light level stays an example only. Deferred.
- The root `CLAUDE.md` actions-and-params rule stands, re-aimed at scripting.

## 2026-11-17: speech commands as Lua rules (`/explore`, reopened by the user)

The user reopened `[[BL-B95]]` with a narrower, concrete entry point: **player speech commands
defined in Lua**, pattern + slot checks + handler. Verbatim:

> *"I have this idea that I'd like to be able to do, in pseudocode
> (note: I'm using brackets '[' to denote optional values.)"*

Example 1:

```
when.speech("turn left <value>")
    .where($value).isNumber()
    .do(
        incrementHeading(-1 * $value)
        .then().say("left $value")
        )
```

> *"Speech meaning player command STT string. Numeric values "315" and "3 1 5" and "three one five"
> must all collapse to 315 before this code runs."*

Example 2:

```
when.speech("[set] mark [heading] <direction> [o'clock] <distance> <distance_unit>")
    .where($direction).isNumber()
    .where($distance).isNumber()
    .where($distance_unit).isOneOf("meters", "kilometers")
    .do(
        if present("heading") then
            heading = $direction
        else if present("o'clock") then
            heading = oclockToHeading($direction)
        else
            say("say again")
            error("direction unit not recognized")
        fi

        distance = $distance
        if $distance_unit == "meters" then
            distance = distance / 1000
        fi
        mark = setMark(currentPosition().translate().heading(heading).distance(distance))
        say("mark $1", mark.number())
```

Example 3:

```
when.speech("engage/'attack run' <unit> <direction> [o'clock] [<distance> kilometers] [<weapon>]")
    .where($unit).isText()
    .where($direction).map("ahead", 12).isNumber()    # map -> if "ahead" change to 12 else pass through
    .where($distance).isNumber()
    .where($weapon).isOneOf("missiles","rockets","guns","bombs")   # note, since weapon is optional value, brackets, it can be empty
    .do(
        unit = getUnit($direction, $distance, $unit)
        setTarget(unit)
        attackRun()
        say("attack run $unit")
        trigger('attack_run')
        )
```

> *"This would move lot's of hardcoded actions to config lua. We'd need exposed tool set to call.
> But then creating and modifying actions (and user speech commands) would become easy."*

### What is already on record (checked before the first question)

- Today a command is a token in `audio-adapter/src/vocabulary.py` (84 tokens, 148 bias phrasings),
  a hand-written `parse_*` slot function there, matching in `command_matcher.py`, and a handler in
  body-layer (`crew_console.py`, plus e.g. `ai_pilot_wheel.py`). Example 1 already exists as
  `turn_heading_relative`; Example 3's shape exists as `engage [<what> <where>] [weapon]`; marks
  exist as `mark_here` / `mark_target`.
- Number collapse already exists for the digit-by-digit form (`_read_digits_after`); whole-number
  words ("three hundred fifteen") are unbenched.
- `vocabulary.py:645` records why **"attack" was refused as an `engage` synonym**: the fuzzy verb
  anchor scores "tanks" vs "attack" at 0.545, over the 0.5 floor, so "the tanks are on the ridge"
  would stop falling through as free speech and become "say again". A pattern written in a script
  meets the same recogniser and matcher, so adding a phrase can change how another one matches.
- BR-2 (`plans/brain-tool-calls/plan.md`): the brain fills the same slots and calls the same handler
  as a matched command; BL-B95's own gap 4 says parsing stays in code.

### Round 1, 2026-11-17

Main loop raised two findings (the "attack"/"tanks" matcher collision above, and adjacent numbers
running together once optional words are dropped: "mark two three kilometers") and asked four
questions. Answers, verbatim:

1. **Phrasing.** *"to get the deterministic (=fast) path, I use fixed wording"*. Fixed wording is the
   fast path; loose speech is not what the patterns are for.
2. **Engage a unit Petrovich has not seen.** *"report no contact"*.
3. **What a mark is.** *"point to come back to, to use as reference for scanning or flight
   waypoint."* (Correction, from the goal check: marks are already numbered per mission —
   `MissionMemoryStore` overwrites the caller's `index=0` from `_next_mark_index` — and "mark here"
   already reads back "mark N set". What is new is a command that *uses* the number.)
4. **Readbacks.** *"each rule writes it's own"*.

**Numbers: the direction's type is always spoken, and the type fixes the digit count.** Verbatim:

> *"heading/bearing <value>" - value is \d\d\d - always three digits*
> *"<value> o'clock" - value is \d\d? - 1 and 12 ok*
> *numeric direction value must specify what type it is "heading", "o'clock", "bearing"*
>
> *From this*
> *"mark heading 3 1 5 2 kilometers" -> mark heading 315, 2 km*
> *"mark heading 0 1 5 2 kilometers" -> mark heading 015, 2 km*
> *"mark 1 o'clock 3 kilometers" -> do action would handle oclockToHeading()*

So the ambiguity is resolved by spoken phraseology, not by the grammar guessing: heading and
bearing take exactly three digits, o'clock takes one or two (1–12) and comes before its type word.

### Round 2, 2026-11-17

Main loop proposed **typed slots defined in code** (`heading`, `bearing`, `oclock`, `distance`),
each owning its spoken shape and normalisation, so a rule receives a parsed value and a slot that
fails to parse means the rule did not match (one standard "say again"). Example 2 reduces to:

```lua
when.speech("[set] mark <dir:heading|oclock> <dist:distance>", function(s)
  local hdg = s.dir.kind == "oclock" and oclock_to_heading(s.dir.hour) or s.dir.deg
  local m = set_mark(position():offset(hdg, s.dist.km))
  say("mark " .. m.number)
end)
```

Answers, verbatim:

1. **Port existing commands or only new ones?** *"all of them. Group by what they do, split to files
   as needed."* All 84 tokens move to Lua rule files, grouped by function. This overrides the
   root `CLAUDE.md` default ("existing hard-coded behaviour stays unless a change touches it") for
   speech commands.
2. **Target choice within a group.** *"as recommended"*: code picks the unit and returns one unit
   or `nil`; the rule says "no contact" on `nil`. Target choice is perception/judgement and stays
   out of scripts.
3. **Heading vs bearing.** *"bearing is ownship relative so that 0 is boresight. Rarely used, but
   let's support it."*
4. **Mark numbers.** *"yes, reference by number. Only ever add marks, edit and delete are not
   supported."* Marks are numbered, referenced later by number, append-only.

### Round 3, 2026-11-17: bearing vs heading, dependency, sequencing

Main loop pointed out that existing code already uses "bearing" for a **compass** direction
("scan bearing three two zero" → compass-absolute sector, `crew_console.py:374`, with a ×5
checksum in `vocabulary.parse_bearing`), which contradicts answer 3. Verbatim:

> *"Standard usage of bearing is ownship relative degrees. Standard usage of heading is compass
> degrees, either magnetic or true depending on application.*
> *Change the naming in existing code to reflect this."*

> *"ok for lupa dependency"*

> *"build the scructure first, then take one or two rules and port them. Then test flight is in
> order. Then we can schedule porting the rest in stages."*

So:

- **Bearing = ownship-relative degrees (0 = boresight). Heading = compass degrees**, magnetic or
  true by application. Existing code that says "bearing" for a compass direction is renamed to
  "heading", spoken vocabulary included ("scan bearing 320" → "scan heading 320").
- **`lupa` (MIT) approved** as a new dependency.
- **Sequencing:** the rule engine structure first, then port one or two existing commands, then a
  test flight, then the remaining commands in scheduled stages.
- Left open, then settled the same day: *"magneric vs true -> use existing convention in code"*;
  *"multiple of 5 -> no, allow any three digit value"*. So the existing magnetic/true usage stays,
  and no direction slot carries the ×5 checksum (today's "scan bearing" checksum is dropped).
