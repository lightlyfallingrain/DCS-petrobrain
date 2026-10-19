# BL-15 Stage 2 — explore notes (briefing at mission start)

`/explore` conversation with the user, 2026-10-19. The user's answers are the specification; quoted
verbatim where the wording carries the reasoning.

## Known before the conversation

- Mission Interpreter wall-clock, measured 2026-09-24 (`docs/acceptance/2026-09-24-mission-interpreter-sortie.md`):
  1:12 with `qwen3:14b` resident, 3:19 cold, 2:28 warm-ish.
- MI-5 asks the player questions partway through, on stdin (`player_intent.main`), today at a Mac
  terminal.
- Nothing in flight reads mission phase (`[[BL-W19]]`, deferred to the brain).

## Decisions

1. **Cold start only.** *"usually cold. This is the case for MI. If not cold start, skip MI phase."*
   A hot or airborne start gets Stage 1's reset and theatre, and no briefing.
2. **"Briefing ready" leads to a walk-through.** *"Go through it to verify both crew knows the
   mission."* The point is shared knowledge between the two crew members, not Petrovich silently
   holding the interpretation.
3. **MI's questions go to the pilot — phased.**
   - Now: *"Petrovich says aloud "mission questions, commander", then player goes to console to look
     at them and type in answers."*
   - **Deferred:** *"use speech (TTS and STT) to answer them."*
4. **Cache invalidation by timestamp.** *"I typically don't. I edit test mission, usually I don't
   create my own missions. For simplicity, if mission file timestamp is newer than cached MI file
   timestamp, regenerate."* Not a content hash — the user chose the simple rule knowingly.

## Second round (2026-10-19)

Shown a mock walk-through (task → route → threats → "Questions?") before answering.

5. **The walk-through stops after every sentence.** *"In cockpit, I'd want a stop after each sentence
   so that I can correct information id needed."*
   - Pilot: *"copy"* → *"good as it is, next line"*.
   - Pilot: *"<quesions, correction>"* → *"process, modify, read modified line"*.
6. **Content and order.** *"order: task, route, threats, allied flights, weapons, fuel, questions"*.
   New over the mock:
   - *"weapon loadout is needed: types and quantity"*
   - *"fuel on board and approximate operating time"*
   - *"allied flight related to our task"*
7. **Pilot chooses when.** *"my choice of timing, "Petrovich, briefing" / "ready for briefing" /
   "do briefing""*. "Briefing ready" is a notice, not the start of the briefing.
8. **Cold start = engines off on the ground** (at mission start).
9. **Questions console: wherever MI runs.** *"wherever the MI is running is fine for now. The console
   solution is meant to be temporary."*

## Third round (2026-10-19)

10. **Briefing ships in two steps — approved.** First step: fixed responses ("copy" and a few
    others). Second step: free-text corrections, which need the brain (free speech → modify the
    interpretation). User: *"Briefig in two steps approved."*
11. **Corrections cannot be specified ahead of a real scenario.** *"I can't really tell without
    exploring a real scenario. It will have to be iterated. Most likely position changes or where
    enemy is expected to be."* So: design the correction path to be iterated on from flight
    feedback, not to a fixed grammar.
12. **Loadout and fuel: read from the aircraft**, not from the mission file — the pilot may rearm
    or refuel on the ramp before the briefing.
13. **Allied units: the ones related to our task, not a roll-call.** *"At least those from mission
    file briefing section. But more usefull than "two ka-50's in the air" would be friendfly flight
    (or ground units) that are related to own target/mission. Units that I need to escort or that
    are ecorting me. SEAD flights that clear a path for us. Ground units moving to attack targets
    and I'm expected to CAS. Known enemy moving in and friendlies defending and my task is to help
    defence. Such things."*

    Constraint this puts on the Mission Interpreter: deciding which friendly units *relate to our
    task* is interpretation (the model's job), but the candidates must still pass MI's
    author-only-knowledge filter — a friendly group the crew could not know about (hidden, late
    activation, scripted) must not be briefed, however relevant.

## Status

**Stage 2 deferred as a whole, explore finished** — user, 2026-10-19: *"Defer MI stage of mission
startup actions as a whole for now, but let's finish the explore."* These notes are the
specification to plan from when it is picked up.
