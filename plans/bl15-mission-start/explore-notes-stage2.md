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

## Still open (follow-up questions put to the user)

- What "cold start" means to detect, and when it is judged.
- Shape of the walk-through: who drives it, how long, when.
- Which console the questions appear on.
