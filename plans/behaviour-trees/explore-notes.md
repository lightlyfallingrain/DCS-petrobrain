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
