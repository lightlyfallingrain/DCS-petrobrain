# BL-B95 — Event-driven behaviour scripting in Lua

- [>] **BL-B95 — Drive Petrovich's behaviour ("what happens when") from Lua scripts over a fixed API
  of effectors, actions, params, triggers and speech. Functionality stays in code.**
  #status/deferred Filed 2026-10-23 as "behaviour trees". **Re-scoped 2026-10-24** to the user's
  event-driven alternative. The full conversation, the user's API sketch and every answer, verbatim,
  are in `plans/behaviour-trees/explore-notes.md`. Concept only, nothing designed.

  > *"I think we're better off expanding the effector table solution. That's already like a branch
  > of a tree. Petrobrain would do better with an event driven system. Expand effector tables to
  > define Petrovitch actions, not only cockpit effector. Add custom triggers that files can register
  > and fire."*

  > *"Tables are good for cockpit switches, they are like checklists. For behaviour, I'd want
  > scripting language like lua."*

  **Deferred until** enough actions, params and commands exist for scripts to be worth more than
  sequence files. In the user's words: *"we'll move in this direction, but need the commands
  first"*. The tree-era warning still applies: *"it would need a comprehensive set of state params
  and actions, otherwise it's very limited."* Meanwhile new code follows root `CLAUDE.md`, "Behaviour
  as actions and params", and the param catalogue is `[[BL-B94]]`.

  ## The concept, as the user sketched it

  A fixed set of functions over named things. Effector names already exist; action names do not yet.
  Triggers come from code (partly exist) and from scripts (custom):

  - `setup():aircraft():role()`, where the role is `copilot` | `pilot` | `crew` | `wingman` | `any`
    (crew = pilot or copilot);
  - `effector(name)`: `get` / `set` / `increment`. Switch checklists stay as BL-B90 tables, which a
    script can run;
  - `param(name)`: `get`, and `set` where writable;
  - `action(name)`: `arg`, `start` / `stop` / `pause` / `continue`;
  - `trigger(name)`: `register` / `fire` / `listen(fn)`;
  - `speak():ics()` / `:radio()`;
  - `interrupt(name)`: a trigger with priority.

  ## Settled in the explore

  - **Mission scripts add to the common one, never replace it.** Both handlers run, common first.
  - **Audience:** *"for now, only me. Eventually, any user who wishes to use it could write their
    own."* The sandbox and load-time checks must eventually hold for strangers' scripts.
  - **Interrupt kinds.**
    - Pre-empt: a missile aimed at us aborts the activity, alerts and releases flares. The operator
      seat can release them.
    - Concurrent: AAA gets an urgent report while the attack run or ATGM guidance carries on, unless
      the pilot aborts, by command or by manoeuvre.
    - During guidance a missile at us is a rule, not absolute: ATGM time to impact against the
      SAM/AAM's.
  - **Resume:** an interrupted activity resumes if its preconditions still hold (e.g. LOS), and
    otherwise starts fresh.
  - **Editable by script:** sector, timing, dwell, scan distance, optic, later flight patterns.
    **Not editable by script:** detection, classification, LOS.
  - **Context the scripts will want:** territory, waypoint, mission phase, target area, time of day,
    player marks. Several of these need the Mission Interpreter. Terrain ("behind ridge") comes from
    the world model.

  ## Gaps raised in evaluation, to resolve at design time

  1. **No omniscience.** Scripts read Petrovich's belief only, never DCS truth.
  2. **Waiting and completion.** Lua coroutines, `done()`, and succeeded/failed results.
  3. **Arbitration in the engine.** Each activity has a priority and the resources it claims:
     sight, voice, hands, later the controls. The engine pre-empts and resumes. Scripts never
     hand-roll this.
  4. **Player commands** arrive as parsed slots plus the raw text, not as a glob. Parsing stays in
     code.
  5. `speak():radio` needs SRS. Writable params are shared script state, kept apart from belief
     params.
  6. **Cost:** a new dependency (`lupa`, MIT; needs the user's approval), weaker load-time checking
     than tables unless every name goes through `register()`, and offline replay testing for
     scripts.

  **Candidate first script:** `[[BL-B89]]`'s scan procedure, which the user wants to *"modify, test
  and iterate to get correct without needing code changes"*. **Biggest payoff:** aircraft control,
  i.e. Petrovich as pilot and the wingman: *"fly heading, alt, speed", "move x km to left", "hide
  behind ridge", "attack run from southeast, pop up 3 km from target", "evasive action behaviour
  automatically"*, and *"sane"* wingman behaviour.
