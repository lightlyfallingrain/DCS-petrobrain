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
