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

## Status: concept only, not a plan

*"Do not architect anything yet. The whole behaviour tree thing is a concept that I want to explore,
it may also not be worth it. One option would be to build future behaviour with it and leave what we
have as is for now."*

No Architect pass. Whether behaviour trees are worth it at all is still open. The user's candidate
route, if they are: new behaviour is built on trees, and existing hard-coded behaviour stays as it is.
