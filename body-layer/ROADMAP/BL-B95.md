# BL-B95 — Behaviour trees: the drill from a file, once the vocabulary exists

- [>] **BL-B95 — Drive Petrovich's drill (what happens when) from behaviour-tree files, with the
  actions and state params staying in code.** #status/deferred Filed 2026-10-23 at user direction,
  closing the explore in `plans/behaviour-trees/explore-notes.md`, which has every answer verbatim.

  > *"Keep this idea, we'll move in this direction, but need the commands first. Future code should
  > be structured so that refactoring to decision trees can be easy."*

  **Deferred until** the vocabulary of commands, actions and state params is large enough for a tree
  to be worth more than a sequence file: *"it would need a comprehensive set of state params and
  actions, otherwise it's very limited."* Meanwhile the vocabulary grows through `[[BL-B94]]`
  (param comparisons in sequence files), and new code follows root `CLAUDE.md`, "Behaviour as
  actions and params".

  **What the explore settled** (details and quotes in the notes):

  - Tree = drill, brain = judgement. The brain turns speech into a choice of tree plus parameters;
    the tree runs the drill; code flies, looks and switches.
  - Editable: which sector, when, how long, scan distance, optic, and later flight patterns. Not
    editable: detection, classification, LOS.
  - Two kinds of interrupt: **pre-empt** (missile aimed at us aborts the activity, alert,
    countermeasures, which the operator seat can release) and **concurrent** (AAA: urgent report,
    attack run and ATGM guidance carry on unless the pilot aborts, by command or by manoeuvre).
    During guidance it is a rule, not absolute: ATGM time to impact against the SAM/AAM's.
  - An interrupted activity resumes where it was if its preconditions still hold (e.g. LOS),
    otherwise it starts fresh.
  - One tree per role (copilot, pilot, wingman); mission types as branches of a common tree
    (escort clearly its own). Context selects the drill: territory, waypoint, mission phase,
    target area, time of day, player marks.
  - Existing hard-coded behaviour stays as it is.

  **Candidate first trial:** `[[BL-B89]]`'s scan procedure. It is new, it is pure drill, and the user
  wants to iterate on it without code changes (*"yes, that would make it easy to modify, test and
  iterate"*). **Biggest payoff:** aircraft control. In the user's words: *"fly heading, alt, speed",
  "move x km to left", "hide behind ridge", "attack run from southeast, pop up 3 km from target",
  "evasive action behaviour automatically"*, and *"sane"* wingman behaviour to replace DCS's own.

  **Known gaps in the vocabulary** that are not body-layer's to fill alone: territory, mission phase,
  target area and marks need mission understanding (Mission Interpreter). Terrain conditions
  ("behind ridge") come from the world model.
